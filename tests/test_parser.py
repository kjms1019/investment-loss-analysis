"""common.parser — 사이클 묶기/손실 필터 단위 테스트."""

from datetime import datetime

from common.parser import build_cycles, filter_loss_cycles
from common.schema import RawTrade


def _t(dt, code, side, qty, price, fee=0.0):
    return RawTrade(datetime=datetime.fromisoformat(dt), code=code,
                    name=code, side=side, qty=qty, price=price, fee=fee)


def test_single_loss_cycle():
    trades = [
        _t("2026-01-02 09:30:00", "005930", "BUY", 100, 1000),
        _t("2026-01-05 09:30:00", "005930", "SELL", 100, 900),
    ]
    cycles = build_cycles(trades)
    assert len(cycles) == 1
    c = cycles[0]
    assert c.closed is True
    assert c.entry_price == 1000
    assert c.realized_pnl == -10000          # (900-1000)*100
    assert round(c.realized_pnl_pct, 2) == -10.0


def test_profit_cycle_filtered_out():
    trades = [
        _t("2026-01-02 09:30:00", "000660", "BUY", 10, 5000),
        _t("2026-01-03 09:30:00", "000660", "SELL", 10, 6000),
    ]
    cycles = build_cycles(trades)
    assert len(cycles) == 1
    assert cycles[0].realized_pnl == 10000
    assert filter_loss_cycles(cycles) == []   # 수익 사이클은 손실 필터에서 제외


def test_averaging_down_uses_avg_cost():
    # 1000에 100주, 800에 100주 → 평단 900. 850에 200주 매도 → 손실.
    trades = [
        _t("2026-01-02 09:30:00", "005930", "BUY", 100, 1000),
        _t("2026-01-03 09:30:00", "005930", "BUY", 100, 800),
        _t("2026-01-06 09:30:00", "005930", "SELL", 200, 850),
    ]
    cycles = build_cycles(trades)
    assert len(cycles) == 1
    assert cycles[0].entry_price == 900       # 이동평균 평단
    assert cycles[0].realized_pnl == -10000   # (850-900)*200


def test_open_position_is_unclosed():
    trades = [_t("2026-01-02 09:30:00", "005930", "BUY", 100, 1000)]
    cycles = build_cycles(trades)
    assert len(cycles) == 1
    assert cycles[0].closed is False
    assert filter_loss_cycles(cycles) == []   # 미청산은 손실 필터 제외
