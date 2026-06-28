"""③ 실/랜덤 데이터 분류기 → 데이터 한계 증명.

결과(이미 도출): 진입맥락 피처(15개)로 군집라벨 예측 AUC ≈ 0.51 (로지스틱),
  0.505 (랜덤포레스트). RF 중요도도 평평 = 노이즈. → 피처/모델 문제 아님, 데이터 문제.
  랜덤 진입은 진입맥락↔손실유형 인과가 없어 원리적으로 예측 불가.
→ 인과가 '있는' 데이터에서 파이프라인이 작동하는지는 step3b(설계 검증셋)에서 확인.

usage: python analysis/label_validation/step3_classifier_real.py
"""
from __future__ import annotations

import argparse
import json
import sys

from label_pipeline import (OUT_DIR, FEATURES, LABEL_SIGNALS,
                            sample_with_features, cluster_labels, clean_features)

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
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score, StratifiedKFold

    print(f"[1/3] 실데이터 샘플 + 피처/신호 (보유 {args.hold_min}~{args.hold_max}분)...")
    df, diag = sample_with_features(args.n, args.hold_min, args.hold_max, args.max_codes, args.seed)
    df = clean_features(df)
    print(f"      drawn {diag['drawn']} / 피처 유효표본 {len(df)}")
    if len(df) < 500:
        sys.exit("표본 부족")

    print("[2/3] 군집 라벨...")
    y, info = cluster_labels(df, cols=LABEL_SIGNALS, seed=args.seed)
    print(f"      stop {int(y.sum())} / entry {int((y==0).sum())}  (실루엣 {info['silhouette']:.3f})")

    print("[3/3] 분류기 비교...")
    X = df[FEATURES].values
    cv = StratifiedKFold(5, shuffle=True, random_state=args.seed)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=1000))
    rf = make_pipeline(SimpleImputer(strategy="median"),
                       RandomForestClassifier(n_estimators=300, max_depth=8,
                                              min_samples_leaf=20, random_state=args.seed, n_jobs=-1))
    auc_lr = cross_val_score(lr, X, y, cv=cv, scoring="roc_auc")
    auc_rf = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")
    print(f"      로지스틱  AUC={auc_lr.mean():.3f} ± {auc_lr.std():.3f}")
    print(f"      랜덤포레스트 AUC={auc_rf.mean():.3f} ± {auc_rf.std():.3f}")
    print("      (0.5=무의미. 둘 다 낮음 → 랜덤데이터엔 진입맥락↔유형 인과 없음=데이터 한계)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step3_classifier_real.json").write_text(json.dumps({
        "n": len(df), "n_stop": int(y.sum()), "n_entry": int((y == 0).sum()),
        "cv_auc_logreg": round(float(auc_lr.mean()), 4),
        "cv_auc_rf": round(float(auc_rf.mean()), 4),
        "features": FEATURES, "label_signals_excluded": LABEL_SIGNALS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step3_classifier_real.json'}")


if __name__ == "__main__":
    main()
