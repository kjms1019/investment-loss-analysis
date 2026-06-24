"""에이전트 어댑터 레지스트리.

각 에이전트를 오케스트레이터 인터페이스에 연결한다.
common/adapters.py의 출력 변환을 활용해 AgentResult 형식을 통일한다.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .router import AGENT_ENTRY_ERROR, AGENT_PSYCH, AGENT_STOP_LOSS_FAILURE
from .schema import AgentResult

# 프로젝트 루트를 sys.path에 추가 (각 에이전트 디렉토리 import용)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENTRY_ERROR_DIR = _PROJECT_ROOT / "entry-error-agent"
_STOP_FAIL_DIR   = _PROJECT_ROOT / "손절실패"

for _p in [str(_PROJECT_ROOT), str(_ENTRY_ERROR_DIR), str(_STOP_FAIL_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


class AgentAdapter:
    agent_id: str = "base"

    def run(self, run_id: str, trade_id: str, cycle_data: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


# ──────────────────────────────────────────────
# 수빈: 진입오류 에이전트
# ──────────────────────────────────────────────

class EntryErrorAdapter(AgentAdapter):
    agent_id = AGENT_ENTRY_ERROR

    def run(self, run_id: str, trade_id: str, cycle_data: Dict[str, Any]) -> AgentResult:
        try:
            from src.feature_engineering import build_feature_result
            from src.min1_classifier import classify_min1_market_state
            from src.min1_labeler import classify_min1_entry_labels, score_min1_labels

            feature_result = build_feature_result(cycle_data)
            state_result   = classify_min1_market_state(feature_result)
            labels         = classify_min1_entry_labels(feature_result, state_result)
            risk            = score_min1_labels(labels)

            triggered = [l for l in labels if l.get("triggered") and l["label_id"] not in (
                "normal_entry", "insufficient_data", "low_confidence",
                "raw_data_absent", "pre_entry_history_short", "feature_missing_or_invalid",
            )]
            top_label = triggered[0]["label_id"] if triggered else "normal_entry"
            raw_score = risk.get("entry_error_risk_score", 0)

            return AgentResult(
                run_id=run_id,
                trade_id=trade_id,
                agent_id=self.agent_id,
                output_status="ok",
                score=round(raw_score / 100, 4),
                severity=risk.get("severity"),
                route_reason="",
                result={
                    "label": top_label,
                    "risk_score_result": risk,
                    "state_classification": state_result,
                    "label_results": labels,
                },
            )
        except Exception as e:
            return _error_result(run_id, trade_id, self.agent_id, e)


# ──────────────────────────────────────────────
# 영현: 손절실패 에이전트
# ──────────────────────────────────────────────

class StopFailAdapter(AgentAdapter):
    agent_id = AGENT_STOP_LOSS_FAILURE

    def run(self, run_id: str, trade_id: str, cycle_data: Dict[str, Any]) -> AgentResult:
        try:
            from agent import analyze_real
            from schema import Transaction

            transactions = [Transaction(**t) for t in cycle_data.get("transactions", [])]
            reports = analyze_real(transactions)
            report  = reports[0] if reports else {}

            return AgentResult(
                run_id=run_id,
                trade_id=trade_id,
                agent_id=self.agent_id,
                output_status="ok",
                score=round(float(report.get("score", 0.0)), 4),
                severity=_score_to_severity(report.get("score", 0.0)),
                route_reason="",
                result={
                    "label": report.get("judgment_type", "해당없음"),
                    "narrative": report.get("narrative", ""),
                    "signals": report.get("signals", {}),
                    "flags": report.get("flags", {}),
                },
            )
        except Exception as e:
            return _error_result(run_id, trade_id, self.agent_id, e)


# ──────────────────────────────────────────────
# 준모: 심리 에이전트
# ──────────────────────────────────────────────

class PsychAdapter(AgentAdapter):
    agent_id = AGENT_PSYCH

    def run(self, run_id: str, trade_id: str, cycle_data: Dict[str, Any]) -> AgentResult:
        try:
            import pandas as pd
            from psych_agent.agent import run as psych_run
            from common.schema import severity_to_score

            df = pd.DataFrame(cycle_data.get("trades", []))
            df["datetime"] = pd.to_datetime(df["datetime"])
            report_obj = psych_run(df)
            report     = report_obj.to_dict()

            findings  = report.get("findings", [])
            detected  = [f for f in findings if f.get("detected")]
            top       = max(detected, key=lambda f: severity_to_score(f.get("severity", "none")), default={})
            score     = severity_to_score(top.get("severity", "none"))
            label     = top.get("type", "none")
            summary   = report.get("diagnosis", {}).get("summary", "")

            return AgentResult(
                run_id=run_id,
                trade_id=trade_id,
                agent_id=self.agent_id,
                output_status="ok",
                score=score,
                severity=top.get("severity", "none"),
                route_reason="",
                result={
                    "label": label,
                    "summary": summary,
                    "findings": findings,
                },
            )
        except Exception as e:
            return _error_result(run_id, trade_id, self.agent_id, e)


# ──────────────────────────────────────────────
# 레지스트리
# ──────────────────────────────────────────────

class AgentRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter) -> None:
        self._adapters[adapter.agent_id] = adapter

    def get(self, agent_id: str) -> Optional[AgentAdapter]:
        return self._adapters.get(agent_id)


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(EntryErrorAdapter())
    registry.register(StopFailAdapter())
    registry.register(PsychAdapter())
    return registry


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _error_result(run_id: str, trade_id: str, agent_id: str, exc: Exception) -> AgentResult:
    return AgentResult(
        run_id=run_id,
        trade_id=trade_id,
        agent_id=agent_id,
        output_status="error",
        score=None,
        severity=None,
        route_reason="",
        result={"error": str(exc)},
    )


def _score_to_severity(score: float) -> str:
    if score >= 0.7:
        return "strong"
    if score >= 0.4:
        return "moderate"
    if score >= 0.1:
        return "weak"
    return "none"
