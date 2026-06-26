"""Data contracts for the runtime predictor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal, Optional


RiskMode = Literal["entry", "live"]
ProblemType = Literal["entry_error", "stop_loss_failure", "unknown"]


@dataclass
class UserRiskProfile:
    """Aggregated mistake profile created from finished trade analysis."""

    user_id: str
    total_analyzed_trades: int = 0
    problem_counts: Dict[str, int] = field(default_factory=dict)
    average_scores: Dict[str, float] = field(default_factory=dict)
    dominant_problem_type: ProblemType = "unknown"
    source: str = "orchestrator_sqlite"

    def prior_for(self, problem_type: str) -> float:
        if self.total_analyzed_trades <= 0:
            return 0.0
        return self.problem_counts.get(problem_type, 0) / self.total_analyzed_trades

    def average_score_for(self, problem_type: str) -> float:
        return self.average_scores.get(problem_type, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntryContext:
    """Features known before or immediately after a new trade entry."""

    user_id: str
    trade_id: str
    code: str
    entered_at: datetime
    recent_trade_count: int = 0
    recent_win_rate: Optional[float] = None
    minutes_since_last_loss: Optional[float] = None
    recent_avg_holding_minutes: Optional[float] = None
    last_loss_pct: Optional[float] = None
    market_mood_score: Optional[float] = None
    same_day_trade_count: int = 0
    features: Dict[str, float] = field(default_factory=dict)

    def to_feature_dict(self) -> Dict[str, float]:
        values = {
            "recent_trade_count": float(self.recent_trade_count),
            "recent_win_rate": _none_to_zero(self.recent_win_rate),
            "minutes_since_last_loss": _none_to_zero(self.minutes_since_last_loss),
            "recent_avg_holding_minutes": _none_to_zero(self.recent_avg_holding_minutes),
            "last_loss_pct": _none_to_zero(self.last_loss_pct),
            "market_mood_score": _none_to_zero(self.market_mood_score),
            "same_day_trade_count": float(self.same_day_trade_count),
        }
        values.update({key: float(value) for key, value in self.features.items()})
        return values


@dataclass
class PositionSnapshot:
    """Current state of one open position from a live stream."""

    user_id: str
    trade_id: str
    code: str
    entry_price: float
    current_price: float
    qty: float
    entry_at: datetime
    observed_at: datetime
    stop_loss_price: Optional[float] = None
    highest_price_since_entry: Optional[float] = None
    minutes_since_stop_breach: Optional[float] = None
    price_change_5m_pct: Optional[float] = None
    volatility_30m_pct: Optional[float] = None
    volume_spike_ratio: Optional[float] = None
    market_mood_score: Optional[float] = None
    features: Dict[str, float] = field(default_factory=dict)

    @property
    def unrealized_return_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100.0

    @property
    def holding_minutes(self) -> float:
        return max((self.observed_at - self.entry_at).total_seconds() / 60.0, 0.0)

    @property
    def stop_breached(self) -> bool:
        return self.stop_loss_price is not None and self.current_price <= self.stop_loss_price

    @property
    def drawdown_from_high_pct(self) -> float:
        high = self.highest_price_since_entry
        if high is None or high <= 0:
            return 0.0
        return min((self.current_price - high) / high * 100.0, 0.0)

    def to_feature_dict(self) -> Dict[str, float]:
        values = {
            "unrealized_return_pct": self.unrealized_return_pct,
            "holding_minutes": self.holding_minutes,
            "stop_breached": 1.0 if self.stop_breached else 0.0,
            "drawdown_from_high_pct": self.drawdown_from_high_pct,
            "minutes_since_stop_breach": _none_to_zero(self.minutes_since_stop_breach),
            "price_change_5m_pct": _none_to_zero(self.price_change_5m_pct),
            "volatility_30m_pct": _none_to_zero(self.volatility_30m_pct),
            "volume_spike_ratio": _none_to_zero(self.volume_spike_ratio),
            "market_mood_score": _none_to_zero(self.market_mood_score),
        }
        values.update({key: float(value) for key, value in self.features.items()})
        return values


@dataclass
class HistoricalTrainingExample:
    """Optional supervised example for ML training.

    Labels should be created only from outcomes known after the trade is closed,
    while features must be restricted to pre-entry or live-at-time-of-alert data.
    """

    mode: RiskMode
    features: Dict[str, float]
    repeated_mistake: bool
    problem_type: ProblemType = "unknown"


@dataclass
class PredictorEvent:
    """Unified event wrapper for entry and live updates."""

    type: Literal["ENTRY", "POSITION_UPDATE"]
    payload: EntryContext | PositionSnapshot


@dataclass
class RiskSignal:
    """Predictor output consumed by notification or UI layers."""

    user_id: str
    trade_id: str
    code: str
    mode: RiskMode
    risk_score: float
    risk_level: Literal["low", "medium", "high"]
    problem_type: ProblemType
    should_alert: bool
    reasons: list[str] = field(default_factory=list)
    message: str = ""              # 사용자에게 보여줄 알림 문장 (LLM, should_alert 시 채움)
    model_used: Literal["rules", "random_forest"] = "rules"
    features: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def _none_to_zero(value: Optional[float]) -> float:
    return 0.0 if value is None else float(value)
