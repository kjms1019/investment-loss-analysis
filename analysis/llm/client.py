"""공용 LLM 클라이언트 — Qwen(OpenAI 호환 규약) 기반.

금융권 망분리(폐쇄망) 환경을 전제로 설계했다. 특정 벤더 SDK에 묶이지 않고
**OpenAI 호환 chat/completions 규약**만 사용하므로, `LLM_BASE_URL` 하나만 바꾸면
동일한 코드가 그대로 사내 추론 서버로 옮겨간다.

    클라우드 데모   LLM_BASE_URL=https://openrouter.ai/api/v1
    사내 vLLM      LLM_BASE_URL=http://10.0.0.5:8000/v1
    로컬 Ollama    LLM_BASE_URL=http://localhost:11434/v1

Qwen을 고른 이유는 오픈웨이트 모델이라 가중치를 폐쇄망 안으로 반입해
자체 GPU에서 구동할 수 있기 때문이다. 외부 API 호출이 금지된 금융사 내부망에서도
같은 서비스가 동작한다.

이 모듈은 LLM 호출의 **단일 창구**다. 리포트·거래설명·알림·총괄대화·심리진단이
모두 여기 `generate()`를 거친다. 새 호출 경로를 따로 만들지 말 것.

LLM은 '설명'만 담당한다(문장 생성). 수치·판정은 전부 룰/통계 엔진이 계산한 값이며,
LLM이 실패하면 항상 룰 템플릿 문장으로 폴백해 서비스 흐름이 끊기지 않는다.

용도별 모델(kind):
  "default" → LLM_MODEL        (리포트·거래별 원인 설명 — 품질 우선)
  "alert"   → ALERT_LLM_MODEL   (실시간 알림 — 저지연·저비용)
  "psych"   → PSYCH_LLM_MODEL   (심리 진단 문장화)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DEFAULT_MODEL = "qwen/qwen3-30b-a3b-instruct-2507"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_MODEL_ENV = {"default": "LLM_MODEL", "alert": "ALERT_LLM_MODEL", "psych": "PSYCH_LLM_MODEL"}

# 사내/로컬 추론 서버는 인증이 없는 경우가 많다. OpenAI SDK는 빈 키를 거부하므로
# 이런 엔드포인트에는 자리표시자 키를 넣어준다.
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
_PLACEHOLDER_KEY = "not-needed"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except Exception:
        pass


def base_url() -> str:
    return (os.getenv("LLM_BASE_URL") or _DEFAULT_BASE_URL).strip()


def _is_local_endpoint(url: str) -> bool:
    return any(h in url for h in _LOCAL_HOSTS)


@lru_cache(maxsize=1)
def _client():
    _load_env()
    url = base_url()
    key = (os.getenv("LLM_API_KEY") or "").strip()
    if not key:
        # 사내/로컬 엔드포인트는 키 없이도 동작한다. 외부 엔드포인트인데 키가 없으면
        # 호출해봐야 401이므로 아예 클라이언트를 만들지 않고 폴백으로 보낸다.
        if not _is_local_endpoint(url):
            return None
        key = _PLACEHOLDER_KEY
    try:
        from openai import OpenAI
        return OpenAI(api_key=key, base_url=url, timeout=30.0, max_retries=2)
    except Exception:
        return None


def _llm_disabled() -> bool:
    """검증·오프라인 실행용 강제 차단 스위치가 켜져 있는지.

    MIRAE_DISABLE_LLM=1|true|yes|on 이면 키가 있어도 모든 LLM 생성이 폴백으로 떨어져
    토큰을 한 톨도 쓰지 않는다. (유저플로우·데이터 검증을 공짜로 돌리기 위한 장치)
    """
    return os.getenv("MIRAE_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes", "on")


def available() -> bool:
    """LLM 호출이 가능한 상태인지. 차단 스위치가 켜져 있으면 False."""
    return not _llm_disabled() and _client() is not None


def strip_code_fence(text: str) -> str:
    """LLM이 ```json ... ``` 으로 감싸 보낸 응답에서 코드펜스를 벗겨낸다."""
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


def engine_tag(kind: str = "default", model: Optional[str] = None) -> str:
    """리포트 스키마에 기록할 엔진 표기. UI가 'LLM · <모델>' 로 보여준다."""
    return f"llm:{model or model_for(kind)}"


def generate(
    system: str,
    user: str,
    *,
    kind: str = "default",
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    fallback: str = "",
    max_output_chars: Optional[int] = None,
) -> str:
    """LLM 문장 생성. 키 없음·차단·네트워크 오류 어느 경우든 fallback 을 돌려준다."""
    if _llm_disabled():
        return fallback
    client = _client()
    if client is None:
        return fallback
    try:
        resp = client.chat.completions.create(
            model=model or model_for(kind),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return _clean_generated_text(text, fallback=fallback, max_output_chars=max_output_chars)
    except Exception:
        return fallback


def _strip_reasoning(text: str) -> str:
    """thinking 계열 모델이 앞에 붙이는 <think>…</think> 추론 블록을 제거한다.

    기본 모델은 instruct(비-thinking) 라 이 블록이 나오지 않는다. 다만 LLM_MODEL 을
    thinking 모델로 바꿔 끼우면, 추론 토큰이 본문으로 새어 들어오고 길이 예산
    (max_output_chars)까지 초과해 **에러 없이 전부 템플릿 폴백**으로 떨어진다.
    모델 교체가 조용한 기능 정지로 이어지지 않도록 여기서 걷어낸다.
    """
    import re
    t = text or ""
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S | re.I)
    # 닫는 태그만 남는 경우(열린 태그가 잘린 응답) — 마지막 </think> 뒤만 취한다.
    if "</think>" in t.lower():
        idx = t.lower().rindex("</think>") + len("</think>")
        t = t[idx:]
    return t.strip()


def _clean_generated_text(
    text: str,
    *,
    fallback: str = "",
    max_output_chars: Optional[int] = None,
) -> str:
    """자연어 출력에 대한 최소한의 UX 가드레일.

    사실 판정은 하지 않는다. 흔한 래핑 아티팩트(코드펜스·따옴표)만 제거하고,
    모델이 길이 예산을 무시했을 때 폴백으로 떨어뜨린다.
    """
    cleaned = _strip_reasoning(text)
    cleaned = strip_code_fence(cleaned).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    if not cleaned:
        return fallback
    if max_output_chars is not None and len(cleaned) > max_output_chars:
        return fallback
    return cleaned
