"""query.py 의 원본 행 + normalizers.py 의 에이전트별 정규화를 조합해
schema.py 의 LossReportItem / LossReportSummary 를 만든다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from . import query
from .normalizers import normalize
from .schema import LossReportItem, LossReportSummary


def build_item(row: Dict[str, Any]) -> LossReportItem:
    result = row.get("result", {})
    narrative, evidence = normalize(row["agent_id"], result)

    decision = result.get("orchestrator_decision") or {}
    prediction = (result.get("learned_classifier") or {}).get("prediction") or {}

    return LossReportItem(
        trade_id=row["trade_id"],
        run_id=row["run_id"],
        code=row.get("code") or "",
        name=row.get("name") or "",
        executed_at=row.get("executed_at"),
        agent_id=row["agent_id"],
        label=result.get("label", ""),
        score=row.get("score"),
        severity=row.get("severity"),
        narrative=narrative,
        evidence=evidence,
        secondary_agent=decision.get("secondary_agent"),
        route_type=decision.get("route_type"),
        routing_confidence=decision.get("confidence"),
        profile_eligible=bool(decision.get("profile_eligible", False)),
        classifier_label=prediction.get("label"),
        classifier_confidence=prediction.get("confidence"),
        classifier_entry_score=prediction.get("entry_error_score"),
        classifier_stop_score=prediction.get("stop_loss_failure_score"),
        raw_result=result,
    )


def build_run_summary(run_id: str, db_path: str = query.DEFAULT_DB_PATH) -> LossReportSummary:
    rows = query.fetch_results_for_run(run_id, db_path=db_path)
    items = [build_item(r) for r in rows]
    return _summarize("run", run_id, items)


def build_user_summary(user_id: str, db_path: str = query.DEFAULT_DB_PATH) -> LossReportSummary:
    """user_profile_trade_labels 의 run_id 매핑을 통해 이 user_id 의 전체 run을 합산한다."""
    rows = query.fetch_results_for_user(user_id, db_path=db_path)
    items = [build_item(r) for r in rows]
    return _summarize("user", user_id, items)


def _summarize(scope: str, scope_id: str, items: List[LossReportItem]) -> LossReportSummary:
    count_by_agent: Dict[str, int] = {}
    scored = [i.score for i in items if i.score is not None]
    for item in items:
        count_by_agent[item.agent_id] = count_by_agent.get(item.agent_id, 0) + 1

    return LossReportSummary(
        scope=scope,
        scope_id=scope_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_loss_trades=len(items),
        count_by_agent=count_by_agent,
        avg_score=round(sum(scored) / len(scored), 4) if scored else None,
        items=sorted(items, key=lambda i: i.score or 0.0, reverse=True),
    )
