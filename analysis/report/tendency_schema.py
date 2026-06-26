"""'내 성향' 리포트(카드 UI) 데이터 계약.

흐름: LossReportSummary (report/schema.py, 이미 구현됨)
      → PatternFact 리스트  [DB/룰엔진이 계산 — 숫자·종목명은 전부 여기서 확정]
      → (LLM 또는 템플릿)  → TendencyCardText 리스트  [문장만 생성]
      → TendencyCard = PatternFact + TendencyCardText 병합  [프론트엔드 렌더용]

LLM은 PatternFact 의 숫자를 절대 새로 만들지 않는다. title/tip/cohort_sentence
같은 텍스트 필드만 메운다. 이렇게 나누는 이유: 분류기가 라벨을 바꿔도(현재
entry-error-agent 라벨 미확정) PatternFact 구조만 안 바뀌면 프롬프트도,
프론트 렌더링도 그대로 간다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RepresentativeTrade:
    code: str
    name: str
    score: Optional[float] = None
    executed_at: Optional[str] = None


@dataclass
class PatternFact:
    """한 패턴 카드의 사실 데이터. LLM 입력(JSON)의 단위 원소."""

    pattern_key: str            # 안정 식별자, 예: "stop_loss_failure.delay_hold"
    category: str               # "손절실패" | "진입오류" (UI 아이콘 그룹)
    category_key: str           # agent_id
    tag: str                    # "처분효과" | "리벤지" | "고점추격" | "추가손실" | "기타"
    tag_key: str
    title_hint: str             # 분류기 라벨의 한국어 직역 (LLM이 다듬을 기본 문구)

    matched_count: int          # 패턴이 실제 발생한 사이클 수 ("14건 중 9건"의 9)
    total_eligible_count: int   # 패턴 판정 대상이 된 사이클 수 (위의 14)
    match_rate: float           # matched_count / total_eligible_count

    severity: str                # 'weak' | 'moderate' | 'strong' (matched 중 최고 심각도)
    avg_score: Optional[float] = None

    representative_trades: List[RepresentativeTrade] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)   # 보조 수치 (LLM 참고용, 화면 미노출 가능)
    correction_hint: str = ""    # 교정 가이드 골자 — LLM은 이 취지를 다듬기만 함

    # 코호트 비교. 시드 단계에서는 None 이거나 is_seed=True 인 고정값.
    cohort: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TendencyReportInput:
    """LLM에 넘기는 최종 JSON 파일의 루트 구조."""

    user_id: str
    generated_at: str
    period_from: Optional[str]
    period_to: Optional[str]
    dominant_problem_type: str
    total_loss_trades: int
    patterns: List[PatternFact] = field(default_factory=list)
    # LLM에게 강제할 제약 — 시스템 프롬프트와 별개로 입력에도 명시해 이중으로 못박는다.
    constraints: Dict[str, Any] = field(
        default_factory=lambda: {"no_blame": True, "no_new_numbers": True, "language": "ko"}
    )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["patterns"] = [p.to_dict() for p in self.patterns]
        return data


@dataclass
class TendencyCardText:
    """LLM(또는 템플릿)이 생성하는 문장 필드. 숫자는 들고 있지 않는다."""

    pattern_key: str
    title: str
    tip: str
    cohort_sentence: Optional[str] = None  # cohort 데이터 없으면 None — 문장 생성 안 함


@dataclass
class TendencyReportText:
    headline: str
    subheadline: str
    insight_banner: str
    cards: List[TendencyCardText] = field(default_factory=list)
    engine: str = "template"   # "anthropic:<model>" | "template" | "llm_error"
    llm_error: Optional[str] = None


@dataclass
class TendencyCard:
    """PatternFact(사실) + TendencyCardText(문장) 병합 — 프론트엔드 렌더용 최종 카드."""

    pattern_key: str
    category: str
    tag: str
    title: str
    matched_count: int
    total_eligible_count: int
    severity: str
    representative_trades: List[RepresentativeTrade]
    tip: str
    cohort_sentence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TendencyReport:
    user_id: str
    generated_at: str
    headline: str
    subheadline: str
    insight_banner: str
    cards: List[TendencyCard] = field(default_factory=list)
    engine: str = "template"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cards"] = [c.to_dict() for c in self.cards]
        return data
