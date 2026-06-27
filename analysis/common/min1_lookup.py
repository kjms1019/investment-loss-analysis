"""1분봉(analysis/data/min1) 공용 조회 유틸.

holding_market_min1.py(보유종목 실시간 시세)와 데모 백필 어댑터가
종목명→코드 매핑, parquet 로딩, 특정 시각 인덱스 조회를 공유한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

# 데이터 루트 단일 소스(MIRAE_DATA_ROOT). DATA_ROOT 는 binsu 코드 호환용 별칭.
from analysis.common.paths import CODES_CSV, DATA_DIR, MIN1_DIR

DATA_ROOT = DATA_DIR

_min1_cache: dict[str, Optional[pd.DataFrame]] = {}
_min1_ohlcv_cache: dict[str, Optional[pd.DataFrame]] = {}
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


def load_min1_ohlcv(code: Optional[str]) -> Optional[pd.DataFrame]:
    """종목코드 → 1분봉 OHLCV DataFrame(진입맥락 피처 계산용), 캐시됨. 파일 없으면 None."""
    if not code:
        return None
    code = str(code).strip().zfill(6)
    if code not in _min1_ohlcv_cache:
        fp = MIN1_DIR / f"{code}.parquet"
        _min1_ohlcv_cache[code] = (
            pd.read_parquet(
                fp, columns=["datetime", "open", "high", "low", "close", "volume"]
            ).sort_values("datetime")
            if fp.exists() else None
        )
    return _min1_ohlcv_cache[code]


def entry_market_features(
    code: Optional[str], when: datetime, *, pre_minutes: int = 200
) -> dict:
    """진입(예정) 시각 직전 pre_minutes 봉으로 진입맥락 피처를 계산.

    분류기·진입오류 에이전트와 동일한 캐노니컬 함수(entry_features_window)를 써서
    "분류 근거 = 예측 근거"를 유지한다. 데이터 없으면 빈 dict.
    반환 키 = FEATURES(rsi_14·range_position_20·entry_vs_high20·ret_120m·volume_ratio_20 등).
    """
    df = load_min1_ohlcv(code)
    if df is None or df.empty:
        return {}
    before = df[df["datetime"] <= pd.to_datetime(when)].tail(pre_minutes)
    if before.empty:
        return {}
    # 지연 import: label_validation ↔ common 순환 import 방지
    from analysis.label_validation.label_pipeline import FEATURES, entry_features_window

    feats = entry_features_window(
        before["open"].to_numpy(float),
        before["high"].to_numpy(float),
        before["low"].to_numpy(float),
        before["close"].to_numpy(float),
        before["volume"].to_numpy(float),
    )
    # 분류기 입력 키(FEATURES)만, None 제외 — 예측기 룰/모델이 바로 소비
    return {k: float(v) for k in FEATURES if (v := feats.get(k)) is not None}


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
