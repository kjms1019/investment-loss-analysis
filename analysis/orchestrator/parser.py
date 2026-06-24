"""Common input parser for user trade CSV files.

The first version supports a conservative generic CSV schema:
datetime, code, name, side, qty, price

Broker-specific column maps can be passed in without changing downstream
orchestrator code.
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .schema import NormalizedTrade, RawTradeRow


DEFAULT_COLUMN_MAP = {
    "executed_at": "datetime",
    "code": "code",
    "name": "name",
    "side": "side",
    "qty": "qty",
    "price": "price",
}


def _clean_code(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def _parse_float(value: object, field_name: str) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError("Missing required numeric field: {0}".format(field_name))
    return float(str(value).replace(",", "").strip())


def _normalize_side(value: object) -> str:
    side = str(value).strip().upper()
    if side in ["B", "BUY"]:
        return "BUY"
    if side in ["S", "SELL"]:
        return "SELL"
    raise ValueError("Unsupported trade side: {0}".format(value))


def read_raw_trade_rows(
    file_path: str,
    batch_id: Optional[str] = None,
) -> Tuple[str, List[RawTradeRow]]:
    """Read a CSV file into raw row records."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("Trade CSV was not found: {0}".format(path))

    batch_id = batch_id or str(uuid.uuid4())
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_index, row in enumerate(reader):
            rows.append(
                RawTradeRow(
                    batch_id=batch_id,
                    row_index=row_index,
                    payload=dict(row),
                )
            )
    return batch_id, rows


def normalize_trade_rows(
    raw_rows: Iterable[RawTradeRow],
    column_map: Optional[Dict[str, str]] = None,
) -> List[NormalizedTrade]:
    """Convert raw broker rows into the shared normalized trade schema."""
    column_map = column_map or DEFAULT_COLUMN_MAP
    normalized = []

    for raw_row in raw_rows:
        payload = raw_row.payload
        trade_id = "{0}:{1}".format(raw_row.batch_id, raw_row.row_index)
        try:
            executed_at = str(payload[column_map["executed_at"]]).strip()
            code = _clean_code(payload[column_map["code"]])
            name = str(payload.get(column_map.get("name", "name"), "")).strip()
            side = _normalize_side(payload[column_map["side"]])
            qty = _parse_float(payload[column_map["qty"]], "qty")
            price = _parse_float(payload[column_map["price"]], "price")
        except KeyError as exc:
            raise ValueError(
                "Missing required source column for normalized trade field: {0}".format(exc)
            )

        normalized.append(
            NormalizedTrade(
                trade_id=trade_id,
                batch_id=raw_row.batch_id,
                source_row_index=raw_row.row_index,
                executed_at=executed_at,
                code=code,
                name=name,
                side=side,
                qty=qty,
                price=price,
                raw_payload=payload,
            )
        )

    return normalized
