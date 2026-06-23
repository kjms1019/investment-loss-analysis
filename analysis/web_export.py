"""웹 데모용 파이프라인 출력 익스포트 (손실선별 → 심리 귀속 라우팅).

각 시나리오로 더미 거래 생성 → pipeline.run → 대시보드용 JSON 저장.
psych_agent.export_web(계좌 전체 패턴)과 달리, 이건 '손실거래별 라우팅' 뷰.

  python -m web_export            # web/src/data 에 flow_*.json 저장
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from psych_agent.config import Config
from psych_agent.diagnose import _CORRECTION
from psych_agent.dummy_data import generate
from psych_agent.focus import cycle_id

from pipeline import run

SCENARIOS = ["all", "revenge", "overtrading", "disposition"]
LABELS = {"all": "혼합 (현실적)", "revenge": "리벤지", "overtrading": "과매매", "disposition": "처분효과"}
TYPES = ["revenge", "overtrading", "disposition"]


def build(scenario: str, config: Config) -> dict:
    df = generate(scenario=scenario, config=config, save=False)
    result = run(df, config)
    screened, attrs = result["screened"], result["attributions"]
    score_by_id = {cycle_id(s.code, s.entry_time): s for s in screened.scores}
    summ = screened.summary()

    routing = {t: 0 for t in TYPES}
    routing["other"] = 0
    losses = []
    for a in attrs:
        routing[a.dominant if a.dominant else "other"] += 1
        sc = score_by_id.get(cycle_id(a.code, a.entry_time))
        signals = {}
        for t in TYPES:
            sig = getattr(a, t)
            signals[t] = {"score": round(sig.score, 1), "evidence": sig.evidence}
        losses.append({
            "code": a.code, "name": a.name, "entry_time": a.entry_time,
            "return_pct": a.return_pct,
            "r_mkt_pct": round(sc.r_mkt * 100, 2) if sc and sc.r_mkt is not None else None,
            "alpha_pct": round(sc.alpha * 100, 2) if sc and sc.alpha is not None else None,
            "tier": sc.tier if sc else None,
            "holding_min": a.holding_min,
            "dominant": a.dominant,
            "signals": signals,
            "correction": _CORRECTION[a.dominant].format(window=config.revenge_window_min) if a.dominant else "",
        })

    return {
        "scenario": scenario,
        "label": LABELS[scenario],
        "screening": {
            "closed": summ["closed_trades"],
            "tier1": summ["tier1"],
            "tier2": summ["tier2"],
            "market_driven_excluded": summ["market_driven_losses"],
            "selected": len(screened.selected),
        },
        "routing": routing,
        "losses": losses,
    }


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out_dir = Path(argv[0]) if argv else Config().min1_dir.parents[2] / "web" / "src" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = Config()
    index = []
    for sc in SCENARIOS:
        rec = build(sc, config)
        (out_dir / f"flow_{sc}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"scenario": sc, "label": LABELS[sc]})
        print(f"  ✓ flow_{sc}.json  (복기대상 {rec['screening']['selected']}, 라우팅 {rec['routing']})")

    (out_dir / "flow_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[익스포트 완료 → {out_dir}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
