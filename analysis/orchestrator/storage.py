"""SQLite storage for raw inputs, normalized trades, runs, and agent results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .schema import AgentResult, CommonFeatureBundle, NormalizedTrade, RawTradeRow


DEFAULT_DB_PATH = "analysis/data/orchestrator.sqlite3"


class OrchestratorStorage:
    """Small SQLite-backed storage used before a production DB is chosen."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def close(self) -> None:
        self.conn.close()

    def initialize(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_batches (
                batch_id TEXT PRIMARY KEY,
                source_name TEXT,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                raw_file_path TEXT,
                row_count INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_trade_rows (
                batch_id TEXT,
                row_index INTEGER,
                raw_payload_json TEXT,
                PRIMARY KEY (batch_id, row_index)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS normalized_trades (
                trade_id TEXT PRIMARY KEY,
                batch_id TEXT,
                source_row_index INTEGER,
                executed_at TEXT,
                code TEXT,
                name TEXT,
                side TEXT,
                qty REAL,
                price REAL,
                raw_payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrator_runs (
                run_id TEXT PRIMARY KEY,
                batch_id TEXT,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                status TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_results (
                run_id TEXT,
                trade_id TEXT,
                agent_id TEXT,
                route_reason TEXT,
                output_status TEXT,
                score REAL,
                severity TEXT,
                result_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (run_id, trade_id, agent_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_bundles (
                run_id TEXT,
                trade_id TEXT,
                feature_status TEXT,
                features_json TEXT,
                data_quality_json TEXT,
                notes_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, trade_id)
            )
            """
        )
        self.conn.commit()

    def create_batch(
        self,
        batch_id: str,
        source_name: str,
        raw_file_path: str,
        row_count: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_batches
            (batch_id, source_name, raw_file_path, row_count)
            VALUES (?, ?, ?, ?)
            """,
            (batch_id, source_name, raw_file_path, row_count),
        )
        self.conn.commit()

    def insert_raw_rows(self, rows: Iterable[RawTradeRow]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO raw_trade_rows
            (batch_id, row_index, raw_payload_json)
            VALUES (?, ?, ?)
            """,
            [
                (
                    row.batch_id,
                    row.row_index,
                    json.dumps(row.payload, ensure_ascii=False),
                )
                for row in rows
            ],
        )
        self.conn.commit()

    def insert_normalized_trades(self, trades: Iterable[NormalizedTrade]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO normalized_trades
            (trade_id, batch_id, source_row_index, executed_at, code, name,
             side, qty, price, raw_payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    trade.trade_id,
                    trade.batch_id,
                    trade.source_row_index,
                    trade.executed_at,
                    trade.code,
                    trade.name,
                    trade.side,
                    trade.qty,
                    trade.price,
                    json.dumps(trade.raw_payload, ensure_ascii=False),
                )
                for trade in trades
            ],
        )
        self.conn.commit()

    def insert_feature_bundles(self, run_id: str, bundles: Iterable[CommonFeatureBundle]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO feature_bundles
            (run_id, trade_id, feature_status, features_json, data_quality_json, notes_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    bundle.trade_id,
                    bundle.feature_status,
                    json.dumps(bundle.features, ensure_ascii=False),
                    json.dumps(bundle.data_quality, ensure_ascii=False),
                    json.dumps(bundle.notes, ensure_ascii=False),
                )
                for bundle in bundles
            ],
        )
        self.conn.commit()
    def create_run(self, run_id: str, batch_id: str, status: str = "running") -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO orchestrator_runs
            (run_id, batch_id, status)
            VALUES (?, ?, ?)
            """,
            (run_id, batch_id, status),
        )
        self.conn.commit()

    def complete_run(self, run_id: str, status: str = "completed") -> None:
        self.conn.execute(
            """
            UPDATE orchestrator_runs
            SET completed_at = CURRENT_TIMESTAMP, status = ?
            WHERE run_id = ?
            """,
            (status, run_id),
        )
        self.conn.commit()

    def insert_agent_result(self, result: AgentResult) -> None:
        """결과 1건 적재. 같은 (run_id, trade_id, agent_id) 는 덮어쓴다(중복 누적 방지).

        commit 하지 않는다 — 호출자가 run 종료 시 complete_run() 에서 일괄 커밋한다.
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO agent_results
            (run_id, trade_id, agent_id, route_reason, output_status, score,
             severity, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                result.trade_id,
                result.agent_id,
                result.route_reason,
                result.output_status,
                result.score,
                result.severity,
                json.dumps(result.result, ensure_ascii=False),
            ),
        )

    def get_batch_id_for_run(self, run_id: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT batch_id FROM orchestrator_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return None if row is None else row["batch_id"]

