"""더미 거래내역 생성기 (실데이터 기반).

실제 1분봉(min1) 종가를 그대로 사용해 '완결 거래내역'을 합성한다.
가격이 진짜이므로 손익·평가손익·보유기간이 모두 현실적이고, 세 가지 심리
패턴(리벤지·과매매·처분효과)이 검출되도록 의도적으로 시나리오를 심는다.

scenario:
  'all'         — 세 패턴을 한 계좌에 섞음(현실적). 리벤지·과매매가 강하게,
                  처분효과는 손실 실현이 많아 희석될 수 있음.
  'disposition' — 처분효과만 깨끗하게: 손실 종목은 고점에 사서 계속 보유,
                  수익 종목은 저점에 사서 빨리 익절 → PGR≫PLR.
  'revenge'     — 리벤지만.
  'overtrading' — 과매매만.

산출: DataFrame[datetime, code, name, side, qty, price]  (체결 단위, 시간순)
저장: analysis/data/dummy_trades.csv
"""

from __future__ import annotations

import random

import pandas as pd

from .config import Config

NAME_MAP_PATH = Config().min1_dir.parent / ".cache" / "kospi_codes.csv"


def _load_names() -> dict[str, str]:
    if NAME_MAP_PATH.exists():
        df = pd.read_csv(NAME_MAP_PATH, dtype=str)
        return dict(zip(df["code"], df["name"]))
    return {}


class _Book:
    """min1 종가를 빠르게 조회하기 위한 종목별 가격 프레임."""

    def __init__(self, config: Config):
        self.config = config
        self._cache: dict[str, pd.DataFrame] = {}

    def df(self, code: str) -> pd.DataFrame:
        if code not in self._cache:
            d = pd.read_parquet(self.config.min1_path(code), columns=["datetime", "close"])
            d["datetime"] = pd.to_datetime(d["datetime"])
            self._cache[code] = d.sort_values("datetime").reset_index(drop=True)
        return self._cache[code]

    def at_or_after(self, code: str, ts: pd.Timestamp) -> tuple[pd.Timestamp, int]:
        d = self.df(code)
        i = min(d["datetime"].searchsorted(pd.Timestamp(ts), side="left"), len(d) - 1)
        row = d.iloc[i]
        return pd.Timestamp(row["datetime"]), int(row["close"])

    def _window(self, code: str, start: pd.Timestamp, horizon_min: int) -> pd.DataFrame:
        d = self.df(code)
        a = d["datetime"].searchsorted(pd.Timestamp(start), side="left")
        b = d["datetime"].searchsorted(pd.Timestamp(start) + pd.Timedelta(minutes=horizon_min), side="right")
        return d.iloc[a:b]

    def quick_exit(self, code, entry_ts, entry_px, sign, horizon_min, thr=0.01):
        """진입 후 horizon 안에서 목표 등락(±thr)을 '처음' 만족하는 시점(빠른 청산).

        없으면 부호를 보장하도록 구간 최고가(win)/최저가(loss)로 대체.
        """
        w = self._window(code, entry_ts + pd.Timedelta(minutes=1), horizon_min)
        if w.empty:
            return self.at_or_after(code, entry_ts + pd.Timedelta(minutes=1))
        if sign == "win":
            hit = w[w["close"] >= entry_px * (1 + thr)]
            row = hit.iloc[0] if not hit.empty else w.loc[w["close"].idxmax()]
        else:
            hit = w[w["close"] <= entry_px * (1 - thr)]
            row = hit.iloc[0] if not hit.empty else w.loc[w["close"].idxmin()]
        return pd.Timestamp(row["datetime"]), int(row["close"])

    def pick_extreme_entry(self, code, around_ts, window_days, kind):
        """[around, around+window] 구간의 고점(kind='high')/저점('low') 진입 시점.

        고점 진입 → 이후 평가손실로 남기 쉬움(처분효과 손실종목용).
        저점 진입 → 빠른 익절 가능(수익종목용).
        """
        w = self._window(code, around_ts, window_days * 24 * 60)
        if w.empty:
            return self.at_or_after(code, around_ts)
        row = w.loc[w["close"].idxmax()] if kind == "high" else w.loc[w["close"].idxmin()]
        return pd.Timestamp(row["datetime"]), int(row["close"])


