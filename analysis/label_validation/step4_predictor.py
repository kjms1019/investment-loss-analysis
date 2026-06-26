"""④ 예측기 — 분류기 라벨을 정답으로, '초기(현시점) 피처'만으로 예측.

구조(대화 합의):
  분류기(teacher, 전체경로 피처) → 손실거래마다 entry_error/stop_loss 라벨 생성
  예측기(student, 초기 피처만)   → 그 라벨을 정답으로 학습  (label distillation)
  진입오류·손절실패 한 모델에서 2-class로 둘 다 예측.

분류기와 데칼코마니, 차이는 '피처 범위'뿐:
  분류기 = 전체경로(사후 포함, 라벨축 제외)  /  예측기 = 초기 진입시점 피처만(look-ahead 없음)

usage:
  python analysis/label_validation/step4_predictor.py            # 설계+랜덤 둘 다
  python analysis/label_validation/step4_predictor.py --data random
"""
from __future__ import annotations

import argparse
import json
import sys

from label_pipeline import (FEATURES, LABEL_SIGNALS, sample_with_features,
                            generate_designed, cluster_labels, clean_features)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _eval(df, seed):
    """분류기 라벨(teacher) ← 결과신호 군집. 예측기(student) ← 초기피처로 그 라벨 학습."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score, StratifiedKFold

    # teacher: 분류기가 만든 라벨 (결과신호 군집 → 분류기 학습 타깃과 동일)
    y, info = cluster_labels(df, cols=LABEL_SIGNALS, seed=seed)

    # student: 초기(진입시점) 피처만으로 그 라벨 예측
    X = df[FEATURES].values
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=1000))
    rf = make_pipeline(SimpleImputer(strategy="median"),
                       RandomForestClassifier(n_estimators=300, max_depth=8,
                                              min_samples_leaf=20, random_state=seed, n_jobs=-1))
    auc_lr = cross_val_score(lr, X, y, cv=cv, scoring="roc_auc").mean()
    auc_rf = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc").mean()
    return {
        "n": int(len(df)), "n_stop": int(y.sum()), "n_entry": int((y == 0).sum()),
        "teacher_silhouette": round(info["silhouette"], 4),
        "predictor_auc_logreg": round(float(auc_lr), 4),
        "predictor_auc_rf": round(float(auc_rf), 4),
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
        print("[설계 데이터] 분류기 라벨 → 초기피처 예측기...")
        df, _ = generate_designed(args.n, args.hold_min, args.hold_max, args.seed)
        out["designed"] = _eval(clean_features(df), args.seed)
        r = out["designed"]
        print(f"  표본 {r['n']} (stop {r['n_stop']}/entry {r['n_entry']})")
        print(f"  예측기 AUC  logreg={r['predictor_auc_logreg']:.3f}  rf={r['predictor_auc_rf']:.3f}")

    if args.data in ("both", "random"):
        print("[랜덤 데이터] 분류기 라벨 → 초기피처 예측기...")
        df, _ = sample_with_features(args.n, args.hold_min, args.hold_max, args.max_codes, args.seed)
        out["random"] = _eval(clean_features(df), args.seed)
        r = out["random"]
        print(f"  표본 {r['n']} (stop {r['n_stop']}/entry {r['n_entry']})")
        print(f"  예측기 AUC  logreg={r['predictor_auc_logreg']:.3f}  rf={r['predictor_auc_rf']:.3f}")

    print("\n해석: 초기피처는 미래(보유경로)를 모름 → 진입맥락에 인과가 있을 때만 예측 가능.")
    print("       설계셋(주입구조)·실거래(행동구조)에선 작동, 순수 랜덤에선 0.5 수렴.")
    from label_pipeline import OUT_DIR
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "step4_predictor.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_DIR / 'step4_predictor.json'}")


if __name__ == "__main__":
    main()
