"""공통 입력 파서.

증권사 CSV → RawTrade 리스트 → TradeCycle 리스트 변환.

사용 예:
    trades = parse_csv("my_trades.csv", broker="kiwoom")
    cycles = build_cycles(trades)
"""

from __future__ import annotations

import csv
import uuid
from datetime import datetime
from typing import Literal, Optional

from common.schema import RawTrade, TradeCycle

BrokerName = Literal["kiwoom", "generic"]


def parse_csv(filepath: str, broker: BrokerName = "generic") -> list[RawTrade]:
    """증권사 CSV 파일을 읽어 RawTrade 리스트로 반환."""
    column_map, side_map, dt_format = _load_broker_config(broker)

    trades: list[RawTrade] = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapped = {
                common_field: row[broker_col]
                for broker_col, common_field in column_map.items()
                if broker_col in row
            }
            try:
                trades.append(RawTrade(
                    datetime=datetime.strptime(mapped["datetime"], dt_format),
                    code=mapped["code"].strip().lstrip("A"),  # 키움은 앞에 A 붙음
                    name=mapped.get("name", ""),
                    side=side_map.get(mapped["side"], mapped["side"]),
                    qty=int(str(mapped["qty"]).replace(",", "")),
                    price=float(str(mapped["price"]).replace(",", "")),
                    fee=float(str(mapped.get("fee", "0")).replace(",", "") or "0"),
                ))
            except (KeyError, ValueError):
                continue  # 파싱 불가 행 스킵

    return sorted(trades, key=lambda t: t.datetime)


def build_cycles(trades: list[RawTrade]) -> list[TradeCycle]:
    """RawTrade 리스트에서 매수→매도 라운드트립 사이클을 묶어 반환.

    종목별로 이동평균법으로 평균단가를 계산하고,
    보유수량이 0이 되는 시점을 사이클 완결로 본다.
    """
    from collections import defaultdict

    # 종목별 미체결 매수 내역 추적
    # {code: {"qty": int, "cost": float, "entry_dt": datetime, "fee": float}}
    positions: dict[str, dict] = defaultdict(lambda: {
        "qty": 0, "cost": 0.0, "entry_dt": None, "fee": 0.0
    })
    cycles: list[TradeCycle] = []

    for t in trades:
        pos = positions[t.code]

        if t.side == "BUY":
            if pos["qty"] == 0:
                pos["entry_dt"] = t.datetime
            pos["cost"] += t.amount
            pos["qty"] += t.qty
            pos["fee"] += t.fee

        elif t.side == "SELL" and pos["qty"] > 0:
            sell_qty = min(t.qty, pos["qty"])
            avg_buy_price = pos["cost"] / pos["qty"]
            realized_pnl = (t.price - avg_buy_price) * sell_qty - t.fee - pos["fee"] * (sell_qty / pos["qty"])

            cycles.append(TradeCycle(
                trade_id=str(uuid.uuid4())[:8],
                code=t.code,
                name=t.name,
                entry_dt=pos["entry_dt"],
                exit_dt=t.datetime,
                entry_price=round(avg_buy_price, 2),
                exit_price=t.price,
                qty=sell_qty,
                realized_pnl=round(realized_pnl, 2),
                realized_pnl_pct=round(realized_pnl / (avg_buy_price * sell_qty) * 100, 4),
                fee=round(t.fee + pos["fee"] * (sell_qty / pos["qty"]), 2),
                closed=True,
            ))

            pos["qty"] -= sell_qty
            pos["cost"] -= avg_buy_price * sell_qty
            pos["fee"] -= pos["fee"] * (sell_qty / (pos["qty"] + sell_qty))
            if pos["qty"] == 0:
                positions[t.code] = {"qty": 0, "cost": 0.0, "entry_dt": None, "fee": 0.0}

    # 미청산 포지션도 미완결 사이클로 추가
    for code, pos in positions.items():
        if pos["qty"] > 0:
            avg_buy_price = pos["cost"] / pos["qty"]
            cycles.append(TradeCycle(
                trade_id=str(uuid.uuid4())[:8],
                code=code,
                name="",
                entry_dt=pos["entry_dt"],
                exit_dt=None,
                entry_price=round(avg_buy_price, 2),
                exit_price=None,
                qty=pos["qty"],
                realized_pnl=0.0,
                realized_pnl_pct=0.0,
                fee=pos["fee"],
                closed=False,
            ))

    return cycles


def filter_loss_cycles(cycles: list[TradeCycle]) -> list[TradeCycle]:
    """손실 완결 사이클만 필터링."""
    return [c for c in cycles if c.closed and c.realized_pnl < 0]


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _load_broker_config(broker: BrokerName):
    if broker == "kiwoom":
        from common.broker.kiwoom import COLUMN_MAP, SIDE_MAP, DATETIME_FORMAT
    else:
        from common.broker.generic import COLUMN_MAP, SIDE_MAP, DATETIME_FORMAT
    return COLUMN_MAP, SIDE_MAP, DATETIME_FORMAT
