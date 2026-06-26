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
from .holding_market_min1 import Min1HoldingMarketDataProvider
from .interaction import build_interaction_state
from .pipeline import run_pipeline
from .planned_entry_predictor import (
    Min1PlannedEntryFeatureProvider,
    PlannedEntryInput,
    PlannedEntryRiskResult,
    build_entry_context,
    evaluate_planned_entries,
)

__all__ = [
    "CurrentHoldingInput",
    "DemoHoldingMarketDataProvider",
    "Min1HoldingMarketDataProvider",
    "Min1PlannedEntryFeatureProvider",
    "HoldingMarketSnapshot",
    "HoldingRiskResult",
    "PlannedEntryInput",
    "PlannedEntryRiskResult",
    "build_entry_context",
    "build_interaction_state",
    "build_position_snapshot",
    "evaluate_current_holdings",
    "evaluate_planned_entries",
    "run_pipeline",
]