def _emit(rows, names, code, t, side, qty, px):
    rows.append({"datetime": t, "code": code, "name": names.get(code, code),
                 "side": side, "qty": qty, "price": px})


def generate(
    codes: list[str] | None = None,
    seed: int = 7,
    config: Config | None = None,
    scenario: str = "all",
    save: bool = True,
) -> pd.DataFrame:
    config = config or Config()
    rng = random.Random(seed)
    names = _load_names()
    book = _Book(config)

    candidate = codes or ["000020", "000040", "000050", "000070", "000080", "000100", "000120", "000150"]
    codes = [c for c in candidate if config.has_min1(c)]
    if len(codes) < 4:
        raise RuntimeError(f"min1 데이터가 있는 종목이 부족합니다: {codes}")

    rows: list[dict] = []

    def buy(code, ts, amount):
        t, px = book.at_or_after(code, ts)
        qty = max(1, round(amount / px))
        _emit(rows, names, code, t, "BUY", qty, px)
        return t, px, qty

    def buy_at(code, ts, px, amount):
        qty = max(1, round(amount / px))
        _emit(rows, names, code, ts, "BUY", qty, px)
        return qty

    def sell(code, ts, qty):
        t, px = book.at_or_after(code, ts)
        _emit(rows, names, code, t, "SELL", qty, px)
        return t, px

    def quick_trip(code, entry_ts, amount, sign, hold_min):
        bt, bpx, qty = buy(code, entry_ts, amount)
        xt, _ = book.quick_exit(code, bt, bpx, sign, hold_min)
        sell(code, xt, qty)
        return bt, xt

    do_all = scenario == "all"

    # ── 처분효과 ────────────────────────────────────────────────────
    if scenario in ("all", "disposition"):
        base = pd.Timestamp("2026-04-06 09:30:00")
        losers = codes[:3]
        loser_state = {}
        # 손실 종목: 각 종목 고점에 진입 → 이후 평가손실로 남김
        for i, code in enumerate(losers):
            et, epx = book.pick_extreme_entry(code, base + pd.Timedelta(days=i), 5, "high")
            q = buy_at(code, et, epx, 5_000_000)
            loser_state[code] = (et, q)

        # 수익 종목: 저점 진입 → 빠르게 익절 (보유 중 손실종목이 평가손실로 깔림)
        winners = codes[3:] or codes[:3]
        for k in range(12):
            code = winners[k % len(winners)]
            around = base + pd.Timedelta(days=2 + k * 2)
            et, epx = book.pick_extreme_entry(code, around, 2, "low")
            qty = buy_at(code, et, epx, 2_500_000)
            xt, _ = book.quick_exit(code, et, epx, "win", horizon_min=180, thr=0.01)
            sell(code, xt, qty)

        # 손실 종목 1개만 한참 뒤 손절(오래 보유), 나머지는 미청산(평가손실 유지)
        c0, (et0, q0) = losers[0], loser_state[losers[0]]
        sell(c0, et0 + pd.Timedelta(days=30), q0)

    # ── 리벤지 트레이딩 ────────────────────────────────────────────
    if scenario in ("all", "revenge"):
        rbase = pd.Timestamp("2026-05-11 09:40:00")
        for k in range(4):
            a, b = codes[k % len(codes)], codes[(k + 3) % len(codes)]
            day = rbase + pd.Timedelta(days=k * 2)
            _, xt = quick_trip(a, day, 3_000_000, "loss", hold_min=60)
            gap = rng.randint(8, 20)
            sign = "loss" if k % 2 == 0 else "win"
            quick_trip(b, xt + pd.Timedelta(minutes=gap), 6_000_000, sign, hold_min=120)

    # ── 과매매 ──────────────────────────────────────────────────────
    if scenario in ("all", "overtrading"):
        obase = pd.Timestamp("2026-06-02 09:10:00")
        for k in range(26):
            code = codes[k % len(codes)]
            entry = obase + pd.Timedelta(days=k % 12, hours=rng.randint(0, 4), minutes=rng.randint(0, 55))
            quick_trip(code, entry, 1_500_000, rng.choice(["win", "loss"]), hold_min=rng.randint(10, 40))

    df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["datetime"])

    if save:
        out = config.min1_dir.parent / "dummy_trades.csv"
        df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    df = generate()
    print(f"생성된 거래 {len(df)}건")
    print(df.head(20).to_string())
