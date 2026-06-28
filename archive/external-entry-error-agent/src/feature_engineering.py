"""Feature engineering helpers for entry-context analysis.

Entry-decision features must be computed using only information available at
or before entry_timestamp. Post-trade values such as exit_price and
trade_return_pct can be included for review context, but must not be used as
direct evidence of entry error. Future rows after entry_timestamp must be
excluded by filter_rows_as_of_entry.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union


FEATURE_COLUMNS = [
    "entry_vs_open_pct",
    "entry_position_in_bar",
    "bar_return_pct",
    "trade_return_pct",
    "volume_value",
    "ma_5",
    "ma_20",
    "ma_20_slope",
    "rsi_14",
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_20d",
    "high_20d",
    "low_20d",
    "avg_volume_20d",
    "avg_turnover_20d",
    "gap_pct",
    "entry_vs_ma20_pct",
    "entry_vs_high20_ratio",
    "range_position_20d",
]

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def parse_datetime(value: Any) -> datetime:
    """Parse a string date/time value into a datetime object."""
    if value is None or str(value).strip() == "":
        raise ValueError("Datetime value is empty.")

    text_value = str(value).strip()
    for date_format in DATETIME_FORMATS:
        try:
            return datetime.strptime(text_value, date_format)
        except ValueError:
            pass
    raise ValueError("Unsupported datetime format: {0}".format(text_value))


def safe_float(value: Any) -> Optional[float]:
    """Convert a CSV value to float, returning None when conversion is unsafe."""
    if value is None or str(value).strip() == "":
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def sort_rows_by_datetime(
    rows: List[Dict[str, str]], datetime_column: str = "datetime"
) -> List[Dict[str, str]]:
    """Return a new list sorted by datetime, with invalid datetimes at the end."""

    def sort_key(row: Dict[str, str]):
        try:
            return (0, parse_datetime(row.get(datetime_column)))
        except ValueError:
            return (1, datetime.max)

    return sorted(list(rows), key=sort_key)


def filter_rows_as_of_entry(
    rows: List[Dict[str, str]],
    entry_timestamp: Union[str, datetime],
    datetime_column: str = "datetime",
) -> List[Dict[str, str]]:
    """Return rows available at or before entry_timestamp.

    Do not use rows after entry_timestamp for entry decision features.
    """
    if isinstance(entry_timestamp, datetime):
        entry_dt = entry_timestamp
    else:
        entry_dt = parse_datetime(entry_timestamp)

    filtered_rows = []
    for row in rows:
        try:
            row_dt = parse_datetime(row.get(datetime_column))
        except ValueError:
            continue
        if row_dt <= entry_dt:
            filtered_rows.append(row)

    return sort_rows_by_datetime(filtered_rows, datetime_column)


def build_entry_context_snapshot(row: Dict[str, str]) -> Dict[str, Any]:
    """Build a simple entry-context snapshot from one mock CSV row."""
    return {
        "trade_id": row.get("trade_id"),
        "symbol": row.get("symbol"),
        "entry_timestamp": row.get("buy_time"),
        "entry_price": safe_float(row.get("buy_price")),
        "exit_price": safe_float(row.get("sell_price")),
        "quantity": safe_float(row.get("quantity")),
        "bar_datetime": row.get("datetime"),
        "open": safe_float(row.get("open")),
        "high": safe_float(row.get("high")),
        "low": safe_float(row.get("low")),
        "close": safe_float(row.get("close")),
        "volume": safe_float(row.get("volume")),
    }


def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Return numerator / denominator when both values are usable."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_basic_mock_features(row: Dict[str, str]) -> Dict[str, Any]:
    """Compute minimal single-row mock features without labeling or advice."""
    snapshot = build_entry_context_snapshot(row)
    entry_price = snapshot["entry_price"]
    exit_price = snapshot["exit_price"]
    open_price = snapshot["open"]
    high_price = snapshot["high"]
    low_price = snapshot["low"]
    close_price = snapshot["close"]
    volume = snapshot["volume"]

    entry_vs_open_pct = None
    if entry_price is not None and open_price is not None:
        entry_vs_open_pct = _safe_divide(entry_price - open_price, open_price)

    entry_position_in_bar = None
    if entry_price is not None and high_price is not None and low_price is not None:
        entry_position_in_bar = _safe_divide(entry_price - low_price, high_price - low_price)

    bar_return_pct = None
    if close_price is not None and open_price is not None:
        bar_return_pct = _safe_divide(close_price - open_price, open_price)

    # TODO: trade_return_pct is post-trade context and must not be used as
    # direct evidence for entry-error decisions.
    trade_return_pct = None
    if exit_price is not None and entry_price is not None:
        trade_return_pct = _safe_divide(exit_price - entry_price, entry_price)

    return {
        "entry_vs_open_pct": entry_vs_open_pct,
        "entry_position_in_bar": entry_position_in_bar,
        "bar_return_pct": bar_return_pct,
        "trade_return_pct": trade_return_pct,
        "volume_value": volume,
        "feature_scope": "single_mock_row_only",
        "look_ahead_warning": (
            "trade_return_pct is post-trade information and must not be used "
            "as entry-decision evidence."
        ),
    }


def build_feature_result(row: Dict[str, str]) -> Dict[str, Any]:
    """Build the standard feature result structure for one mock row."""
    context_snapshot = build_entry_context_snapshot(row)
    features = compute_basic_mock_features(row)
    insufficient_reasons = []

    for key in ["trade_id", "symbol", "entry_timestamp", "entry_price", "open", "high", "low", "close"]:
        if context_snapshot.get(key) is None:
            insufficient_reasons.append("missing_{0}".format(key))

    feature_status = "ok"
    if insufficient_reasons:
        feature_status = "insufficient_data"

    return {
        "feature_status": feature_status,
        "context_snapshot": context_snapshot,
        "features": features,
        "insufficient_reasons": insufficient_reasons,
        "notes": [
            "Only single mock row features are computed in step 5.",
            "Rolling indicators will be implemented later.",
        ],
    }


def _not_implemented_result() -> Dict[str, str]:
    """Return a placeholder result for future historical OHLCV features."""
    return {
        "status": "not_implemented",
        "todo": "This feature will be implemented after real OHLCV history is available.",
    }


def compute_rolling_indicators(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Return a TODO result for future rolling indicators."""
    return _not_implemented_result()


def compute_rsi_14(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Return a TODO result for future RSI calculation."""
    return _not_implemented_result()


def compute_moving_averages(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Return a TODO result for future moving average calculation."""
    return _not_implemented_result()


def compute_high_low_features(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Return a TODO result for future high/low lookback features."""
    return _not_implemented_result()


def compute_volume_features(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Return a TODO result for future volume features."""
    return _not_implemented_result()
