"""총괄 대화 문장 (LLM).

interaction.py가 만든 통계(유형별 빈도·손실금, 1순위 문제)를 따뜻한 대화체 안내/질문으로
다듬는다. 라우팅·집계 '결정'엔 LLM이 안 들어간다 — 여기는 사용자에게 말 거는 '표현'만.
키 없으면 interaction의 템플릿 prompt_body로 폴백.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from analysis.llm import generate

_SYSTEM = """너는 국내주식 거래 복기 서비스 '왜 잃었지?'의 총괄 코치다.
주어진 통계 사실(JSON: 유형별 건수·손실금, 1순위 문제, 질문필요 여부)로 사용자에게
건넬 1~2문장의 대화체 안내를 쓴다.

원칙:
1. 입력에 없는 수치를 지어내지 않는다.
2. 비난 금지, 따뜻하고 차분하게.
3. 질문필요=true 면 "자주 반복된 문제 vs 손실 큰 문제, 어느 쪽부터 볼까요?"처럼
   선택을 부드럽게 묻는다. false 면 1순위 문제를 짚고 분석을 권한다.
4. 안내 문장만 출력(머리말·마크다운 없이)."""

_LABEL = {"entry_error": "진입오류", "stop_loss_failure": "손절실패"}


def llm_interaction_prompt(state: Dict[str, Any], *, fallback: str = "") -> str:
    """interaction_state(dict) → 대화체 안내. 폴백 = state['prompt_body']."""
    stats = {
        _LABEL.get(aid, aid): {"건수": s.get("count"), "손실금합": s.get("loss_amount_sum")}
        for aid, s in (state.get("category_stats") or {}).items()
        if s.get("count")
    }
    facts = {
        "유형별": stats,
        "가장_자주": _LABEL.get(state.get("frequency_winner"), state.get("frequency_winner")),
        "손실금_최다": _LABEL.get(state.get("amount_winner"), state.get("amount_winner")),
        "질문필요": state.get("question_required"),
    }
    fb = fallback or state.get("prompt_body", "")
    return generate(
        _SYSTEM, json.dumps(facts, ensure_ascii=False),
        kind="default", max_tokens=220, fallback=fb,
    )
