"""시장 제거 손실 거래 선별기.

각 청산 사이클(라운드트립)에 대해 보유구간 기준으로:
  R_bh   = 종목 단순보유 수익률 (진입가→청산가)          ← 종목 자체 성과
  R_mkt  = 합성지수 수익률 (같은 구간)                    ← 시장 성분(제거 대상)
  α(초과)= R_bh − R_mkt                                  ← '시장 빼고 종목 선택이 얼마나 못했나'
  R_trade= 실현 수익률(체결 반영)                         ← 실제 손익
  timing = R_trade − R_bh                                ← 체결/타이밍 성분(단순보유 대비)

선별(복기 대상) 우선순위:
  1순위: 절대손실(realized_pnl<0) ∧ α<0   → α 오름차순(가장 시장대비 못한 것)
  2순위: α<0 이지만 번 거래(realized_pnl≥0) → 기회손실
나머지(시장 탓 손실 / 시장대비 선방)는 '이 사람 매매 실패'로 보지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from psych_agent.config import Config
from psych_agent.preprocess import preprocess, trades_from_df
from psych_agent.prices import PriceLookup
from psych_agent.schema import Preprocessed, Trade

from .market_index import MarketIndex


@dataclass
class TradeScore:
    code: str
    name: str
    entry_time: str
    exit_time: str
    realized_pnl: float
    r_trade: float       # 실현 수익률
    r_bh: float | None   # 단순보유 수익률
    r_mkt: float | None  # 시장(합성지수) 수익률
    alpha: float | None  # 초과수익 R_bh - R_mkt (선택 성분)
    timing: float | None # R_trade - R_bh (체결 성분)
    abs_loss: bool
    tier: int            # 1=절대손실∧α-, 2=기회손실(α-), 0=선별 제외


@dataclass
class ScreenResult:
    scores: list[TradeScore]
    selected: list[TradeScore] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "closed_trades": len(self.scores),
            "tier1": sum(s.tier == 1 for s in self.scores),
            "tier2": sum(s.tier == 2 for s in self.scores),
            "market_driven_losses": sum(
                s.abs_loss and (s.alpha is not None and s.alpha >= 0) for s in self.scores
            ),
        }


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return b / a - 1.0


def cycle_key(code: str, entry_time) -> str:
    """사이클 식별 키 (psych 귀속에서 손실거래 ↔ 사이클 매칭용)."""
    return f"{code}@{entry_time}"


def score_cycles(
    pre: Preprocessed,
    market: MarketIndex,
    prices: PriceLookup,
) -> ScreenResult:
    """이미 preprocess 된 데이터에 대해 사이클별 α/티어 점수만 계산.

    오케스트레이션에서 preprocess 를 1회만 돌리고 screener·psych 가 공유하도록 분리.
    """
    scores: list[TradeScore] = []
    for c in pre.closed_cycles:
        entry_px = prices.price_at(c.code, c.entry_time)
        exit_px = prices.price_at(c.code, c.exit_time)
        r_bh = _pct(entry_px, exit_px)
        r_mkt = market.ret_between(c.entry_time, c.exit_time)
        alpha = (r_bh - r_mkt) if (r_bh is not None and r_mkt is not None) else None
        r_trade = c.return_pct
        timing = (r_trade - r_bh) if r_bh is not None else None
        abs_loss = c.realized_pnl < 0

        if alpha is not None and alpha < 0 and abs_loss:
            tier = 1
        elif alpha is not None and alpha < 0:
            tier = 2
        else:
            tier = 0

        scores.append(
            TradeScore(
                code=c.code, name=c.name,
                entry_time=str(c.entry_time), exit_time=str(c.exit_time),
                realized_pnl=round(c.realized_pnl, 0),
                r_trade=round(r_trade, 4),
                r_bh=round(r_bh, 4) if r_bh is not None else None,
                r_mkt=round(r_mkt, 4) if r_mkt is not None else None,
                alpha=round(alpha, 4) if alpha is not None else None,
                timing=round(timing, 4) if timing is not None else None,
                abs_loss=abs_loss, tier=tier,
            )
        )

    # 우선순위 정렬: tier(1→2) → α 오름차순
    selected = sorted(
        [s for s in scores if s.tier in (1, 2)],
        key=lambda s: (s.tier, s.alpha if s.alpha is not None else 0.0),
    )
    return ScreenResult(scores=scores, selected=selected)


def screen_trades(
    trades: list[Trade] | "pd.DataFrame",  # noqa: F821
    config: Config | None = None,
    market: MarketIndex | None = None,
    prices: PriceLookup | None = None,
) -> ScreenResult:
    config = config or Config()
    if not isinstance(trades, list):
        trades = trades_from_df(trades)
    pre = preprocess(trades, config)
    market = market or MarketIndex(config)
    prices = prices or PriceLookup(config)
    return score_cycles(pre, market, prices)
