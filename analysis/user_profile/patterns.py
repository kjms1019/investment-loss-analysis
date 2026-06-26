"""반복 실수 패턴 집계 — 최종 프로파일 DB의 '성향 리포트' 구성.

거래별 에이전트 결과(result["label"], result["psych"])에서 명명된 패턴을 뽑아
사용자별로 빈도 집계한다. design-brief의 "반복 패턴 카드"에 해당.
  예) "손절선 이탈 후 지연 보유 → 4건", "단기 과열 진입 → 3건"
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, List

# label_id → (한글 패턴명, 한 줄 교정 조언)
PATTERN_META = {
    # 진입오류 (min1_labeler label_id)
    "gap_up_chase": ("상승 구간 단기 추격 진입", "급등 직후 추격 매수를 멈추고 눌림을 기다리세요."),
    "weak_flow_near_high": ("고점 근처 수급 부족 진입", "신고가권은 거래량 동반을 확인하고 진입하세요."),
    "short_term_overheat": ("단기 과열 구간 진입", "RSI 과열·단기 급등 구간 추격을 피하세요."),
    "early_pullback_entry": ("지지 확인 없는 눌림목 조기 진입", "지지선 반등을 확인한 뒤 진입하세요."),
    "unstable_pullback_flow": ("수급 불안 눌림목 진입", "거래량이 살아날 때까지 기다리세요."),
    "premature_bottom_fishing": ("하락 중 성급한 저가 매수", "추세 반전 신호 없이 저가 매수를 자제하세요."),
    "downtrend_without_reversal": ("반등 확인 없는 하락추세 진입", "이평 기울기·반등을 확인하고 진입하세요."),
    "range_top_chase": ("박스권 상단 추격 진입", "박스 상단보다 하단 지지에서 분할 진입하세요."),
    "low_liquidity_range_chase": ("저유동성 박스권 추격", "저유동성 종목 추격은 슬리피지 위험이 큽니다."),
    # 손절실패 (judgment_type)
    "물타기형": ("손실 중 물타기(추가매수)", "'손실 중 추가매수 금지' 규칙을 미리 정해두세요."),
    "지연형": ("손절선 이탈 후 지연 보유", "손절선을 넘기면 기계적으로 끊는 규칙을 지키세요."),
    # 흡수된 심리
    "psych_revenge": ("리벤지 — 손실 직후 충동 재진입", "손실 직후 30분은 재진입을 멈추고 한 박자 쉬세요."),
    "psych_disposition": ("처분효과 — 이익 짧게·손실 길게", "손실도 이익처럼 미리 정한 기준에서 끊으세요."),
}

# 패턴으로 집계하지 않는 라벨 (정상/데이터부족)
_SKIP_LABELS = {
    None, "", "normal_entry", "해당없음", "low_confidence", "insufficient_data",
    "raw_data_absent", "pre_entry_history_short", "feature_missing_or_invalid",
}


def _meta(label: str):
    return PATTERN_META.get(label, (str(label), "반복되는 패턴입니다 — 진입·청산 규칙을 점검하세요."))


def build_patterns(results: Iterable[Any], *, top_n: int = 4) -> List[dict]:
    """AgentResult 들 → 명명된 반복 패턴 빈도순 상위 N개."""
    agg: dict = defaultdict(lambda: {"domain": "", "label": "", "count": 0,
                                     "trade_ids": [], "score_sum": 0.0, "score_n": 0})

    def add(pattern_id: str, domain: str, label: str, result: Any) -> None:
        a = agg[pattern_id]
        a["domain"], a["label"] = domain, label
        a["count"] += 1
        a["trade_ids"].append(result.trade_id)
        if result.score is not None:
            a["score_sum"] += float(result.score)
            a["score_n"] += 1

    for r in results:
        if getattr(r, "output_status", None) != "ok":
            continue
        res = r.result if isinstance(r.result, dict) else {}
        label = res.get("label")
        if label not in _SKIP_LABELS:
            add(f"{r.agent_id}:{label}", r.agent_id, label, r)
        psych = res.get("psych") or {}
        if psych.get("detected"):
            p = f"psych_{psych.get('pattern')}"
            add(f"{r.agent_id}:{p}", r.agent_id, p, r)

    patterns: List[dict] = []
    for pattern_id, a in agg.items():
        name, correction = _meta(a["label"])
        patterns.append({
            "pattern_id": pattern_id,
            "domain": a["domain"],
            "name_ko": name,
            "count": a["count"],
            "trade_ids": a["trade_ids"],
            "representative_trade": a["trade_ids"][0] if a["trade_ids"] else None,
            "avg_score": round(a["score_sum"] / a["score_n"], 4) if a["score_n"] else None,
            "correction": correction,
        })
    patterns.sort(key=lambda p: (-p["count"], -(p["avg_score"] or 0.0)))
    return patterns[:top_n]
