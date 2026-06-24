"""Agent adapter registry for the top-level orchestrator.

Real adapters should wrap the entry-error, stop-loss-failure, and psych agents
after the shared output schema is finalized.
"""

from __future__ import annotations

from typing import Dict, Optional

from .router import AGENT_ENTRY_ERROR, AGENT_PSYCH, AGENT_STOP_LOSS_FAILURE
from .schema import AgentResult, CommonFeatureBundle, NormalizedTrade, RouteDecision


class AgentAdapter:
    """Base adapter interface for one agent."""

    agent_id = "base"

    def run(
        self,
        run_id: str,
        trade: NormalizedTrade,
        route: RouteDecision,
        features: Optional[CommonFeatureBundle] = None,
    ) -> AgentResult:
        raise NotImplementedError


class PlaceholderAgentAdapter(AgentAdapter):
    """Adapter used until each real agent output schema is finalized."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def run(
        self,
        run_id: str,
        trade: NormalizedTrade,
        route: RouteDecision,
        features: Optional[CommonFeatureBundle] = None,
    ) -> AgentResult:
        feature_status = None if features is None else features.feature_status
        return AgentResult(
            run_id=run_id,
            trade_id=trade.trade_id,
            agent_id=self.agent_id,
            output_status="placeholder_not_run",
            score=None,
            severity=None,
            route_reason=route.reason,
            result={
                "message": "Real agent adapter is not connected yet.",
                "trade": trade.to_dict(),
                "feature_status": feature_status,
            },
        )


class AgentRegistry:
    """Registry that resolves route decisions to adapter instances."""

    def __init__(self) -> None:
        self._adapters: Dict[str, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter) -> None:
        self._adapters[adapter.agent_id] = adapter

    def get(self, agent_id: str) -> Optional[AgentAdapter]:
        return self._adapters.get(agent_id)


def build_default_registry() -> AgentRegistry:
    """Return a registry with placeholder adapters for the three agents."""
    registry = AgentRegistry()
    registry.register(PlaceholderAgentAdapter(AGENT_ENTRY_ERROR))
    registry.register(PlaceholderAgentAdapter(AGENT_STOP_LOSS_FAILURE))
    registry.register(PlaceholderAgentAdapter(AGENT_PSYCH))
    return registry
