"""orchestrator.router — 2-way 라우팅 단위 테스트.

하이브리드 분배: 리벤지→진입오류, 처분효과→손절실패, 과매매→제외.
"""

from analysis.orchestrator.router import (
    AGENT_ENTRY_ERROR,
    AGENT_STOP_LOSS_FAILURE,
    route_cycle,
)


def test_disposition_routes_to_stop_loss():
    d = route_cycle("t1", psych_dominant="disposition",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE


def test_revenge_routes_to_entry_error():
    d = route_cycle("t2", psych_dominant="revenge",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR


def test_overtrading_is_ignored_falls_to_default():
    # 과매매는 도메인 매핑 없음 → 손절 행동 없으니 기본(미이탈) entry_error
    d = route_cycle("t3", psych_dominant="overtrading",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR


def test_stop_behavior_routes_to_stop_loss():
    d = route_cycle("t4", psych_dominant=None,
                    breached=True, delay_days=3, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE


def test_breached_short_delay_defaults_to_stop():
    # 이탈은 했으나 1일만 버팀 → 손절 도메인이 분석 (영현이 정상손절로 판정)
    d = route_cycle("t5", psych_dominant=None,
                    breached=True, delay_days=1, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.reason == "default_breached"


def test_no_signal_defaults_to_entry_error():
    d = route_cycle("t6", psych_dominant=None,
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.reason == "default_entry_error"


def test_early_loss_routes_to_entry_error():
    d = route_cycle("t7", psych_dominant=None,
                    breached=False, delay_days=0, loss_early_ratio=0.8)
    assert d.agent_id == AGENT_ENTRY_ERROR


def test_both_signals_stop_behavior_wins():
    # 손절선 이탈+버팀(행동 증거) + 리벤지(진입 심리) → 손절 우선
    d = route_cycle("t8", psych_dominant="revenge",
                    breached=True, delay_days=4, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.reason == "both_signals_stop_behavior_wins"
