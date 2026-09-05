"""데이터 루트 경로 단일 해소 모듈.

분봉(min1) parquet·종목코드 캐시가 어디에 있는지를 한 곳에서 정한다.
이전에는 min1_lookup / collector.config / agent_registry / stop-loss-agent.data_loader
네 곳이 각자 `analysis/data/min1` 를 상대경로로 재정의해, 다른 PC나 공유
드라이브에 데이터를 두면 경로를 일일이 바꿔야 했다.

우선순위:
    1. 환경변수 MIRAE_DATA_ROOT (.env 또는 셸) — 예: G:/내 드라이브/mirae_data
    2. 저장소 기본값  <repo>/analysis/data

MIRAE_DATA_ROOT 는 "min1/ 와 .cache/ 를 담는 상위 폴더"를 가리킨다.
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# .env 로드(있으면). dotenv 미설치/부재 환경에서도 깨지지 않게 방어.
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except Exception:
    pass


def data_root() -> Path:
    """데이터 상위 폴더. MIRAE_DATA_ROOT 가 있으면 그것을, 없으면 저장소 기본값."""
    env = os.getenv("MIRAE_DATA_ROOT")
    return Path(env).expanduser() if env else _REPO_ROOT / "analysis" / "data"


DATA_DIR = data_root()
MIN1_DIR = DATA_DIR / "min1"            # 종목별 1분봉 parquet
CACHE_DIR = DATA_DIR / ".cache"         # 토큰/종목리스트 캐시 (git 미추적)
CODES_CSV = CACHE_DIR / "kospi_codes.csv"
