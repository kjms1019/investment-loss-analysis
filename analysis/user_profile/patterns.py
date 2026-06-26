"""반복 실수 패턴 집계 — 최종 프로파일 DB의 '성향 리포트' 구성.

패턴 분류체계는 analysis.report.tendency_taxonomy(PATTERN_TAXONOMY)를 **단일 소스**로
공유한다. 이 모듈(write)은 거래별 에이전트 결과(result["label"])를 사용자별로 빈도
집계해 user_profile_patterns 테이블에 저장하고, analysis.report(read)는 같은 taxonomy로
"14건 중 9건"·코호트 등 풍부한 카드를 만든다. (심리는 별도 카드가 아니라 taxonomy의 태그)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, List

from analysis.report.tendency_taxonomy import lookup_taxonomy

# 패턴으로 집계하지 않는 라벨 (정상/데이터부족)
_SKIP_LABELS = {
    None, "", "normal_entry", "해당없음", "low_confidence", "insufficient_data",
    "raw_data_absent", "pre_entry_history_short", "feature_missing_or_invalid",
}


def build_patterns(results: Iterable[Any], *, top_n: int = 4) -> List[dict]:
    """AgentResult 들 → (agent, label) 빈도순 상위 N개. 이름·태그·교정은 taxonomy 공유."""
    agg: dict = defaultdict(lambda: {"agent_id": "", "label": "", "count": 0,
                                     "trade_ids": [], "score_sum": 0.0, "score_n": 0})
    for r in results:
        if getattr(r, "output_status", None) != "ok":
            continue
        res = r.result if isinstance(r.result, dict) else {}
        # 라우팅이 분류기 단독이므로 카드 기준 = profile_eligible(분류기 확신). report와 동일.
        if not (res.get("orchestrator_decision") or {}).get("profile_eligible", True):
            continue
        label = res.get("label")
        if label in _SKIP_LABELS:
            continue
        tax = lookup_taxonomy(r.agent_id, label)
        if tax.tag_key in ("unlabeled", "unclassified"):
            continue  # 분류기가 아직 라벨을 못 뱉은 사이클은 카드화하지 않음
        a = agg[tax.pattern_key]
        a["agent_id"], a["label"] = r.agent_id, label
        a["count"] += 1
        a["trade_ids"].append(r.trade_id)
        if r.score is not None:
            a["score_sum"] += float(r.score)
            a["score_n"] += 1

    patterns: List[dict] = []
    for a in agg.values():
        tax = lookup_taxonomy(a["agent_id"], a["label"])
        patterns.append({
            "pattern_id": f"{a['agent_id']}:{a['label']}",
            "pattern_key": tax.pattern_key,
            "domain": a["agent_id"],
            "category": tax.category,
            "tag": tax.tag,
            "name_ko": tax.title_hint,
            "count": a["count"],
            "trade_ids": a["trade_ids"],
            "representative_trade": a["trade_ids"][0] if a["trade_ids"] else None,
            "avg_score": round(a["score_sum"] / a["score_n"], 4) if a["score_n"] else None,
            "correction": tax.correction_hint,
        })
    patterns.sort(key=lambda p: (-p["count"], -(p["avg_score"] or 0.0)))
    return patterns[:top_n]
