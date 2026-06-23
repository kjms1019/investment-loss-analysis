"""준모 심리·과매매 분석 에이전트.

완결된 국내주식 거래내역을 사후 복기해 3가지 심리 매매 패턴을 진단한다.
  - 리벤지 트레이딩 (손실 직후 충동 재진입)        ← 결정/시간 축
  - 과매매 (Barber & Odean 2000)                  ← 결정/빈도 축
  - 처분효과 (Shefrin & Statman 1985 / Odean 1998) ← 포지션/보유기간 축

룰·통계 엔진이 팩트를 계산(결정적)하고, LLM이 진단 문장만 입힌다(하이브리드).
LLM 키가 없으면 템플릿 폴백으로도 그대로 구동된다.
"""

from .config import Config
from .agent import PsychAgent, run

__all__ = ["Config", "PsychAgent", "run"]
