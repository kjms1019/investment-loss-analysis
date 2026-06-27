from datetime import datetime

from analysis.orchestrator.interaction import build_interaction_state
from analysis.orchestrator.router import AGENT_ENTRY_ERROR, AGENT_STOP_LOSS_FAILURE
from analysis.orchestrator.schema import AgentResult
from common.schema import TradeCycle


def _cycle(trade_id, pnl):
    return TradeCycle(
        trade_id=trade_id,
        code="005930",
        name="삼성전자",
        entry_dt=datetime(2026, 1, 2, 9, 0),
        exit_dt=datetime(2026, 1, 2, 10, 0),
        entry_price=10000,
        exit_price=9000,
        qty=1,
        realized_pnl=pnl,
        realized_pnl_pct=-10.0,
        closed=True,
    )


def _result(trade_id, agent_id):
    return AgentResult(
        run_id="run1",
        trade_id=trade_id,
        agent_id=agent_id,
        output_status="ok",
        score=0.7,
        severity="strong",
    )


def test_interaction_asks_when_frequency_and_amount_winners_differ():
    state = build_interaction_state(
        [
            _result("t1", AGENT_ENTRY_ERROR),
            _result("t2", AGENT_ENTRY_ERROR),
            _result("t3", AGENT_STOP_LOSS_FAILURE),
        ],
        [_cycle("t1", -10000), _cycle("t2", -10000), _cycle("t3", -50000)],
    )

    data = state.to_dict()

    assert data["frequency_winner"] == AGENT_ENTRY_ERROR
    assert data["amount_winner"] == AGENT_STOP_LOSS_FAILURE
    assert data["question_required"] is True
    assert "어떤 문제를 중심으로 분석해볼까요?" in data["prompt_body"]
    assert data["options"][0]["label"] == "자주 반복된 문제"
    assert data["options"][0]["agent_id"] == AGENT_ENTRY_ERROR
    assert data["options"][1]["label"] == "손실 금액이 컸던 문제"
    assert data["options"][1]["agent_id"] == AGENT_STOP_LOSS_FAILURE


def test_interaction_uses_abs_realized_pnl_for_loss_amount():
    state = build_interaction_state(
        [_result("t1", AGENT_STOP_LOSS_FAILURE)],
        [_cycle("t1", -12345)],
    )

    stat = state.to_dict()["category_stats"][AGENT_STOP_LOSS_FAILURE]

    assert stat["loss_amount_sum"] == 12345.0
    assert state.auto_selected_agent_id == AGENT_STOP_LOSS_FAILURE
    assert state.auto_selected_basis == "auto_same_winner"


def test_interaction_followup_prompt_for_remaining_agent():
    state = build_interaction_state(
        [
            _result("t1", AGENT_ENTRY_ERROR),
            _result("t2", AGENT_STOP_LOSS_FAILURE),
        ],
        [_cycle("t1", -10000), _cycle("t2", -20000)],
        completed_agent_ids=[AGENT_ENTRY_ERROR],
    )

    data = state.to_dict()

    assert data["remaining_agent_ids"] == [AGENT_STOP_LOSS_FAILURE]
    assert data["followup_prompt_body"] == "손절실패 분석도 이어서 확인해볼까요?\n[예] [아니오]"


def test_interaction_user_selection_sets_focus_and_queue():
    state = build_interaction_state(
        [
            _result("t1", AGENT_ENTRY_ERROR),
            _result("t2", AGENT_ENTRY_ERROR),
            _result("t3", AGENT_STOP_LOSS_FAILURE),
        ],
        [_cycle("t1", -10000), _cycle("t2", -10000), _cycle("t3", -50000)],
        selected_agent_id=AGENT_STOP_LOSS_FAILURE,
        selected_basis="amount",
    )

    data = state.to_dict()

    assert data["question_required"] is False
    assert data["focus_agent_id"] == AGENT_STOP_LOSS_FAILURE
    assert data["focus_basis"] == "amount"
    assert data["focus_trade_ids"] == ["t3"]
    assert data["analysis_queue"][0] == AGENT_STOP_LOSS_FAILURE
    assert data["auto_selected_basis"] == "amount"
