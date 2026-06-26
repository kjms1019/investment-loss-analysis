"""LossReportSummary (이미 구현됨) → PatternFact 리스트 ("14건 중 9건"의 분모/분자 계산).

라우팅은 분류기(classify_entry) 단독으로 결정된다(router.py: 심리/손절 신호는
routing-excluded, 도메인 에이전트의 해석/분석에만 쓰인다). 따라서 "이 패턴 판정
대상이 된 사이클(분모)"도 분류기가 만든 단일 신호 하나로 충분하다:
  - CycleRouteDecision.profile_eligible — top_score가 정책 임계값(min_route_score 등)을
    넘고 route_type이 단일 주에이전트로 확정된 경우에만 True (abstain/review_required 제외).
도메인별로 다른 잠정 규칙(예: stop_loss_failure 의 breached)을 두지 않는다 — 분류기가
이미 그 사이클을 해당 도메인으로 확신 있게 분류했다는 뜻이므로, 그 결정을 그대로 따른다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .schema import LossReportItem, LossReportSummary
from .tendency_schema import PatternFact, RepresentativeTrade
from .tendency_taxonomy import cohort_match_rate, lookup_taxonomy

_SEVERITY_RANK = {"none": 0, "weak": 1, "moderate": 2, "strong": 3}


def _is_eligible(item: LossReportItem) -> bool:
    """분류기 단독 라우팅이 확신을 갖고 채택한 사이클인가 (router.CycleRouteDecision.profile_eligible)."""
    return bool(item.profile_eligible)


def _max_severity(severities: List[str]) -> str:
    present = [s for s in severities if s]
    if not present:
        return "none"
    return max(present, key=lambda s: _SEVERITY_RANK.get(s, 0))


def _representative_trades(items: List[LossReportItem], limit: int = 2) -> List[RepresentativeTrade]:
    """점수 높은 순으로, 종목명 중복 없이 최대 limit개."""
    ranked = sorted(items, key=lambda i: i.score or 0.0, reverse=True)
    seen: set[str] = set()
    reps: List[RepresentativeTrade] = []
    for item in ranked:
        if item.name in seen:
            continue
        seen.add(item.name)
        reps.append(
            RepresentativeTrade(code=item.code, name=item.name, score=item.score, executed_at=item.executed_at)
        )
        if len(reps) >= limit:
            break
    return reps


def build_pattern_facts(summary: LossReportSummary) -> List[PatternFact]:
    """카드 후보가 없는(=패턴 미감지) 경우 빈 리스트를 반환한다 — 그 자체가 팩트다."""
    eligible_by_agent: Dict[str, int] = defaultdict(int)
    for item in summary.items:
        if _is_eligible(item):
            eligible_by_agent[item.agent_id] += 1

    matched_groups: Dict[str, List[LossReportItem]] = defaultdict(list)
    for item in summary.items:
        if not _is_eligible(item):
            continue
        taxonomy = lookup_taxonomy(item.agent_id, item.label)
        if taxonomy.tag_key in ("unlabeled", "unclassified"):
            continue  # 분류기가 아직 라벨을 못 뱉은 사이클 — 카드화하지 않는다
        if item.severity not in taxonomy.match_severities:
            continue
        matched_groups[taxonomy.pattern_key].append(item)

    facts: List[PatternFact] = []
    for items in matched_groups.values():
        taxonomy = lookup_taxonomy(items[0].agent_id, items[0].label)
        total_eligible = eligible_by_agent.get(taxonomy.category_key, len(items))
        scored = [i.score for i in items if i.score is not None]
        facts.append(
            PatternFact(
                pattern_key=taxonomy.pattern_key,
                category=taxonomy.category,
                category_key=taxonomy.category_key,
                tag=taxonomy.tag,
                tag_key=taxonomy.tag_key,
                title_hint=taxonomy.title_hint,
                matched_count=len(items),
                total_eligible_count=total_eligible,
                match_rate=round(len(items) / total_eligible, 4) if total_eligible else 1.0,
                severity=_max_severity([i.severity for i in items]),
                avg_score=round(sum(scored) / len(scored), 4) if scored else None,
                representative_trades=_representative_trades(items),
                correction_hint=taxonomy.correction_hint,
                cohort=cohort_match_rate(taxonomy.pattern_key),
            )
        )

    facts.sort(key=lambda f: f.matched_count, reverse=True)
    return facts
