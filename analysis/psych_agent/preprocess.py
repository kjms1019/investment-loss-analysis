"""거래내역 → 포지션 사이클 + 매도 이벤트 전처리.

계좌 전체를 시간순으로 1회 리플레이하면서 두 산출물을 동시에 만든다.
  · 포지션 사이클: 종목별로 보유수량이 0→양수→0 으로 돌아오는 라운드트립.
  · 매도 이벤트:  매도 체결마다, 판 종목의 실현손익 부호 + 그 순간 보유 중인
                 '다른' 종목들의 평균단가 스냅샷(처분효과 평가손익 판정용).

평균단가 회계(이동평균법)를 쓴다 — 한국 증권사 거래내역 손익계산 관행과 일치.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from .config import Config
from .schema import PositionCycle, Preprocessed, SellEvent, Trade


@dataclass
class _OpenPos:
    """종목별 현재 열린 포지션 상태 (이동평균법)."""

    code: str
    name: str
    qty: int = 0
    avg_cost: float = 0.0
    # 진행 중 사이클 누적
    entry_time: pd.Timestamp | None = None
    invested: int = 0       # 사이클 총 매수금액
    proceeds: int = 0       # 사이클 총 매도금액
    realized_pnl: float = 0.0


def trades_from_df(df: pd.DataFrame) -> list[Trade]:
    """DataFrame(datetime,code,name,side,qty,price) → Trade 리스트 (시간순)."""
    df = df.sort_values("datetime").reset_index(drop=True)
    return [
        Trade(
            datetime=pd.Timestamp(r.datetime),
            code=str(r.code),
            name=str(r.name),
            side=str(r.side).upper(),
            qty=int(r.qty),
            price=int(r.price),
        )
        for r in df.itertuples(index=False)
    ]


def preprocess(trades: list[Trade], config: Config | None = None) -> Preprocessed:
    config = config or Config()
    trades = sorted(trades, key=lambda t: t.datetime)

    open_by_code: dict[str, _OpenPos] = {}
    cycles: list[PositionCycle] = []
    sell_events: list[SellEvent] = []

    def open_others(exclude: str) -> list[tuple[str, float]]:
        return [
            (p.code, p.avg_cost)
            for c, p in open_by_code.items()
            if c != exclude and p.qty > 0
        ]

    for t in trades:
        pos = open_by_code.get(t.code)
        if pos is None:
            pos = _OpenPos(code=t.code, name=t.name)
            open_by_code[t.code] = pos

        if t.side == "BUY":
            if pos.qty == 0:  # 새 사이클 시작
                pos.entry_time = t.datetime
                pos.invested = 0
                pos.proceeds = 0
                pos.realized_pnl = 0.0
            # 이동평균 단가 갱신
            new_qty = pos.qty + t.qty
            pos.avg_cost = (pos.avg_cost * pos.qty + t.amount) / new_qty
            pos.qty = new_qty
            pos.invested += t.amount

        elif t.side == "SELL":
            if pos.qty <= 0:
                # 보유 없는 매도(공매도/데이터 오류)는 무시
                continue
            sell_qty = min(t.qty, pos.qty)
            cost_basis = pos.avg_cost * sell_qty
            gross = t.price * sell_qty
            fee = gross * config.fee_rate
            realized = gross - cost_basis - fee

            pos.realized_pnl += realized
            pos.proceeds += gross
            pos.qty -= sell_qty

            sell_events.append(
                SellEvent(
                    datetime=t.datetime,
                    code=t.code,
                    name=t.name,
                    sold_is_gain=realized > 0,
                    open_others=open_others(exclude=t.code),
                )
            )

            if pos.qty == 0:  # 사이클 종료
                cycles.append(
                    PositionCycle(
                        code=pos.code,
                        name=pos.name,
                        entry_time=pos.entry_time,
                        exit_time=t.datetime,
                        invested=pos.invested,
                        proceeds=pos.proceeds,
                        realized_pnl=pos.realized_pnl,
                        closed=True,
                    )
                )
                pos.avg_cost = 0.0  # 다음 사이클 위해 초기화

    # 기간 말 미청산 포지션 → 열린 사이클로 기록 (보유 중 = 평가 대상)
    for pos in open_by_code.values():
        if pos.qty > 0 and pos.entry_time is not None:
            cycles.append(
                PositionCycle(
                    code=pos.code,
                    name=pos.name,
                    entry_time=pos.entry_time,
                    exit_time=None,
                    invested=pos.invested,
                    proceeds=pos.proceeds,
                    realized_pnl=pos.realized_pnl,
                    closed=False,
                )
            )

    cycles.sort(key=lambda c: c.entry_time)
    sell_events.sort(key=lambda e: e.datetime)
    return Preprocessed(cycles=cycles, sell_events=sell_events, trades=trades)
