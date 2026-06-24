"""사이클 단위 2-way 규칙 기반 라우터.

하이브리드 구조 채택: 심리 3패턴을 두 도메인에 흡수해 2-way로 라우팅한다.
  - 리벤지   → 진입오류 도메인 (손실 직후 충동 재진입 = 진입 결정 붕괴)
  - 처분효과 → 손절실패 도메인 (손실 오래 보유 = 손절 실패의 심리 원인)
  - 과매매   → 제외 (계좌 전체 습관 문제, 개별 사이클에 귀속하지 않음)

판정:
  손절실패 신호  = (손절선 이탈 ∧ 2거래일 이상 버팀) ∨ 처분효과 dominant
  진입오류 신호  = 리벤지 dominant ∨ 보유 초반 손실 집중
  둘 다 / 둘 다 아님일 때는 더 구체적인 행동 증거(손절선 이탈)를 우선한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

AGENT_ENTRY_ERROR       = "entry_error"
AGENT_STOP_LOSS_FAILURE = "stop_loss_failure"

# 심리 dominant → 도메인 매핑 (하이브리드 분배 기준)
_PSYCH_TO_DOMAIN = {
    "revenge":     AGENT_ENTRY_ERROR,
    "disposition": AGENT_STOP_LOSS_FAILURE,
    # "overtrading" 은 의도적으로 제외 (라우팅에 영향 없음)
}


@dataclass
class CycleRouteDecision:
    trade_id: str
    agent_id: str
    route_status: str       # "routed"
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
    """완결된 손실 사이클 하나를 entry_error / stop_loss_failure 중 하나로 라우팅.

    Args:
        psych_dominant  : focus.py dominant ('revenge'|'overtrading'|'disposition'|None)
        breached        : 손절선 이탈 여부
        delay_days      : 이탈 후 보유 영업일 수
        loss_early_ratio: 보유 초반 20% 구간 손실 비율 (분봉 없으면 None)
    """
    psych_domain = _PSYCH_TO_DOMAIN.get(psych_dominant or "")

    stop_behavior  = breached and delay_days >= 2
    entry_behavior = loss_early_ratio is not None and loss_early_ratio >= 0.7

    stop_signal  = stop_behavior or psych_domain == AGENT_STOP_LOSS_FAILURE
    entry_signal = entry_behavior or psych_domain == AGENT_ENTRY_ERROR

    # 1) 손절실패 신호만
    if stop_signal and not entry_signal:
        return _decide(trade_id, AGENT_STOP_LOSS_FAILURE, 0.72,
                       _stop_reason(stop_behavior, psych_domain, delay_days))

    # 2) 진입오류 신호만
    if entry_signal and not stop_signal:
        return _decide(trade_id, AGENT_ENTRY_ERROR, 0.68,
                       _entry_reason(entry_behavior, psych_domain, loss_early_ratio))

    # 3) 둘 다 → 손절선 이탈(행동 증거)이 있으면 손절실패 우선
    if stop_signal and entry_signal:
        if stop_behavior:
            return _decide(trade_id, AGENT_STOP_LOSS_FAILURE, 0.60,
                           "both_signals_stop_behavior_wins")
        return _decide(trade_id, AGENT_ENTRY_ERROR, 0.55, "both_signals_entry_wins")

    # 4) 둘 다 없음 → 손절선 이탈 여부로 기본 분기
    if breached:
        return _decide(trade_id, AGENT_STOP_LOSS_FAILURE, 0.45, "default_breached")
    return _decide(trade_id, AGENT_ENTRY_ERROR, 0.45, "default_entry_error")


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _decide(trade_id, agent_id, confidence, reason) -> CycleRouteDecision:
    return CycleRouteDecision(
        trade_id=trade_id, agent_id=agent_id,
        route_status="routed", confidence=confidence, reason=reason,
    )


def _stop_reason(stop_behavior, psych_domain, delay_days) -> str:
    if stop_behavior and psych_domain == AGENT_STOP_LOSS_FAILURE:
        return f"stop_breached_delay_{delay_days}d+disposition"
    if stop_behavior:
        return f"stop_breached_delay_{delay_days}d"
    return "disposition_dominant"


def _entry_reason(entry_behavior, psych_domain, ratio) -> str:
    if entry_behavior and psych_domain == AGENT_ENTRY_ERROR:
        return f"early_loss_{ratio:.2f}+revenge"
    if entry_behavior:
        return f"loss_concentrated_early_{ratio:.2f}"
    return "revenge_dominant"
