from datetime import date
from typing import Optional
from schema import Cycle, OHLCV
from config import Config, DEFAULT_CONFIG


def _compute_atr(ohlcv_days: list, period: int) -> Optional[float]:
    """Wilder's ATR (RMA smoothing). Seeds with the first `period` TRs' SMA,
    then applies ATR_t = (ATR_{t-1} * (period-1) + TR_t) / period.
    Falls back to a plain mean when there aren't enough bars."""
    if len(ohlcv_days) < 2:
        return None
    trs = []
    for i in range(1, len(ohlcv_days)):
        prev_close = ohlcv_days[i - 1].close
        h, l = ohlcv_days[i].high, ohlcv_days[i].low
        trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
    if not trs:
        return None
    if len(trs) < period:
        return sum(trs) / len(trs)

    atr = sum(trs[:period]) / period          # seed = SMA of first `period` TRs
    for tr in trs[period:]:                    # Wilder recursive smoothing
        atr = (atr * (period - 1) + tr) / period
    return atr


def _determine_stop_line(
    cycle: Cycle,
    pre_entry_ohlcv: list,
    user_stop_pct: Optional[float],
    config: Config,
) -> tuple:
    """Returns (stop_pct, method). Priority: user → ATR → fixed."""
    if user_stop_pct is not None:
        return user_stop_pct, "user"
    atr = _compute_atr(pre_entry_ohlcv, config.atr_period)
    if atr is not None and cycle.avg_buy_price > 0:
        stop_pct = -(config.atr_k * atr / cycle.avg_buy_price) * 100
        return stop_pct, "atr"
    return config.fixed_stop_pct, "fixed"


def _latest_avg_cost(cost_checkpoints: list, day_date: date) -> float:
    """Most recent checkpoint on or before day_date."""
    result = cost_checkpoints[0][1]
    for checkpoint_date, avg_cost in cost_checkpoints:
        if checkpoint_date <= day_date:
            result = avg_cost
        else:
            break
    return result


def _scan_daily(holding_days: list, cost_checkpoints: list, stop_pct: float) -> tuple:
    """
    일봉 저가 기준 MAE·이탈일 계산 (분봉 없을 때 폴백).
    Returns (MAE, breach_date).
    """
    MAE = 0.0
    breach_date: Optional[date] = None
    for day in holding_days:
        avg = _latest_avg_cost(cost_checkpoints, day.date)
        if avg <= 0:
            continue
        unreal = (day.low - avg) / avg * 100
        MAE = min(MAE, unreal)
        if breach_date is None and unreal <= stop_pct:
            breach_date = day.date
    return MAE, breach_date


def _scan_minute(minute_df, holding_date_range: tuple, cost_checkpoints: list, stop_pct: float) -> tuple:
    """
    분봉 low 기준 정밀 MAE·이탈일 계산.
    minute_df: load_minute_df() 반환값 (pandas DataFrame).
    Returns (MAE, breach_date) — breach_date는 여전히 date 단위.
    """
    entry_dt, exit_dt = holding_date_range
    mask = (
        (minute_df["datetime"].dt.date >= entry_dt) &
        (minute_df["datetime"].dt.date <= exit_dt)
    )
    holding = minute_df[mask]
    if holding.empty:
        return None, None   # caller falls back to daily

    MAE = 0.0
    breach_date: Optional[date] = None
    for row in holding.itertuples(index=False):
        day_date = row.datetime.date()
        avg = _latest_avg_cost(cost_checkpoints, day_date)
        if avg <= 0:
            continue
        unreal = (row.low - avg) / avg * 100
        MAE = min(MAE, unreal)
        if breach_date is None and unreal <= stop_pct:
            breach_date = day_date
    return MAE, breach_date


def attach_path_features(
    cycle: Cycle,
    all_ohlcv: list,
    user_stop_pct: Optional[float] = None,
    config: Config = DEFAULT_CONFIG,
    minute_df=None,  # pd.DataFrame | None — 분봉 있으면 MAE 정밀도 향상
) -> Cycle:
    """
    MAE, breach_date, delay_days를 계산해 cycle에 붙인다.

    해상도 우선순위:
      분봉 DataFrame 있음 → 분봉 low 기준 MAE (정밀)
      없음               → 일봉 low 기준 MAE (폴백)
    delay_days는 항상 영업일(일봉 기준) 단위.
    """
    ticker_ohlcv = sorted(
        [d for d in all_ohlcv if d.ticker == cycle.ticker],
        key=lambda x: x.date,
    )
    holding_days = [d for d in ticker_ohlcv if cycle.entry_ts <= d.date <= cycle.exit_ts]
    pre_entry_days = [d for d in ticker_ohlcv if d.date < cycle.entry_ts]

    stop_pct, stop_method = _determine_stop_line(cycle, pre_entry_days, user_stop_pct, config)
    cycle.stop_pct = stop_pct
    cycle.stop_method = stop_method

    # 분봉 레이어 시도 → 실패 시 일봉 폴백
    MAE, breach_date = None, None
    if minute_df is not None and not minute_df.empty:
        MAE, breach_date = _scan_minute(
            minute_df,
            (cycle.entry_ts, cycle.exit_ts),
            cycle.cost_checkpoints,
            stop_pct,
        )

    if MAE is None:  # 분봉 없거나 빈 구간 → 일봉 폴백
        MAE, breach_date = _scan_daily(holding_days, cycle.cost_checkpoints, stop_pct)

    cycle.MAE_pct = MAE
    cycle.breached = breach_date is not None
    cycle.breach_date = breach_date

    holding_dates = [d.date for d in holding_days]
    if breach_date is not None and breach_date in holding_dates:
        breach_idx = holding_dates.index(breach_date)
        cycle.delay_days = len(holding_dates) - 1 - breach_idx
    else:
        cycle.delay_days = 0

    return cycle
