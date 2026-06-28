"""Lightweight CSV loading helpers for the mock CSV stage.

Only Python standard library modules are used here. Type conversion, date
parsing, numeric parsing, and pandas-based loading are intentionally deferred.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional, Union


CsvRow = Dict[str, str]


def load_csv_rows(file_path: Union[str, Path]) -> List[CsvRow]:
    """Read CSV rows as dictionaries without type conversion."""
    csv_path = Path(file_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            "CSV file was not found. Please check the path: {0}".format(csv_path)
        )

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [dict(row) for row in reader]


def load_tiny_mock_data(project_root: Optional[Union[str, Path]] = None) -> List[CsvRow]:
    """Load sample_data/tiny_mock.csv as a list of row dictionaries."""
    if project_root is None:
        root_path = Path(__file__).resolve().parent.parent
    else:
        root_path = Path(project_root)

    return load_csv_rows(root_path / "sample_data" / "tiny_mock.csv")


def summarize_rows(rows: List[CsvRow]) -> Dict[str, object]:
    """Return a small summary for loaded CSV rows."""
    if not rows:
        return {
            "row_count": 0,
            "columns": [],
            "first_row": None,
        }

    first_row = rows[0]
    return {
        "row_count": len(rows),
        "columns": list(first_row.keys()),
        "first_row": first_row,
    }


# ---------------------------------------------------------------------------
# Real 1-minute parquet data loading helpers
# ---------------------------------------------------------------------------

def _normalize_stock_code(code):
    """Normalize a stock code to a 6-digit string."""
    code_text = str(code).strip()
    if code_text.endswith(".0"):
        code_text = code_text[:-2]
    return code_text.zfill(6)


def find_parquet_by_code(code, data_dir="/content/mirae_asset_agent/analysis/data/min1"):
    """Find one parquet file for a stock code.

    This function does not assume a single fixed filename format.
    It first tries exact stem match like 023530.parquet, then falls back to
    filenames containing the code.
    """
    data_path = Path(data_dir)
    normalized_code = _normalize_stock_code(code)

    if not data_path.exists():
        raise FileNotFoundError(
            "Parquet data directory was not found: {0}".format(data_path)
        )

    parquet_files = sorted(data_path.rglob("*.parquet"))

    exact_matches = [
        file_path
        for file_path in parquet_files
        if file_path.stem == normalized_code
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    contains_matches = [
        file_path
        for file_path in parquet_files
        if normalized_code in file_path.name
    ]
    if len(contains_matches) == 1:
        return contains_matches[0]

    if len(exact_matches) > 1 or len(contains_matches) > 1:
        raise ValueError(
            "Multiple parquet files matched code {0}. Please check filenames.".format(
                normalized_code
            )
        )

    raise FileNotFoundError(
        "No parquet file matched code {0} under {1}".format(
            normalized_code,
            data_path,
        )
    )


def load_symbol_min1(code, data_dir="/content/mirae_asset_agent/analysis/data/min1"):
    """Load one symbol's 1-minute OHLCV parquet data as a pandas DataFrame."""
    import pandas as pd

    parquet_path = find_parquet_by_code(code, data_dir=data_dir)
    df = pd.read_parquet(parquet_path)

    required_columns = ["datetime", "open", "high", "low", "close", "volume", "code"]
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            "Missing required min1 columns: {0}".format(missing_columns)
        )

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["code"] = df["code"].apply(_normalize_stock_code)

    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if "acc_volume" in df.columns:
        df["acc_volume"] = pd.to_numeric(df["acc_volume"], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)

    return df


def extract_trade_window(df, buy_time, pre_minutes=120, post_minutes=30):
    """Extract rows around buy_time from 1-minute data.

    pre_minutes are used for entry-decision features.
    post_minutes are kept only for review context and must not be used as
    direct evidence of entry error.
    """
    import pandas as pd

    if df.empty:
        raise ValueError("Input min1 DataFrame is empty.")

    buy_dt = pd.to_datetime(buy_time)
    start_dt = buy_dt - pd.Timedelta(minutes=pre_minutes)
    end_dt = buy_dt + pd.Timedelta(minutes=post_minutes)

    window = df[
        (df["datetime"] >= start_dt)
        & (df["datetime"] <= end_dt)
    ].copy()

    if window.empty:
        raise ValueError(
            "No rows found around buy_time {0}. Check code/date/time.".format(buy_time)
        )

    before_or_at_entry = window[window["datetime"] <= buy_dt]
    after_entry = window[window["datetime"] > buy_dt]

    return {
        "buy_time": buy_dt,
        "pre_minutes": pre_minutes,
        "post_minutes": post_minutes,
        "window": window.reset_index(drop=True),
        "before_or_at_entry": before_or_at_entry.reset_index(drop=True),
        "after_entry": after_entry.reset_index(drop=True),
        "row_count": len(window),
        "pre_entry_row_count": len(before_or_at_entry),
        "post_entry_row_count": len(after_entry),
    }

