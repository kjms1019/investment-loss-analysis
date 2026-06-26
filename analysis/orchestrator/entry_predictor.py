"""예정 매수(투자계획) → EntryContext → 진입오류 실시간 예측.

binsu의 holding_predictor가 '현재보유 → 손절실패 경고'를 다뤘다면, 이 모듈은
'예정 매수 → 진입오류 경고'(예측단 매수 이벤트)를 다룬다.

흐름: 투자계획(업로드) + 사용자 종결거래(행동 이력) → EntryContext 생성 →
      predictor.predict_entry_risk → 진입오류 위험/알림.
EntryContext의 행동피처(최근 승률·직전 손실 후 경과 등)는 '예정 시점에 알 수 있는'
사용자 이력으로만 계산한다(look-ahead 없음).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from analysis.predictor import (
    EntryContext,
    NotificationPolicy,
    RiskSignal,
    TradeRiskPredictor,
    UserRiskProfile,
)


@dataclass(frozen=True)
class PlannedEntryInput:
    """투자계획 업로드 한 건."""

    user_id: str
    plan_id: str
    name: str
    qty: float
    planned_at: datetime
    code: Optional[str] = None

    @classmethod
    def from_row(
        cls, row: dict, *,
        user_key="사용자명", plan_key="계획ID", name_key="종목명",
        qty_key="예정수량", planned_key="예정일시", code_key="종목코드",
    ) -> "PlannedEntryInput":
        return cls(
            user_id=str(row[user_key]),
            plan_id=str(row[plan_key]),
            name=str(row[name_key]),
            qty=float(row[qty_key]),
            planned_at=_to_dt(row[planned_key]),
            code=str(row[code_key]).strip().lstrip("A") if row.get(code_key) else None,
        )


@dataclass(frozen=True)
class ClosedTradeFact:
    """행동 이력 1건 (EntryContext 계산용). 수익률은 호출자가 채운다(min1/브로커)."""

    entry_at: datetime
    exit_at: datetime
    return_pct: float


@dataclass
class PlannedEntryRiskResult:
    planned: PlannedEntryInput
    context: EntryContext
    signal: RiskSignal

    def to_dict(self) -> dict:
        return {
            "planned": {
                "user_id": self.planned.user_id, "plan_id": self.planned.plan_id,
                "name": self.planned.name, "qty": self.planned.qty,
                "planned_at": self.planned.planned_at.isoformat(), "code": self.planned.code,
            },
            "context": self.context.to_feature_dict(),
            "signal": self.signal.to_dict(),
        }


def closed_trade_facts_from_cycles(cycles: Iterable) -> List[ClosedTradeFact]:
    """common.schema.TradeCycle 들 → ClosedTradeFact (entry_dt/exit_dt/realized_pnl_pct)."""
    facts = []
    for c in cycles:
        if getattr(c, "entry_dt", None) and getattr(c, "exit_dt", None):
            facts.append(ClosedTradeFact(
                entry_at=c.entry_dt, exit_at=c.exit_dt,
                return_pct=float(getattr(c, "realized_pnl_pct", 0.0) or 0.0)))
    return facts


def build_entry_context(planned: PlannedEntryInput, history: List[ClosedTradeFact]) -> EntryContext:
    """예정 시점 이전 이력으로 행동피처를 계산해 EntryContext 생성."""
    prior = [h for h in history if h.exit_at <= planned.planned_at]
    last10 = sorted(prior, key=lambda h: h.exit_at)[-10:]
    losses = [h for h in prior if h.return_pct < 0]
    last_loss = max(losses, key=lambda h: h.exit_at) if losses else None
    hold_min = [(h.exit_at - h.entry_at).total_seconds() / 60 for h in last10]
    same_day = sum(1 for h in history if h.entry_at.date() == planned.planned_at.date())

    return EntryContext(
        user_id=planned.user_id,
        trade_id=planned.plan_id,
        code=planned.code or planned.name,
        entered_at=planned.planned_at,
        recent_trade_count=len(last10),
        recent_win_rate=(sum(1 for h in last10 if h.return_pct > 0) / len(last10)) if last10 else None,
        minutes_since_last_loss=((planned.planned_at - last_loss.exit_at).total_seconds() / 60)
        if last_loss else None,
        recent_avg_holding_minutes=(sum(hold_min) / len(hold_min)) if hold_min else None,
        last_loss_pct=last_loss.return_pct if last_loss else None,
        same_day_trade_count=same_day,
    )


def evaluate_planned_entries(
    plans: Iterable[PlannedEntryInput | dict],
    history: List[ClosedTradeFact],
    *,
    profile: Optional[UserRiskProfile] = None,
    notification_policy: Optional[NotificationPolicy] = None,
) -> List[PlannedEntryRiskResult]:
    """예정 매수들에 대해 진입오류 예측기를 돌린다."""
    normalized = [p if isinstance(p, PlannedEntryInput) else PlannedEntryInput.from_row(p)
                  for p in plans]
    if not normalized:
        return []
    predictor = TradeRiskPredictor(
        profile=profile or UserRiskProfile(user_id=normalized[0].user_id),
        notification_policy=notification_policy or NotificationPolicy(),
    )
    results = []
    for planned in normalized:
        ctx = build_entry_context(planned, history)
        sig = predictor.predict_entry_risk(ctx)
        results.append(PlannedEntryRiskResult(planned=planned, context=ctx, signal=sig))
    return results


def _to_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    import pandas as pd
    return pd.to_datetime(value).to_pydatetime()
