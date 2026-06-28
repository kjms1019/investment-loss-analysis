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


# ---------------------------------------------------------------------------
# Real 1-minute OHLCV window feature engineering
# ---------------------------------------------------------------------------

FEATURE_STATUS_OK = "ok"
FEATURE_STATUS_PARTIAL = "partial"
FEATURE_STATUS_RAW_DATA_ABSENT = "raw_data_absent"
FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT = "pre_entry_history_short"
FEATURE_STATUS_FEATURE_MISSING_OR_INVALID = "feature_missing_or_invalid"

MIN_PRE_ENTRY_BARS_FOR_BASIC = 5
MIN_PRE_ENTRY_BARS_FOR_STATE = 40

def _safe_percent_change(current_value, base_value):
    """Return (current - base) / base when values are usable."""
    if current_value is None or base_value is None:
        return None
    try:
        current_value = float(current_value)
        base_value = float(base_value)
    except (TypeError, ValueError):
        return None
    if base_value == 0:
        return None
    return (current_value - base_value) / base_value


def _series_value(series, index_from_end):
    """Return a float value from a pandas Series by negative position."""
    if series is None or len(series) < abs(index_from_end):
        return None
    value = series.iloc[index_from_end]
    if value != value:
        return None
    return float(value)


def _compute_rsi_from_close(close_series, period=14):
    """Compute simple RSI using only close prices available up to entry."""
    if close_series is None or len(close_series) < period + 1:
        return None

    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    last_avg_gain = avg_gain.iloc[-1]
    last_avg_loss = avg_loss.iloc[-1]

    if last_avg_gain != last_avg_gain or last_avg_loss != last_avg_loss:
        return None
    if last_avg_loss == 0:
        return 100.0

    rs = last_avg_gain / last_avg_loss
    return float(100 - (100 / (1 + rs)))


