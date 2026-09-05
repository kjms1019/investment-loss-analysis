"""Runtime database backend contract.

The batch pipeline currently writes to SQLite. Production can switch to
Supabase/Postgres without changing analysis logic if the runtime first resolves
one backend config and passes an implementation with the same storage methods.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from analysis.common.paths import DATA_DIR


BackendName = Literal["sqlite", "supabase"]


@dataclass(frozen=True)
class DatabaseBackendConfig:
    backend: BackendName = "sqlite"
    sqlite_orchestrator_path: str = "analysis/data/orchestrator.sqlite3"
    sqlite_profile_path: str = "analysis/data/user_profiles.sqlite3"
    supabase_url: str = ""
    supabase_service_key: str = ""

    @property
    def is_supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    def validate(self) -> None:
        if self.backend == "sqlite":
            return
        if self.backend == "supabase" and self.is_supabase_ready:
            return
        raise RuntimeError(
            "MIRAE_DB_BACKEND=supabase requires SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY."
        )


def database_backend_from_env() -> DatabaseBackendConfig:
    backend = os.getenv("MIRAE_DB_BACKEND", "sqlite").strip().lower()
    if backend not in {"sqlite", "supabase"}:
        raise RuntimeError("MIRAE_DB_BACKEND must be either 'sqlite' or 'supabase'.")
    return DatabaseBackendConfig(
        backend=backend,  # type: ignore[arg-type]
        # 기본값은 paths.DATA_DIR 기준. 예전엔 상대경로 문자열이라 작업 디렉터리가
        # 다른 환경(배포 등)에서 DB 를 못 찾았고, MIRAE_DATA_ROOT 도 무시됐다.
        sqlite_orchestrator_path=os.getenv(
            "MIRAE_ORCHESTRATOR_DB", str(DATA_DIR / "orchestrator.sqlite3")
        ),
        sqlite_profile_path=os.getenv(
            "MIRAE_PROFILE_DB", str(DATA_DIR / "user_profiles.sqlite3")
        ),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
    )
