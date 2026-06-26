"""예정 매수(투자계획) → 진입오류 예측 모듈 테스트 (LLM/min1 비의존)."""
from datetime import datetime

from analysis.orchestrator import (
    ClosedTradeFact,
    PlannedEntryInput,
    build_entry_context,
    evaluate_planned_entries,
)
from analysis.predictor import NotificationPolicy, UserRiskProfile


def _history():
    # 최근 손실 위주 이력 (승률 낮음)
    return [
        ClosedTradeFact(datetime(2026, 1, 5, 10), datetime(2026, 1, 6, 10), return_pct=-8.0),
        ClosedTradeFact(datetime(2026, 2, 1, 10), datetime(2026, 2, 2, 10), return_pct=-5.0),
        ClosedTradeFact(datetime(2026, 3, 1, 10), datetime(2026, 3, 2, 10), return_pct=3.0),
        ClosedTradeFact(datetime(2026, 6, 1, 10), datetime(2026, 6, 2, 10), return_pct=-6.0),
    ]


def _plan():
    return PlannedEntryInput(user_id="u1", plan_id="P1", name="삼성전자", qty=10,
                             planned_at=datetime(2026, 6, 10, 10), code="005930")


def test_build_entry_context_features():
    ctx = build_entry_context(_plan(), _history())
    assert ctx.recent_trade_count == 4
    assert abs(ctx.recent_win_rate - 0.25) < 1e-6      # 1/4 수익
    assert ctx.last_loss_pct == -6.0                   # 직전 손실
    assert ctx.minutes_since_last_loss is not None and ctx.minutes_since_last_loss > 0


def test_from_row_parses_plan():
    row = {"사용자명": "u1", "계획ID": "P9", "종목명": "에코프로",
           "예정수량": 5, "예정일시": "2026-06-29 13:19:00"}
    p = PlannedEntryInput.from_row(row)
    assert p.plan_id == "P9" and p.name == "에코프로" and p.qty == 5.0
    assert p.planned_at == datetime(2026, 6, 29, 13, 19, 0)


def test_evaluate_planned_entries_runs():
    prof = UserRiskProfile(user_id="u1", total_analyzed_trades=4,
                           problem_counts={"entry_error": 3}, dominant_problem_type="entry_error")
    results = evaluate_planned_entries([_plan()], _history(), profile=prof,
                                       notification_policy=NotificationPolicy(threshold=0.4))
    assert len(results) == 1
    sig = results[0].signal
    assert sig.mode == "entry"
    assert 0.0 <= sig.risk_score <= 1.0
    assert sig.problem_type in ("entry_error", "stop_loss_failure", "unknown")
