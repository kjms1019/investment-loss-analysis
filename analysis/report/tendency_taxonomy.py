"""(agent_id, label) → 카드 분류 매핑 (placeholder).

entry-error-agent / stop-loss-failure 분류기의 라벨 체계가 아직 확정되지 않았다.
이 파일은 "분류기가 무슨 라벨을 뱉든, 카드 1장으로 바꾸려면 어떤 필드가 필요한가"의
설계 자리만 잡아두는 용도다. 라벨이 추가/변경되면 여기 딕셔너리만 늘리면 되고
builder.py / prompt.py 는 손댈 필요가 없다.

COHORT_SEED_BENCHMARK: "다른 nn%의 사용자도 반복" 비교용 코호트 매치율.
지금은 실제 전체 사용자 집계가 아니라 고정 시드 값이다 (설계상 자리만 비워둠).
충분한 사용자 수가 쌓이면 analysis/user_profile 쪽에서 실제 집계로 교체하고,
이 테이블은 그 함수의 폴백 기본값으로만 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternTaxonomyEntry:
    pattern_key: str       # 안정적인 내부 식별자 (LLM/프론트 모두 이 값으로 카드 매칭)
    category: str          # 사람이 읽는 대분류 (UI 아이콘 그룹) — "손절실패" | "진입오류"
    category_key: str       # agent_id 그대로 — "stop_loss_failure" | "entry_error"
    tag: str                # UI 태그 pill — "처분효과" | "리벤지" | "고점추격" | "추가손실"
    tag_key: str
    title_hint: str         # 분류기 라벨 → 사람이 읽는 패턴명 (LLM이 다듬을 기본 문구)
    # detected==True 로 셀 조건. severity 기반이 기본값이고, 필요하면 라벨별로 덮어쓴다.
    match_severities: tuple[str, ...] = ("moderate", "strong")
    correction_hint: str = ""   # 행동 교정 가이드 골자 (LLM이 새로 만들지 않고 다듬기만 함)


# key = f"{agent_id}:{label}" — label 은 각 분류기 result_json 의 label / judgment_type 값.
PATTERN_TAXONOMY: dict[str, PatternTaxonomyEntry] = {
    "stop_loss_failure:지연형": PatternTaxonomyEntry(
        pattern_key="stop_loss_failure.delay_hold",
        category="손절실패",
        category_key="stop_loss_failure",
        tag="처분효과",
        tag_key="disposition_effect",
        title_hint="손절선 이탈 후 2일 이상 보유",
        correction_hint="손절가는 진입과 동시에 정해 자동 알림으로 걸어두면 버티는 습관을 줄이는 데 도움이 됩니다.",
    ),
    "stop_loss_failure:물타기형": PatternTaxonomyEntry(
        pattern_key="stop_loss_failure.avg_down",
        category="손절실패",
        category_key="stop_loss_failure",
        tag="추가손실",
        tag_key="averaging_down",
        title_hint="하락장에서 물타기",
        correction_hint="방향이 틀렸을 때는 평단을 낮추기보다 비중을 줄이는 쪽이 손실을 작게 만듭니다.",
    ),
    "entry_error:revenge_reentry_30min": PatternTaxonomyEntry(
        pattern_key="entry_error.revenge_reentry",
        category="진입오류",
        category_key="entry_error",
        tag="리벤지",
        tag_key="revenge_trading",
        title_hint="손실 직후 30분 내 재진입",
        correction_hint="손실을 본 직후에는 신규 진입을 잠시 멈추는 것만으로 충동 매매를 줄일 수 있습니다.",
    ),
    "entry_error:gap_up_chase": PatternTaxonomyEntry(
        pattern_key="entry_error.high_chase",
        category="진입오류",
        category_key="entry_error",
        tag="고점추격",
        tag_key="high_price_chase",
        title_hint="20일 신고가권에서 추격 매수",
        correction_hint="급등 직후보다 눌림목에서 분할로 접근하는 거래의 성적이 더 좋습니다.",
    ),
}

# label 매칭이 안 될 때 agent_id 단위로만 거는 기본값 (분류기 미완성 구간 보호용).
DEFAULT_TAXONOMY_BY_AGENT: dict[str, PatternTaxonomyEntry] = {
    "stop_loss_failure": PatternTaxonomyEntry(
        pattern_key="stop_loss_failure.unlabeled",
        category="손절실패",
        category_key="stop_loss_failure",
        tag="기타",
        tag_key="unlabeled",
        title_hint="손절 기준 이탈",
    ),
    "entry_error": PatternTaxonomyEntry(
        pattern_key="entry_error.unlabeled",
        category="진입오류",
        category_key="entry_error",
        tag="기타",
        tag_key="unlabeled",
        title_hint="진입 시점 오류",
    ),
}

# pattern_key -> 코호트 매치율(%) 시드값. source/is_seed 플래그로 실데이터 교체 시점을 추적.
COHORT_SEED_BENCHMARK: dict[str, int] = {
    "stop_loss_failure.delay_hold": 68,
    "stop_loss_failure.avg_down": 54,
    "entry_error.revenge_reentry": 61,
    "entry_error.high_chase": 47,
}


def lookup_taxonomy(agent_id: str, label: str) -> PatternTaxonomyEntry:
    key = f"{agent_id}:{label}"
    if key in PATTERN_TAXONOMY:
        return PATTERN_TAXONOMY[key]
    if agent_id in DEFAULT_TAXONOMY_BY_AGENT:
        return DEFAULT_TAXONOMY_BY_AGENT[agent_id]
    return PatternTaxonomyEntry(
        pattern_key=f"{agent_id}.unclassified",
        category=agent_id,
        category_key=agent_id,
        tag="기타",
        tag_key="unclassified",
        title_hint=label or agent_id,
    )


def cohort_match_rate(pattern_key: str) -> dict | None:
    pct = COHORT_SEED_BENCHMARK.get(pattern_key)
    if pct is None:
        return None
    return {"match_rate_pct": pct, "source": "seed_v0", "is_seed": True}
