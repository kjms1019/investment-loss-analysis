from datetime import datetime

import pytest

from analysis.common.db_backend import database_backend_from_env
from analysis.llm.client import _clean_generated_text
from analysis.orchestrator.streaming_runtime import StreamingRiskRuntime
from analysis.predictor import (
    EntryContext,
    NotificationPolicy,
    PredictorEvent,
    PredictorScoringConfig,
    TradeRiskPredictor,
    UserRiskProfile,
)


def test_db_backend_requires_supabase_credentials(monkeypatch):
    monkeypatch.setenv("MIRAE_DB_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    config = database_backend_from_env()

    with pytest.raises(RuntimeError):
        config.validate()


def test_llm_generated_text_guardrails_fallback_on_overlong_output():
    assert _clean_generated_text('"짧은 문장"', fallback="FB") == "짧은 문장"
    assert _clean_generated_text("너무 긴 문장입니다", fallback="FB", max_output_chars=5) == "FB"


def test_predictor_scoring_config_controls_risk_bands():
    predictor = TradeRiskPredictor(
        scoring_config=PredictorScoringConfig(risk_medium=0.2, risk_high=0.95),
        notification_policy=NotificationPolicy(threshold=0.0),
    )

    signal = predictor.predict_entry_risk(
        EntryContext(
            user_id="u1",
            trade_id="t1",
            code="005930",
            entered_at=datetime(2026, 1, 2, 9, 30),
        )
    )

    assert signal.risk_level == "low"


def test_streaming_runtime_enriches_entry_features_before_prediction():
    predictor = TradeRiskPredictor(
        profile=UserRiskProfile(user_id="u1", dominant_problem_type="entry_error"),
        notification_policy=NotificationPolicy(threshold=0.0),
    )
    runtime = StreamingRiskRuntime(
        predictor,
        entry_feature_provider=lambda code, when: {
            "range_position_20": 0.9,
            "rsi_14": 72.0,
        },
    )

    signal = runtime.evaluate(
        PredictorEvent(
            type="ENTRY",
            payload=EntryContext(
                user_id="u1",
                trade_id="planned-1",
                code="005930",
                entered_at=datetime(2026, 1, 2, 9, 30),
            ),
        )
    )

    assert signal.mode == "entry"
    assert "range_top_chase" in signal.reasons
    assert "rsi_14" in signal.features
