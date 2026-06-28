"""과매매 검출 (결정/빈도 축).

표준 레퍼런스: Barber & Odean (2000) "Trading Is Hazardous to Your Wealth".
  과매매 그룹의 연 회전율이 약 258%로, 순수익률을 크게 갉아먹는다.

측정 (절대 기준 + 개인 상대 기준 병행):
  · 연 회전율 ≈ 총 매수금액 / 투입자본(기간 중 최대 동시 보유원가) × (365/기간일수).
    투입자본은 계좌 잔고 대신 데이터로 추정한 '최대 동시 deployed capital'.
    250%(2.5배) 이상이면 절대 기준상 과매매 분위.
  · 월별 거래(결정) 건수의 개인 중앙값 대비, 특정 달이 N배 이상이면 집중 과매매월.
"""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schema import Preprocessed, TypeFinding

REFERENCE = "Barber & Odean (2000): 연 회전율 ↑ → 순수익 잠식. 과매매 그룹 ≈ 258%"


def _peak_deployed_capital(pre: Preprocessed) -> float:
    """기간 중 최대 동시 보유원가(이동평균법). 회전율 분모(투입자본) 추정."""
    qty: dict[str, int] = {}
    avg: dict[str, float] = {}
    peak = 0.0
    for t in sorted(pre.trades, key=lambda x: x.datetime):
        q, a = qty.get(t.code, 0), avg.get(t.code, 0.0)
        if t.side == "BUY":
            nq = q + t.qty
            avg[t.code] = (a * q + t.amount) / nq if nq else 0.0
            qty[t.code] = nq
        elif t.side == "SELL":
            qty[t.code] = max(0, q - t.qty)
            if qty[t.code] == 0:
                avg[t.code] = 0.0
        deployed = sum(avg[c] * qty[c] for c in qty)
        peak = max(peak, deployed)
    return peak


def detect_overtrading(pre: Preprocessed, config: Config | None = None) -> TypeFinding:
    config = config or Config()
    trades = sorted(pre.trades, key=lambda t: t.datetime)
    if not trades:
        return TypeFinding(
            "overtrading", "과매매", False, "none",
            {"reason": "no trades"}, [], REFERENCE,
        )

    t0, t1 = trades[0].datetime, trades[-1].datetime
    period_days = max((t1 - t0).total_seconds() / 86400.0, 1.0)

    total_buy_value = sum(t.amount for t in trades if t.side == "BUY")
    peak_capital = _peak_deployed_capital(pre)
    annual_turnover = (
        (total_buy_value / peak_capital) * (365.0 / period_days)
        if peak_capital
        else 0.0
    )

    # 월별 거래(결정) 건수
    months = pd.Series([t.datetime.to_period("M") for t in trades])
    monthly_counts = months.value_counts().sort_index()
    median_monthly = float(monthly_counts.median())
    max_month = monthly_counts.idxmax()
    max_month_count = int(monthly_counts.max())
    freq_multiple = (max_month_count / median_monthly) if median_monthly else 0.0

    turnover_flag = annual_turnover >= config.overtrade_annual_turnover
    freq_flag = freq_multiple >= config.overtrade_freq_multiple

    if turnover_flag and freq_flag:
        severity = "strong"
    elif turnover_flag:
        severity = "moderate"
    elif freq_flag:
        severity = "weak"
    else:
        severity = "none"

    evidence = [
        f"연 환산 회전율 ≈ {annual_turnover * 100:.0f}% "
        f"(절대 임계 {config.overtrade_annual_turnover * 100:.0f}%"
        f"{' 초과' if turnover_flag else ' 이내'})",
        f"총 거래 {len(trades)}건 / {period_days:.0f}일, "
        f"월 거래 중앙값 {median_monthly:.0f}건",
    ]
    if freq_flag:
        evidence.append(
            f"{max_month} 월 {max_month_count}건 = 평소의 {freq_multiple:.1f}배 (집중 과매매월)"
        )

    return TypeFinding(
        type_key="overtrading",
        type_label="과매매",
        detected=turnover_flag or freq_flag,
        severity=severity,
        metrics={
            "annual_turnover": round(annual_turnover, 3),
            "annual_turnover_pct": round(annual_turnover * 100, 1),
            "threshold_pct": config.overtrade_annual_turnover * 100,
            "total_trades": len(trades),
            "period_days": round(period_days, 1),
            "total_buy_value": int(total_buy_value),
            "peak_deployed_capital": int(peak_capital),
            "median_monthly_trades": median_monthly,
            "busiest_month": str(max_month),
            "busiest_month_trades": max_month_count,
            "freq_multiple": round(freq_multiple, 2),
        },
        evidence=evidence,
        reference=REFERENCE,
    )
