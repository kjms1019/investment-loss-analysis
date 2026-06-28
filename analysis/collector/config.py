"""수집기 공통 설정 — .env 로드 및 경로 정의."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from analysis.common.paths import CACHE_DIR, DATA_DIR, MIN1_DIR  # 데이터 루트 단일 소스(MIRAE_DATA_ROOT)

# analysis/collector/config.py → 프로젝트 루트는 두 단계 위
ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

# 키움 REST 자격증명 — .env 에서 주입
APP_KEY = os.getenv("KIWOOM_APP_KEY", "")
APP_SECRET = os.getenv("KIWOOM_APP_SECRET", "")

# 실전: https://api.kiwoom.com  /  모의: https://mockapi.kiwoom.com
BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")

# 안전 수집 파라미터 (.env 로 덮어쓸 수 있음)
SLEEP_PER_REQUEST = float(os.getenv("KIWOOM_SLEEP", "0.35"))  # 요청 간 최소 대기(초)
MAX_RETRIES = int(os.getenv("KIWOOM_MAX_RETRIES", "4"))
RETRY_BACKOFF = float(os.getenv("KIWOOM_RETRY_BACKOFF", "2.0"))
REQUEST_TIMEOUT = int(os.getenv("KIWOOM_TIMEOUT", "30"))


def ensure_dirs() -> None:
    MIN1_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
