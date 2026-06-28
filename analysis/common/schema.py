"""공통 입출력 스키마.

모든 에이전트가 공유하는 데이터 구조.
- RawTrade   : 체결 단위 원시 데이터 (영현, 준모 입력)
- TradeCycle : 매수→매도 라운드트립 사이클 (수빈 입력)
- AgentResult: 에이전트 공통 출력
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


# ──────────────────────────────────────────────
# 입력 스키마
# ──────────────────────────────────────────────

@dataclass
class RawTrade:
    """체결 단위 원시 거래 데이터."""
    datetime: datetime
    code: str
    name: str
    side: Literal["BUY", "SELL"]
    qty: int
    price: float
    fee: float = 0.0

    @property
    def amount(self) -> float:
        return self.qty * self.price


@dataclass
class TradeCycle:
    """매수→매도 완결 라운드트립 사이클."""
    trade_id: str
    code: str
    name: str
    entry_dt: datetime
    exit_dt: Optional[datetime]       # 미청산이면 None
    entry_price: float
    exit_price: Optional[float]
    qty: int
    realized_pnl: float
    realized_pnl_pct: float
    fee: float = 0.0
    closed: bool = True


# ──────────────────────────────────────────────
# 출력 스키마
# ──────────────────────────────────────────────

@dataclass
class AgentResult:
    """에이전트 공통 출력. 총괄 오케스트레이터가 이 형식으로 수신."""
    agent_type: Literal["entry_error", "stop_fail", "psych"]
    trade_id: str
    score: float                      # 0~1 (수빈 /100, 준모 severity→수치 변환)
    label: str                        # 주요 라벨
    summary: str                      # 자연어 요약
    details: dict[str, Any] = field(default_factory=dict)   # 에이전트별 원본 결과
    analyzed_at: datetime = field(default_factory=datetime.now)


# ──────────────────────────────────────────────
# severity 변환 헬퍼
# ──────────────────────────────────────────────

SEVERITY_TO_SCORE: dict[str, float] = {
    "none":     0.0,
    "weak":     0.25,
    "moderate": 0.6,
    "strong":   1.0,
}


def severity_to_score(severity: str) -> float:
    return SEVERITY_TO_SCORE.get(severity.lower(), 0.0)
