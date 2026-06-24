"""Export hybrid-agent reports for the web demo.

The original three agents are left untouched. This exporter runs the two new
hybrid agents and writes static JSON that the Next.js app can import at build
time.

    python -m hybrid_web_export
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from hybrid_agents import EntryErrorPsychHybridAgent, StopLossPsychHybridAgent
from hybrid_agents.psych_split import ENTRY_ERROR_ASSIGNMENTS, STOP_LOSS_ASSIGNMENTS
from psych_agent.config import Config
from psych_agent.dummy_data import generate

SCENARIOS = ["all", "revenge", "disposition"]
LABELS = {
    "all": "혼합",
    "revenge": "리벤지 중심",
    "disposition": "처분효과 중심",
}

SEVERITY_SCORE = {"none": 0.0, "weak": 33.33, "moderate": 66.67, "strong": 100.0}


def _web_data_dir(config: Config) -> Path:
    return config.min1_dir.parents[2] / "web" / "src" / "data"


def _finding(report: dict, type_key: str) -> dict:
    for item in report["findings"]:
        if item["type"] == type_key:
            return item
    raise KeyError(type_key)


def _agent_dict(
    agent_id: str,
    base_agent_id: str,
    assignment,
    finding: dict,
    summary: str,
    recommendations: list[str],
) -> dict:
    return {
        "agent_id": agent_id,
        "base_agent_id": base_agent_id,
        "score": SEVERITY_SCORE[finding["severity"]],
        "severity": finding["severity"],
        "summary": summary,
        "psych_assignments": [asdict(assignment)],
        "findings": [finding],
        "recommendations": recommendations,
    }


def build_from_existing_web_json(scenario: str, config: Config) -> dict:
    """Fallback for workspaces that do not have the gitignored min1 data."""
    data_dir = _web_data_dir(config)
    source = scenario if scenario != "all" else "all"
    report = json.loads((data_dir / f"{source}.json").read_text(encoding="utf-8"))

    revenge = _finding(report, "revenge")
    disposition_source = "disposition" if scenario == "revenge" else source
    disposition_report = json.loads(
        (data_dir / f"{disposition_source}.json").read_text(encoding="utf-8")
    )
    disposition = _finding(disposition_report, "disposition")

    return {
        "scenario": scenario,
        "label": LABELS[scenario],
        "agents": [
            _agent_dict(
                "entry_error_psych_hybrid",
                "entry_error",
                ENTRY_ERROR_ASSIGNMENTS[0],
                revenge,
                "진입 의사결정 오류와 결합된 리벤지 신호를 확인합니다.",
                ["손실 직후 일정 시간 신규 진입을 차단하는 쿨다운 규칙을 둔다."],
            ),
            _agent_dict(
                "stop_loss_psych_hybrid",
                "stop_loss_failure",
                STOP_LOSS_ASSIGNMENTS[0],
                disposition,
                "손절 실패와 결합된 처분효과 신호를 확인합니다.",
                [
                    "진입과 동시에 손절 가격과 시간 제한을 기록하고 예외 조건을 미리 정한다.",
                    "수익 포지션 청산 전 손실 포지션의 보유 사유를 먼저 점검한다.",
                ],
            ),
        ],
        "discarded_psych_features": [
            {
                "type": "overtrading",
                "label": "과매매",
                "reason": "거래 빈도와 습관 문제라 진입오류/손절실패 중 하나에 강제로 붙이지 않음.",
            }
        ],
    }


def build(scenario: str, config: Config) -> dict:
    try:
        df = generate(scenario=scenario, config=config, save=False)
    except RuntimeError:
        return build_from_existing_web_json(scenario, config)

    entry = EntryErrorPsychHybridAgent(config).analyze_df(df).to_dict()
    stop = StopLossPsychHybridAgent(config).analyze_df(df).to_dict()

    return {
        "scenario": scenario,
        "label": LABELS[scenario],
        "agents": [entry, stop],
        "discarded_psych_features": [
            {
                "type": "overtrading",
                "label": "과매매",
                "reason": "거래 빈도와 습관 문제라 진입오류/손절실패 중 하나에 강제로 붙이지 않음.",
            }
        ],
    }


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out_dir = Path(argv[0]) if argv else _web_data_dir(Config())
    out_dir.mkdir(parents=True, exist_ok=True)

    config = Config()
    index = []
    for scenario in SCENARIOS:
        rec = build(scenario, config)
        (out_dir / f"hybrid_{scenario}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        index.append({"scenario": scenario, "label": LABELS[scenario]})
        agent_summary = ", ".join(
            f"{agent['agent_id']}={agent['severity']}" for agent in rec["agents"]
        )
        print(f"  hybrid_{scenario}.json ({agent_summary})")

    (out_dir / "hybrid_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[hybrid export complete -> {out_dir}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
