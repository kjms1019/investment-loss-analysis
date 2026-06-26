"""1분봉(analysis/data/min1) 공용 조회 유틸.

holding_market_min1.py(보유종목 실시간 시세)와 데모 백필 어댑터가
종목명→코드 매핑, parquet 로딩, 특정 시각 인덱스 조회를 공유한다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
MIN1_DIR = _ROOT / "analysis" / "data" / "min1"
CODES_CSV = _ROOT / "analysis" / "data" / ".cache" / "kospi_codes.csv"

_min1_cache: dict[str, Optional[pd.DataFrame]] = {}
_name_to_code_cache: Optional[dict] = None


def load_name_to_code() -> dict:
    """종목명 → 종목코드 매핑 (analysis/data/.cache/kospi_codes.csv)."""
    global _name_to_code_cache
    if _name_to_code_cache is None:
        if CODES_CSV.exists():
            df = pd.read_csv(CODES_CSV, dtype=str)
            _name_to_code_cache = dict(zip(df["name"], df["code"]))
        else:
            _name_to_code_cache = {}
    return _name_to_code_cache


def load_min1(code: Optional[str]) -> Optional[pd.DataFrame]:
    """종목코드 → 1분봉 DataFrame(datetime/high/close), 캐시됨. 파일 없으면 None."""
    if not code:
        return None
    code = str(code).strip().zfill(6)
    if code not in _min1_cache:
        fp = MIN1_DIR / f"{code}.parquet"
        _min1_cache[code] = (
            pd.read_parquet(fp, columns=["datetime", "high", "close"]).sort_values("datetime")
            if fp.exists() else None
        )
    return _min1_cache[code]


def index_at(dts: np.ndarray, when: datetime) -> int:
    """정렬된 datetime 배열에서 when 시각 이하의 가장 마지막 인덱스."""
    i = np.searchsorted(dts, np.datetime64(pd.to_datetime(when)), side="right") - 1
    return int(max(0, min(i, len(dts) - 1)))


def price_at(df: Optional[pd.DataFrame], when: datetime) -> Optional[float]:
    """when 시각 이하 가장 가까운 종가. 데이터 없으면 None."""
    if df is None or df.empty:
        return None
    dts = df["datetime"].to_numpy()
    idx = index_at(dts, when)
    return float(df["close"].to_numpy(float)[idx])
