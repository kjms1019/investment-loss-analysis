"""실 min1 기반 보유 시세 제공자.

binsu의 holding_predictor.DemoHoldingMarketDataProvider(가짜 해시값)를 대체해,
실제 1분봉(analysis/data/min1)에서 보유종목의 진입가·현재가·손절선·낙폭·변동성을
계산해 HoldingMarketSnapshot 을 만든다. (HoldingMarketDataProvider 프로토콜 구현)

흐름: 현재보유(업로드) → 이 provider가 min1로 시세 채움 → PositionSnapshot →
      예측기 monitor_live_position → 손절실패 실시간 경고.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .holding_predictor import CurrentHoldingInput, HoldingMarketSnapshot

_ROOT = Path(__file__).resolve().parents[2]
_MIN1_DIR = _ROOT / "analysis" / "data" / "min1"
_CODES_CSV = _ROOT / "analysis" / "data" / ".cache" / "kospi_codes.csv"


def _load_name_to_code() -> dict:
    if not _CODES_CSV.exists():
        return {}
    df = pd.read_csv(_CODES_CSV, dtype=str)
    return dict(zip(df["name"], df["code"]))


def _idx_at(dts: np.ndarray, when: datetime) -> int:
    i = np.searchsorted(dts, np.datetime64(pd.to_datetime(when)), side="right") - 1
    return int(max(0, min(i, len(dts) - 1)))


class Min1HoldingMarketDataProvider:
    """현재보유 → 실 min1 시세 스냅샷. observed_at 미지정 시 최신 봉을 '현재'로 본다."""

    def __init__(self, *, stop_loss_pct: float = 0.05, observed_at: Optional[datetime] = None,
                 name_to_code: Optional[dict] = None) -> None:
        self.stop_loss_pct = stop_loss_pct
        self.observed_at = observed_at
        self.name_to_code = name_to_code if name_to_code is not None else _load_name_to_code()
        self._cache: dict = {}

    def _load(self, code: Optional[str]):
        if not code:
            return None
        code = str(code).strip().zfill(6)
        if code not in self._cache:
            fp = _MIN1_DIR / f"{code}.parquet"
            self._cache[code] = (
                pd.read_parquet(fp, columns=["datetime", "high", "close"]).sort_values("datetime")
                if fp.exists() else None
            )
        return self._cache[code]

    def __call__(self, holding: CurrentHoldingInput) -> HoldingMarketSnapshot:
        code = holding.code or self.name_to_code.get(holding.name)
        df = self._load(code)
        if df is None:
            # min1 없음 → 시세 미상(예측기는 0 수익률로 보수적 처리)
            return HoldingMarketSnapshot(
                entry_price=0.0, current_price=0.0,
                observed_at=self.observed_at or datetime.now(),
            )
        dts = df["datetime"].to_numpy()
        close = df["close"].to_numpy(float)
        high = df["high"].to_numpy(float)

        e = _idx_at(dts, holding.bought_at)
        cur = _idx_at(dts, self.observed_at) if self.observed_at else len(close) - 1
        if cur < e:
            cur = e
        entry = float(close[e])
        current = float(close[cur])
        seg_close = close[e:cur + 1]
        seg_high = high[e:cur + 1]
        stop_price = entry * (1 - self.stop_loss_pct)

        below = np.where(seg_close <= stop_price)[0]
        minutes_since_breach = float(cur - (e + int(below[0]))) if len(below) else None
        rets = np.diff(seg_close) / seg_close[:-1] if len(seg_close) >= 2 else np.array([0.0])

        return HoldingMarketSnapshot(
            entry_price=round(entry, 2),
            current_price=round(current, 2),
            observed_at=pd.to_datetime(dts[cur]).to_pydatetime(),
            stop_loss_price=round(stop_price, 2),
            highest_price_since_entry=round(float(seg_high.max()), 2),
            minutes_since_stop_breach=minutes_since_breach,
            price_change_5m_pct=round((current / close[cur - 5] - 1) * 100, 3) if cur >= 5 else None,
            volatility_30m_pct=round(float(rets[-30:].std()) * 100, 3),
            market_mood_score=None,
        )
