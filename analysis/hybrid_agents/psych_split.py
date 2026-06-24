"""Split psych-agent functionality into entry-error and stop-loss domains."""

from __future__ import annotations

from psych_agent.config import Config
from psych_agent.detectors import detect_disposition, detect_revenge
from psych_agent.prices import PriceLookup
from psych_agent.schema import Preprocessed, TypeFinding

from .schema import PsychAssignment


ENTRY_ERROR_AGENT_ID = "entry_error_psych_hybrid"
STOP_LOSS_AGENT_ID = "stop_loss_psych_hybrid"


ENTRY_ERROR_ASSIGNMENTS = [
    PsychAssignment(
        type_key="revenge",
        target_agent_id=ENTRY_ERROR_AGENT_ID,
        rationale=(
            "손실 직후 빠른 재진입과 포지션 확대는 청산 이후의 다음 매수 결정이 "
            "무너진 패턴이므로 진입 오류 쪽에 더 가깝다."
        ),
    ),
]


STOP_LOSS_ASSIGNMENTS = [
    PsychAssignment(
        type_key="disposition",
        target_agent_id=STOP_LOSS_AGENT_ID,
        rationale=(
            "처분효과는 이익은 빨리 실현하고 손실은 오래 보유하는 비대칭으로, "
            "손절 실패의 심리적 하위 원인에 가장 직접적으로 대응한다."
        ),
    )
]


def detect_entry_error_psych_findings(
    pre: Preprocessed, config: Config | None = None
) -> list[TypeFinding]:
    """Return psych findings that should feed the entry-error hybrid agent."""
    config = config or Config()
    if not pre.trades:
        return []
    return [detect_revenge(pre, config)]


def detect_stop_loss_psych_findings(
    pre: Preprocessed,
    config: Config | None = None,
    prices: PriceLookup | None = None,
) -> list[TypeFinding]:
    """Return psych findings that should feed the stop-loss hybrid agent."""
    config = config or Config()
    if not pre.sell_events:
        return []
    return [detect_disposition(pre, config, prices)]
