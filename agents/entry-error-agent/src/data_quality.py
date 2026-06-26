"""Data quality checks for mock CSV rows.

This module validates string values loaded from CSV files. It does not perform
trading analysis, labeling, report generation, or technical indicator logic.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


NUMERIC_COLUMNS = [
    "buy_price",
    "sell_price",
    "quantity",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

OPTIONAL_NUMERIC_COLUMNS = [
    "realized_pnl",
    "realized_pnl_pct",
    "fees",
]

DATETIME_COLUMNS = [
    "buy_time",
    "sell_time",
    "datetime",
]

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def is_missing_value(value: Any) -> bool:
    """Return True when a CSV value is empty or missing."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def parse_float(value: Any) -> Optional[float]:
    """Parse a CSV value into float without changing the original row."""
    if is_missing_value(value):
        return None
    normalized_value = str(value).replace(",", "").strip()
    return float(normalized_value)


def is_valid_float(value: Any) -> bool:
    """Return True when a value can be parsed as a float."""
    try:
        parse_float(value)
        return True
    except ValueError:
        return False


def is_valid_datetime_string(value: Any) -> bool:
    """Return True when a value matches one of the accepted date formats."""
    if is_missing_value(value):
        return False

    text_value = str(value).strip()
    for date_format in DATETIME_FORMATS:
        try:
            datetime.strptime(text_value, date_format)
            return True
        except ValueError:
            pass
    return False


def validate_numeric_columns(
    row: Dict[str, str], numeric_columns: List[str]
) -> List[Dict[str, Any]]:
    """Return numeric validation errors for required numeric columns."""
    errors = []
    for column in numeric_columns:
        value = row.get(column)
        if is_missing_value(value):
            errors.append(
                {
                    "column": column,
                    "value": value,
                    "reason": "missing",
                }
            )
            continue
        if not is_valid_float(value):
            errors.append(
                {
                    "column": column,
                    "value": value,
                    "reason": "not_numeric",
                }
            )
    return errors


def validate_datetime_columns(
    row: Dict[str, str], datetime_columns: List[str]
) -> List[Dict[str, Any]]:
    """Return datetime validation errors for required datetime columns."""
    errors = []
    for column in datetime_columns:
        value = row.get(column)
        if is_missing_value(value):
            errors.append(
                {
                    "column": column,
                    "value": value,
                    "reason": "missing",
                }
            )
            continue
        if not is_valid_datetime_string(value):
            errors.append(
                {
                    "column": column,
                    "value": value,
                    "reason": "invalid_datetime_format",
                }
            )
    return errors


def _get_float(row: Dict[str, str], column: str) -> Optional[float]:
    """Return a parsed float or None when parsing is not possible."""
    try:
        return parse_float(row.get(column))
    except ValueError:
        return None


def validate_price_logic(row: Dict[str, str]) -> List[Dict[str, str]]:
    """Return basic price and volume logic errors for one row."""
    errors = []
    buy_price = _get_float(row, "buy_price")
    sell_price = _get_float(row, "sell_price")
    quantity = _get_float(row, "quantity")
    open_price = _get_float(row, "open")
    high_price = _get_float(row, "high")
    low_price = _get_float(row, "low")
    close_price = _get_float(row, "close")
    volume = _get_float(row, "volume")

    if buy_price is not None and buy_price <= 0:
        errors.append({"field": "buy_price", "reason": "must_be_positive"})
    if sell_price is not None and sell_price <= 0:
        errors.append({"field": "sell_price", "reason": "must_be_positive"})
    if quantity is not None and quantity <= 0:
        errors.append({"field": "quantity", "reason": "must_be_positive"})

    for field_name, value in [
        ("open", open_price),
        ("high", high_price),
        ("low", low_price),
        ("close", close_price),
    ]:
        if value is not None and value <= 0:
            errors.append({"field": field_name, "reason": "must_be_positive"})

    if volume is not None and volume < 0:
        errors.append({"field": "volume", "reason": "must_be_zero_or_positive"})

    if high_price is not None and low_price is not None and high_price < low_price:
        errors.append({"field": "high_low", "reason": "high_is_lower_than_low"})

    if (
        high_price is not None
        and open_price is not None
        and low_price is not None
        and not (high_price >= open_price >= low_price)
    ):
        errors.append({"field": "open_range", "reason": "open_outside_high_low"})

    if (
        high_price is not None
        and close_price is not None
        and low_price is not None
        and not (high_price >= close_price >= low_price)
    ):
        errors.append({"field": "close_range", "reason": "close_outside_high_low"})

    return errors


def _validate_optional_numeric_columns(row: Dict[str, str]) -> List[Dict[str, Any]]:
    """Return validation errors for optional numeric columns when present."""
    errors = []
    for column in OPTIONAL_NUMERIC_COLUMNS:
        if column not in row or is_missing_value(row.get(column)):
            continue
        if not is_valid_float(row.get(column)):
            errors.append(
                {
                    "column": column,
                    "value": row.get(column),
                    "reason": "not_numeric",
                }
            )
    return errors


def build_data_quality_report(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Build a compact data quality report for loaded CSV rows."""
    row_count = len(rows)
    errors = []
    valid_row_count = 0

    for row_index, row in enumerate(rows):
        row_has_errors = False

        numeric_errors = validate_numeric_columns(row, NUMERIC_COLUMNS)
        optional_numeric_errors = _validate_optional_numeric_columns(row)
        if numeric_errors or optional_numeric_errors:
            row_has_errors = True
            errors.append(
                {
                    "row_index": row_index,
                    "error_type": "numeric_validation",
                    "details": numeric_errors + optional_numeric_errors,
                }
            )

        datetime_errors = validate_datetime_columns(row, DATETIME_COLUMNS)
        if datetime_errors:
            row_has_errors = True
            errors.append(
                {
                    "row_index": row_index,
                    "error_type": "datetime_validation",
                    "details": datetime_errors,
                }
            )

        price_logic_errors = validate_price_logic(row)
        if price_logic_errors:
            row_has_errors = True
            errors.append(
                {
                    "row_index": row_index,
                    "error_type": "price_logic_validation",
                    "details": price_logic_errors,
                }
            )

        if not row_has_errors:
            valid_row_count += 1

    invalid_row_count = row_count - valid_row_count
    has_errors = len(errors) > 0

    if row_count == 0:
        quality_score = 0.0
    elif not has_errors:
        quality_score = 1.0
    else:
        quality_score = float(valid_row_count) / float(row_count)

    return {
        "row_count": row_count,
        "valid_row_count": valid_row_count,
        "invalid_row_count": invalid_row_count,
        "has_errors": has_errors,
        "errors": errors,
        "warnings": [],
        "quality_score": quality_score,
    }
