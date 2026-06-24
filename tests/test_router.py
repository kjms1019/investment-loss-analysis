"""orchestrator.router — 3단계 라우팅 우선순위 단위 테스트."""

from analysis.orchestrator.router import (
    AGENT_ENTRY_ERROR,
    AGENT_PSYCH,
    AGENT_STOP_LOSS_FAILURE,
    route_cycle,
)


def test_psych_takes_priority():
    # 심리 패턴이 dominant 면 손절 신호가 있어도 psych 우선
    d = route_cycle("t1", psych_dominant="revenge",
                    breached=True, delay_days=10, loss_early_ratio=0.9)
    assert d.agent_id == AGENT_PSYCH
    assert d.route_status == "routed"


def test_stop_fail_when_breached_and_delayed():
    d = route_cycle("t2", psych_dominant=None,
                    breached=True, delay_days=3, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE


def test_breach_without_enough_delay_falls_to_entry_error():
    # 이탈했지만 1일만 버팀 → 손절실패 아님 → entry_error
    d = route_cycle("t3", psych_dominant=None,
                    breached=True, delay_days=1, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR


def test_default_entry_error():
    d = route_cycle("t4", psych_dominant=None,
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.reason == "default_entry_error"


def test_early_loss_raises_entry_error_confidence():
    low  = route_cycle("t5", psych_dominant=None, breached=False,
                       delay_days=0, loss_early_ratio=0.3)
    high = route_cycle("t6", psych_dominant=None, breached=False,
                       delay_days=0, loss_early_ratio=0.8)
    assert high.agent_id == AGENT_ENTRY_ERROR
    assert high.confidence > low.confidence
