"""Current-holding feature builder and live predictor orchestration.

This module covers the current-holdings timing: when a user uploads holdings,
the orchestrator computes one position snapshot per holding and immediately
evaluates live-position risk. Planned or just-before-order entry risk remains a
separate streaming-time flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from typing import Iterable, Optional, Protocol

from analysis.predictor import (
    NotificationPolicy,
    PositionSnapshot,
    RiskSignal,
    TradeRiskPredictor,
    UserRiskProfile,
)


@dataclass(frozen=True)
class CurrentHoldingInput:
    """Minimal current-holding input accepted from the user upload."""

    user_id: str
    holding_id: str
    name: str
    qty: float
    bought_at: datetime
    code: Optional[str] = None

    @classmethod
    def from_row(
        cls,
        row: dict,
        *,
        user_key: str = "\uc0ac\uc6a9\uc790\uba85",
        holding_key: str = "\ubcf4\uc720ID",
        name_key: str = "\uc885\ubaa9\uba85",
        qty_key: str = "\ud604\uc7ac\ubcf4\uc720\uc218\ub7c9",
        bought_at_key: str = "\ub9e4\uc218\uc77c\uc2dc",
        code_key: str = "\uc885\ubaa9\ucf54\ub4dc",
    ) -> "CurrentHoldingInput":
        return cls(
            user_id=str(row[user_key]),
            holding_id=str(row[holding_key]),
            name=str(row[name_key]),
            qty=float(row[qty_key]),
            bought_at=_parse_datetime(row[bought_at_key]),
            code=str(row[code_key]).strip().lstrip("A") if row.get(code_key) else None,
        )


@dataclass(frozen=True)
class HoldingMarketSnapshot:
    """Market data needed to build a predictor PositionSnapshot."""

    entry_price: float
    current_price: float
    observed_at: datetime
    stop_loss_price: Optional[float] = None
    highest_price_since_entry: Optional[float] = None
    minutes_since_stop_breach: Optional[float] = None
    price_change_5m_pct: Optional[float] = None
    volatility_30m_pct: Optional[float] = None
    volume_spike_ratio: Optional[float] = None
    market_mood_score: Optional[float] = None


class HoldingMarketDataProvider(Protocol):
    """Provider hook for broker/minute-bar data."""

    def __call__(self, holding: CurrentHoldingInput) -> HoldingMarketSnapshot:
        ...


@dataclass
class HoldingRiskResult:
    holding: CurrentHoldingInput
    snapshot: PositionSnapshot
    signal: RiskSignal

    def to_dict(self) -> dict:
        return {
            "holding": {
                "user_id": self.holding.user_id,
                "holding_id": self.holding.holding_id,
                "name": self.holding.name,
                "qty": self.holding.qty,
                "bought_at": self.holding.bought_at.isoformat(),
                "code": self.holding.code,
            },
            "snapshot": self.snapshot.to_feature_dict(),
            "signal": self.signal.to_dict(),
        }


def evaluate_current_holdings(
    holdings: Iterable[CurrentHoldingInput | dict],
    *,
    profile: Optional[UserRiskProfile] = None,
    market_data_provider: Optional[HoldingMarketDataProvider] = None,
    notification_policy: Optional[NotificationPolicy] = None,
) -> list[HoldingRiskResult]:
    """Compute holding snapshots once and evaluate the live-position predictor."""
    normalized = [
        item if isinstance(item, CurrentHoldingInput) else CurrentHoldingInput.from_row(item)
        for item in holdings
    ]
    if not normalized:
        return []

    provider = market_data_provider or DemoHoldingMarketDataProvider()
    predictor = TradeRiskPredictor(
        profile=profile or UserRiskProfile(user_id=normalized[0].user_id),
        notification_policy=notification_policy or NotificationPolicy(),
    )

    results: list[HoldingRiskResult] = []
    for holding in normalized:
        market = provider(holding)
        snapshot = build_position_snapshot(holding, market)
        signal = predictor.monitor_live_position(snapshot)
        results.append(HoldingRiskResult(holding=holding, snapshot=snapshot, signal=signal))
    return results


def build_position_snapshot(
    holding: CurrentHoldingInput,
    market: HoldingMarketSnapshot,
) -> PositionSnapshot:
    """Build the predictor contract from uploaded holding plus market features."""
    return PositionSnapshot(
        user_id=holding.user_id,
        trade_id=holding.holding_id,
        code=holding.code or holding.name,
        entry_price=market.entry_price,
        current_price=market.current_price,
        qty=holding.qty,
        entry_at=holding.bought_at,
        observed_at=market.observed_at,
        stop_loss_price=market.stop_loss_price,
        highest_price_since_entry=market.highest_price_since_entry,
        minutes_since_stop_breach=market.minutes_since_stop_breach,
        price_change_5m_pct=market.price_change_5m_pct,
        volatility_30m_pct=market.volatility_30m_pct,
        volume_spike_ratio=market.volume_spike_ratio,
        market_mood_score=market.market_mood_score,
    )


@dataclass
class DemoHoldingMarketDataProvider:
    """Deterministic provider for local demos/tests until broker data is wired."""

    observed_at: datetime = field(default_factory=lambda: datetime(2026, 6, 26, 10, 30))
    stop_loss_pct: float = 0.05

    def __call__(self, holding: CurrentHoldingInput) -> HoldingMarketSnapshot:
        seed = int(hashlib.sha256(holding.holding_id.encode("utf-8")).hexdigest()[:8], 16)
        entry_price = 8_000 + seed % 9_000
        risky = seed % 3 != 0
        current_price = entry_price * (0.90 if risky else 1.01)
        stop_loss_price = entry_price * (1 - self.stop_loss_pct)
        highest = max(entry_price, current_price) * (1.03 if risky else 1.01)
        minutes_since_stop = 45.0 if current_price <= stop_loss_price else None
        return HoldingMarketSnapshot(
            entry_price=round(entry_price, 2),
            current_price=round(current_price, 2),
            observed_at=self.observed_at,
            stop_loss_price=round(stop_loss_price, 2),
            highest_price_since_entry=round(highest, 2),
            minutes_since_stop_breach=minutes_since_stop,
            price_change_5m_pct=-2.5 if risky else 0.2,
            volatility_30m_pct=3.5 if risky else 1.0,
            market_mood_score=-0.6 if risky else 0.0,
        )


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(text)