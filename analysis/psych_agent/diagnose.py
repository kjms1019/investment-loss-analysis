"""진단 문장화 (룰+LLM 하이브리드의 LLM 단).

룰/통계 엔진이 만든 팩트(TypeFinding)는 그대로 두고, 여기서는 '문장'만 입힌다.
  · ANTHROPIC_API_KEY 가 있고 anthropic 패키지가 설치돼 있으면 Claude 호출.
  · 없으면 결정적 템플릿 폴백 → 키 없이도 그대로 구동된다.

LLM은 수치를 새로 만들지 않는다. 주어진 팩트만 해석·요약하도록 강하게 제약한다.
"""

from __future__ import annotations

import json
import os

from .config import Config
from .schema import TypeFinding

_SEVERITY_KR = {
    "none": "해당 없음",
    "weak": "약",
    "moderate": "중",
    "strong": "강",
}

# 유형별 개인화 교정 규칙 (추천 아님 — 행동 교정 가이드)
_CORRECTION = {
    "revenge": "손절 직후 최소 {window}분(권장: 당일 종가까지) 신규 진입을 잠그는 '쿨다운 룰'을 두세요. 만회 충동이 가장 강한 구간을 물리적으로 차단합니다.",
    "overtrading": "월 거래 건수 상한(예: 개인 중앙값 수준)을 사전에 정하고, 진입 전 '이 거래가 계획된 것인가'를 1줄로 적는 체크를 도입하세요.",
    "disposition": "진입과 동시에 손절·익절 가격을 같이 적어두고 기계적으로 집행하세요. 손실은 빨리 끊고 수익은 끌고 가도록 비대칭을 교정합니다.",
}


def _build_correction(f: TypeFinding, config: Config) -> str:
    tmpl = _CORRECTION.get(f.type_key, "")
    return tmpl.format(window=config.revenge_window_min)


# ─────────────────────────────────────────────────────────────────
# 템플릿 폴백
# ─────────────────────────────────────────────────────────────────
def _template_diagnose(findings: list[TypeFinding], config: Config) -> dict:
    detected = [f for f in findings if f.detected]
    detected.sort(key=lambda f: {"strong": 3, "moderate": 2, "weak": 1}.get(f.severity, 0), reverse=True)

    lines = []
    per_type = {}
    for f in findings:
        sev = _SEVERITY_KR[f.severity]
        if f.detected:
            body = f"**{f.type_label}** ({sev}): " + " / ".join(f.evidence)
            correction = _build_correction(f, config)
        else:
            body = f"**{f.type_label}**: 유의한 신호 없음."
            correction = ""
        per_type[f.type_key] = {
            "label": f.type_label,
            "severity": f.severity,
            "summary": body,
            "correction": correction,
        }
        lines.append(body)
        if correction:
            lines.append(f"  → 교정: {correction}")

    if detected:
        head = "이번 기간 거래에서 " + ", ".join(
            f"{f.type_label}({_SEVERITY_KR[f.severity]})" for f in detected
        ) + " 패턴이 관찰됩니다."
    else:
        head = "이번 기간에는 세 가지 심리 매매 패턴에서 유의한 신호가 관찰되지 않았습니다."

    return {
        "engine": "template",
        "headline": head,
        "body": "\n".join(lines),
        "per_type": per_type,
    }


# ─────────────────────────────────────────────────────────────────
# LLM (Anthropic)
# ─────────────────────────────────────────────────────────────────
def _llm_diagnose(findings: list[TypeFinding], config: Config) -> dict | None:
    if not config.use_llm:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return None

    model = os.environ.get("PSYCH_LLM_MODEL", config.llm_model)
    facts = [
        {
            "type": f.type_key,
            "label": f.type_label,
            "detected": f.detected,
            "severity": f.severity,
            "metrics": f.metrics,
            "evidence": f.evidence,
            "reference": f.reference,
        }
        for f in findings
    ]

    system = (
        "너는 국내주식 거래 복기 시스템의 '심리·과매매' 분석 에이전트다. "
        "아래 팩트(룰/통계 엔진이 계산한 결과)만 근거로 진단을 작성한다. "
        "절대 새로운 수치를 지어내지 말고, 매매 추천도 하지 마라(복기·교정만). "
        "차분하고 구체적인 한국어로, 각 유형마다 (1) 무슨 일이 있었는지 "
        "(2) 왜 문제인지(학술 근거 한 줄) (3) 다음에 어떻게 교정할지를 적는다."
    )
    user = (
        "다음은 한 사용자의 최근 거래 복기 팩트(JSON)다:\n\n"
        + json.dumps(facts, ensure_ascii=False, indent=2)
        + "\n\n이 팩트만으로 진단 리포트를 작성하라."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return {"engine": f"anthropic:{model}", "headline": "", "body": text.strip(), "per_type": {}}
    except Exception as e:  # noqa: BLE001 - 폴백을 위해 광범위 캐치
        return {"engine": "llm_error", "error": str(e)}


def diagnose(findings: list[TypeFinding], config: Config | None = None) -> dict:
    config = config or Config()
    result = _llm_diagnose(findings, config)
    if result and result.get("engine", "").startswith("anthropic"):
        return result
    # LLM 에러/미사용/키없음 → 템플릿 폴백
    fallback = _template_diagnose(findings, config)
    if result and result.get("engine") == "llm_error":
        fallback["llm_error"] = result["error"]
    return fallback
