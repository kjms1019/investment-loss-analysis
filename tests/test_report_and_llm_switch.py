"""빈수 검증 지적 #1·#2 회귀 테스트.

#1 build_user_summary(profile_db_path=...) 가 임시 user_profile DB 를 가리킬 수 있어야
   테스트/환경 분리에서 사용자 리포트가 0건으로 보이지 않는다.
#2 MIRAE_DISABLE_LLM 이면 키가 있어도 generate() 가 fallback 을 반환한다.
"""
import inspect

from analysis.report import builder
from analysis.llm import client as llm_client


def test_build_user_summary_accepts_profile_db_path():
    sig = inspect.signature(builder.build_user_summary)
    assert "profile_db_path" in sig.parameters


def test_llm_disabled_switch_forces_fallback(monkeypatch):
    monkeypatch.setenv("MIRAE_DISABLE_LLM", "1")
    assert llm_client.available() is False
    out = llm_client.generate("sys", "user", fallback="FB")
    assert out == "FB"


def test_llm_switch_off_does_not_force_fallback(monkeypatch):
    # 스위치가 꺼져 있으면(미설정) 차단 로직 자체는 통과 — 실제 호출 여부는 키 유무가 결정.
    monkeypatch.delenv("MIRAE_DISABLE_LLM", raising=False)
    assert llm_client._llm_disabled() is False
