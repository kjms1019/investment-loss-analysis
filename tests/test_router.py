"""orchestrator.router — 라우팅은 '분류기 단독'으로 결정한다(설계 의도).

심리귀속·손절엔진(breach/delay)은 라우팅에 가산하지 않는다.
  · 심리 → 도메인 에이전트 '해석'으로 (attach_psych_evidence)
  · 손절엔진 → 손절 에이전트 '분석'으로
따라서 분류기 점수가 없으면(심리/breach만 있으면) 라우팅은 abstain 한다.
"""

from analysis.orchestrator.router import (
    AGENT_ENTRY_ERROR,
    AGENT_STOP_LOSS_FAILURE,
    route_cycle,
)


# ── 분류기 점수가 라우팅을 결정 ───────────────────────────────────────────
def test_classifier_entry_routes_to_entry_error():
    d = route_cycle("t1", psych_dominant=None, breached=False, delay_days=0,
                    loss_early_ratio=None,
                    classifier_entry_score=0.95, classifier_stop_score=0.10)
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.route_type == "single_primary"


def test_classifier_stop_routes_to_stop_loss():
    d = route_cycle("t2", psych_dominant=None, breached=False, delay_days=0,
                    loss_early_ratio=None,
                    classifier_entry_score=0.10, classifier_stop_score=0.95)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.route_type == "single_primary"


def test_classifier_both_strong_records_secondary():
    d = route_cycle("t3", psych_dominant=None, breached=False, delay_days=0,
                    loss_early_ratio=None,
                    classifier_entry_score=0.60, classifier_stop_score=0.90)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.route_type == "single_primary_with_secondary"
    assert d.secondary_factors == [AGENT_ENTRY_ERROR]


# ── 라우팅 미반영 신호들은 단독으로 라우팅하지 않는다(abstain) ─────────────
def test_psych_alone_does_not_route():
    # 심리(처분효과)는 라우팅 신호가 아니라 에이전트 해석용 → 단독이면 abstain
    d = route_cycle("t4", psych_dominant="disposition", breached=False,
                    delay_days=0, loss_early_ratio=None)
    assert d.route_status == "abstained"


def test_revenge_alone_does_not_route():
    d = route_cycle("t5", psych_dominant="revenge", breached=False,
                    delay_days=0, loss_early_ratio=None)
    assert d.route_status == "abstained"


def test_breach_alone_does_not_route():
    # 손절엔진(breach/delay)은 손절 에이전트 분석용 → 라우팅 단독 신호 아님
    d = route_cycle("t6", psych_dominant=None, breached=True, delay_days=3,
                    loss_early_ratio=None)
    assert d.route_status == "abstained"


def test_loss_early_ratio_alone_does_not_route():
    # 라벨 정의축 → 라우팅 신호 아님(0.7 고정컷 제거)
    d = route_cycle("t7", psych_dominant=None, breached=False, delay_days=0,
                    loss_early_ratio=0.8)
    assert d.route_status == "abstained"


def test_no_signal_abstains():
    d = route_cycle("t8", psych_dominant=None, breached=False, delay_days=0,
                    loss_early_ratio=None)
    assert d.route_status == "abstained"
