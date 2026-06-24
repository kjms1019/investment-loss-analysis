"""Stop-loss-failure agent with the relevant psych-agent pieces absorbed.

Included psych pattern:
- disposition effect

Excluded psych patterns:
- revenge trading and overtrading, because they primarily explain the next
  entry decision rather than the failure to exit a losing position.
"""

from __future__ import annotations

import pandas as pd

from psych_agent.config import Config
from psych_agent.preprocess import preprocess, trades_from_df
from psych_agent.prices import PriceLookup
from psych_agent.schema import Trade

from .psych_split import STOP_LOSS_AGENT_ID, STOP_LOSS_ASSIGNMENTS, detect_stop_loss_psych_findings
from .schema import HybridAgentReport


class StopLossPsychHybridAgent:
    """New hybrid surface for stop-loss failures with exit-psych signals."""

    agent_id = STOP_LOSS_AGENT_ID
    base_agent_id = "stop_loss_failure"

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.prices = PriceLookup(self.config)

    def analyze(self, trades: list[Trade]) -> HybridAgentReport:
        pre = preprocess(trades, self.config)
        findings = detect_stop_loss_psych_findings(pre, self.config, self.prices)
        detected = [f for f in findings if f.detected]

        if detected:
            summary = "손절 실패와 결합된 처분효과 신호가 관찰됨."
        else:
            summary = "손절 실패에 붙일 처분효과 심리 신호는 관찰되지 않음."

        return HybridAgentReport(
            agent_id=self.agent_id,
            base_agent_id=self.base_agent_id,
            psych_assignments=STOP_LOSS_ASSIGNMENTS,
            findings=findings,
            preprocessed=pre,
            summary=summary,
            recommendations=[
                "진입과 동시에 손절 가격과 시간 제한을 기록하고 예외 조건을 미리 정한다.",
                "수익 포지션 청산 전 손실 포지션의 보유 사유를 먼저 점검한다.",
            ],
        )

    def analyze_df(self, df: pd.DataFrame) -> HybridAgentReport:
        return self.analyze(trades_from_df(df))


def run_stop_loss_hybrid(
    trades: list[Trade] | pd.DataFrame,
    config: Config | None = None,
) -> HybridAgentReport:
    agent = StopLossPsychHybridAgent(config)
    if isinstance(trades, pd.DataFrame):
        return agent.analyze_df(trades)
    return agent.analyze(trades)
