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
from .planned_entry_predictor import (
    ClosedTradeFact,
    PlannedEntryInput,
    PlannedEntryRiskResult,
    build_entry_context,
    closed_trade_facts_from_cycles,
    evaluate_planned_entries,
)
from .interaction import build_interaction_state
from .pipeline import run_pipeline
from .streaming_runtime import StreamingRiskRuntime

__all__ = [
    "CurrentHoldingInput",
    "DemoHoldingMarketDataProvider",
    "Min1HoldingMarketDataProvider",
    "HoldingMarketSnapshot",
    "HoldingRiskResult",
    "ClosedTradeFact",
    "PlannedEntryInput",
    "PlannedEntryRiskResult",
    "build_entry_context",
    "closed_trade_facts_from_cycles",
    "build_interaction_state",
    "build_position_snapshot",
    "evaluate_current_holdings",
    "evaluate_planned_entries",
    "run_pipeline",
    "StreamingRiskRuntime",
]
