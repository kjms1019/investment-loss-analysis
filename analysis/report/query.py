"""orchestrator.sqlite3 읽기 전용 조회.

쓰기는 절대 하지 않는다 (orchestrator/storage.py 의 책임). 이 모듈은
normalized_trades ⋈ agent_results 조인만 담당하고, dict 행을 그대로 반환한다.
가공(narrative 생성, 집계)은 builder.py 가 한다.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from analysis.orchestrator.storage import DEFAULT_DB_PATH
from analysis.user_profile import DEFAULT_PROFILE_DB_PATH

_JOIN_SQL = """
    SELECT
        ar.run_id, ar.trade_id, ar.agent_id, ar.output_status,
        ar.score, ar.severity, ar.result_json, ar.route_reason,
        ar.created_at,
        nt.code, nt.name, nt.side, nt.qty, nt.price, nt.executed_at
    FROM agent_results ar
    LEFT JOIN normalized_trades nt ON nt.trade_id = ar.trade_id
"""


def _connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(Path(db_path)))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    raw = data.pop("result_json", None)
    data["result"] = json.loads(raw) if raw else {}
    return data


def fetch_results_for_run(run_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """run_id 1회 실행분의 손실 진단 결과 전체 (사이클별 1건)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(f"{_JOIN_SQL} WHERE ar.run_id = ?", (run_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def fetch_results_for_trade(trade_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """특정 사이클(trade_id)의 결과 (보통 run 당 1건, run 재실행 시 여러 건일 수 있음)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(f"{_JOIN_SQL} WHERE ar.trade_id = ?", (trade_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _run_ids_for_user(user_id: str, profile_db_path: str = DEFAULT_PROFILE_DB_PATH) -> List[str]:
    """user_profile_trade_labels(analysis/user_profile/storage.py) 에서 user_id → run_id 목록 조회.

    orchestrator_runs/agent_results 에는 user_id 컬럼이 없으므로, 이 매핑을
    user_profile DB 쪽에서 가져온다(파이프라인이 run마다 거기에도 적재함).
    """
    conn = sqlite3.connect(str(Path(profile_db_path)))
    try:
        rows = conn.execute(
            "SELECT DISTINCT run_id FROM user_profile_trade_labels WHERE user_id = ? ORDER BY run_id",
            (user_id,),
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def fetch_results_for_user(
    user_id: str,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
) -> List[Dict[str, Any]]:
    """user_id 기준 전체 run 누적 결과.

    user_profile_trade_labels 에서 이 user_id 가 만든 run_id 목록을 먼저 구하고,
    각 run을 orchestrator.sqlite3 에서 조회해 합친다. 같은 거래가 여러 run에
    걸쳐 재분석됐다면 run별로 모두 포함된다(중복 제거는 호출자 책임).
    """
    run_ids = _run_ids_for_user(user_id, profile_db_path)
    results: List[Dict[str, Any]] = []
    for run_id in run_ids:
        results.extend(fetch_results_for_run(run_id, db_path=db_path))
    return results
