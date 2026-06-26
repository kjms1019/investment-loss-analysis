"""orchestrator.router — classifier scores + primary routing policy tests."""

from analysis.orchestrator.router import (
    AGENT_ENTRY_ERROR,
    AGENT_STOP_LOSS_FAILURE,
    route_cycle,
)


def test_disposition_routes_to_stop_loss_primary():
    d = route_cycle("t1", psych_dominant="disposition",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.route_type == "single_primary"
    assert d.profile_eligible is True


def test_revenge_routes_to_entry_error_primary():
    d = route_cycle("t2", psych_dominant="revenge",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.route_type == "single_primary"


def test_overtrading_without_trade_signal_abstains():
    d = route_cycle("t3", psych_dominant="overtrading",
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.route_status == "abstained"
    assert d.route_type == "abstain"


def test_stop_behavior_routes_to_stop_loss():
    d = route_cycle("t4", psych_dominant=None,
                    breached=True, delay_days=3, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.route_type == "single_primary"


def test_breached_short_delay_uses_minute_policy():
    d = route_cycle("t5", psych_dominant=None,
                    breached=True, delay_days=1, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.reason.startswith("primary_stop_loss_failure")


def test_no_signal_abstains_instead_of_defaulting():
    d = route_cycle("t6", psych_dominant=None,
                    breached=False, delay_days=0, loss_early_ratio=None)
    assert d.route_status == "abstained"


def test_early_loss_routes_to_entry_error():
    d = route_cycle("t7", psych_dominant=None,
                    breached=False, delay_days=0, loss_early_ratio=0.8)
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.route_type == "single_primary"


def test_both_signals_choose_primary_and_record_secondary():
    d = route_cycle("t8", psych_dominant="revenge",
                    breached=True, delay_days=4, loss_early_ratio=None)
    assert d.agent_id == AGENT_STOP_LOSS_FAILURE
    assert d.route_type == "single_primary_with_secondary"
    assert d.secondary_factors == [AGENT_ENTRY_ERROR]


def test_learned_classifier_scores_can_drive_routing():
    d = route_cycle(
        "t9",
        psych_dominant=None,
        breached=False,
        delay_days=0,
        loss_early_ratio=None,
        classifier_entry_score=0.95,
        classifier_stop_score=0.1,
        classifier_result={"label": "entry_error", "confidence": 0.95},
    )
    assert d.agent_id == AGENT_ENTRY_ERROR
    assert d.route_type == "single_primary"
    assert d.classifier_scores.entry_error_score > d.classifier_scores.stop_loss_failure_score
