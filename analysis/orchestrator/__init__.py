"""Top-level orchestrator pipeline."""

import sys
from pathlib import Path

_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

from .holding_predictor import (
    CurrentHoldingInput,
    DemoHoldingMarketDataProvider,
    HoldingMarketSnapshot,
    HoldingRiskResult,
    build_position_snapshot,
    evaluate_current_holdings,
)
from .interaction import build_interaction_state
from .pipeline import run_pipeline

__all__ = [
    "CurrentHoldingInput",
    "DemoHoldingMarketDataProvider",
    "HoldingMarketSnapshot",
    "HoldingRiskResult",
    "build_interaction_state",
    "build_position_snapshot",
    "evaluate_current_holdings",
    "run_pipeline",
]
