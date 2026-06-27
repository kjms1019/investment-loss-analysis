"""?⑤벊??Claude(Anthropic) LLM ?????곷섧??

ANTHROPIC_API_KEY + anthropic ???텕筌왖揶쎛 ??됱몵筌?Claude???紐꾪뀱??랁? ??얘탢????쎈솭??롢늺
fallback(????쀫탣???얜㈇????獄쏆꼹???뺣뼄 ??????곷선????뺥돩??? ??繹먥뫁彛??

筌뤴뫀諭?LLM ?癒?염????밴쉐(?귐뗫７?留욌０援???癒?뵥??살구夷??쇰뻻揶????뵝夷뚨룯?룻겣 ???????????곭몴??⑤벊???뺣뼄.
?癒?뒅: ??????ъ쁽夷뚧뉩?④탢)?? ?紐꾪뀱?癒? ?닌듼?酉鍮???띾┛?? LLM?? '??쀬겱'筌???뺣뼄(??띿퍟 獄쎻뫗?).

筌뤴뫀???醫뤾문(kind):
  "default" ??LLM_MODEL        (?귐뗫７?留욌０援??뤾퐬筌? ??됱춳)  疫꿸퀡??claude-sonnet-4-6
  "alert"   ??ALERT_LLM_MODEL  (??쇰뻻揶????뵝, ????붾８?뚨뵳?  疫꿸퀡??claude-haiku-4-5-20251001
  "psych"   ??PSYCH_LLM_MODEL  (????筌욊쑬??
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
    """野꺜筌???쎈늄??깆뵥??揶쏅벡??筌△뫀????쇱맄燁? ??? ??됰선???醫뤾쿃?????怨뚯쓺 ??뺣뼄.

    MIRAE_DISABLE_LLM=1|true|yes|on ????筌뤴뫀諭?LLM ??밴쉐??fallback ??곗쨮 ??λ선筌욊쑬??
    (??? ??곸뱽 ???癒?짗 fallback ??癰귢쑨而삥에? '??삳뮉 ???筌?????????봔?쒕??? 野꺜筌앹빘??)
    """
    return os.getenv("MIRAE_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes", "on")


def available() -> bool:
    """LLM ?紐꾪뀱 揶쎛???????텕筌왖) ???. 筌△뫀????쇱맄燁살꼵? ?녹뮇?筌?False."""
    return not _llm_disabled() and _client() is not None


def strip_code_fence(text: str) -> str:
    """LLM??```json ... ``` ??곗쨮 揶쏅Ŋ??獄쏆꼹???????뽯뮞??甕곗り볼 ??뽯땾 癰귣챶揆筌?獄쏆꼹??"""
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
    max_output_chars: Optional[int] = None,
) -> str:
    """Claude嚥???용뮞????밴쉐. ?븍뜃?/??쎈솭/筌△뫀????fallback 獄쏆꼹??"""
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
        return _clean_generated_text(text, fallback=fallback, max_output_chars=max_output_chars)
    except Exception:
        return fallback

def _clean_generated_text(
    text: str,
    *,
    fallback: str = "",
    max_output_chars: Optional[int] = None,
) -> str:
    """Small UX guardrail for natural-language LLM output.

    This does not judge facts. It only removes common wrapping artifacts and
    falls back when the model ignores a strict length budget.
    """
    cleaned = strip_code_fence(text).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    if not cleaned:
        return fallback
    if max_output_chars is not None and len(cleaned) > max_output_chars:
        return fallback
    return cleaned
