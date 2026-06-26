"""SQLite helpers for predictor profiles and alert logging."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional

from analysis.user_profile import DEFAULT_PROFILE_DB_PATH, UserProfileStorage

from .schema import RiskSignal, UserRiskProfile


class PredictorStorage:
    """Read orchestrator results and persist predictor alerts.

    The current orchestrator DB does not carry a user_id column yet. Until that
    exists, this class treats one DB file as one user's local analysis history.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    ) -> None:
        if db_path is None:
            # lazy import — predictor↔orchestrator 모듈 로드 시 순환 방지
            from analysis.orchestrator.storage import DEFAULT_DB_PATH
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.profile_db_path = profile_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def close(self) -> None:
        self.conn.close()

    def initialize(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictor_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                trade_id TEXT,
                code TEXT,
                mode TEXT,
                problem_type TEXT,
                risk_score REAL,
                risk_level TEXT,
                should_alert INTEGER,
                reasons_json TEXT,
                features_json TEXT,
                model_used TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def load_user_profile(self, user_id: str = "default") -> UserRiskProfile:
        profile_storage = UserProfileStorage(db_path=self.profile_db_path)
        try:
            profile = profile_storage.load_profile(user_id=user_id)
        finally:
            profile_storage.close()
        if profile.total_analyzed_trades > 0:
            return profile

        try:
            rows = self.conn.execute(
                """
                SELECT agent_id, score
                FROM agent_results
                WHERE output_status = 'ok'
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return UserRiskProfile(user_id=user_id, source="empty_sqlite")

        counts: dict[str, int] = defaultdict(int)
        score_sums: dict[str, float] = defaultdict(float)
        score_counts: dict[str, int] = defaultdict(int)

        for row in rows:
            agent_id = row["agent_id"] or "unknown"
            counts[agent_id] += 1
            if row["score"] is not None:
                score_sums[agent_id] += float(row["score"])
                score_counts[agent_id] += 1

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
        )

    def insert_alert(self, signal: RiskSignal) -> None:
        self.conn.execute(
            """
            INSERT INTO predictor_alerts
            (user_id, trade_id, code, mode, problem_type, risk_score, risk_level,
             should_alert, reasons_json, features_json, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.user_id,
                signal.trade_id,
                signal.code,
                signal.mode,
                signal.problem_type,
                signal.risk_score,
                signal.risk_level,
                1 if signal.should_alert else 0,
                json.dumps(signal.reasons, ensure_ascii=False),
                json.dumps(signal.features, ensure_ascii=False),
                signal.model_used,
            ),
        )
        self.conn.commit()

    def latest_alert(
        self,
        user_id: str,
        trade_id: str,
        mode: str,
        problem_type: str,
    ) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM predictor_alerts
            WHERE user_id = ? AND trade_id = ? AND mode = ? AND problem_type = ?
            ORDER BY created_at DESC, alert_id DESC
            LIMIT 1
            """,
            (user_id, trade_id, mode, problem_type),
        ).fetchone()
