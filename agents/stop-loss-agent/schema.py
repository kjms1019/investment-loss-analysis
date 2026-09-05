from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional


@dataclass
class Transaction:
    trade_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    qty: int
    price: float
    executed_at: date
    fee: float = 0.0


@dataclass
class OHLCV:
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class BuyRecord:
    ts: date
    price: float
    qty: int
    in_loss: bool   # True if bought while position was already at a loss


@dataclass
class SellRecord:
    ts: date
    price: float
    qty: int


@dataclass
class Cycle:
    ticker: str
    entry_ts: date
    exit_ts: Optional[date] = None
    buys: list = field(default_factory=list)        # list[BuyRecord]
    sells: list = field(default_factory=list)       # list[SellRecord]
    cost_checkpoints: list = field(default_factory=list)  # list[(date, avg_cost)]

    # Derived in build_cycles
    avg_buy_price: float = 0.0
    realized_return: float = 0.0    # percentage, negative = loss
    avg_down_count: int = 0         # number of add-on buys while in loss
    avg_down_qty: float = 0.0       # add-on qty / first buy qty

    # Derived in attach_path_features
    MAE_pct: float = 0.0
    breached: bool = False
    breach_date: Optional[date] = None
    delay_days: int = 0
    stop_pct: float = -5.0
    stop_method: str = "fixed"      # "user" | "atr" | "fixed"
