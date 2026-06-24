"""Top-level orchestration pipeline skeleton.

Current flow:
CSV ingest -> raw row persistence -> normalized trades -> placeholder routing
-> placeholder agent adapters -> persisted agent results.
"""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from .agent_registry import AgentRegistry, build_default_registry
from .parser import normalize_trade_rows, read_raw_trade_rows
from .router import route_trade
from .schema import CommonFeatureBundle, OrchestratorRunResult
from .storage import DEFAULT_DB_PATH, OrchestratorStorage


def run_orchestrator(
    trade_csv_path: str,
    source_name: str = "user_csv",
    db_path: str = DEFAULT_DB_PATH,
    column_map: Optional[Dict[str, str]] = None,
    feature_bundles_by_trade_id: Optional[Dict[str, CommonFeatureBundle]] = None,
    registry: Optional[AgentRegistry] = None,
) -> OrchestratorRunResult:
    """Run the first orchestration skeleton for one input CSV file."""
    registry = registry or build_default_registry()
    feature_bundles_by_trade_id = feature_bundles_by_trade_id or {}

    batch_id, raw_rows = read_raw_trade_rows(trade_csv_path)
    normalized_trades = normalize_trade_rows(raw_rows, column_map=column_map)
    run_id = str(uuid.uuid4())

    storage = OrchestratorStorage(db_path=db_path)
    agent_results = []
    try:
        storage.create_batch(
            batch_id=batch_id,
            source_name=source_name,
            raw_file_path=trade_csv_path,
            row_count=len(raw_rows),
        )
        storage.insert_raw_rows(raw_rows)
        storage.insert_normalized_trades(normalized_trades)
        storage.create_run(run_id=run_id, batch_id=batch_id)

        for trade in normalized_trades:
            features = feature_bundles_by_trade_id.get(trade.trade_id)
            route_decisions = route_trade(trade, features=features)

            for route in route_decisions:
                adapter = registry.get(route.agent_id)
                if adapter is None:
                    continue
                result = adapter.run(
                    run_id=run_id,
                    trade=trade,
                    route=route,
                    features=features,
                )
                storage.insert_agent_result(result)
                agent_results.append(result)

        storage.complete_run(run_id=run_id, status="completed")
        status = "completed"
    except Exception:
        storage.complete_run(run_id=run_id, status="failed")
        raise
    finally:
        storage.close()

    return OrchestratorRunResult(
        run_id=run_id,
        batch_id=batch_id,
        status=status,
        normalized_count=len(normalized_trades),
        agent_results=agent_results,
        notes=[
            "This is an orchestration skeleton.",
            "Real feature calculation, routing, and agent adapters are not connected yet.",
        ],
    )
