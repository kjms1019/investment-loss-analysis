"""오케스트레이션 데모: 손실 선별 → 심리 유형 귀속 → (라우팅) 진단.

흐름:
  전체거래 ─preprocess─► 사이클
        ├─ screener.score_cycles : α 기준 손실 선별 (복기 대상)
        └─ psych.focus.attribute_losses : 각 손실거래에 리벤지/과매매/처분효과 귀속
  → 각 손실거래의 dominant 유형이 곧 '어느 에이전트로 보낼지'(다중분류기 자리).

실제 시스템에선 진입오류/손절실패 에이전트도 후보지만, 여기선 심리 3유형으로
귀속 데모만 보인다. 진입/손절 분류는 각 담당 에이전트의 신호와 합쳐 결정.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from psych_agent.config import Config
from psych_agent.dummy_data import generate
from psych_agent.focus import attribute_losses, cycle_id
from psych_agent.preprocess import preprocess, trades_from_df
from psych_agent.prices import PriceLookup
from psych_agent.diagnose import _CORRECTION  # 유형별 교정 템플릿 재사용

from loss_screener.market_index import MarketIndex
from loss_screener.screener import score_cycles

TYPE_KR = {"revenge": "리벤지 트레이딩", "overtrading": "과매매", "disposition": "처분효과", None: "기타(비심리)"}


def run(trades, config: Config | None = None) -> dict:
    config = config or Config()
    if not isinstance(trades, list):
        trades = trades_from_df(trades)

    # 1) 전체 거래 1회 전처리 (screener·psych 공유)
    pre = preprocess(trades, config)
    market = MarketIndex(config)
    prices = PriceLookup(config)

    # 2) 손실 선별 (시장 제거 α 기준)
    screened = score_cycles(pre, market, prices)

    # 3) 선별된 손실거래 ↔ 사이클 매칭
    cyc_by_id = {cycle_id(c.code, c.entry_time): c for c in pre.closed_cycles}
    focus_cycles = [
        cyc_by_id[cycle_id(ts.code, ts.entry_time)]
        for ts in screened.selected
        if cycle_id(ts.code, ts.entry_time) in cyc_by_id
    ]

    # 4) 각 손실거래에 심리 유형 귀속
    attributions = attribute_losses(pre, focus_cycles, config)

    return {"pre": pre, "screened": screened, "attributions": attributions}


def _fmt_pct(x):
    return "  —  " if x is None else f"{x * 100:+6.2f}%"


def _print(result: dict) -> None:
    screened = result["screened"]
    attrs = result["attributions"]
    score_by_id = {cycle_id(s.code, s.entry_time): s for s in screened.scores}

    print("=" * 88)
    print('  오케스트레이션 데모 · 손실 선별 → 심리 유형 귀속 ("왜 잃었지?")')
    print("=" * 88)
    s = screened.summary()
    print(f"청산 {s['closed_trades']}건 → 복기대상 {len(screened.selected)}건 "
          f"(1순위 {s['tier1']}, 2순위 {s['tier2']}, 시장탓 제외 {s['market_driven_losses']})\n")

    # 라우팅 집계
    tally: dict = {}
    for a in attrs:
        tally[a.dominant] = tally.get(a.dominant, 0) + 1
    print("── 라우팅 집계 (손실거래 → 심리 유형) ──────────────────────────────────────")
    for k in ["revenge", "overtrading", "disposition", None]:
        if tally.get(k):
            print(f"   {TYPE_KR[k]:<14} {tally[k]}건")
    print()

    print("── 손실거래별 귀속 진단 ─────────────────────────────────────────────────────")
    for i, a in enumerate(attrs, 1):
        sc = score_by_id.get(cycle_id(a.code, a.entry_time))
        alpha = _fmt_pct(sc.alpha) if sc else "  —  "
        mkt = _fmt_pct(sc.r_mkt) if sc else "  —  "
        hold = (f"{a.holding_min:.0f}분" if a.holding_min and a.holding_min < 1440
                else (f"{a.holding_min / 1440:.1f}일" if a.holding_min else "—"))
        print(f"\n[{i}] {a.name}  실현 {a.return_pct:+.2f}% | 시장 {mkt} | α {alpha} | 보유 {hold}")
        print(f"     → 심리 유형: {TYPE_KR[a.dominant]}"
              + (f"  (점수 R{a.revenge.score:.0f}/O{a.overtrading.score:.0f}/D{a.disposition.score:.0f})"
                 if a.dominant else ""))
        for sig_key in ["revenge", "overtrading", "disposition"]:
            sig = getattr(a, sig_key)
            for ev in sig.evidence:
                mark = "▸" if sig_key == a.dominant else "·"
                print(f"        {mark} [{TYPE_KR[sig_key]}] {ev}")
        if a.dominant:
            corr = _CORRECTION[a.dominant].format(window=Config().revenge_window_min)
            print(f"        ✎ 교정: {corr}")

    print("\n해설: dominant = 그 손실을 가장 잘 설명하는 심리 유형(= 다중분류기가 보낼 곳).")
    print("      α(시장 제거 초과수익)로 '네 탓 손실'만 추린 뒤, 그 원인을 심리로 귀속함.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="손실 선별 → 심리 귀속 파이프라인")
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

    _print(run(df, config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
