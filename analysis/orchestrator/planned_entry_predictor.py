"""Planned-entry feature builder and predictor orchestration.

The uploaded investment plan stays intentionally small:
user, plan id, symbol/name, planned time, and planned quantity. Runtime features
for the predictor are computed here, immediately before calling the entry-risk
predictor, from already-known trade history plus optional 1-minute market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Protocol

import pandas as pd

from analysis.common.schema import TradeCycle
from analysis.label_validation.label_pipeline import entry_features_window
from analysis.predictor import (
    EntryContext,
    NotificationPolicy,
    RiskSignal,
    TradeRiskPredictor,
    UserRiskProfile,
)
from analysis.predictor.alert_message import build_alert_message


_ROOT = Path(__file__).resolve().parents[2]
_MIN1_DIR = _ROOT / "analysis" / "data" / "min1"
_CODES_CSV = _ROOT / "analysis" / "data" / ".cache" / "kospi_codes.csv"


@dataclass(frozen=True)
class PlannedEntryInput:
    """Minimal planned-entry input accepted from the user upload."""

    user_id: str
    plan_id: str
    name: str
    planned_at: datetime
    qty: float
    code: Optional[str] = None

    @classmethod
    def from_row(
        cls,
        row: dict,
        *,
        user_key: str = "\uc0ac\uc6a9\uc790\uba85",
        plan_key: str = "\uacc4\ud68dID",
        name_key: str = "\uc885\ubaa9\uba85",
        planned_at_key: str = "\uc608\uc815\uc77c\uc2dc",
        qty_key: str = "\uc608\uc815\uc218\ub7c9",
        code_key: str = "\uc885\ubaa9\ucf54\ub4dc",
    ) -> "PlannedEntryInput":
        return cls(
            user_id=str(row[user_key]),
            plan_id=str(row[plan_key]),
            name=str(row[name_key]),
            planned_at=_parse_datetime(row[planned_at_key]),
            qty=float(row[qty_key]),
            code=str(row[code_key]).strip().lstrip("A") if row.get(code_key) else None,
        )


@dataclass(frozen=True)
class ClosedTradeFact:
    """Closed-trade history fact used to build planned-entry behavior features."""

    entry_at: datetime
    exit_at: datetime
    return_pct: float
    user_id: Optional[str] = None


class PlannedEntryMarketFeatureProvider(Protocol):
    """Provider hook for broker/minute-bar data at planned-entry time."""

    def __call__(self, planned: PlannedEntryInput) -> dict[str, float]:
        ...


@dataclass
class PlannedEntryRiskResult:
    planned: PlannedEntryInput
    context: EntryContext
    signal: RiskSignal
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "planned": {
                "user_id": self.planned.user_id,
                "plan_id": self.planned.plan_id,
                "name": self.planned.name,
                "planned_at": self.planned.planned_at.isoformat(),
                "qty": self.planned.qty,
                "code": self.planned.code,
            },
            "context": self.context.to_feature_dict(),
            "signal": self.signal.to_dict(),
            "message": self.message,
        }


def evaluate_planned_entries(
    planned_entries: Iterable[PlannedEntryInput | dict],
    history: Optional[Iterable[ClosedTradeFact | TradeCycle]] = None,
    *,
    historical_cycles: Optional[Iterable[ClosedTradeFact | TradeCycle]] = None,
    profile: Optional[UserRiskProfile] = None,
    market_feature_provider: Optional[PlannedEntryMarketFeatureProvider] = None,
    notification_policy: Optional[NotificationPolicy] = None,
) -> list[PlannedEntryRiskResult]:
    """Compute entry contexts once and evaluate the planned-entry predictor."""
    normalized = [
        item if isinstance(item, PlannedEntryInput) else PlannedEntryInput.from_row(item)
        for item in planned_entries
    ]
    if not normalized:
        return []

    cycles = list(historical_cycles if historical_cycles is not None else (history or []))
    provider = market_feature_provider or Min1PlannedEntryFeatureProvider()
    predictor = TradeRiskPredictor(
        profile=profile or UserRiskProfile(user_id=normalized[0].user_id),
        notification_policy=notification_policy or NotificationPolicy(),
    )

    results: list[PlannedEntryRiskResult] = []
    for planned in normalized:
        context = build_entry_context(planned, cycles, market_feature_provider=provider)
        signal = predictor.predict_entry_risk(context)
        message = build_alert_message(signal) if signal.should_alert else ""
        results.append(
            PlannedEntryRiskResult(
                planned=planned,
                context=context,
                signal=signal,
                message=message,
            )
        )
    return results


def build_entry_context(
    planned: PlannedEntryInput,
    historical_cycles: Iterable[ClosedTradeFact | TradeCycle] = (),
    *,
    market_feature_provider: Optional[PlannedEntryMarketFeatureProvider] = None,
    recent_limit: int = 20,
) -> EntryContext:
    """Build the predictor contract from a plan row plus runtime features."""
    cycles = _closed_before(historical_cycles, planned.user_id, planned.planned_at)
    recent = cycles[-recent_limit:]
    losses = [cycle for cycle in cycles if _return_pct(cycle) < 0 and _exit_dt(cycle) is not None]
    last_loss = losses[-1] if losses else None
    same_day_count = sum(
        1
        for cycle in cycles
        if _entry_dt(cycle) is not None and _entry_dt(cycle).date() == planned.planned_at.date()
    )

    if recent:
        wins = sum(1 for cycle in recent if _return_pct(cycle) > 0)
        recent_win_rate = wins / len(recent)
        holding_minutes = [
            (_exit_dt(cycle) - _entry_dt(cycle)).total_seconds() / 60.0
            for cycle in recent
            if _exit_dt(cycle) is not None and _entry_dt(cycle) is not None
        ]
        avg_holding = sum(holding_minutes) / len(holding_minutes) if holding_minutes else None
    else:
        recent_win_rate = None
        avg_holding = None

    if last_loss and _exit_dt(last_loss) is not None:
        minutes_since_last_loss = max(
            (planned.planned_at - _exit_dt(last_loss)).total_seconds() / 60.0,
            0.0,
        )
        last_loss_pct = float(_return_pct(last_loss))
    else:
        minutes_since_last_loss = None
        last_loss_pct = None

    provider = market_feature_provider
    market_features = provider(planned) if provider is not None else {}

    return EntryContext(
        user_id=planned.user_id,
        trade_id=planned.plan_id,
        code=planned.code or planned.name,
        entered_at=planned.planned_at,
        recent_trade_count=len(recent),
        recent_win_rate=recent_win_rate,
        minutes_since_last_loss=minutes_since_last_loss,
        recent_avg_holding_minutes=avg_holding,
        last_loss_pct=last_loss_pct,
        market_mood_score=market_features.pop("market_mood_score", None),
        same_day_trade_count=same_day_count,
        features=market_features,
    )


@dataclass
class Min1PlannedEntryFeatureProvider:
    """1-minute market feature provider for planned-entry prediction."""

    min1_dir: Path = _MIN1_DIR
    name_to_code: Optional[dict[str, str]] = None
    pre_minutes: int = 200

    def __post_init__(self) -> None:
        if self.name_to_code is None:
            self.name_to_code = _load_name_to_code()
        self._cache: dict[str, Optional[pd.DataFrame]] = {}

    def __call__(self, planned: PlannedEntryInput) -> dict[str, float]:
        code = planned.code or (self.name_to_code or {}).get(planned.name)
        df = self._load(code)
        if df is None or df.empty:
            return {}

        before = df[df["datetime"] <= pd.to_datetime(planned.planned_at)].tail(self.pre_minutes)
        if before.empty:
            return {}

        features = entry_features_window(
            before["open"].to_numpy(float),
            before["high"].to_numpy(float),
            before["low"].to_numpy(float),
            before["close"].to_numpy(float),
            before["volume"].to_numpy(float),
        )
        return {key: value for key, value in features.items() if value is not None}

    def _load(self, code: Optional[str]) -> Optional[pd.DataFrame]:
        if not code:
            return None
        norm = str(code).strip().zfill(6)
        if norm not in self._cache:
            fp = self.min1_dir / f"{norm}.parquet"
            if not fp.exists():
                self._cache[norm] = None
            else:
                self._cache[norm] = (
                    pd.read_parquet(
                        fp,
                        columns=["datetime", "open", "high", "low", "close", "volume"],
                    )
                    .assign(datetime=lambda df: pd.to_datetime(df["datetime"]))
                    .sort_values("datetime")
                )
        return self._cache[norm]


def closed_trade_facts_from_cycles(cycles: Iterable[TradeCycle]) -> list[ClosedTradeFact]:
    """Convert common.schema.TradeCycle rows into planned-entry history facts."""
    facts: list[ClosedTradeFact] = []
    for cycle in cycles:
        if cycle.entry_dt is None or cycle.exit_dt is None:
            continue
        facts.append(
            ClosedTradeFact(
                entry_at=cycle.entry_dt,
                exit_at=cycle.exit_dt,
                return_pct=float(cycle.realized_pnl_pct or 0.0),
                user_id=getattr(cycle, "user_id", None),
            )
        )
    return facts


def _closed_before(
    cycles: Iterable[ClosedTradeFact | TradeCycle],
    user_id: str,
    planned_at: datetime,
) -> list[ClosedTradeFact | TradeCycle]:
    # TradeCycle does not currently carry user_id. When callers pass only one
    # user's history, this preserves the existing schema while still keeping the
    # function ready for a future user_id attribute.
    filtered = [
        cycle
        for cycle in cycles
        if getattr(cycle, "user_id", user_id) in (None, user_id)
        and _is_closed(cycle)
        and _exit_dt(cycle) is not None
        and _exit_dt(cycle) <= planned_at
    ]
    return sorted(filtered, key=lambda cycle: _exit_dt(cycle) or datetime.min)


def _entry_dt(cycle: ClosedTradeFact | TradeCycle) -> Optional[datetime]:
    return getattr(cycle, "entry_at", None) or getattr(cycle, "entry_dt", None)


def _exit_dt(cycle: ClosedTradeFact | TradeCycle) -> Optional[datetime]:
    return getattr(cycle, "exit_at", None) or getattr(cycle, "exit_dt", None)


def _return_pct(cycle: ClosedTradeFact | TradeCycle) -> float:
    if hasattr(cycle, "return_pct"):
        return float(getattr(cycle, "return_pct") or 0.0)
    return float(getattr(cycle, "realized_pnl_pct", 0.0) or 0.0)


def _is_closed(cycle: ClosedTradeFact | TradeCycle) -> bool:
    if isinstance(cycle, ClosedTradeFact):
        return True
    return bool(getattr(cycle, "closed", True))


def _load_name_to_code() -> dict[str, str]:
    if not _CODES_CSV.exists():
        return {}
    df = pd.read_csv(_CODES_CSV, dtype=str)
    if "name" not in df.columns or "code" not in df.columns:
        return {}
    return dict(zip(df["name"], df["code"]))


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
