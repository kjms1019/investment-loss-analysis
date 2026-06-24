"""Hybrid agents that absorb selected psych-agent signals.

These modules do not modify the original entry-error, stop-loss-failure, or
psych agents. They provide new agent surfaces that reuse the psych signal
detectors after assigning each psychological pattern to the better matching
trading-error domain.
"""

from .entry_error_psych_agent import EntryErrorPsychHybridAgent, run_entry_error_hybrid
from .stop_loss_psych_agent import StopLossPsychHybridAgent, run_stop_loss_hybrid

__all__ = [
    "EntryErrorPsychHybridAgent",
    "StopLossPsychHybridAgent",
    "run_entry_error_hybrid",
    "run_stop_loss_hybrid",
]
