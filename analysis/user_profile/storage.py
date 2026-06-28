"""SQLite storage for repeated mistake profiles.

This is the second DB in the batch-analysis loop:

1. orchestrator.sqlite3 keeps parsed trades, runs, and per-trade agent results.
2. user_profiles.sqlite3 keeps the aggregated user profile consumed by alerts.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional


DEFAULT_PROFILE_DB_PATH = "analysis/data/user_profiles.sqlite3"

if TYPE_CHECKING:
    from analysis.orchestrator.schema import AgentResult
    from analysis.predictor.schema import UserRiskProfile


class UserProfileStorage:
    """Persist and read the profile produced after batch analysis."""

    def __init__(self, db_path: str = DEFAULT_PROFILE_DB_PATH) -> None:
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
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                latest_run_id TEXT,
                total_analyzed_trades INTEGER NOT NULL,
                dominant_problem_type TEXT NOT NULL,
                problem_counts_json TEXT NOT NULL,
                average_scores_json TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile_trade_labels (
                user_id TEXT,
                run_id TEXT,
                trade_id TEXT,
                agent_id TEXT,
                score REAL,
                severity TEXT,
                route_reason TEXT,
                result_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, run_id, trade_id, agent_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile_patterns (
                user_id TEXT,
                run_id TEXT,
                pattern_id TEXT,
                domain TEXT,
                name_ko TEXT,
                count INTEGER NOT NULL,
                avg_score REAL,
                representative_trade TEXT,
                trade_ids_json TEXT,
                correction TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (user_id, pattern_id)
            )
            """
        )
        self.conn.commit()

    def upsert_profile(
        self,
        profile: "UserRiskProfile",
        *,
        latest_run_id: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO user_profiles
            (user_id, latest_run_id, total_analyzed_trades, dominant_problem_type,
             problem_counts_json, average_scores_json, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.user_id,
                latest_run_id,
                profile.total_analyzed_trades,
                profile.dominant_problem_type,
                json.dumps(profile.problem_counts, ensure_ascii=False),
                json.dumps(profile.average_scores, ensure_ascii=False),
                profile.source,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()

    def insert_trade_labels(self, user_id: str, results: Iterable["AgentResult"]) -> None:
        rows = [
            (
                user_id,
                result.run_id,
                result.trade_id,
                result.agent_id,
                result.score,
                result.severity,
                result.route_reason,
                json.dumps(result.result, ensure_ascii=False),
            )
            for result in results
        ]
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO user_profile_trade_labels
            (user_id, run_id, trade_id, agent_id, score, severity, route_reason,
             result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def upsert_patterns(self, user_id: str, run_id: str, patterns: Iterable[dict]) -> None:
        """사용자의 반복 패턴 집계를 최신 run 기준으로 교체 저장."""
        self.conn.execute(
            "DELETE FROM user_profile_patterns WHERE user_id = ?", (user_id,)
        )
        now = datetime.now().isoformat()
        rows = [
            (
                user_id, run_id, p["pattern_id"], p["domain"], p["name_ko"],
                p["count"], p.get("avg_score"), p.get("representative_trade"),
                json.dumps(p.get("trade_ids", []), ensure_ascii=False),
                p.get("correction"), now,
            )
            for p in patterns
        ]
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO user_profile_patterns
            (user_id, run_id, pattern_id, domain, name_ko, count, avg_score,
             representative_trade, trade_ids_json, correction, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def load_patterns(self, user_id: str = "default") -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM user_profile_patterns WHERE user_id = ? ORDER BY count DESC",
            (user_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["trade_ids"] = json.loads(d.pop("trade_ids_json") or "[]")
            out.append(d)
        return out

    def load_profile(self, user_id: str = "default") -> "UserRiskProfile":
        from analysis.predictor.schema import UserRiskProfile

        row = self.conn.execute(
            """
            SELECT *
            FROM user_profiles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return UserRiskProfile(user_id=user_id, source="empty_profile_db")

        return UserRiskProfile(
            user_id=row["user_id"],
            total_analyzed_trades=int(row["total_analyzed_trades"]),
            problem_counts=json.loads(row["problem_counts_json"]),
            average_scores=json.loads(row["average_scores_json"]),
            dominant_problem_type=row["dominant_problem_type"],
            source=row["source"],
        )


def build_profile(
    user_id: str,
    results: Iterable[Any],
    *,
    source: str = "user_profile_sqlite",
) -> "UserRiskProfile":
    from analysis.predictor.schema import UserRiskProfile

    counts: dict[str, int] = defaultdict(int)
    score_sums: dict[str, float] = defaultdict(float)
    score_counts: dict[str, int] = defaultdict(int)

    for result in results:
        if result.output_status != "ok":
            continue
        counts[result.agent_id] += 1
        if result.score is not None:
            score_sums[result.agent_id] += float(result.score)
            score_counts[result.agent_id] += 1

    averages = {
        agent_id: round(score_sums[agent_id] / score_counts[agent_id], 4)
        for agent_id in score_counts
        if score_counts[agent_id] > 0
    }
    dominant = "unknown"
    if counts:
        dominant = max(counts.items(), key=lambda item: item[1])[0]

    return UserRiskProfile(
        user_id=user_id,
        total_analyzed_trades=sum(counts.values()),
        problem_counts=dict(counts),
        average_scores=averages,
        dominant_problem_type=dominant,  # type: ignore[arg-type]
        source=source,
    )
