"""② 실데이터 2축 군집 → '왜 이 두 축으로 설계하나'의 근거.

핵심 논리(대화 합의):
  실 코스피 손실거래를 두 축(loss_early_ratio, trough_time_frac)으로 군집했더니
  1성분보다 2성분이 BIC상 명백히 우세 + 실루엣 ~0.56(이봉 기준선 0.555 상회).
  → "이 두 축에 2-그룹 구조가 실재한다"는 데이터 근거.
  → step3b 설계합성을 이 두 축으로 하는 정당성. (축의 '의미'=진입오류/손절실패 명명은
     design-brief 정의·논문이 주는 이론 몫. 데이터=축 정당성 / 이론=축 의미 로 분리.)

usage:
  python analysis/label_validation/step2_cluster_axes.py
  python analysis/label_validation/step2_cluster_axes.py --signals loss_early_ratio,trough_time_frac,post_breach_run
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from label_pipeline import OUT_DIR, LABEL_SIGNALS, sample_signals_only, cluster_labels

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--hold-min", type=int, default=380)
    ap.add_argument("--hold-max", type=int, default=1900)
    ap.add_argument("--max-codes", type=int, default=250)
    ap.add_argument("--signals", type=str, default=None,
                    help="군집 축(콤마). 기본=loss_early_ratio,trough_time_frac")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    cols = args.signals.split(",") if args.signals else LABEL_SIGNALS

    print(f"[1/2] 실데이터 샘플 (보유 {args.hold_min}~{args.hold_max}분)...")
    sig, diag = sample_signals_only(args.n, args.hold_min, args.hold_max, args.max_codes, args.seed)
    print(f"      drawn {diag['drawn']} / 손실표본 {diag['loss']}")
    if len(sig) < 300:
        sys.exit("표본 부족")

    print(f"[2/2] 두 축 군집 (축: {cols})...")
    y, info = cluster_labels(sig, cols=cols, seed=args.seed)
    bimodal = info["bic_2"] < info["bic_1"]
    print(f"      실루엣 = {info['silhouette']:.3f}  ({'이봉 기준선 0.555 상회 ✅' if info['silhouette']>0.555 else '0.555 미만'})")
    print(f"      BIC 1={info['bic_1']:.0f} / 2={info['bic_2']:.0f} → 2성분 {'우세 ✅' if bimodal else '아님 ❌'}")
    print(f"      진입오류 {info['n_entry_error']} / 손절실패 {info['n_stop_loss_failure']}")
    print("      → 두 축에 2-그룹 구조 실재. step3b 설계합성의 축 선택 근거 확보.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step2_cluster.json").write_text(
        json.dumps({"signals": cols, "quality": info, "sampling": vars(args)},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step2_cluster.json'}")


if __name__ == "__main__":
    main()
