"""런타임 분류기(analysis.classifier) 스모크 테스트."""
import numpy as np
import pandas as pd

from analysis.classifier import classify_entry, entry_min1_score, load_default
from analysis.classifier.model import EntryStopClassifier
from analysis.label_validation.label_pipeline import FEATURES, CLASSIFIER_FEATURES

# 진입오류 케이스(전체피처): 추격 진입 + 손실이 초반에 몰림
#   (사후피처 — 큰 초반낙폭 mae_ratio↑, 이른 손절선 돌파 breach_time_frac↓, 적은 돌파후하락)
CHASE = {"rsi_14": 75, "range_position_20": 0.9, "range_position_60": 0.9,
         "ret_5m": 0.01, "ret_20m": 0.03, "ret_60m": 0.06, "ret_120m": 0.10,
         "accel": -0.02, "entry_vs_high20": 0.995, "entry_vs_high60": 0.99,
         "entry_vs_ma20": 0.05, "ma_20_slope": 0.01, "vol_20": 0.004,
         "vol_60": 0.004, "volume_ratio_20": 1.8,
         "mae_ratio": 1.4, "post_breach_run": 0.1, "breach_time_frac": 0.1}


def test_predict_output_shape():
    r = classify_entry(CHASE)
    assert set(r) == {"entry_error_score", "stop_loss_failure_score", "label", "confidence"}
    assert 0.0 <= r["entry_error_score"] <= 1.0
    # 두 점수는 확률이라 합이 1
    assert abs(r["entry_error_score"] + r["stop_loss_failure_score"] - 1.0) < 1e-6
    assert r["label"] in ("entry_error", "stop_loss_failure")


def test_chase_leans_entry_error():
    r = classify_entry(CHASE)
    assert r["entry_error_score"] > r["stop_loss_failure_score"]
    assert r["label"] == "entry_error"


def test_entry_min1_score_is_float_in_unit():
    s = entry_min1_score(CHASE)
    assert isinstance(s, float) and 0.0 <= s <= 1.0


def test_missing_features_handled():
    # 일부 피처만 줘도 예외 없이 동작 (NaN→median 대치)
    r = classify_entry({"rsi_14": 70, "volume_ratio_20": 1.9})
    assert 0.0 <= r["confidence"] <= 1.0


def test_default_model_metadata():
    clf = load_default()
    # 분석단 분류기 = 전체경로 피처(진입 + 사후경로)
    assert clf.meta["features"] == CLASSIFIER_FEATURES
    assert clf.meta["label_map"] == {"0": "entry_error", "1": "stop_loss_failure"}


def test_save_load_roundtrip(tmp_path):
    # 작은 합성으로 즉석 학습 → 저장 → 로드 → 동일 예측
    from analysis.label_validation.label_pipeline import (
        generate_designed, cluster_labels, clean_features)
    df, _ = generate_designed(800, 380, 1900, seed=1)
    df = clean_features(df)
    y, _ = cluster_labels(df, seed=1)
    clf = EntryStopClassifier.fit(df[FEATURES], y, seed=1)
    p1 = clf.predict(CHASE)
    path = clf.save(tmp_path / "m.joblib")
    p2 = EntryStopClassifier.load(path).predict(CHASE)
    assert p1 == p2
