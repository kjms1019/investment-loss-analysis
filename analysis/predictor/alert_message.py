"""Real-time alert message generation.

The predictor calculates risk. This module only turns a RiskSignal into a short
user-facing sentence. If LLM is disabled or unavailable, deterministic Korean
fallback templates are used.
"""
from __future__ import annotations

import json
from typing import Any

from analysis.llm import generate

_SYSTEM = """You write short Korean alerts for a stock-trading reflection service.
Use only the supplied JSON facts: timing, problem type, risk level, reasons,
stock code, and unrealized return. Do not invent numbers or advice. Avoid blame
and direct buy/sell instructions. Output only 1-2 user-facing Korean sentences."""

_PROBLEM_KR = {
    "entry_error": "\uc9c4\uc785\uc624\ub958",
    "stop_loss_failure": "\uc190\uc808\uc2e4\ud328",
    "unknown": "\uc8fc\uc758",
}


def _template(signal: Any) -> str:
    when = "\uc9c0\uae08 \uc0ac\ub824\ub294 \uc885\ubaa9" if signal.mode == "entry" else "\ubcf4\uc720 \uc885\ubaa9"
    prob = _PROBLEM_KR.get(signal.problem_type, "\uc8fc\uc758")
    if signal.mode == "entry":
        return f"{when}, \uacfc\uac70 '{prob}' \ud328\ud134\uacfc \ube44\uc2b7\ud55c \uc0c1\ud669\uc774\uc5d0\uc694. \ud55c \ubc88 \ub354 \uc0dd\uac01\ud574\ubcfc\uae4c\uc694?"
    return f"{when}\uc774 \uc190\uc808 \uae30\uc900\uc5d0 \uac00\uae4c\uc6cc\uc694. \ud3c9\uc18c '{prob}' \uacbd\ud5a5\uc774 \uc788\uc73c\ub2c8 \ubbf8\ub9ac \uc815\ud55c \uae30\uc900\uc744 \uc9c0\ucf1c\ubcf4\uc138\uc694."


def build_alert_message(signal: Any, *, fallback: str = "") -> str:
    """Return an alert sentence. Risk calculation never depends on this text."""
    facts = {
        "timing": "entry_before_buy" if signal.mode == "entry" else "live_position",
        "problem_type": _PROBLEM_KR.get(signal.problem_type, "\uc8fc\uc758"),
        "risk_level": signal.risk_level,
        "reasons": signal.reasons,
        "code": signal.code,
        "unrealized_return_pct": (signal.features or {}).get("unrealized_return_pct"),
    }
    fb = fallback or _template(signal)
    return generate(
        _SYSTEM,
        json.dumps(facts, ensure_ascii=False),
        kind="alert",
        max_tokens=120,
        fallback=fb,
        max_output_chars=160,
    )