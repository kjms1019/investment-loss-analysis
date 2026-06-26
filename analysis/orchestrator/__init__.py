"""총괄 오케스트레이션 파이프라인."""

import sys
from pathlib import Path

_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

from .interaction import build_interaction_state
from .pipeline import run_pipeline

__all__ = ["build_interaction_state", "run_pipeline"]
