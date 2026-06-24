"""사이클 단위 규칙 기반 라우터.

완결된 손실 사이클을 시간축 기준으로 3개 에이전트 중 하나로 라우팅한다.

우선순위:
  1. psych      — 계좌 전체에서 심리 패턴(리벤지/과매매/처분효과)이 dominant
  2. stop_fail  — 손절선 이탈 후 2거래일 이상 버팀
  3. entry_error — 나머지 (진입 시점 문제가 주원인)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

AGENT_ENTRY_ERROR       = "entry_error"
AGENT_STOP_LOSS_FAILURE = "stop_loss_failure"
AGENT_PSYCH             = "psych"


@dataclass
class CycleRouteDecision:
    trade_id: str
    agent_id: str
    route_status: str       # "routed" | "skipped"
    confidence: float       # 0~1
    reason: str

    def to_dict(self) -> dict:
        return {
            "trade_id":     self.trade_id,
            "agent_id":     self.agent_id,
            "route_status": self.route_status,
            "confidence":   self.confidence,
            "reason":       self.reason,
        }


def route_cycle(
    trade_id: str,
    *,
    psych_dominant: Optional[str],
    breached: bool,
    delay_days: int,
    loss_early_ratio: Optional[float],
) -> CycleRouteDecision:
    """완결된 손실 사이클 하나를 라우팅.

    Args:
        trade_id        : 사이클 식별자
        psych_dominant  : focus.py dominant 값 ('revenge'|'overtrading'|'disposition'|None)
        breached        : 손절선 이탈 여부
        delay_days      : 이탈 후 보유 영업일 수
        loss_early_ratio: 보유 초반 20% 구간에서 발생한 손실 비율 (분봉 없으면 None)
    """

    # 1순위: 심리 패턴
    if psych_dominant in ("revenge", "overtrading", "disposition"):
        return CycleRouteDecision(
            trade_id=trade_id,
            agent_id=AGENT_PSYCH,
            route_status="routed",
            confidence=0.75,
            reason=f"psych_dominant:{psych_dominant}",
        )

    # 2순위: 손절선 이탈 후 2거래일 이상 버팀
    if breached and delay_days >= 2:
        return CycleRouteDecision(
            trade_id=trade_id,
            agent_id=AGENT_STOP_LOSS_FAILURE,
            route_status="routed",
            confidence=0.70,
            reason=f"stop_breached_delay_{delay_days}days",
        )

    # 3순위: 진입 오류 (손실이 초반에 집중됐거나 기본값)
    if loss_early_ratio is not None and loss_early_ratio >= 0.7:
        confidence = 0.65
        reason = f"loss_concentrated_early:{loss_early_ratio:.2f}"
    else:
        confidence = 0.50
        reason = "default_entry_error"

    return CycleRouteDecision(
        trade_id=trade_id,
        agent_id=AGENT_ENTRY_ERROR,
        route_status="routed",
        confidence=confidence,
        reason=reason,
    )
