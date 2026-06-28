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
