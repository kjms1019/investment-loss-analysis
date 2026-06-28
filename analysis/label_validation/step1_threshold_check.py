"""① 단일 고정컷(loss_early_ratio >= 0.7) 검증 + 보유기간 sweep.

결론(이미 도출): 고정 컷은 부적절. 데이터-경계가 보유기간 따라 0→0.44로 미끄러지고
  0.7은 모든 구간에서 부트스트랩 95% CI 밖. 깨끗한 이봉도 없음.
→ 단일 축 + 고정 컷을 버리고 step2(다중신호 군집)로 가는 근거.

usage:
  python analysis/label_validation/step1_threshold_check.py            # 단일 실행
  python analysis/label_validation/step1_threshold_check.py --sweep    # 보유구간 비교
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from label_pipeline import OUT_DIR, sample_signals_only

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EPS = 1e-3
REGIMES = [("scalp", 10, 60), ("intraday", 60, 380),
           ("short_swing", 380, 1900), ("long_swing", 1900, 7600)]


def bimodality_coefficient(x):
    from scipy.stats import skew, kurtosis
    n = len(x)
    g = skew(x, bias=False); k = kurtosis(x, fisher=True, bias=False)
    denom = k + 3.0 * ((n - 1) ** 2) / ((n - 2) * (n - 3))
    return (g ** 2 + 1) / denom


def gmm_boundary(w, seed):
    from sklearn.mixture import GaussianMixture
    W = w.reshape(-1, 1)
    g1 = GaussianMixture(1, random_state=seed).fit(W)
    g2 = GaussianMixture(2, n_init=5, random_state=seed).fit(W)
    means = g2.means_.ravel()
    lo, hi = float(means.min()), float(means.max())
    if hi - lo < 1e-9:
        return None, g1.bic(W), g2.bic(W)
    grid = np.linspace(lo, hi, 4001).reshape(-1, 1)
    post = g2.predict_proba(grid)[:, int(np.argmax(means))]
    return float(grid[int(np.argmin(np.abs(post - 0.5))), 0]), g1.bic(W), g2.bic(W)


def analyze(x, seed, boot, current_cut):
    w = np.log(np.clip(x, EPS, None))
    bc = bimodality_coefficient(w)
    bw, bic1, bic2 = gmm_boundary(w, seed)
    boundary = float(np.exp(bw)) if bw is not None else None
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(boot):
        bb, _, _ = gmm_boundary(np.log(np.clip(x[rng.integers(0, len(x), len(x))], EPS, None)), seed)
        if bb is not None:
            vals.append(np.exp(bb))
    vals = np.asarray(vals)
    ci = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))
    return {"bc": round(bc, 3), "bic_1": round(bic1, 1), "bic_2": round(bic2, 1),
            "boundary": round(boundary, 4) if boundary else None,
            "ci": [round(ci[0], 4), round(ci[1], 4)],
            "cut_inside": bool(ci[0] <= current_cut <= ci[1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--hold-min", type=int, default=380)
    ap.add_argument("--hold-max", type=int, default=1900)
    ap.add_argument("--max-codes", type=int, default=250)
    ap.add_argument("--boot", type=int, default=400)
    ap.add_argument("--current-cut", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    regimes = REGIMES if args.sweep else [("single", args.hold_min, args.hold_max)]
    results = {}
    print(f"{'regime':<12}{'n':>6}{'BC':>7}{'2comp':>7}{'boundary':>10}{'CI_low':>9}{'CI_hi':>8}{'0.7?':>6}")
    print("-" * 75)
    for name, hmin, hmax in regimes:
        x, diag = sample_signals_only(args.n, hmin, hmax, args.max_codes, args.seed)
        x = x["loss_early_ratio"].to_numpy()
        if len(x) < 200:
            print(f"{name:<12} 표본부족"); continue
        r = analyze(x, args.seed, args.boot, args.current_cut)
        r["n"] = len(x); results[name] = r
        print(f"{name:<12}{len(x):>6}{r['bc']:>7.2f}"
              f"{('Y' if r['bic_2'] < r['bic_1'] else 'N'):>7}"
              f"{(r['boundary'] or 0):>10.3f}{r['ci'][0]:>9.3f}{r['ci'][1]:>8.3f}"
              f"{('in' if r['cut_inside'] else 'OUT'):>6}")
    print("-" * 75)
    print("BC>0.555=깨끗한 이봉.  '0.7?'=현재 하드컷이 부트스트랩 CI 안(in)/밖(OUT)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step1_threshold.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step1_threshold.json'}")


if __name__ == "__main__":
    main()
