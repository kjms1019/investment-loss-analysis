"""런타임 진입오류/손절실패 분류기.

서비스/오케스트레이터가 import해서 바로 쓰는 컴포넌트.

    from analysis.classifier import classify_entry
    result = classify_entry(entry_features)
    # → {"entry_error_score": .., "stop_loss_failure_score": .., "label": .., "confidence": ..}

학습/영속화는 analysis.classifier.train (기본 소스=설계 합성 검증셋).
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
