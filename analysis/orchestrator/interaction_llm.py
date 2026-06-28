"""Top-level interaction prompt generation.

The interaction layer decides frequency/amount winners deterministically. This
module only rewrites that state into a short user-facing sentence. If LLM is
disabled or unavailable, the deterministic prompt_body is returned.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from analysis.llm import generate

_SYSTEM = """You are the top-level coach for a Korean stock-trading reflection service.
Use only the supplied JSON facts: counts, loss amounts, frequency winner,
amount winner, and whether a question is needed. Write 1-2 warm Korean
sentences. Do not invent facts, numbers, or advice. Output only the sentence."""

_LABEL = {
    "entry_error": "\uc9c4\uc785\uc624\ub958",
    "stop_loss_failure": "\uc190\uc808\uc2e4\ud328",
}


def llm_interaction_prompt(state: Dict[str, Any], *, fallback: str = "") -> str:
    """Return a conversational prompt. Fallback is state['prompt_body']."""
    stats = {
        _LABEL.get(agent_id, agent_id): {
            "count": stat.get("count"),
            "loss_amount_sum": stat.get("loss_amount_sum"),
        }
        for agent_id, stat in (state.get("category_stats") or {}).items()
        if stat.get("count")
    }
    facts = {
        "stats": stats,
        "frequency_winner": _LABEL.get(state.get("frequency_winner"), state.get("frequency_winner")),
        "amount_winner": _LABEL.get(state.get("amount_winner"), state.get("amount_winner")),
        "question_required": state.get("question_required"),
    }
    fb = fallback or state.get("prompt_body", "")
    return generate(
        _SYSTEM,
        json.dumps(facts, ensure_ascii=False),
        kind="default",
        max_tokens=220,
        fallback=fb,
        max_output_chars=260,
    )