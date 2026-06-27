"""User interaction state for the top-level orchestrator.

The interaction layer runs after per-trade routing. It summarizes routed loss
trades by problem domain, then decides whether the web UI should ask the user
which problem perspective they want to analyze. If the user already chose a
perspective, it turns that choice into the focused analysis queue consumed by
UI/API layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional

from common.schema import TradeCycle

from .router import AGENT_ENTRY_ERROR, AGENT_STOP_LOSS_FAILURE
from .schema import AgentResult


SELECTABLE_AGENT_IDS = [AGENT_ENTRY_ERROR, AGENT_STOP_LOSS_FAILURE]

AGENT_LABELS = {
    AGENT_ENTRY_ERROR: "진입오류",
    AGENT_STOP_LOSS_FAILURE: "손절실패",
}


@dataclass
class CategoryStat:
    agent_id: str
    label: str
    count: int = 0
    loss_amount_sum: float = 0.0
    trade_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["loss_amount_sum"] = round(self.loss_amount_sum, 2)
        return data


@dataclass
class InteractionOption:
    option_id: str
    label: str
    basis: str
    agent_id: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InteractionState:
    category_stats: Dict[str, CategoryStat]
    frequency_winner: Optional[str]
    amount_winner: Optional[str]
    question_required: bool
    prompt_body: str
    options: List[InteractionOption] = field(default_factory=list)
    auto_selected_agent_id: Optional[str] = None
    auto_selected_basis: Optional[str] = None
    completed_agent_ids: List[str] = field(default_factory=list)
    remaining_agent_ids: List[str] = field(default_factory=list)
    round_index: int = 1
    max_rounds: int = 2
    followup_prompt_body: Optional[str] = None
    focus_agent_id: Optional[str] = None
    focus_basis: Optional[str] = None
    focus_trade_ids: List[str] = field(default_factory=list)
    analysis_queue: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category_stats": {
                agent_id: stat.to_dict()
                for agent_id, stat in self.category_stats.items()
            },
            "frequency_winner": self.frequency_winner,
            "amount_winner": self.amount_winner,
            "question_required": self.question_required,
            "prompt_body": self.prompt_body,
            "options": [option.to_dict() for option in self.options],
            "auto_selected_agent_id": self.auto_selected_agent_id,
            "auto_selected_basis": self.auto_selected_basis,
            "completed_agent_ids": self.completed_agent_ids,
            "remaining_agent_ids": self.remaining_agent_ids,
            "round_index": self.round_index,
            "max_rounds": self.max_rounds,
            "followup_prompt_body": self.followup_prompt_body,
            "focus_agent_id": self.focus_agent_id,
            "focus_basis": self.focus_basis,
            "focus_trade_ids": self.focus_trade_ids,
            "analysis_queue": self.analysis_queue,
        }


def build_interaction_state(
    agent_results: Iterable[AgentResult],
    loss_cycles: Iterable[TradeCycle],
    *,
    completed_agent_ids: Optional[Iterable[str]] = None,
    selected_agent_id: Optional[str] = None,
    selected_basis: Optional[str] = None,
    round_index: int = 1,
    max_rounds: int = 2,
) -> InteractionState:
    """Build the web-facing interaction state from routed loss-trade results."""
    completed = [
        agent_id for agent_id in (completed_agent_ids or [])
        if agent_id in SELECTABLE_AGENT_IDS
    ]
    selected = selected_agent_id if selected_agent_id in SELECTABLE_AGENT_IDS else None
    loss_by_trade_id = {
        cycle.trade_id: abs(float(cycle.realized_pnl or 0.0))
        for cycle in loss_cycles
        if cycle.closed and cycle.realized_pnl < 0
    }
    stats = _empty_stats()

    for result in agent_results:
        if result.agent_id not in stats:
            continue
        loss_amount = loss_by_trade_id.get(result.trade_id, 0.0)
        stat = stats[result.agent_id]
        stat.count += 1
        stat.loss_amount_sum += loss_amount
        stat.trade_ids.append(result.trade_id)

    active_stats = [stat for stat in stats.values() if stat.count > 0]
    if not active_stats:
        return InteractionState(
            category_stats=stats,
            frequency_winner=None,
            amount_winner=None,
            question_required=False,
            prompt_body="분석할 수 있는 손실 문제를 찾지 못했습니다.",
            completed_agent_ids=completed,
            remaining_agent_ids=[],
            focus_agent_id=None,
            focus_basis=None,
            focus_trade_ids=[],
            analysis_queue=[],
            round_index=round_index,
            max_rounds=max_rounds,
        )

    frequency_winner = _winner_by_frequency(active_stats)
    amount_winner = _winner_by_amount(active_stats)
    remaining = [
        agent_id for agent_id in SELECTABLE_AGENT_IDS
        if agent_id not in completed and stats[agent_id].count > 0
    ]

    focus_agent_id = selected or (frequency_winner if frequency_winner == amount_winner else None)
    focus_basis = selected_basis or ("auto_same_winner" if focus_agent_id else None)
    focus_trade_ids = stats[focus_agent_id].trade_ids if focus_agent_id else []
    analysis_queue = _analysis_queue(stats, focus_agent_id, completed)

    if selected:
        prompt = (
            "사용자가 선택한 기준에 따라 "
            f"'{AGENT_LABELS[selected]}' 문제를 먼저 분석합니다."
        )
        return InteractionState(
            category_stats=stats,
            frequency_winner=frequency_winner,
            amount_winner=amount_winner,
            question_required=False,
            prompt_body=prompt,
            auto_selected_agent_id=selected,
            auto_selected_basis=selected_basis or "user_selected",
            completed_agent_ids=completed,
            remaining_agent_ids=remaining,
            round_index=round_index,
            max_rounds=max_rounds,
            followup_prompt_body=_followup_prompt(stats, completed + [selected], max_rounds),
            focus_agent_id=selected,
            focus_basis=selected_basis or "user_selected",
            focus_trade_ids=focus_trade_ids,
            analysis_queue=analysis_queue,
        )

    if frequency_winner == amount_winner:
        prompt = (
            "사용자의 과거 손실 거래 통계를 보면,\n"
            f"가장 자주 반복되고 손실 금액도 가장 컸던 문제는 "
            f"'{AGENT_LABELS[frequency_winner]}'로 파악되었습니다."
        )
        return InteractionState(
            category_stats=stats,
            frequency_winner=frequency_winner,
            amount_winner=amount_winner,
            question_required=False,
            prompt_body=prompt,
            auto_selected_agent_id=frequency_winner,
            auto_selected_basis="auto_same_winner",
            completed_agent_ids=completed,
            remaining_agent_ids=remaining,
            round_index=round_index,
            max_rounds=max_rounds,
            followup_prompt_body=_followup_prompt(stats, completed, max_rounds),
            focus_agent_id=focus_agent_id,
            focus_basis=focus_basis,
            focus_trade_ids=focus_trade_ids,
            analysis_queue=analysis_queue,
        )

    prompt = (
        "사용자의 과거 손실 거래 통계를 보면,\n"
        f"가장 자주 반복된 문제는 '{AGENT_LABELS[frequency_winner]}'이고,\n"
        f"손실 금액이 가장 컸던 문제는 '{AGENT_LABELS[amount_winner]}'로 파악되었습니다.\n\n"
        "어떤 문제를 중심으로 분석해볼까요?"
    )
    options = [
        InteractionOption(
            option_id="frequent_problem",
            label="자주 반복된 문제",
            basis="frequency",
            agent_id=frequency_winner,
        ),
        InteractionOption(
            option_id="large_loss_problem",
            label="손실 금액이 컸던 문제",
            basis="amount",
            agent_id=amount_winner,
        ),
    ]
    return InteractionState(
        category_stats=stats,
        frequency_winner=frequency_winner,
        amount_winner=amount_winner,
        question_required=True,
        prompt_body=prompt,
        options=options,
        completed_agent_ids=completed,
        remaining_agent_ids=remaining,
        round_index=round_index,
        max_rounds=max_rounds,
        followup_prompt_body=_followup_prompt(stats, completed, max_rounds),
        focus_agent_id=focus_agent_id,
        focus_basis=focus_basis,
        focus_trade_ids=focus_trade_ids,
        analysis_queue=analysis_queue,
    )


def _empty_stats() -> Dict[str, CategoryStat]:
    return {
        agent_id: CategoryStat(agent_id=agent_id, label=AGENT_LABELS[agent_id])
        for agent_id in SELECTABLE_AGENT_IDS
    }


def _winner_by_frequency(stats: List[CategoryStat]) -> str:
    return max(
        stats,
        key=lambda stat: (
            stat.count,
            stat.loss_amount_sum,
            -SELECTABLE_AGENT_IDS.index(stat.agent_id),
        ),
    ).agent_id


def _winner_by_amount(stats: List[CategoryStat]) -> str:
    return max(
        stats,
        key=lambda stat: (
            stat.loss_amount_sum,
            stat.count,
            -SELECTABLE_AGENT_IDS.index(stat.agent_id),
        ),
    ).agent_id


def _analysis_queue(
    stats: Dict[str, CategoryStat],
    focus_agent_id: Optional[str],
    completed_agent_ids: List[str],
) -> List[str]:
    ordered: List[str] = []
    if focus_agent_id and stats[focus_agent_id].count > 0:
        ordered.append(focus_agent_id)
    for agent_id in SELECTABLE_AGENT_IDS:
        if agent_id in ordered or agent_id in completed_agent_ids:
            continue
        if stats[agent_id].count > 0:
            ordered.append(agent_id)
    return ordered


def _followup_prompt(
    stats: Dict[str, CategoryStat],
    completed_agent_ids: List[str],
    max_rounds: int,
) -> Optional[str]:
    if len(completed_agent_ids) >= max_rounds:
        return None

    remaining = [
        agent_id for agent_id in SELECTABLE_AGENT_IDS
        if agent_id not in completed_agent_ids and stats[agent_id].count > 0
    ]
    if len(remaining) != 1:
        return None

    agent_id = remaining[0]
    return (
        f"{AGENT_LABELS[agent_id]} 분석도 이어서 확인해볼까요?\n"
        "[예] [아니오]"
    )