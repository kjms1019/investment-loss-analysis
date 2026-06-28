"""Compatibility wrapper for planned-entry prediction.

The canonical implementation lives in planned_entry_predictor.py, where planned
entries can use both user trade history and optional 1-minute market features.
This module keeps the develop entry_predictor import path working without
maintaining a second implementation.
"""
from __future__ import annotations

from .planned_entry_predictor import (
    ClosedTradeFact,
    PlannedEntryInput,
    PlannedEntryRiskResult,
    build_entry_context,
    closed_trade_facts_from_cycles,
    evaluate_planned_entries,
)

__all__ = [
    "ClosedTradeFact",
    "PlannedEntryInput",
    "PlannedEntryRiskResult",
    "build_entry_context",
    "closed_trade_facts_from_cycles",
    "evaluate_planned_entries",
]
