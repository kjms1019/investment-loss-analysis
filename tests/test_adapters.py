"""common.adapters / schema — 출력 변환 단위 테스트."""

from common.schema import severity_to_score
from common.adapters import (
    from_junmo_result,
    from_subin_result,
    from_younghyun_result,
)


def test_severity_to_score():
    assert severity_to_score("strong") == 1.0
    assert severity_to_score("moderate") == 0.6
    assert severity_to_score("weak") == 0.25
    assert severity_to_score("none") == 0.0
    assert severity_to_score("unknown") == 0.0     # 미정의는 0


def test_from_subin_result_normalizes_score():
    result = {
        "risk_score_result": {"entry_error_risk_score": 80, "severity": "high"},
        "label_results": [
            {"label_id": "gap_up_chase", "triggered": True},
        ],
    }
    out = from_subin_result("t1", result)
    assert out.agent_type == "entry_error"
    assert out.score == 0.8                         # 80/100
    assert out.label == "gap_up_chase"


def test_from_younghyun_result():
    result = {
        "score": 0.532,
        "judgment_type": "지연형",
        "narrative": "6영업일 버팀",
    }
    out = from_younghyun_result("t2", result)
    assert out.agent_type == "stop_fail"
    assert out.score == 0.532
    assert out.label == "지연형"
    assert out.summary == "6영업일 버팀"


def test_from_junmo_result_picks_strongest_detected():
    result = {
        "findings": [
            {"type": "revenge", "detected": True, "severity": "weak"},
            {"type": "overtrading", "detected": True, "severity": "strong"},
            {"type": "disposition", "detected": False, "severity": "moderate"},
        ],
        "diagnosis": {"summary": "과매매 우세"},
    }
    out = from_junmo_result("t3", result)
    assert out.agent_type == "psych"
    assert out.label == "overtrading"               # detected 중 최강 severity
    assert out.score == 1.0                          # strong


def test_from_junmo_result_ignores_undetected():
    # detected=False 만 있으면 점수 0
    result = {
        "findings": [
            {"type": "revenge", "detected": False, "severity": "strong"},
        ],
        "diagnosis": {},
    }
    out = from_junmo_result("t4", result)
    assert out.score == 0.0
    assert out.label == "none"
