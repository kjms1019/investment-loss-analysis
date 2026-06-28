"""⑤ 손절실패 실시간(live) 예측기 — 보유 이벤트.

진입오류 예측기(step4)는 '매수 순간' 이벤트라 진입맥락 피처를 썼다.
손절실패 예측기는 '보유 중 폭락해 손절선 접근하는 순간' 이벤트 → **현재 포지션 피처**를 쓴다.

설계(대화 합의):
  · 알림 시점 = 보유 중 손절선(-3%) 첫 돌파 순간 t  (오늘 폭락 = 그 순간)
  · 피처 = t 시점까지만 아는 포지션 상태 (미실현손실·보유시간·최근낙폭·고점대비·진입후고점 …)
           ※ t 이후(미래)는 절대 안 씀 — look-ahead 금지
  · 정답 = 그 거래의 분류기 라벨(손절실패=1)  ← 결과신호 군집 (teacher)

→ "현재 포지션이 이렇게 생겼을 때, 이 거래는 손절실패로 갈 위험이 높다"를 예측.

usage: python analysis/label_validation/step5_stop_predictor_live.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys

import numpy as np
import pandas as pd

from label_pipeline import (MIN1_DIR, PRE, BREACH_THR, outcome_signals,
                            cluster_labels, _designed_path)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LIVE_FEATURES = [
    "unrealized_return_pct",   # 현재 미실현 손익
    "holding_minutes",         # 진입 후 경과(절대) — entry_error는 짧고 stop은 긺
    "drop_5m", "drop_20m",     # 최근 낙폭(오늘 폭락 속도)
    "drawdown_from_high",      # 진입후 고점 대비 하락
    "runup_before",            # 돌파 전 최대 상승(올랐다 빠졌나)
    "vol_20m",                 # 최근 변동성
]


def _breach_index(c, e, hold):
    """진입 후 손절선(-BREACH_THR) 첫 돌파 인덱스 t. 없으면 None."""
    entry = c[e]
    rel = (c[e:e + hold + 1] - entry) / entry
    hit = np.where(rel <= -BREACH_THR)[0]
    return (e + int(hit[0])) if len(hit) else None


def _live_features(c, e, t):
    """t 시점까지만 아는 포지션 피처 (look-ahead 없음)."""
    entry = c[e]
    seg = c[e:t + 1]
    hi = float(seg.max())
    rets = np.diff(seg) / seg[:-1] if len(seg) >= 2 else np.array([0.0])
    return {
        "unrealized_return_pct": (c[t] - entry) / entry,
        "holding_minutes": float(t - e),
        "drop_5m": (c[t] - c[t - 5]) / c[t - 5] if t >= 5 else 0.0,
        "drop_20m": (c[t] - c[t - 20]) / c[t - 20] if t >= 20 else 0.0,
        "drawdown_from_high": (c[t] - hi) / hi if hi > 0 else 0.0,
        "runup_before": (hi - entry) / entry,
        "vol_20m": float(rets[-20:].std()),
    }


def _record(l, c, e, hold):
    """손실거래 하나 → (손절선 돌파 순간 포지션 피처) + (전체 결과신호=라벨용). 미돌파면 None."""
    if (c[e + hold] - c[e]) / c[e] >= 0:
        return None                        # 손실거래만
    t = _breach_index(c, e, hold)
    if t is None or t <= e + 1:
        return None                        # 손절선 미돌파 → 알림 이벤트 없음
    sig = outcome_signals(l, c, e, hold)   # 라벨용 (전체경로)
    if sig is None:
        return None
    feat = _live_features(c, e, t)
    feat.update(sig)
    return feat


def sample_random(n, hold_min, hold_max, max_codes, seed):
    rng = np.random.default_rng(seed)
    files = sorted(MIN1_DIR.glob("*.parquet")); random.Random(seed).shuffle(files)
    files = files[:max_codes]
    rows = []
    for fp in files:
        if len(rows) >= n:
            break
        df = pd.read_parquet(fp, columns=["low", "close"])
        l, c = df["low"].to_numpy(float), df["close"].to_numpy(float)
        nn = len(c)
        if nn < PRE + hold_max + 2:
            continue
        per = max(8, math.ceil(n / max_codes) * 3)
        for _ in range(per):
            if len(rows) >= n:
                break
            hold = int(rng.integers(hold_min, hold_max + 1)); e = int(rng.integers(PRE, nn - hold - 1))
            if c[e] <= 0:
                continue
            rec = _record(l, c, e, hold)
            if rec:
                rows.append(rec)
    return pd.DataFrame(rows)


def sample_designed(n, hold_min, hold_max, seed):
    rng = np.random.default_rng(seed)
    rows, tried = [], 0
    while len(rows) < n and tried < n * 8:
        tried += 1
        kind = int(rng.integers(0, 2))
        hold = int(rng.integers(hold_min, hold_max + 1))
        _, _, l, c, _ = _designed_path(rng, kind, hold)
        rec = _record(l, c, PRE - 1, hold)
        if rec:
            rec["true_type"] = "stop_loss_failure" if kind == 1 else "entry_error"
            rows.append(rec)
    return pd.DataFrame(rows)


def _eval(df, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score, StratifiedKFold

    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=LIVE_FEATURES)
    y, info = cluster_labels(df, seed=seed)         # teacher = 분류기 라벨(손절실패=1)
    X = df[LIVE_FEATURES].values
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=1000))
    rf = make_pipeline(SimpleImputer(strategy="median"),
                       RandomForestClassifier(n_estimators=300, max_depth=8,
                                              min_samples_leaf=20, random_state=seed, n_jobs=-1))
    return {
        "n": int(len(df)), "n_stop": int(y.sum()), "n_entry": int((y == 0).sum()),
        "auc_logreg": round(float(cross_val_score(lr, X, y, cv=cv, scoring="roc_auc").mean()), 4),
        "auc_rf": round(float(cross_val_score(rf, X, y, cv=cv, scoring="roc_auc").mean()), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--hold-min", type=int, default=380)
    ap.add_argument("--hold-max", type=int, default=1900)
    ap.add_argument("--max-codes", type=int, default=250)
    ap.add_argument("--data", choices=["both", "designed", "random"], default="both")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out = {}
    if args.data in ("both", "designed"):
        print("[설계] 보유 폭락 순간 포지션 피처 → 손절실패 예측...")
        r = _eval(sample_designed(args.n, args.hold_min, args.hold_max, args.seed), args.seed)
        out["designed"] = r
        print(f"  표본 {r['n']} (stop {r['n_stop']}/entry {r['n_entry']})  "
              f"AUC logreg={r['auc_logreg']:.3f} rf={r['auc_rf']:.3f}")

    if args.data in ("both", "random"):
        print("[랜덤] 보유 폭락 순간 포지션 피처 → 손절실패 예측...")
        r = _eval(sample_random(args.n, args.hold_min, args.hold_max, args.max_codes, args.seed), args.seed)
        out["random"] = r
        print(f"  표본 {r['n']} (stop {r['n_stop']}/entry {r['n_entry']})  "
              f"AUC logreg={r['auc_logreg']:.3f} rf={r['auc_rf']:.3f}")

    print("\n피처는 전부 '돌파 순간까지'만 사용(look-ahead 없음). 정답=분류기 라벨.")
    from label_pipeline import OUT_DIR
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step5_stop_predictor_live.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step5_stop_predictor_live.json'}")


if __name__ == "__main__":
    main()
