"""거래별 원인 설명 (LLM 한 단락).

분류기/에이전트가 만든 사실(label·evidence·종목·심각도)만으로 손실 거래 하나의 원인을
차분히 한 단락으로 설명한다. 사실은 코드가 주고 LLM은 '표현'만(환각 방지).
키 없으면 normalizers의 룰 narrative로 폴백 → 안 깨짐. (design-brief 화면 ④)
"""
from __future__ import annotations

import json
from typing import Any, Optional

from analysis.llm import generate
from .normalizers import normalize

_SYSTEM = """너는 국내주식 거래 복기 코치 '왜 잃었지?'의 거래별 설명 작성기다.
주어진 사실(JSON: 종목·유형·라벨·근거)만으로 이 손실 거래의 원인을 한 단락
(2~3문장, 120자 내외)으로 쓴다.

원칙:
1. 입력에 없는 수치·종목·사실을 절대 새로 만들지 않는다.
2. 비난 금지. "잘못했다"가 아니라 "이런 패턴이 관찰된다"는 관찰자 시점.
3. 사후 복기 톤. 미래 지시·매매 추천 금지.
4. 설명 문장만 출력(머리말·마크다운·따옴표 없이).
5. 줄표(—, –)를 쓰지 않는다. 쉼표·마침표·가운뎃점(·)으로 끊는다."""


def explain_trade(
    *,
    agent_id: str,
    name: str,
    label: str,
    evidence: Any = None,
    severity: Optional[str] = None,
    fallback: str = "",
) -> str:
    """구조화된 사실 → 한 단락 설명. 키 없으면 fallback."""
    facts = {
        "종목": name,
        "유형": "손절실패" if agent_id == "stop_loss_failure" else "진입오류",
        "라벨": label,
        "심각도": severity,
        "근거": (evidence or [])[:6] if isinstance(evidence, list) else evidence,
    }
    return generate(
        _SYSTEM, json.dumps(facts, ensure_ascii=False),
        kind="default", max_tokens=220, fallback=fallback,
    )


def explain_report_item(item: Any) -> str:
    """report.LossReportItem → LLM 설명. 폴백 = normalizers 룰 narrative."""
    rule_narrative, evidence = normalize(item.agent_id, getattr(item, "raw_result", {}) or {})
    fb = rule_narrative or f"{item.name} · {item.label}"
    return explain_trade(
        agent_id=item.agent_id, name=item.name, label=item.label,
        evidence=evidence, severity=item.severity, fallback=fb,
    )


def enrich_summary_narratives(summary: Any) -> Any:
    """LossReportSummary의 각 거래 narrative를 LLM 설명으로 채운다(in-place).

    LLM 미사용(키 없음) 시 각 호출이 룰 narrative로 폴백되므로 그대로 안전.
    리포트 생성 시점에만 호출(거래 수만큼 LLM 호출 — on-demand)."""
    from analysis.llm import available
    if not available():
        return summary  # 키 없으면 룰 narrative 유지 (불필요한 호출 안 함)
    for item in summary.items:
        item.narrative = explain_report_item(item)
    return summary
