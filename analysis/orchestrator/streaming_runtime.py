"""Thin runtime wrapper for live predictor events.

Batch analysis remains responsible for closed trades and initial feature
bundles. This module is the separate streaming loop boundary: it accepts a
normalized event, enriches only the features needed at that moment, and then
delegates scoring, cooldown, message generation, and alert persistence to the
predictor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from analysis.common.min1_lookup import entry_market_features
from analysis.predictor import (
    EntryContext,
    PositionSnapshot,
    PredictorEvent,
    RiskSignal,
    TradeRiskPredictor,
)


EntryFeatureProvider = Callable[[str, datetime], dict[str, float]]


class StreamingRiskRuntime:
    """Evaluate normalized live events without touching the batch pipeline."""

    def __init__(
        self,
        predictor: TradeRiskPredictor,
        *,
        entry_feature_provider: Optional[EntryFeatureProvider] = None,
    ) -> None:
        self.predictor = predictor
        self.entry_feature_provider = entry_feature_provider or entry_market_features

    def evaluate(self, event: PredictorEvent) -> RiskSignal:
        if event.type == "ENTRY":
            if not isinstance(event.payload, EntryContext):
                raise TypeError("ENTRY events require EntryContext payload")
            return self.evaluate_entry(event.payload)
        if event.type == "POSITION_UPDATE":
            if not isinstance(event.payload, PositionSnapshot):
                raise TypeError("POSITION_UPDATE events require PositionSnapshot payload")
            return self.evaluate_position(event.payload)
        raise ValueError(f"Unsupported predictor event type: {event.type}")

    def evaluate_entry(self, context: EntryContext) -> RiskSignal:
        if not context.features:
            context = EntryContext(
                user_id=context.user_id,
                trade_id=context.trade_id,
                code=context.code,
                entered_at=context.entered_at,
                recent_trade_count=context.recent_trade_count,
                recent_win_rate=context.recent_win_rate,
                minutes_since_last_loss=context.minutes_since_last_loss,
                recent_avg_holding_minutes=context.recent_avg_holding_minutes,
                last_loss_pct=context.last_loss_pct,
                market_mood_score=context.market_mood_score,
                same_day_trade_count=context.same_day_trade_count,
                features=self.entry_feature_provider(context.code, context.entered_at),
            )
        return self.predictor.predict_entry_risk(context)

    def evaluate_position(self, snapshot: PositionSnapshot) -> RiskSignal:
        return self.predictor.monitor_live_position(snapshot)
