"""공용 Claude(Anthropic) LLM 클라이언트.

ANTHROPIC_API_KEY + anthropic 패키지가 있으면 Claude를 호출하고, 없거나 실패하면
fallback(룰/템플릿 문구)을 반환한다 → 키 없어도 서비스가 안 깨진다.

모든 LLM 자연어 생성(리포트·거래 원인설명·실시간 알림·총괄 대화)이 이 헬퍼를 공유한다.
원칙: 사실(숫자·근거)은 호출자가 구조화해 넘기고, LLM은 '표현'만 한다(환각 방지).

모델 선택(kind):
  "default" → LLM_MODEL        (리포트·거래설명, 품질)  기본 claude-sonnet-4-6
  "alert"   → ALERT_LLM_MODEL  (실시간 알림, 저렴·빠름)  기본 claude-haiku-4-5-20251001
  "psych"   → PSYCH_LLM_MODEL  (심리 진단)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MODEL_ENV = {"default": "LLM_MODEL", "alert": "ALERT_LLM_MODEL", "psych": "PSYCH_LLM_MODEL"}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except Exception:
        pass


@lru_cache(maxsize=1)
def _client():
    _load_env()
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception:
        return None


def _llm_disabled() -> bool:
    """검증/오프라인용 강제 차단 스위치. 키가 있어도 토큰을 안 쓰게 한다.

    MIRAE_DISABLE_LLM=1|true|yes|on 이면 모든 LLM 생성이 fallback 으로 떨어진다.
    (키가 없을 때 자동 fallback 과 별개로, '키는 있지만 일부러 안 부르는' 검증용.)
    """
    return os.getenv("MIRAE_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes", "on")


def available() -> bool:
    """LLM 호출 가능(키+패키지) 여부. 차단 스위치가 켜지면 False."""
    return not _llm_disabled() and _client() is not None


def strip_code_fence(text: str) -> str:
    """LLM이 ```json ... ``` 으로 감싸 반환할 때 펜스를 벗겨 순수 본문만 반환."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def model_for(kind: str = "default") -> str:
    env = _MODEL_ENV.get(kind, "LLM_MODEL")
    return os.getenv(env) or os.getenv("LLM_MODEL") or _DEFAULT_MODEL


def generate(
    system: str,
    user: str,
    *,
    kind: str = "default",
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    fallback: str = "",
) -> str:
    """Claude로 텍스트 생성. 불가/실패/차단 시 fallback 반환."""
    if _llm_disabled():
        return fallback
    client = _client()
    if client is None:
        return fallback
    try:
        resp = client.messages.create(
            model=model or model_for(kind),
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = "".join(parts).strip()
        return text or fallback
    except Exception:
        return fallback
