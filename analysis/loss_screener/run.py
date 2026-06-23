"""손실 거래 선별기 데모 CLI.

  python -m loss_screener.run --demo            # 더미 거래 생성 후 선별
  python -m loss_screener.run --trades t.csv    # 실제 거래내역 선별
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from psych_agent.config import Config
from psych_agent.dummy_data import generate

from .screener import ScreenResult, screen_trades


def _fmt_pct(x):
    return "  —  " if x is None else f"{x * 100:+6.2f}%"


def _print(res: ScreenResult) -> None:
    s = res.summary()
    print("=" * 84)
    print("  오케스트레이션 1단계 · 시장 제거 손실 거래 선별  (\"왜 잃었지?\")")
    print("=" * 84)
    print(
        f"청산 거래 {s['closed_trades']}건 | "
        f"복기대상 1순위(절대손실∧α-) {s['tier1']}건, 2순위(기회손실 α-) {s['tier2']}건 | "
        f"시장탓 손실(선별 제외) {s['market_driven_losses']}건\n"
    )

    print("── 복기 대상 (시장 빼고 유독 못한 순) ───────────────────────────────────────────")
    print(f"{'#':>2} {'tier':>4} {'종목':<10} {'실현':>9} {'단순보유':>8} {'시장':>8} {'초과α':>8} {'타이밍':>8}")
    for i, t in enumerate(res.selected, 1):
        print(
            f"{i:>2} {t.tier:>4} {t.name:<10} {_fmt_pct(t.r_trade)} "
            f"{_fmt_pct(t.r_bh)} {_fmt_pct(t.r_mkt)} {_fmt_pct(t.alpha)} {_fmt_pct(t.timing)}"
        )
    if not res.selected:
        print("  (선별된 복기 대상 없음)")

    print("\n── 선별 제외: 시장 탓 손실 (절대론 손실이나 α≥0 → 시장 따라 빠진 것) ──────────")
    excluded = [t for t in res.scores if t.abs_loss and t.tier == 0]
    for t in excluded[:8]:
        print(
            f"   {t.name:<10} 실현{_fmt_pct(t.r_trade)}  하지만 시장{_fmt_pct(t.r_mkt)} → α{_fmt_pct(t.alpha)} (네 탓 아님)"
        )
    if not excluded:
        print("   (없음)")

    print("\n해설: 초과α = 단순보유 − 시장.  타이밍 = 실현 − 단순보유(체결/타이밍 성분).")
    print("      1순위 거래들이 다중분류기 → 진입/손절/심리 에이전트로 라우팅됩니다.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="시장 제거 손실 거래 선별기")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--trades", type=str)
    p.add_argument("--scenario", default="all")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)

    config = Config()
    if args.trades:
        df = pd.read_csv(args.trades)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["code"] = df["code"].astype(str).str.zfill(6)
    elif args.demo:
        df = generate(seed=args.seed, config=config, scenario=args.scenario, save=False)
        print(f"[더미 거래 {len(df)}건 생성 (scenario={args.scenario})]\n")
    else:
        p.error("--demo 또는 --trades 필요")
        return 2

    res = screen_trades(df, config)
    _print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
