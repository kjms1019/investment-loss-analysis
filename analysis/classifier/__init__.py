"""런타임 진입오류/손절실패 분류기 (분석단 — 청산 손실거래 사후 분류 전용).

서비스/오케스트레이터가 import해서 바로 쓰는 컴포넌트.

    from analysis.classifier import classify_entry
    # 입력은 진입맥락 15 + 사후경로 3 = label_pipeline.CLASSIFIER_FEATURES(전체경로).
    result = classify_entry(full_path_features)
    # → {"entry_error_score": .., "stop_loss_failure_score": .., "label": .., "confidence": ..}

진입 전 예측(예정매수/현재보유)은 이 모델이 아니라 predictor 룰 스코어러를 쓴다.
학습/영속화는 analysis.classifier.train (기본 소스=실 min1 랜덤샘플 + 군집라벨).
"""
from analysis.classifier.model import (
    EntryStopClassifier,
    classify_entry,
    entry_min1_score,
    load_default,
    DEFAULT_MODEL,
)

__all__ = [
    "EntryStopClassifier",
    "classify_entry",
    "entry_min1_score",
    "load_default",
    "DEFAULT_MODEL",
]
