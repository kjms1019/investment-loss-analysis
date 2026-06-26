"""③' 설계된(designed) 합성 검증셋 → 파이프라인 작동 검증.

⚠️ 정직성 고지: 랜덤이 아니라 정답 구조를 의도적으로 심은 '설계된 검증셋'.
  용도: 인과가 실재할 때 (군집 라벨러 + 분류기)가 그 구조를 복원하는지 확인.
  금지: '0.7이 맞다' 등 임계값 증명(순환). 실제 시장에 그 구조가 있는지도 증명 못 함.
  축 선택의 정당성은 step2(실데이터 2축 군집)가 제공.

결과(이미 도출): 군집↔주입유형 정확도 ~0.98, 분류기 AUC ~0.96.
  → 같은 코드, 데이터만 구조 있게 바꾸니 0.51→0.96. "막힌 건 데이터지 파이프라인 아님".

usage: python analysis/label_validation/step3b_classifier_designed.py
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from label_pipeline import (OUT_DIR, FEATURES, generate_designed,
                            cluster_labels, clean_features)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--hold-min", type=int, default=380)
    ap.add_argument("--hold-max", type=int, default=1900)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import adjusted_rand_score, accuracy_score

    print(f"[1/4] 설계된 합성 거래 생성 (보유 {args.hold_min}~{args.hold_max}분)...")
    df, diag = generate_designed(args.n, args.hold_min, args.hold_max, args.seed)
    df = clean_features(df)
    print(f"      생성시도 {diag['tried']} / 손실표본 {len(df)}")
    true = (df["true_type"] == "stop_loss_failure").astype(int).values

    print("[2/4] 군집 라벨러 ↔ 주입한 진짜유형 일치도...")
    y, info = cluster_labels(df, seed=args.seed)
    acc = max(accuracy_score(true, y), accuracy_score(true, 1 - y))
    ari = adjusted_rand_score(true, y)
    print(f"      정확도={acc:.3f}  ARI={ari:.3f} (1=완벽)  실루엣={info['silhouette']:.3f}")

    X = df[FEATURES].values
    cv = StratifiedKFold(5, shuffle=True, random_state=args.seed)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=1000))
    rf = make_pipeline(SimpleImputer(strategy="median"),
                       RandomForestClassifier(n_estimators=300, max_depth=8,
                                              min_samples_leaf=20, random_state=args.seed, n_jobs=-1))
    print("[3/4] 진입맥락 피처 → 군집라벨 예측 AUC...")
    auc_lr = cross_val_score(lr, X, y, cv=cv, scoring="roc_auc")
    auc_rf = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")
    auc_true = cross_val_score(lr, X, true, cv=cv, scoring="roc_auc")
    print(f"      로지스틱 AUC={auc_lr.mean():.3f} ± {auc_lr.std():.3f}")
    print(f"      랜덤포레스트 AUC={auc_rf.mean():.3f} ± {auc_rf.std():.3f}")
    print(f"      (참고: 진짜유형 기준 로지스틱 AUC={auc_true.mean():.3f})")

    lr.fit(X, y)
    coefs = sorted(zip(FEATURES, lr.named_steps["logisticregression"].coef_[0]),
                   key=lambda t: -abs(t[1]))
    print("[4/4] 로지스틱 계수 β (양수=손절실패, 음수=진입오류) 상위:")
    for name, b in coefs[:6]:
        print(f"        {name:<20} {b:+.3f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step3b_designed.json").write_text(json.dumps({
        "kind": "DESIGNED validation set (NOT random)",
        "n": len(df), "label_vs_true_accuracy": round(acc, 4), "label_vs_true_ari": round(ari, 4),
        "cv_auc_logreg": round(float(auc_lr.mean()), 4),
        "cv_auc_rf": round(float(auc_rf.mean()), 4),
        "cv_auc_logreg_true": round(float(auc_true.mean()), 4),
        "coefficients": {n: round(float(b), 4) for n, b in coefs},
        "note": "파이프라인 작동 검증용. 임계값/현실구조 증명엔 사용 불가(순환).",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step3b_designed.json'}")


if __name__ == "__main__":
    main()
