"""Entry-error agent with the relevant psych-agent pieces absorbed.

Included psych patterns:
- revenge trading

Excluded psych pattern:
- disposition effect, because it explains holding and exit behavior better
  than the original entry decision.
- overtrading, because it is a broad frequency/habit signal and is not specific
  enough to either entry-error or stop-loss-failure.
"""

from __future__ import annotations

import pandas as pd

from psych_agent.config import Config
from psych_agent.preprocess import preprocess, trades_from_df
from psych_agent.schema import Trade

from .psych_split import ENTRY_ERROR_AGENT_ID, ENTRY_ERROR_ASSIGNMENTS, detect_entry_error_psych_findings
from .schema import HybridAgentReport


class EntryErrorPsychHybridAgent:
    """New hybrid surface for entry errors with decision-psych signals."""

    agent_id = ENTRY_ERROR_AGENT_ID
    base_agent_id = "entry_error"

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def analyze(self, trades: list[Trade]) -> HybridAgentReport:
        pre = preprocess(trades, self.config)
        findings = detect_entry_error_psych_findings(pre, self.config)
        detected = [f for f in findings if f.detected]

        if detected:
            labels = ", ".join(f.type_label for f in detected)
            summary = f"진입 의사결정 오류와 결합된 심리 신호가 관찰됨: {labels}."
        else:
            summary = "진입 오류에 붙일 리벤지/과매매 심리 신호는 관찰되지 않음."

        return HybridAgentReport(
            agent_id=self.agent_id,
            base_agent_id=self.base_agent_id,
            psych_assignments=ENTRY_ERROR_ASSIGNMENTS,
            findings=findings,
            preprocessed=pre,
            summary=summary,
            recommendations=[
                "손실 직후 일정 시간 신규 진입을 차단하는 쿨다운 규칙을 둔다.",
            ],
        )

    def analyze_df(self, df: pd.DataFrame) -> HybridAgentReport:
        return self.analyze(trades_from_df(df))


def run_entry_error_hybrid(
    trades: list[Trade] | pd.DataFrame,
    config: Config | None = None,
) -> HybridAgentReport:
    agent = EntryErrorPsychHybridAgent(config)
    if isinstance(trades, pd.DataFrame):
        return agent.analyze_df(trades)
    return agent.analyze(trades)