def build_feature_result_from_min1_window(window_result, code=None, buy_price=None):
    """Build feature result from real 1-minute OHLCV data.

    Only rows at or before buy_time are used for entry-decision features.
    Rows after buy_time are kept out of features to avoid look-ahead bias.

    Parameters
    ----------
    window_result:
        Result dictionary returned by extract_trade_window().
    code:
        Optional stock code for the report context.
    buy_price:
        Optional actual buy price. If omitted, the close price of the entry
        minute is used as a fallback for development testing.
    """
    import pandas as pd

    if not window_result or window_result.get("window") is None:
        return {
            "feature_status": FEATURE_STATUS_RAW_DATA_ABSENT,
            "data_availability_status": FEATURE_STATUS_RAW_DATA_ABSENT,
            "context_snapshot": {
                "symbol": code,
                "entry_timestamp": None,
                "entry_price": buy_price,
            },
            "features": {},
            "insufficient_reasons": ["raw_min1_window_absent"],
            "notes": ["No parquet/window data was available for this trade."],
        }

    buy_time = pd.to_datetime(window_result["buy_time"])
    pre_df = window_result["before_or_at_entry"].copy()

    insufficient_reasons = []

    if pre_df.empty:
        insufficient_reasons.append("no_pre_entry_rows")
        return {
            "feature_status": FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT,
            "data_availability_status": FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT,
            "context_snapshot": {
                "symbol": code,
                "entry_timestamp": str(buy_time),
                "entry_price": buy_price,
            },
            "features": {},
            "insufficient_reasons": insufficient_reasons,
            "notes": ["No pre-entry 1-minute rows were available."],
        }

    pre_df = pre_df.sort_values("datetime").reset_index(drop=True)

    entry_bar = pre_df.iloc[-1]
    entry_open = float(entry_bar["open"])
    entry_high = float(entry_bar["high"])
    entry_low = float(entry_bar["low"])
    entry_close = float(entry_bar["close"])
    entry_volume = float(entry_bar["volume"])

    used_fallback_buy_price = False
    if buy_price is None:
        buy_price = entry_close
        used_fallback_buy_price = True
    else:
        buy_price = float(buy_price)

    # 피처 계산은 분류기와 공유하는 단일 캐노니컬 함수에 위임한다.
    # (분류기 label_pipeline.entry_features_window 와 동일 — 분류 근거 = 분석 근거 일치)
    from analysis.label_validation.label_pipeline import entry_features_window
    feats = entry_features_window(
        pre_df["open"].to_numpy(float),
        pre_df["high"].to_numpy(float),
        pre_df["low"].to_numpy(float),
        pre_df["close"].to_numpy(float),
        pre_df["volume"].to_numpy(float),
        buy_price=buy_price,
    )
    ma_20 = feats["ma_20"]
    ma_20_slope = feats["ma_20_slope"]
    rsi_14 = feats["rsi_14"]
    ret_20m = feats["ret_20m"]
    entry_vs_ma20_pct = feats["entry_vs_ma20_pct"]
    range_position_20m = feats["range_position_20m"]

    if len(pre_df) < MIN_PRE_ENTRY_BARS_FOR_STATE:
        insufficient_reasons.append("pre_entry_history_short")
    if len(pre_df) < 20:
        insufficient_reasons.append("less_than_20_pre_entry_bars")
    if ma_20 is None:
        insufficient_reasons.append("ma20_unavailable")
    if rsi_14 is None:
        insufficient_reasons.append("rsi14_unavailable")

    required_state_features = {
        "ma_20_slope": ma_20_slope,
        "ret_20m": ret_20m,
        "entry_vs_ma20_pct": entry_vs_ma20_pct,
        "range_position_20m": range_position_20m,
    }
    missing_required_state_features = [
        name for name, value in required_state_features.items() if value is None
    ]

    feature_status = FEATURE_STATUS_OK
    data_availability_status = FEATURE_STATUS_OK
    if len(pre_df) < MIN_PRE_ENTRY_BARS_FOR_BASIC:
        feature_status = FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT
        data_availability_status = FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT
    elif len(pre_df) < MIN_PRE_ENTRY_BARS_FOR_STATE:
        feature_status = FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT
        data_availability_status = FEATURE_STATUS_PRE_ENTRY_HISTORY_SHORT
    elif missing_required_state_features:
        feature_status = FEATURE_STATUS_FEATURE_MISSING_OR_INVALID
        data_availability_status = FEATURE_STATUS_FEATURE_MISSING_OR_INVALID
        insufficient_reasons.extend(
            [
                "missing_or_invalid_{0}".format(name)
                for name in missing_required_state_features
            ]
        )
    elif insufficient_reasons:
        feature_status = FEATURE_STATUS_PARTIAL

    return {
        "feature_status": feature_status,
        "data_availability_status": data_availability_status,
        "context_snapshot": {
            "trade_id": None,
            "symbol": code,
            "entry_timestamp": str(buy_time),
            "entry_price": buy_price,
            "bar_datetime": str(entry_bar["datetime"]),
            "open": entry_open,
            "high": entry_high,
            "low": entry_low,
            "close": entry_close,
            "volume": entry_volume,
            "used_fallback_buy_price": used_fallback_buy_price,
        },
        "features": {
            "entry_vs_open_pct": feats["entry_vs_open_pct"],
            "entry_position_in_bar": feats["entry_position_in_bar"],
            "bar_return_pct": feats["bar_return_pct"],
            "trade_return_pct": None,
            "volume_value": feats["volume_value"],
            "ma_5": feats["ma_5"],
            "ma_20": feats["ma_20"],
            "ma_20_slope": feats["ma_20_slope"],
            "rsi_14": feats["rsi_14"],
            "ret_1m": feats["ret_1m"],
            "ret_3m": feats["ret_3m"],
            "ret_5m": feats["ret_5m"],
            "ret_20m": feats["ret_20m"],
            "high_20m": feats["high_20m"],
            "low_20m": feats["low_20m"],
            "avg_volume_20m": feats["avg_volume_20m"],
            "volume_ratio_20m": feats["volume_ratio_20m"],
            "entry_vs_ma20_pct": feats["entry_vs_ma20_pct"],
            "entry_vs_high20_ratio": feats["entry_vs_high20_ratio"],
            "range_position_20m": feats["range_position_20m"],
            "feature_scope": "real_min1_pre_entry_window",
            "look_ahead_warning": (
                "Only rows at or before entry_timestamp were used for entry-decision features. "
                "Post-entry rows are excluded from label evidence."
            ),
        },
        "insufficient_reasons": insufficient_reasons,
        "missing_required_state_features": missing_required_state_features,
        "pre_entry_row_count": len(pre_df),
        "notes": [
            "This feature set is based on 1-minute OHLCV history.",
            "Thresholds should be validated across many trades, not fitted to a single ticker.",
        ],
    }

