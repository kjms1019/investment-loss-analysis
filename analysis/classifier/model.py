"""EntryStopClassifier — 오케스트레이터가 호출하는 런타임 분류기.

검증 파이프라인(analysis.label_validation)이 '방법이 맞다'를 증명했고,
이 모듈은 그 결과물인 **학습된 분류 모델**을 서비스가 바로 쓰도록 fit/predict/save/load
API로 노출한다.

용도 한정: 이 분류기는 **분석단(청산된 손실거래의 사후 분류)** 전용이다.
학습·추론 모두 label_pipeline.CLASSIFIER_FEATURES(진입맥락 15 + 사후경로 3,
post_breach_run·mae_ratio·breach_time_frac) **전체경로 피처**를 쓴다.
  ※ 진입 전 예측(예정매수/현재보유)은 이 모델이 아니라 predictor 의 룰
    스코어러를 쓴다 — 그 시점엔 사후경로 피처가 존재하지 않기 때문.
    진입맥락 피처(FEATURES, 15)만 넘기면 빠진 사후피처 3개가 median 으로
    조용히 대치되어 엉뚱한 점수가 나오니 절대 그렇게 쓰지 말 것.

입력  : 분류기 전체경로 피처 dict (label_pipeline.CLASSIFIER_FEATURES 키)
출력  : {entry_error_score, stop_loss_failure_score, label, confidence}
모델  : 로지스틱 회귀(해석 가능 — 계수가 곧 근거). 라벨 1 = stop_loss_failure.

오케스트레이터 연동: router.score_cycle_candidates(entry_min1_score=...) 슬롯에
  entry_error_score 를 넣으면 된다(이미 비워둔 훅). README 참고.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd

from analysis.label_validation.label_pipeline import CLASSIFIER_FEATURES

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_MODEL = ARTIFACT_DIR / "entry_stop_clf.joblib"


class EntryStopClassifier:
    """진입오류 / 손절실패 런타임 분류기."""

    def __init__(self, pipeline, meta: Dict):
        self.pipeline = pipeline
        self.meta = meta
        # 전체경로 분류기 — meta 없을 때의 기본값도 CLASSIFIER_FEATURES 로 둔다
        # (FEATURES(15)로 폴백하면 사후피처 3개가 누락돼 학습 아티팩트와 어긋남).
        self.features = meta.get("features", CLASSIFIER_FEATURES)

    # ── 학습 ──────────────────────────────────────────────────────────────
    @classmethod
    def fit(cls, X: pd.DataFrame, y, *, seed: int = 42, meta_extra: Dict = None):
        """피처 DataFrame X + 라벨 y(1=stop_loss_failure)로 학습."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import cross_val_score, StratifiedKFold

        feats = list(X.columns)
        pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(max_iter=1000))
        cv = StratifiedKFold(5, shuffle=True, random_state=seed)
        auc = cross_val_score(pipe, X.values, np.asarray(y), cv=cv, scoring="roc_auc")
        pipe.fit(X.values, np.asarray(y))
        lr = pipe.named_steps["logisticregression"]
        meta = {
            "features": feats,
            "label_map": {"0": "entry_error", "1": "stop_loss_failure"},
            "n_train": int(len(y)),
            "cv_auc_mean": round(float(auc.mean()), 4),
            "cv_auc_std": round(float(auc.std()), 4),
            "coefficients": {f: round(float(b), 4) for f, b in zip(feats, lr.coef_[0])},
        }
        if meta_extra:
            meta.update(meta_extra)
        return cls(pipe, meta)

    # ── 추론 ──────────────────────────────────────────────────────────────
    def predict(self, features: Union[Dict, pd.Series]) -> Dict:
        """단일 거래. 누락 피처는 NaN→median 대치."""
        x = np.array([[float(features.get(f, np.nan)) if features.get(f) is not None else np.nan
                       for f in self.features]], dtype=float)
        p_stop = float(self.pipeline.predict_proba(x)[0, 1])
        return self._format(p_stop)

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """여러 거래 한 번에."""
        X = df.reindex(columns=self.features).to_numpy(dtype=float)
        p = self.pipeline.predict_proba(X)[:, 1]
        return pd.DataFrame({
            "entry_error_score": np.round(1 - p, 4),
            "stop_loss_failure_score": np.round(p, 4),
            "label": np.where(p >= 0.5, "stop_loss_failure", "entry_error"),
            "confidence": np.round(np.maximum(p, 1 - p), 4),
        }, index=df.index)

    @staticmethod
    def _format(p_stop: float) -> Dict:
        return {
            "entry_error_score": round(1 - p_stop, 4),
            "stop_loss_failure_score": round(p_stop, 4),
            "label": "stop_loss_failure" if p_stop >= 0.5 else "entry_error",
            "confidence": round(max(p_stop, 1 - p_stop), 4),
        }

    # ── 영속화 ────────────────────────────────────────────────────────────
    def save(self, path: Path = DEFAULT_MODEL) -> Path:
        import joblib
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "meta": self.meta}, path)
        path.with_suffix(".meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL):
        import joblib
        if not Path(path).exists():
            raise FileNotFoundError(
                f"학습된 모델이 없습니다: {path}\n"
                f"먼저 학습하세요: python -m analysis.classifier.train")
        obj = joblib.load(path)
        return cls(obj["pipeline"], obj["meta"])


@lru_cache(maxsize=1)
def load_default() -> EntryStopClassifier:
    """기본 모델 1회 로드 후 캐시 (서비스 반복 호출용)."""
    clf = EntryStopClassifier.load(DEFAULT_MODEL)
    try:
        clf.predict({feature: 0.0 for feature in clf.features})
    except Exception:
        clf = _fit_runtime_fallback()
    return clf


def classify_entry(features: Dict) -> Dict:
    """서비스 단발 호출 헬퍼."""
    return load_default().predict(features)


def entry_min1_score(features: Dict) -> float:
    """router.score_cycle_candidates(entry_min1_score=...) 슬롯에 넣을 값."""
    return load_default().predict(features)["entry_error_score"]


def _fit_runtime_fallback() -> EntryStopClassifier:
    """Fit a small in-memory fallback when persisted sklearn artifacts mismatch.

    The committed artifact is the preferred path. This fallback keeps the
    orchestrator usable across local sklearn minor versions.
    """
    from analysis.label_validation.label_pipeline import (
        CLASSIFIER_FEATURES,
        clean_features,
        cluster_labels,
        generate_designed,
    )

    df, diag = generate_designed(1200, 380, 1900, seed=42)
    df = clean_features(df)
    y, info = cluster_labels(df, seed=42)
    # 커밋 아티팩트와 동일하게 전체경로 피처(CLASSIFIER_FEATURES, 18)로 학습.
    return EntryStopClassifier.fit(
        df[CLASSIFIER_FEATURES],
        y,
        seed=42,
        meta_extra={
            "source": "runtime_fallback_designed",
            "reason": "persisted_artifact_incompatible_with_local_sklearn",
            "generated": diag,
            "cluster_quality": info,
        },
    )
