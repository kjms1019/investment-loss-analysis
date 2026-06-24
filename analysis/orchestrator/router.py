"""Placeholder router for deciding which agent should review a trade.

The final router should use the unified feature schema and calibrated agent
scores. This version only creates an explicit routing seam for integration.
"""

from __future__ import annotations

from typing import List, Optional

from .schema import CommonFeatureBundle, NormalizedTrade, RouteDecision


AGENT_ENTRY_ERROR = "entry_error"
AGENT_STOP_LOSS_FAILURE = "stop_loss_failure"
AGENT_PSYCH = "psych"


def route_trade(
    trade: NormalizedTrade,
    features: Optional[CommonFeatureBundle] = None,
) -> List[RouteDecision]:
    """Return conservative placeholder route decisions for one trade row."""
    feature_status = "missing"
    if features is not None:
        feature_status = features.feature_status

    if trade.side == "BUY":
        return [
            RouteDecision(
                trade_id=trade.trade_id,
                agent_id=AGENT_ENTRY_ERROR,
                route_status="candidate",
                confidence=0.2,
                reason="buy_execution_entry_review_placeholder",
            )
        ]

    if trade.side == "SELL":
        return [
            RouteDecision(
                trade_id=trade.trade_id,
                agent_id=AGENT_STOP_LOSS_FAILURE,
                route_status="candidate",
                confidence=0.2,
                reason="sell_execution_exit_review_placeholder",
            ),
            RouteDecision(
                trade_id=trade.trade_id,
                agent_id=AGENT_PSYCH,
                route_status="candidate",
                confidence=0.2,
                reason="sell_execution_psych_review_placeholder",
            ),
        ]

    return [
        RouteDecision(
            trade_id=trade.trade_id,
            agent_id="unrouted",
            route_status="skipped",
            confidence=0.0,
            reason="unsupported_trade_side_or_feature_status_{0}".format(feature_status),
        )
    ]
