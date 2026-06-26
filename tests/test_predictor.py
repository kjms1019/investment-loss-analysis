from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

from analysis.predictor import (
    EntryContext,
    NotificationPolicy,
    PositionSnapshot,
    PredictorStorage,
    TradeRiskPredictor,
    UserRiskProfile,
)


def test_entry_risk_flags_quick_reentry_after_loss():
    predictor = TradeRiskPredictor(
        profile=UserRiskProfile(
            user_id="u1",
            total_analyzed_trades=5,
            problem_counts={"entry_error": 4, "stop_loss_failure": 1},
            average_scores={"entry_error": 0.7},
            dominant_problem_type="entry_error",
        ),
        notification_policy=NotificationPolicy(threshold=0.7),
    )

    signal = predictor.predict_entry_risk(
        EntryContext(
            user_id="u1",
            trade_id="t-entry",
            code="005930",
            entered_at=datetime(2026, 1, 2, 9, 30),
            recent_trade_count=5,
            recent_win_rate=0.2,
            minutes_since_last_loss=20,
            last_loss_pct=-6.5,
            same_day_trade_count=5,
            market_mood_score=-0.6,
        )
    )

    assert signal.mode == "entry"
    assert signal.problem_type == "entry_error"
    assert signal.should_alert is True
    assert "quick_reentry_after_loss" in signal.reasons


def test_live_position_risk_is_per_position():
    predictor = TradeRiskPredictor(
        profile=UserRiskProfile(
            user_id="u1",
            total_analyzed_trades=4,
            problem_counts={"stop_loss_failure": 3, "entry_error": 1},
            average_scores={"stop_loss_failure": 0.75},
            dominant_problem_type="stop_loss_failure",
        ),
        notification_policy=NotificationPolicy(threshold=0.7),
    )
    now = datetime(2026, 1, 2, 10, 30)

    risky = PositionSnapshot(
        user_id="u1",
        trade_id="t-risky",
        code="000660",
        entry_price=10000,
        current_price=9100,
        qty=10,
        entry_at=now - timedelta(hours=2),
        observed_at=now,
        stop_loss_price=9500,
        minutes_since_stop_breach=45,
        highest_price_since_entry=10300,
        price_change_5m_pct=-2.5,
    )
    calm = PositionSnapshot(
        user_id="u1",
        trade_id="t-calm",
        code="005930",
        entry_price=10000,
        current_price=10050,
        qty=10,
        entry_at=now - timedelta(hours=2),
        observed_at=now,
    )

    signals = predictor.evaluate_positions([risky, calm])

    assert [signal.trade_id for signal in signals] == ["t-risky", "t-calm"]
    assert signals[0].should_alert is True
    assert signals[0].problem_type == "stop_loss_failure"
    assert signals[1].should_alert is False


def test_notification_policy_deduplicates_until_escalation_or_cooldown():
    policy = NotificationPolicy(threshold=0.7, cooldown_minutes=30)
    predictor = TradeRiskPredictor(notification_policy=policy)
    now = datetime(2026, 1, 2, 10, 0)

    snapshot = PositionSnapshot(
        user_id="u1",
        trade_id="t1",
        code="005930",
        entry_price=10000,
        current_price=9000,
        qty=1,
        entry_at=now - timedelta(hours=1),
        observed_at=now,
        stop_loss_price=9500,
        minutes_since_stop_breach=40,
    )

    first = predictor.monitor_live_position(snapshot)
    second = predictor.monitor_live_position(snapshot)

    assert first.should_alert is True
    assert second.should_alert is False


def test_storage_handles_empty_database():
    with TemporaryDirectory() as tmp:
        storage = PredictorStorage(db_path=f"{tmp}/predictor.sqlite3")
        profile = storage.load_user_profile(user_id="u1")
        storage.close()

    assert profile.user_id == "u1"
    assert profile.total_analyzed_trades == 0
    assert profile.dominant_problem_type == "unknown"
