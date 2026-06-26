"""분류기 학습 + 영속화.

학습 데이터 = 라벨된 손실거래(진입맥락 피처 + 군집 라벨).
  현재 소스: 설계 합성 검증셋(generate_designed) — 실거래 로그가 없으므로 placeholder.
  실거래가 생기면 --source real 로 교체 (closed-trade 피처/신호 parquet에서 로드).

라벨은 결과신호 군집(cluster_labels)으로 생성 → 피처(진입맥락)로 학습 → 순환 없음.

usage:
  python -m analysis.classifier.train                 # 설계셋으로 학습 후 저장
  python -m analysis.classifier.train --n 8000
"""
from __future__ import annotations

import argparse
import sys

from analysis.label_validation.label_pipeline import (
    CLASSIFIER_FEATURES, sample_with_features, generate_designed,
    cluster_labels, clean_features,
)
from analysis.classifier.model import EntryStopClassifier, DEFAULT_MODEL

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000, help="학습 표본 수")
    ap.add_argument("--hold-min", type=int, default=380)
    ap.add_argument("--hold-max", type=int, default=1900)
    # random = 실 min1 랜덤샘플(아키텍처 기준). designed = 구조주입 참고용(검증 전용).
    ap.add_argument("--source", choices=["random", "designed"], default="random",
                    help="학습 데이터 소스. random=실 min1 랜덤샘플(기본) / designed=참고용")
    ap.add_argument("--max-codes", type=int, default=250, help="random 소스에서 로드할 종목 수")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print(f"[1/3] 학습 데이터 준비 (source={args.source}, n={args.n})...")
    if args.source == "random":
        df, _ = sample_with_features(args.n, args.hold_min, args.hold_max, args.max_codes, args.seed)
        trained_on = "random-sampled real KOSPI min1 (cluster labels) — architecture basis"
    else:
        df, _ = generate_designed(args.n, args.hold_min, args.hold_max, args.seed)
        trained_on = "DESIGNED synthetic (reference/validation only — NOT architecture basis)"
    df = clean_features(df)
    print(f"      유효표본 {len(df)}")

    print("[2/3] 라벨 생성(결과신호 군집) + 학습 (전체경로 피처)...")
    y, info = cluster_labels(df, seed=args.seed)
    clf = EntryStopClassifier.fit(df[CLASSIFIER_FEATURES], y, seed=args.seed, meta_extra={
        "trained_on": trained_on,
        "feature_scope": "full_path (entry-context + post-entry path, label-axes excluded)",
        "label_source": "GMM cluster on outcome signals (loss_early_ratio, trough_time_frac)",
        "cluster_silhouette": round(info["silhouette"], 4),
        "source": args.source,
    })
    print(f"      학습완료 — 5-fold AUC={clf.meta['cv_auc_mean']:.3f} ± {clf.meta['cv_auc_std']:.3f}")
    print("      상위 계수(양수=손절실패, 음수=진입오류):")
    top = sorted(clf.meta["coefficients"].items(), key=lambda t: -abs(t[1]))[:5]
    for name, b in top:
        print(f"        {name:<20} {b:+.3f}")

    print("[3/3] 모델 저장...")
    path = clf.save(DEFAULT_MODEL)
    print(f"      → {path}")
    print(f"      → {path.with_suffix('.meta.json')}")
    if args.source == "random":
        print("\n실 min1 랜덤샘플 + 군집라벨 학습(아키텍처 기준). 실 사용자 거래로그 확보 시 갱신.")
    else:
        print("\n⚠️ designed는 참고/검증용 — 배포 모델은 --source random 사용.")


if __name__ == "__main__":
    main()
