"""
실데이터 로더 — analysis/data/min1/*.parquet 읽기.

외부에서 받은 분봉 parquet을 엔진 스키마(OHLCV)와 분봉 DataFrame 두 형태로 제공한다.
증권사 CSV 거래내역 파서는 별도 파일(transaction_parser.py)로 추가 예정.
"""
from pathlib import Path
from datetime import date
from typing import Optional
import pandas as pd

from schema import OHLCV

# 기본 데이터 경로 — 프로젝트 루트 기준
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "analysis" / "data" / "min1"


def _parquet_path(ticker: str, data_dir: Path) -> Path:
    return data_dir / f"{ticker}.parquet"


def load_minute_df(
    ticker: str,
    data_dir: Path = _DEFAULT_DATA_DIR,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> pd.DataFrame:
    """
    분봉 DataFrame 반환. 종목 파일이 없으면 빈 DataFrame.
    start/end 지정 시 해당 구간만 자름.
    컬럼: datetime, code, open, high, low, close, volume, acc_volume
    """
    path = _parquet_path(ticker, data_dir)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if start is not None:
        df = df[df["datetime"].dt.date >= start]
    if end is not None:
        df = df[df["datetime"].dt.date <= end]
    return df.reset_index(drop=True)


def load_daily_ohlcv(
    ticker: str,
    data_dir: Path = _DEFAULT_DATA_DIR,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list:
    """
    분봉을 일봉으로 집계해 list[OHLCV] 반환.
    open  = 당일 첫 봉의 open
    high  = 당일 분봉 high 최대값
    low   = 당일 분봉 low 최솟값
    close = 당일 마지막 봉의 close
    """
    df = load_minute_df(ticker, data_dir, start, end)
    if df.empty:
        return []

    df = df.copy()
    df["_date"] = df["datetime"].dt.date

    daily = (
        df.groupby("_date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )

    return [
        OHLCV(
            ticker=ticker,
            date=row["_date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row["volume"]),
        )
        for _, row in daily.iterrows()
    ]


def available_tickers(data_dir: Path = _DEFAULT_DATA_DIR) -> list:
    """데이터가 있는 종목코드 목록."""
    return sorted(p.stem for p in data_dir.glob("*.parquet"))
