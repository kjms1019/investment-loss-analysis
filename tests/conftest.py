"""테스트 공통 설정 — 프로젝트 루트와 analysis 를 import 경로에 추가."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "analysis")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
