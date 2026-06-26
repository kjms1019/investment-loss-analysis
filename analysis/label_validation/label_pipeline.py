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
    else:
        trough_after = path_low[below[0]:].min()
        run = max(0.0, (breach_level - trough_after) / entry / total_loss)
    return {"loss_early_ratio": ler, "trough_time_frac": ttf, "post_breach_run": run}


# ── 진입맥락 피처 (분류기용) ───────────────────────────────────────────────
def entry_features(o, h, l, c, vol, e):
    """진입시점(e) 기준 backward 피처. 진입 전 PRE봉 필요."""
    entry = c[e]
    cb = c[e - PRE + 1:e + 1]; hb = h[e - PRE + 1:e + 1]
    lb = l[e - PRE + 1:e + 1]; vb = vol[e - PRE + 1:e + 1]
    high20 = hb[-20:].max(); low20 = lb[-20:].min()
    high60 = hb[-60:].max(); low60 = lb[-60:].min()
    rng20 = high20 - low20; rng60 = high60 - low60
    ma20 = cb[-20:].mean(); ma20_prev = cb[-40:-20].mean()
    rets = np.diff(cb) / cb[:-1]
    r5 = entry / cb[-6] - 1; r20 = entry / cb[-21] - 1
    r60 = entry / cb[-61] - 1; r120 = entry / cb[-121] - 1
    return {
        "rsi_14": _rsi(cb, 14),
        "range_position_20": (entry - low20) / rng20 if rng20 > 0 else np.nan,
        "range_position_60": (entry - low60) / rng60 if rng60 > 0 else np.nan,
        "ret_5m": r5, "ret_20m": r20, "ret_60m": r60, "ret_120m": r120,
        "accel": r5 - r20,
        "entry_vs_high20": entry / high20 if high20 > 0 else np.nan,
        "entry_vs_high60": entry / high60 if high60 > 0 else np.nan,
        "entry_vs_ma20": entry / ma20 - 1 if ma20 > 0 else np.nan,
        "ma_20_slope": (ma20 - ma20_prev) / ma20_prev if ma20_prev > 0 else np.nan,
        "vol_20": rets[-20:].std(), "vol_60": rets[-60:].std(),
        "volume_ratio_20": vol[e] / vb[-20:].mean() if vb[-20:].mean() > 0 else np.nan,
    }


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
