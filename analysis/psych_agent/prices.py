"""1분봉 맥락 데이터 조회 서비스.

처분효과의 '평가손익' 판정에는 매도 시점의 시장가가 필요하다.
analysis/data/min1/{code}.parquet 를 종목별로 1회 로드해 캐시하고,
임의 시각의 직전 체결가(close)를 merge_asof(backward)로 돌려준다.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import Config


class PriceLookup:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._cache: dict[str, pd.DataFrame] = {}

    def _load(self, code: str) -> pd.DataFrame | None:
        if code in self._cache:
            return self._cache[code]
        path = self.config.min1_path(code)
        if not path.exists():
            self._cache[code] = None
            return None
        df = (
            pd.read_parquet(path, columns=["datetime", "close"])
            .sort_values("datetime")
            .reset_index(drop=True)
        )
        df["datetime"] = pd.to_datetime(df["datetime"])
        self._cache[code] = df
        return df

    def price_at(self, code: str, ts: pd.Timestamp) -> int | None:
        """ts 시점 직전(포함)의 마지막 체결가. 데이터 없으면 None."""
        df = self._load(code)
        if df is None or df.empty:
            return None
        ts = pd.Timestamp(ts)
        idx = df["datetime"].searchsorted(ts, side="right") - 1
        if idx < 0:
            return None
        return int(df["close"].iloc[idx])

    def prices_at(self, code: str, timestamps: pd.Series) -> pd.Series:
        """여러 시각을 한 번에 (merge_asof backward). 정렬된 Series 반환."""
        df = self._load(code)
        ts = pd.to_datetime(pd.Series(timestamps)).sort_values()
        if df is None or df.empty:
            return pd.Series([None] * len(ts), index=ts.index)
        merged = pd.merge_asof(
            ts.to_frame("datetime"),
            df,
            on="datetime",
            direction="backward",
        )
        return merged["close"]

    def first_minute(self, code: str) -> pd.DataFrame | None:
        return self._load(code)
