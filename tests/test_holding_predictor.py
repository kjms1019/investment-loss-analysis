from datetime import datetime

from analysis.orchestrator import (
    CurrentHoldingInput,
    HoldingMarketSnapshot,
    build_position_snapshot,
    evaluate_current_holdings,
)
from analysis.predictor import NotificationPolicy, UserRiskProfile


def test_build_position_snapshot_uses_uploaded_buy_time_for_holding_minutes():
    holding = CurrentHoldingInput(
        user_id="u1",
        holding_id="h1",
        name="Samsung",
        qty=10,
        bought_at=datetime(2026, 6, 26, 9, 0),
        code="005930",
    )
    snapshot = build_position_snapshot(
        holding,
        HoldingMarketSnapshot(
            entry_price=10000,
            current_price=9000,
            observed_at=datetime(2026, 6, 26, 10, 30),
            stop_loss_price=9500,
            highest_price_since_entry=10300,
            minutes_since_stop_breach=45,
            price_change_5m_pct=-2.5,
        ),
    )

    assert snapshot.trade_id == "h1"
    assert snapshot.code == "005930"
    assert snapshot.holding_minutes == 90
    assert snapshot.stop_breached is True
    assert snapshot.unrealized_return_pct == -10


def test_evaluate_current_holdings_builds_snapshots_and_signals_from_upload_rows():
    rows = [
        {
            "\uc0ac\uc6a9\uc790\uba85": "u1",
            "\ubcf4\uc720ID": "h-risky",
            "\uc885\ubaa9\uba85": "Samsung",
            "\ud604\uc7ac\ubcf4\uc720\uc218\ub7c9": 10,
            "\ub9e4\uc218\uc77c\uc2dc": "2026-06-26 09:00:00",
            "\uc885\ubaa9\ucf54\ub4dc": "005930",
        }
    ]

    def provider(holding):
        return HoldingMarketSnapshot(
            entry_price=10000,
            current_price=9000,
            observed_at=datetime(2026, 6, 26, 10, 30),
            stop_loss_price=9500,
            highest_price_since_entry=10400,
            minutes_since_stop_breach=45,
            price_change_5m_pct=-2.5,
            volatility_30m_pct=3.5,
            market_mood_score=-0.6,
        )

    results = evaluate_current_holdings(
        rows,
        profile=UserRiskProfile(
            user_id="u1",
            total_analyzed_trades=4,
            problem_counts={"stop_loss_failure": 3, "entry_error": 1},
            average_scores={"stop_loss_failure": 0.75},
            dominant_problem_type="stop_loss_failure",
        ),
        market_data_provider=provider,
        notification_policy=NotificationPolicy(threshold=0.7),
    )

    assert len(results) == 1
    assert results[0].snapshot.holding_minutes == 90
    assert results[0].signal.mode == "live"
    assert results[0].signal.should_alert is True
    assert "stop_loss_breached" in results[0].signal.reasons
