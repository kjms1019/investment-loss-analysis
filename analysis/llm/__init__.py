"""공용 Claude LLM 클라이언트 — 리포트·거래설명·알림·총괄대화 공유.

    from analysis.llm import generate, available
    text = generate(system="...", user="...", kind="alert", fallback="룰 문구")
"""
from .client import available, generate, model_for, strip_code_fence

__all__ = ["available", "generate", "model_for", "strip_code_fence"]
