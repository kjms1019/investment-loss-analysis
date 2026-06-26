"""진입오류/손절실패 분류기 — 공유 코어.

이 모듈은 단계 스크립트(step1~3b)가 함께 쓰는 빌딩블록을 모은다:
  - 결과신호(라벨용)  : loss_early_ratio, trough_time_frac, post_breach_run
  - 진입맥락 피처(분류기용) : rsi/range_position/momentum/vol/volume ...
  - 샘플러            : 실 min1에서 손실거래 추출 (신호만 / 피처+신호)
  - 군집 라벨러        : 다중신호 GMM(K=2) → entry_error / stop_loss_failure
  - 설계 합성 생성기    : 정답 구조를 주입한 검증셋

설계 원칙(대화 합의):
  · 라벨 = 결과(사후) 신호로 생성  /  피처 = 진입시점 맥락 → 둘을 분리해 순환 방지
  · 임계값은 손으로 안 박고 군집이 경계 결정 (단일 고정컷 0.7은 step1에서 기각됨)
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

# ── 경로 / 상수 ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
MIN1_DIR = ROOT / "analysis" / "data" / "min1"
OUT_DIR = ROOT / "analysis" / "data" / "_label_validation"   # gitignored

PRE = 130           # 진입 전 참조 분(bars)
EARLY_FRAC = 0.2    # '보유 초반' 구간 비율
BREACH_THR = 0.03   # 손절선 근사 (-3%)

# 분류기 입력 피처 (진입시점 맥락 — look-ahead 금지)
FEATURES = [
    "rsi_14",
    "range_position_20", "range_position_60",
    "ret_5m", "ret_20m", "ret_60m", "ret_120m",
    "accel",
    "entry_vs_high20", "entry_vs_high60",
    "entry_vs_ma20", "ma_20_slope",
    "vol_20", "vol_60",
    "volume_ratio_20",
]
# 라벨 정의축 (결과신호 — 피처로 재사용 금지)
LABEL_SIGNALS = ["loss_early_ratio", "trough_time_frac"]
_RATIO_LIKE = {"loss_early_ratio", "post_breach_run"}   # 군집 전 로그/윈저 대상

# 사후 경로피처 (라벨축 아님 — 분석단 분류기 전용. 진입피처에 더해 '전체경로' 구성)
POST_ENTRY_FEATURES = ["post_breach_run", "mae_ratio", "breach_time_frac"]

# 분석단 분류기 = 전체경로 피처 (진입맥락 + 사후경로, 라벨축 제외). 예측기는 FEATURES(진입)만.
CLASSIFIER_FEATURES = FEATURES + POST_ENTRY_FEATURES


# ── 결과신호 (라벨용) ─────────────────────────────────────────────────────
def _rsi(close, period=14):
    if len(close) < period + 1:
        return np.nan
    d = np.diff(close)
    ag = np.clip(d, 0, None)[-period:].mean()
    al = (-np.clip(d, None, 0))[-period:].mean()
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def outcome_signals(low, close, e, hold):
    """손실거래의 사후 결과신호. 손실 아니면 None."""
    entry = close[e]
    if entry <= 0:
        return None
    ret = (close[e + hold] - entry) / entry
    total_loss = -ret
    if total_loss <= 0:
        return None
    early_end = e + max(1, int(math.ceil(EARLY_FRAC * hold)))
    early_low = low[e:early_end + 1].min()
    ler = max(0.0, (entry - early_low) / entry) / total_loss

    path_low = low[e:e + hold + 1]
    ttf = int(np.argmin(path_low)) / hold

    breach_level = entry * (1 - BREACH_THR)
    below = np.where(path_low <= breach_level)[0]
    if len(below) == 0:
        run = 0.0
        breach_time_frac = 1.0
    else:
        trough_after = path_low[below[0]:].min()
        run = max(0.0, (breach_level - trough_after) / entry / total_loss)
        breach_time_frac = below[0] / hold
    mae_ratio = max(0.0, (entry - path_low.min()) / entry) / total_loss
    return {
        # 라벨 정의축
        "loss_early_ratio": ler, "trough_time_frac": ttf,
        # 사후 경로피처 (라벨축 아님 → 분류기 전체피처에 포함 가능)
        "post_breach_run": run, "mae_ratio": mae_ratio, "breach_time_frac": breach_time_frac,
    }


# ── 진입맥락 피처 (분류기 · 진입오류 에이전트 공용 캐노니컬) ─────────────────
def entry_features_window(wo, wh, wl, wc, wvol, buy_price=None):
    """진입 전 윈도우 봉(마지막=진입봉)에서 진입맥락 피처 계산 — 단일 소스.

    분류기·진입오류 에이전트가 공유한다. 호출자는 각자 윈도우 봉을 넘긴다
    (분류기=인덱스 윈도우 / 에이전트=시간 윈도우 pre_df). 윈도우 선택은 호출자 몫.

    buy_price=None → 진입봉 종가 기준(분류기). 주어지면 position/vs 피처는 체결가 기준
    (에이전트). ret_*는 항상 진입봉 종가 기준. 봉 부족 피처는 None.
    """
    cb = np.asarray(wc, float); hb = np.asarray(wh, float)
    lb = np.asarray(wl, float); vb = np.asarray(wvol, float)
    n = len(cb)
    entry_close = float(cb[-1])
    bp = entry_close if buy_price is None else float(buy_price)
    eo, eh, el, ev = float(wo[-1]), float(wh[-1]), float(wl[-1]), float(wvol[-1])

    def pc(a, b):
        return (a - b) / b if (b is not None and b == b and b != 0) else None

    def wmax(a, k): return float(a[-k:].max()) if n >= k else None
    def wmin(a, k): return float(a[-k:].min()) if n >= k else None

    high20, low20 = wmax(hb, 20), wmin(lb, 20)
    high60, low60 = wmax(hb, 60), wmin(lb, 60)
    avgvol20 = float(vb[-20:].mean()) if n >= 20 else None
    ma5 = float(cb[-5:].mean()) if n >= 5 else None
    ma20 = float(cb[-20:].mean()) if n >= 20 else None
    ma20_prev = float(cb[-40:-20].mean()) if n >= 40 else None
    rsi = _rsi(cb, 14)
    rets = np.diff(cb) / cb[:-1] if n >= 2 else np.array([])
    r1 = pc(entry_close, float(cb[-2])) if n >= 2 else None
    r3 = pc(entry_close, float(cb[-4])) if n >= 4 else None
    r5 = pc(entry_close, float(cb[-6])) if n >= 6 else None
    r20 = pc(entry_close, float(cb[-21])) if n >= 21 else None
    r60 = pc(entry_close, float(cb[-61])) if n >= 61 else None
    r120 = pc(entry_close, float(cb[-121])) if n >= 121 else None
    rng20 = (high20 - low20) if (high20 is not None and low20 is not None) else None
    rng60 = (high60 - low60) if (high60 is not None and low60 is not None) else None

    def rng_pos(lo, rg): return (bp - lo) / rg if (rg is not None and rg > 0) else None
    def ratio(num, den): return num / den if (den is not None and den > 0) else None

    out = {
        # 분류기 키
        "rsi_14": rsi,
        "range_position_20": rng_pos(low20, rng20),
        "range_position_60": rng_pos(low60, rng60),
        "ret_5m": r5, "ret_20m": r20, "ret_60m": r60, "ret_120m": r120,
        "accel": (r5 - r20) if (r5 is not None and r20 is not None) else None,
        "entry_vs_high20": ratio(bp, high20),
        "entry_vs_high60": ratio(bp, high60),
        "entry_vs_ma20": pc(bp, ma20),
        "ma_20_slope": pc(ma20, ma20_prev),
        "vol_20": float(rets[-20:].std()) if n >= 21 else None,
        "vol_60": float(rets[-60:].std()) if n >= 61 else None,
        "volume_ratio_20": ratio(ev, avgvol20),
        # 진입오류 에이전트 키/별칭 (같은 값, 이름만 호환)
        "entry_position_in_bar": (bp - el) / (eh - el) if eh > el else None,
        "entry_vs_open_pct": pc(bp, eo),
        "bar_return_pct": pc(entry_close, eo),
        "ret_1m": r1, "ret_3m": r3,
        "ma_5": ma5, "ma_20": ma20,
        "high_20m": high20, "low_20m": low20, "avg_volume_20m": avgvol20,
        "volume_value": ev,
        "range_position_20m": rng_pos(low20, rng20),
        "volume_ratio_20m": ratio(ev, avgvol20),
        "entry_vs_high20_ratio": ratio(bp, high20),
        "entry_vs_ma20_pct": pc(bp, ma20),
    }
    # nan → None (에이전트 상태로직의 `is None` 체크 호환)
    return {k: (None if isinstance(v, float) and v != v else v) for k, v in out.items()}


def entry_features(o, h, l, c, vol, e, buy_price=None):
    """인덱스 윈도우(직전 PRE봉) 기반 진입맥락 피처 — 분류기 샘플러용 래퍼."""
    s = max(0, e - PRE + 1)
    return entry_features_window(o[s:e + 1], h[s:e + 1], l[s:e + 1],
                                 c[s:e + 1], vol[s:e + 1], buy_price=buy_price)


# ── 실 min1 샘플러 ────────────────────────────────────────────────────────
def _files(max_codes, seed):
    files = sorted(MIN1_DIR.glob("*.parquet"))
    if not files:
        raise SystemExit(f"min1 parquet 없음: {MIN1_DIR}")
    random.Random(seed).shuffle(files)
    return files[:max_codes]


def sample_signals_only(n_target, hold_min, hold_max, max_codes, seed):
    """결과신호만 빠르게 추출 (close/low). step1·step2용."""
    rng = np.random.default_rng(seed)
    rows, drawn = [], 0
    for fp in _files(max_codes, seed):
        if len(rows) >= n_target:
            break
        df = pd.read_parquet(fp, columns=["close", "low"])
        c = df["close"].to_numpy(float); lo = df["low"].to_numpy(float)
        n = len(c)
        if n < hold_max + 2:
            continue
        per = max(8, math.ceil(n_target / max_codes) * 3)
        for _ in range(per):
            if len(rows) >= n_target:
                break
            hold = int(rng.integers(hold_min, hold_max + 1))
            e = int(rng.integers(0, n - hold - 1))
            drawn += 1
            s = outcome_signals(lo, c, e, hold)
            if s:
                rows.append(s)
    return pd.DataFrame(rows), {"drawn": drawn, "loss": len(rows)}


def sample_with_features(n_target, hold_min, hold_max, max_codes, seed):
    """피처 + 결과신호 동시 추출 (OHLCV). step3용."""
    rng = np.random.default_rng(seed)
    rows, drawn = [], 0
    for fp in _files(max_codes, seed):
        if len(rows) >= n_target:
            break
        df = pd.read_parquet(fp, columns=["open", "high", "low", "close", "volume"])
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        v = df["volume"].to_numpy(float)
        n = len(c)
        if n < PRE + hold_max + 2:
            continue
        per = max(8, math.ceil(n_target / max_codes) * 3)
        for _ in range(per):
            if len(rows) >= n_target:
                break
            hold = int(rng.integers(hold_min, hold_max + 1))
            e = int(rng.integers(PRE, n - hold - 1))
            drawn += 1
            s = outcome_signals(lo, c, e, hold)
            if s is None:
                continue
            feat = entry_features(o, h, lo, c, v, e)
            feat.update(s)
            rows.append(feat)
    return pd.DataFrame(rows), {"drawn": drawn, "loss": len(rows)}


# ── 분석단 추론용: 실 거래 → 전체피처 ─────────────────────────────────────
def classifier_features_for_trade(code, entry_dt, exit_dt):
    """실 min1에서 한 손실거래의 분류기 전체피처(CLASSIFIER_FEATURES) 계산.

    분석단 파이프라인이 거래마다 호출(전체경로 정보 사용). 진입맥락(진입 전 윈도우)
    + 사후경로(진입~청산 보유경로) 피처. min1 데이터 없으면 None-채움 → 분류기 스킵.
    """
    import pandas as pd
    base = {name: None for name in CLASSIFIER_FEATURES}
    fp = MIN1_DIR / f"{str(code).strip().zfill(6)}.parquet"
    if not fp.exists() or entry_dt is None:
        return base
    df = pd.read_parquet(fp, columns=["datetime", "open", "high", "low", "close", "volume"])
    dt = pd.to_datetime(df["datetime"]).to_numpy()
    e_dt = np.datetime64(pd.to_datetime(entry_dt))
    x_dt = np.datetime64(pd.to_datetime(exit_dt)) if exit_dt is not None else e_dt
    e_idx = np.where(dt <= e_dt)[0]
    if len(e_idx) == 0:
        return base
    e = int(e_idx[-1])
    x_idx = np.where(dt <= x_dt)[0]
    xi = int(x_idx[-1]) if len(x_idx) else e
    c = df["close"].to_numpy(float)
    hold = min(max(1, xi - e), len(c) - 1 - e)
    if hold < 1:
        return base
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); v = df["volume"].to_numpy(float)
    s = max(0, e - PRE + 1)
    feats = entry_features_window(o[s:e + 1], h[s:e + 1], l[s:e + 1], c[s:e + 1], v[s:e + 1])
    sig = outcome_signals(l, c, e, hold)
    out = {name: feats.get(name) for name in FEATURES}
    for name in POST_ENTRY_FEATURES:
        out[name] = sig[name] if sig else None
    return {name: out.get(name) for name in CLASSIFIER_FEATURES}


# ── 군집 라벨러 (②) ──────────────────────────────────────────────────────
def cluster_labels(df, cols=None, seed=42):
    """다중신호 GMM(K=2) → y(1=stop_loss_failure). 품질지표 함께 반환.

    꼬리 긴 비율신호는 99% 윈저+log1p, 유계신호는 그대로 → 표준화 후 군집.
    loss_early_ratio 평균 높은 군집 = entry_error 로 명명.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.mixture import GaussianMixture
    from sklearn.metrics import silhouette_score

    cols = cols or LABEL_SIGNALS
    X = pd.DataFrame(index=df.index)
    for col in cols:
        v = df[col].to_numpy(float)
        if col in _RATIO_LIKE:
            v = np.log1p(np.clip(v, None, np.percentile(v, 99)))
        X[col] = v
    Z = StandardScaler().fit_transform(X.values)

    g1 = GaussianMixture(1, random_state=seed).fit(Z)
    g2 = GaussianMixture(2, n_init=5, random_state=seed).fit(Z)
    lab = g2.predict(Z)
    means = [df["loss_early_ratio"].values[lab == k].mean() for k in (0, 1)]
    entry_k = int(np.argmax(means))
    y = (lab != entry_k).astype(int)            # 1 = stop_loss_failure
    info = {
        "silhouette": float(silhouette_score(Z, lab)),
        "bic_1": float(g1.bic(Z)), "bic_2": float(g2.bic(Z)),
        "n_entry_error": int((y == 0).sum()), "n_stop_loss_failure": int(y.sum()),
        "cols": list(cols),
    }
    return y, info


