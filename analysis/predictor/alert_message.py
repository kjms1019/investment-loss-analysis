"""실시간 알림 문장 생성 (LLM).

예측기 RiskSignal(점수·유형·근거)을 친근하고 위협적이지 않은 경고 1~2문장으로 옮긴다.
대량·실시간이라 저렴·빠른 모델(ALERT_LLM_MODEL=haiku) 사용. 키 없으면 룰 템플릿 폴백.
예측기의 점수 계산엔 LLM이 안 들어간다 — 여기는 '표현'만. (design-brief 화면 ⑥)
"""
from __future__ import annotations

import json
from typing import Any

from analysis.llm import generate

_SYSTEM = """너는 투자 코치 '왜 잃었지?'의 실시간 알림 작성기다.
주어진 사실(JSON: 시점·유형·위험도·근거·종목·미실현손익)로 짧고 친근한 경고를
1~2문장(80자 내외)으로 쓴다.

원칙:
1. 입력에 없는 수치·사실을 지어내지 않는다.
2. 위협 금지, 비난 금지. 사후 사실 서술형(예: "당신은 이런 경향이 있어요").
3. 매매 추천·미래 지시 금지(규제). "사라/팔라"가 아니라 "조심해볼까요" 톤.
4. 알림 문장만 출력(머리말·따옴표·마크다운 없이)."""

_PROBLEM_KR = {"entry_error": "진입오류", "stop_loss_failure": "손절실패", "unknown": "주의"}


def _template(signal: Any) -> str:
    when = "지금 사려는 종목" if signal.mode == "entry" else "보유 종목"
    prob = _PROBLEM_KR.get(signal.problem_type, "주의")
    if signal.mode == "entry":
        return f"{when}, 과거 '{prob}' 패턴과 비슷한 상황이에요. 한 번 더 생각해볼까요?"
    return f"{when}이 손절 기준에 가까워요. 평소 '{prob}' 경향이 있으니 미리 정한 기준을 지켜보세요."


def build_alert_message(signal: Any, *, fallback: str = "") -> str:
    """RiskSignal → 알림 문장. should_alert 여부와 무관하게 문장만 만든다."""
    facts = {
        "시점": "오늘 매수 직전" if signal.mode == "entry" else "보유 중 현재",
        "유형": _PROBLEM_KR.get(signal.problem_type, "주의"),
        "위험도": signal.risk_level,
        "근거": signal.reasons,
        "종목": signal.code,
        "미실현손익_pct": (signal.features or {}).get("unrealized_return_pct"),
    }
    fb = fallback or _template(signal)
    return generate(
        _SYSTEM, json.dumps(facts, ensure_ascii=False),
        kind="alert", max_tokens=120, fallback=fb,
    )
