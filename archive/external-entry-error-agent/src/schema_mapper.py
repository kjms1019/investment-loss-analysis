"""Standard schema definitions for the mock CSV stage.

The current tiny_mock.csv is a minimal combined mock file that contains both
trade fields and market OHLCV fields. In the real project, trade CSV files and
OHLCV CSV files may be separated, so this module should stay easy to extend.
"""

from typing import Dict, List


TRADE_REQUIRED_COLUMNS = [
    "trade_id",
    "symbol",
    "buy_time",
    "buy_price",
    "sell_time",
    "sell_price",
    "quantity",
]

MARKET_REQUIRED_COLUMNS = [
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

TRADE_NUMERIC_COLUMNS = [
    "buy_price",
    "sell_price",
    "quantity",
]

MARKET_NUMERIC_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]

DATETIME_COLUMNS = [
    "buy_time",
    "sell_time",
    "datetime",
]

OPTIONAL_NUMERIC_COLUMNS = [
    "realized_pnl",
    "realized_pnl_pct",
    "fees",
]

# TODO: Extend this mapping when real broker/export CSV column names are known.
COLUMN_MAP = {
    "trade": {
        "trade_id": "trade_id",
        "symbol": "symbol",
        "buy_time": "buy_time",
        "buy_price": "buy_price",
        "sell_time": "sell_time",
        "sell_price": "sell_price",
        "quantity": "quantity",
    },
    "market": {
        "datetime": "datetime",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    },
}


def validate_required_columns(
    row: Dict[str, str], required_columns: List[str]
) -> List[str]:
    """Return required column names that are missing from a row dictionary."""
    return [column for column in required_columns if column not in row]


def get_standard_column_summary() -> Dict[str, List[str]]:
    """Return the current standard trade and market column definitions."""
    return {
        "trade_required_columns": TRADE_REQUIRED_COLUMNS,
        "market_required_columns": MARKET_REQUIRED_COLUMNS,
        "trade_numeric_columns": TRADE_NUMERIC_COLUMNS,
        "market_numeric_columns": MARKET_NUMERIC_COLUMNS,
        "datetime_columns": DATETIME_COLUMNS,
        "optional_numeric_columns": OPTIONAL_NUMERIC_COLUMNS,
    }
