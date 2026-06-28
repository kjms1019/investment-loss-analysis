"""준모 심리·과매매 에이전트 CLI.

사용 예:
  # 더미 데이터 생성 후 분석 (키 없으면 템플릿 진단으로 그대로 구동)
  python -m psych_agent.run --demo

  # 직접 만든 거래내역 CSV(datetime,code,name,side,qty,price) 분석
  python -m psych_agent.run --trades path/to/trades.csv

  # 결과 JSON 저장
  python -m psych_agent.run --demo --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from .agent import PsychAgent
from .config import Config
from .dummy_data import generate
from .schema import TypeFinding

_SEV_BADGE = {"strong": "🔴 강", "moderate": "🟠 중", "weak": "🟡 약", "none": "⚪ 없음"}


def _print_report(report, df: pd.DataFrame) -> None:
    print("=" * 70)
    print("  준모 · 심리/과매매 매매 복기 리포트  (\"왜 잃었지?\")")
    print("=" * 70)
    print(f"분석 대상 거래 {len(df)}건 | 기간 {df['datetime'].min():%Y-%m-%d} ~ {df['datetime'].max():%Y-%m-%d}")
    print()

    print("── 유형별 팩트 ──────────────────────────────────────────────────────")
    for f in report.findings:  # type: TypeFinding
        print(f"\n▸ {f.type_label}  [{_SEV_BADGE.get(f.severity, f.severity)}]")
        print(f"  근거: {f.reference}")
        for line in f.evidence:
            print(f"   · {line}")
        if not f.evidence:
            print("   · (유의 신호 없음)")

    print()
    print("── 진단 ─────────────────────────────────────────────────────────────")
    diag = report.diagnosis
    print(f"[엔진: {diag.get('engine')}]")
    if diag.get("headline"):
        print(diag["headline"])
        print()
    print(diag.get("body", ""))
    if diag.get("llm_error"):
        print(f"\n(LLM 호출 실패 → 템플릿 폴백: {diag['llm_error']})")
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="준모 심리·과매매 분석 에이전트")
    p.add_argument("--demo", action="store_true", help="실 min1 기반 더미 거래내역 생성 후 분석")
    p.add_argument("--trades", type=str, help="거래내역 CSV 경로 (datetime,code,name,side,qty,price)")
    p.add_argument("--scenario", choices=["all", "revenge", "overtrading", "disposition"],
                   default="all", help="더미 시나리오 (기본 all)")
    p.add_argument("--seed", type=int, default=7, help="더미 생성 시드")
    p.add_argument("--json", type=str, help="결과 JSON 저장 경로")
    p.add_argument("--no-llm", action="store_true", help="LLM 비활성화(템플릿만)")
    args = p.parse_args(argv)

    config = Config()
    if args.no_llm:
        config.use_llm = False

    if args.trades:
        df = pd.read_csv(args.trades)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["code"] = df["code"].astype(str).str.zfill(6)
    elif args.demo:
        df = generate(seed=args.seed, config=config, scenario=args.scenario)
        print(f"[더미 거래내역 {len(df)}건 생성 (scenario={args.scenario}) → analysis/data/dummy_trades.csv]\n")
    else:
        p.error("--demo 또는 --trades 중 하나가 필요합니다.")
        return 2

    agent = PsychAgent(config)
    report = agent.analyze_df(df)
    _print_report(report, df)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)
        print(f"[결과 JSON 저장: {args.json}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
