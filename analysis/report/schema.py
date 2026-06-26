"""손실 리포트 레이어의 데이터 계약.

orchestrator.sqlite3 (normalized_trades + agent_results) 를 읽기 전용으로
조합한 결과물이다. 새 테이블을 만들지 않고, 이미 적재된 "최종 라우팅 결과"를
사람이 읽을 수 있는 형태로 재구성하는 것이 이 레이어의 역할이다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LossReportItem:
    """사이클(trade_id) 1건의 최종 손실 진단 리포트.

    agent_id/label/score/severity 는 agent_results 원본 그대로이며,
    narrative/evidence 는 normalizers.py 가 에이전트별 result_json 을
    공통 형태로 변환해 채운다 (에이전트마다 result_json 구조가 다르므로).
    """

    trade_id: str
    run_id: str
    code: str
    name: str
    executed_at: Optional[str]

    agent_id: str                 # 최종 채택된 에이전트 (예: stop_loss_failure, entry_error, unclassified)
    label: str                    # 진단 라벨 (judgment_type / top_label 등)
    score: Optional[float]
    severity: Optional[str]

    narrative: str = ""           # 사람이 읽는 설명. 에이전트별 normalizer 가 채움
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    secondary_agent: Optional[str] = None

    # 라우팅은 분류기 단독으로 결정된다(router.py). orchestrator_decision 에서 그대로 가져온다.
    route_type: Optional[str] = None
    routing_confidence: Optional[float] = None
    profile_eligible: bool = False

    # 분류기(classify_entry) 원본 출력. learned_classifier.prediction 에서 그대로 가져온다.
    classifier_label: Optional[str] = None
    classifier_confidence: Optional[float] = None
    classifier_entry_score: Optional[float] = None
    classifier_stop_score: Optional[float] = None

    raw_result: Dict[str, Any] = field(default_factory=dict)  # 원본 result_json 보존 (디버깅/완전성)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LossReportSummary:
    """run_id 또는 user_id 단위 집계 리포트."""

    scope: str                    # "run" | "user"
    scope_id: str
    generated_at: str
    total_loss_trades: int = 0
    count_by_agent: Dict[str, int] = field(default_factory=dict)
    avg_score: Optional[float] = None
    items: List[LossReportItem] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data
