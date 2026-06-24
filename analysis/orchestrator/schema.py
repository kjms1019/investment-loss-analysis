"""Shared data contracts for the top-level orchestrator.

These contracts are intentionally small. The team-wide feature schema and the
three agent output schemas can replace the placeholder fields later without
changing the orchestration flow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawTradeRow:
    batch_id: str
    row_index: int
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedTrade:
    trade_id: str
    batch_id: str
    source_row_index: int
    executed_at: str
    code: str
    name: str
    side: str
    qty: float
    price: float
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommonFeatureBundle:
    trade_id: str
    feature_status: str = "not_computed"
    features: Dict[str, Any] = field(default_factory=dict)
    data_quality: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteDecision:
    trade_id: str
    agent_id: str
    route_status: str
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    run_id: str
    trade_id: str
    agent_id: str
    output_status: str
    score: Optional[float] = None
    severity: Optional[str] = None
    result: Dict[str, Any] = field(default_factory=dict)
    route_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorRunResult:
    run_id: str
    batch_id: str
    status: str
    normalized_count: int
    agent_results: List[AgentResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["agent_results"] = [result.to_dict() for result in self.agent_results]
        return data
