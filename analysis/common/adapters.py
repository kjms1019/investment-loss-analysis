"""에이전트별 입출력 어댑터.

공통 스키마 ↔ 각 에이전트 내부 스키마 변환.
각 에이전트는 이 모듈만 import해서 사용.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from common.schema import AgentResult, RawTrade, TradeCycle, severity_to_score


# ──────────────────────────────────────────────
# 입력 어댑터: 공통 → 에이전트 내부 스키마
# ──────────────────────────────────────────────

def to_junmo_trade(raw: RawTrade) -> dict:
    """RawTrade → 준모 psych_agent Trade 호환 dict."""
    return {
        "datetime": raw.datetime,
        "code": raw.code,
        "name": raw.name,
        "side": raw.side,
        "qty": raw.qty,
        "price": raw.price,
    }


def to_younghyun_transaction(raw: RawTrade) -> dict:
    """RawTrade → 영현 손절실패 Transaction 호환 dict."""
    return {
        "trade_id": f"{raw.code}_{raw.datetime.strftime('%Y%m%d%H%M%S')}",
        "ticker": raw.code,
        "side": raw.side,
        "qty": raw.qty,
        "price": raw.price,
        "executed_at": raw.datetime.date(),
        "fee": raw.fee,
    }


def to_subin_trade(cycle: TradeCycle) -> dict:
    """TradeCycle → 수빈 entry-error-agent 호환 dict."""
    return {
        "trade_id": cycle.trade_id,
        "symbol": cycle.code,
        "buy_time": cycle.entry_dt.isoformat() if cycle.entry_dt else None,
        "buy_price": cycle.entry_price,
        "sell_time": cycle.exit_dt.isoformat() if cycle.exit_dt else None,
        "sell_price": cycle.exit_price,
        "quantity": cycle.qty,
        "realized_pnl": cycle.realized_pnl,
        "realized_pnl_pct": cycle.realized_pnl_pct,
        "fees": cycle.fee,
    }


# ──────────────────────────────────────────────
# 출력 어댑터: 에이전트 결과 → AgentResult
# ──────────────────────────────────────────────

def from_subin_result(trade_id: str, result: dict[str, Any]) -> AgentResult:
    """수빈 에이전트 출력 → AgentResult.

    result 구조:
      classification_result["risk_score_result"]["entry_error_risk_score"] (0~100)
      classification_result["label_results"][i]["label_id"], ["triggered"]
    """
    risk = result.get("risk_score_result", {})
    raw_score = risk.get("entry_error_risk_score") or 0

    triggered = [l for l in result.get("label_results", []) if l.get("triggered")]
    top_label = triggered[0]["label_id"] if triggered else "normal_entry"

    severity = risk.get("severity", "")
    summary = f"진입오류 위험점수 {raw_score}/100 (severity: {severity})"

    return AgentResult(
        agent_type="entry_error",
        trade_id=trade_id,
        score=round(raw_score / 100, 4),
        label=top_label,
        summary=summary,
        details=result,
    )


def from_younghyun_result(trade_id: str, result: dict[str, Any]) -> AgentResult:
    """영현 에이전트 출력 → AgentResult.

    result 구조:
      result["score"] (0~1)
      result["judgment_type"]: "물타기형" | "지연형" | "해당없음"
      result["narrative"]: 자연어 요약
    """
    return AgentResult(
        agent_type="stop_fail",
        trade_id=trade_id,
        score=round(float(result.get("score", 0.0)), 4),
        label=result.get("judgment_type", "해당없음"),
        summary=result.get("narrative", ""),
        details=result,
    )


def from_junmo_result(trade_id: str, result: dict[str, Any]) -> AgentResult:
    """준모 에이전트 출력 → AgentResult.

    result 구조 (PsychReport.to_dict()):
      result["findings"][i]["type"], ["severity"], ["detected"]
      result["diagnosis"]

    감지된 패턴 중 severity가 가장 강한 것을 대표로 사용.
    """
    findings = result.get("findings", [])
    detected = [f for f in findings if f.get("detected")]
    top = max(detected, key=lambda f: severity_to_score(f.get("severity", "none")), default={})

    score = severity_to_score(top.get("severity", "none"))
    label = top.get("type", "none")
    summary = result.get("diagnosis", {}).get("summary", "")

    return AgentResult(
        agent_type="psych",
        trade_id=trade_id,
        score=score,
        label=label,
        summary=summary,
        details=result,
    )
