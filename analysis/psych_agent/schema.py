"""핵심 데이터 구조.

거래내역(입력) → 포지션 사이클·매도 이벤트(전처리) → 팩트(검출) 흐름의 자료형.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────────
# 입력: 완결 거래내역 1건 (체결 단위)
# ─────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    datetime: pd.Timestamp
    code: str
    name: str
    side: str  # 'BUY' | 'SELL'
    qty: int
    price: int

    @property
    def amount(self) -> int:
        return self.qty * self.price


# ─────────────────────────────────────────────────────────────────
# 전처리 산출물 1: 포지션 사이클 (flat → 진입·증감 → flat 한 라운드트립)
#   처분효과·리벤지의 측정 단위.
# ─────────────────────────────────────────────────────────────────
@dataclass
class PositionCycle:
    code: str
    name: str
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]  # 미청산이면 None
    invested: int          # 사이클 동안 총 매수금액 (포지션 크기 비교용)
    proceeds: int          # 총 매도금액
    realized_pnl: float    # 실현손익 (수수료/세금 반영)
    closed: bool

    @property
    def return_pct(self) -> float:
        return self.realized_pnl / self.invested if self.invested else 0.0

    @property
    def is_win(self) -> bool:
        return self.realized_pnl > 0

    @property
    def holding_minutes(self) -> Optional[float]:
        if not self.closed or self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds() / 60.0


# ─────────────────────────────────────────────────────────────────
# 전처리 산출물 2: 매도(실현) 이벤트 — 처분효과 PGR/PLR 측정용.
#   매도 시점에 '판 종목'은 실현, '들고 있던 다른 종목'은 평가 대상.
# ─────────────────────────────────────────────────────────────────
@dataclass
class SellEvent:
    datetime: pd.Timestamp
    code: str
    name: str
    sold_is_gain: bool                         # 판 종목이 실현이익이면 True
    # 그 순간 보유 중이던 '다른' 종목들: (code, 평균단가)
    open_others: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class Preprocessed:
    cycles: list[PositionCycle]
    sell_events: list[SellEvent]
    trades: list[Trade]

    @property
    def closed_cycles(self) -> list[PositionCycle]:
        return [c for c in self.cycles if c.closed]


# ─────────────────────────────────────────────────────────────────
# 검출 결과: 한 유형의 진단 팩트
# ─────────────────────────────────────────────────────────────────
@dataclass
class TypeFinding:
    type_key: str          # 'revenge' | 'overtrading' | 'disposition'
    type_label: str
    detected: bool
    severity: str          # 'none' | 'weak' | 'moderate' | 'strong'
    metrics: dict          # 수치 팩트 (그대로 보고서/LLM 입력)
    evidence: list[str] = field(default_factory=list)  # 사람이 읽는 근거 라인
    reference: str = ""    # 학술 레퍼런스
