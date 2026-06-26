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
    CLASSIFIER_FEATURES, generate_designed, cluster_labels, clean_features,
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
    ap.add_argument("--source", choices=["designed"], default="designed",
                    help="학습 데이터 소스 (real은 실거래 로그 생기면 추가)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print(f"[1/3] 학습 데이터 준비 (source={args.source}, n={args.n})...")
    df, _ = generate_designed(args.n, args.hold_min, args.hold_max, args.seed)
    df = clean_features(df)
    print(f"      유효표본 {len(df)}")

    print("[2/3] 라벨 생성(결과신호 군집) + 학습 (전체경로 피처)...")
    y, info = cluster_labels(df, seed=args.seed)
    clf = EntryStopClassifier.fit(df[CLASSIFIER_FEATURES], y, seed=args.seed, meta_extra={
        "trained_on": "DESIGNED synthetic validation set (placeholder until real labeled trades)",
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
    print("\n⚠️ 설계 합성으로 학습된 placeholder. 실거래 라벨 확보 시 재학습 필요.")


if __name__ == "__main__":
    main()
