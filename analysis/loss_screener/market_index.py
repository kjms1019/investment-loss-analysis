"""보유 종목 유니버스 기반 동일가중 합성 시장지수 (분 단위).

각 종목 종가를 자기 첫 종가로 정규화(rebase=1.0)한 뒤, 같은 분(minute)끼리
횡단면 평균낸 레벨을 지수로 쓴다.
  norm_i[t] = close_i[t] / close_i[첫분]
  level[t]  = 100 * mean_over_stocks( norm_i[t] )
정규화 레벨을 평균하므로 분 수익률 누적복리에서 생기는 마이크로구조 상방편향
(호가 bounce·볼록성)이 없다 — 동일가중 지수의 표준 산출 방식.
그 분에 존재하는 종목만 평균하므로 상장 갭/결측에도 강하다.

한 번 만들어 analysis/data/market_index.parquet 로 캐시한다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from psych_agent.config import Config

CACHE_PATH = Config().min1_dir.parent / "market_index.parquet"


def build_market_index(
    config: Config | None = None,
    max_codes: int | None = None,
    save: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    config = config or Config()
    files = sorted(config.min1_dir.glob("*.parquet"))
    if max_codes:
        files = files[:max_codes]

    # 1패스: 공통 분(minute) 그리드(전 종목 타임스탬프 합집합) 구성
    grid: set = set()
    for f in files:
        grid.update(pd.read_parquet(f, columns=["datetime"])["datetime"].to_numpy())
    grid_idx = pd.DatetimeIndex(sorted(grid))
    if verbose:
        print(f"  공통 그리드 {len(grid_idx):,} 분 확보")

    # 2패스: 각 종목을 그리드에 reindex + ffill 해 '안정적 구성'으로 평균
    #   (그 분에 체결이 없어도 직전 정규화 가격을 유지 → 구성 변동 점프 제거)
    sum_norm = pd.Series(0.0, index=grid_idx)
    cnt = pd.Series(0.0, index=grid_idx)
    for i, f in enumerate(files):
        d = pd.read_parquet(f, columns=["datetime", "close"])
        d = d.drop_duplicates("datetime").set_index("datetime").sort_index()
        close = d["close"].dropna()
        if close.empty or close.iloc[0] == 0:
            continue
        norm = (close / close.iloc[0]).reindex(grid_idx).ffill()  # 상장 전 구간은 NaN 유지
        present = norm.notna()
        sum_norm = sum_norm.add(norm.fillna(0.0))
        cnt = cnt.add(present.astype(float))
        if verbose and (i + 1) % 100 == 0:
            print(f"  ...{i + 1}/{len(files)} 종목 누적")

    mean_norm = (sum_norm / cnt.replace(0.0, pd.NA)).astype(float)
    level = 100.0 * mean_norm
    idx = pd.DataFrame(
        {"datetime": mean_norm.index, "n_stocks": cnt.reindex(mean_norm.index).values,
         "level": level.values}
    ).reset_index(drop=True)

    if save:
        idx.to_parquet(CACHE_PATH, index=False)
        if verbose:
            print(f"[합성지수 캐시 저장 → {CACHE_PATH}  ({len(idx):,} 분, 종목 {len(files)})]")
    return idx


def load_market_index(config: Config | None = None, rebuild: bool = False) -> pd.DataFrame:
    config = config or Config()
    if CACHE_PATH.exists() and not rebuild:
        df = pd.read_parquet(CACHE_PATH)
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df
    return build_market_index(config)


class MarketIndex:
    """진입/청산 시각의 지수 레벨을 빠르게 조회 (merge_asof backward)."""

    def __init__(self, config: Config | None = None, rebuild: bool = False):
        self.df = load_market_index(config, rebuild=rebuild).sort_values("datetime").reset_index(drop=True)

    def level_at(self, ts: pd.Timestamp) -> float | None:
        ts = pd.Timestamp(ts)
        i = self.df["datetime"].searchsorted(ts, side="right") - 1
        if i < 0:
            return None
        return float(self.df["level"].iloc[i])

    def ret_between(self, t0: pd.Timestamp, t1: pd.Timestamp) -> float | None:
        a, b = self.level_at(t0), self.level_at(t1)
        if a is None or b is None or a == 0:
            return None
        return b / a - 1.0


if __name__ == "__main__":
    build_market_index()