# ── 설계 합성 생성기 (③') ─────────────────────────────────────────────────
def _designed_path(rng, kind, hold):
    """유형별 1분봉 OHLCV 경로. e=PRE-1(진입), 길이 PRE+hold.

    kind 0 = 진입오류형: 사전 급등 → 진입후 초반 급락 (front-loaded)
    kind 1 = 손절실패형: 사전 잔잔/약세 → 진입후 완만한 지속하락 (back-loaded)
    """
    n = PRE + hold
    sigma = rng.uniform(0.0012, 0.0020)
    drift = np.zeros(n - 1)
    pre, post = slice(0, PRE - 1), slice(PRE - 1, n - 1)
    early_len = max(1, int(EARLY_FRAC * hold))
    if kind == 0:
        drift[pre] = rng.uniform(0.0002, 0.0006)                       # 사전 급등
        drift[PRE - 1:PRE - 1 + early_len] = -rng.uniform(0.0030, 0.0060)  # 초반 급락
        drift[PRE - 1 + early_len:] = rng.uniform(-0.0002, 0.0006)     # 이후 횡보/반등
        vmult = rng.uniform(1.2, 2.0)
    else:
        drift[pre] = rng.uniform(-0.0003, 0.0001)                      # 사전 잔잔/약세
        drift[post] = -rng.uniform(0.0004, 0.0010)                     # 완만한 지속하락
        vmult = rng.uniform(0.7, 1.1)
    shocks = rng.normal(drift, sigma)
    close = 10000.0 * np.exp(np.cumsum(np.concatenate([[0.0], shocks])))
    openp = np.concatenate([[close[0]], close[:-1]])
    wig = np.abs(rng.normal(0, sigma, n)) * close
    high = np.maximum(openp, close) + wig
    low = np.minimum(openp, close) - wig
    avgv = rng.uniform(8000, 20000)
    volume = np.abs(rng.normal(avgv, avgv * 0.3, n))
    volume[PRE - 1] *= vmult
    return openp, high, low, close, volume


def generate_designed(n_target, hold_min, hold_max, seed):
    """정답 구조 주입 검증셋. 피처/신호는 실 파이프라인과 동일 코드로 계산."""
    rng = np.random.default_rng(seed)
    rows, tried = [], 0
    while len(rows) < n_target and tried < n_target * 6:
        tried += 1
        kind = int(rng.integers(0, 2))
        hold = int(rng.integers(hold_min, hold_max + 1))
        o, h, l, c, v = _designed_path(rng, kind, hold)
        s = outcome_signals(l, c, PRE - 1, hold)
        if s is None:
            continue
        feat = entry_features(o, h, l, c, v, PRE - 1)
        feat.update(s)
        feat["true_type"] = "entry_error" if kind == 0 else "stop_loss_failure"
        rows.append(feat)
    return pd.DataFrame(rows), {"tried": tried, "loss": len(rows)}


def clean_features(df):
    """피처 결측/무한 제거."""
    return df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES)
