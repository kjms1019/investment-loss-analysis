"""웹 데모용 리포트 JSON 익스포트.

각 시나리오로 더미 거래를 생성→분석하고, 대시보드가 바로 쓸 수 있는
풍부한 JSON(요약/팩트/진단/거래 미리보기)을 지정 폴더에 떨군다.

사용:
  python -m psych_agent.export_web ../web/data
  (인자 없으면 프로젝트 루트의 web/src/data 로 저장)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from .agent import PsychAgent
from .config import Config
from .dummy_data import generate

SCENARIOS = ["all", "revenge", "overtrading", "disposition"]
LABELS = {
    "all": "혼합 (현실적)",
    "revenge": "리벤지 트레이딩",
    "overtrading": "과매매",
    "disposition": "처분효과",
}


def build(scenario: str, config: Config) -> dict:
    df = generate(scenario=scenario, config=config, save=False)
    agent = PsychAgent(config)
    report = agent.analyze_df(df)
    pre = report.preprocessed

    closed = pre.closed_cycles
    record = report.to_dict()
    record["scenario"] = scenario
    record["label"] = LABELS[scenario]
    record["summary"] = {
        "trade_count": int(len(df)),
        "period_start": str(df["datetime"].min().date()),
        "period_end": str(df["datetime"].max().date()),
        "cycle_count": len(pre.cycles),
        "closed_cycle_count": len(closed),
        "win_count": sum(1 for c in closed if c.is_win),
        "loss_count": sum(1 for c in closed if not c.is_win),
        "total_realized_pnl": int(sum(c.realized_pnl for c in closed)),
    }
    # 사이클(라운드트립) 미리보기 — 차트/타임라인용
    record["cycles"] = [
        {
            "code": c.code,
            "name": c.name,
            "entry_time": str(c.entry_time),
            "exit_time": str(c.exit_time) if c.exit_time else None,
            "invested": c.invested,
            "realized_pnl": round(c.realized_pnl, 0),
            "return_pct": round(c.return_pct * 100, 2),
            "holding_min": round(c.holding_minutes, 1) if c.holding_minutes is not None else None,
            "closed": c.closed,
            "is_win": c.is_win,
        }
        for c in sorted(pre.cycles, key=lambda x: x.entry_time)
    ]
    return record


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv:
        out_dir = Path(argv[0])
    else:
        out_dir = Config().min1_dir.parents[1] / "web" / "src" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = Config()
    index = []
    for sc in SCENARIOS:
        rec = build(sc, config)
        (out_dir / f"{sc}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index.append({"scenario": sc, "label": LABELS[sc]})
        print(f"  ✓ {sc}.json  ({rec['summary']['trade_count']} trades)")

    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[익스포트 완료 → {out_dir}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
