"""에이전트 실행 어댑터.

각 에이전트를 격리 로더(`_agent_loader`)로 안전하게 호출하고, 결과를
오케스트레이터 공통 `AgentResult` 로 변환한다.

핵심 설계:
- 영현(손절실패)·준모(심리)는 LLM 없이 룰로 점수를 내므로 라우팅 신호 계산용으로
  전체를 한 번 돌려도 토큰 비용이 없다. 따라서 pipeline 이 이들을 1회 실행하고
  결과를 재사용한다. (entry_error 만 라우팅된 사이클에 대해 개별 호출)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .schema import AgentResult
from ._agent_loader import vendored_agent

# 프로젝트 루트 및 에이전트 폴더
_PROJECT_ROOT     = Path(__file__).resolve().parents[2]
_AGENTS_DIR       = _PROJECT_ROOT / "agents"
_ENTRY_ERROR_DIR  = _AGENTS_DIR / "entry-error-agent"
_STOP_FAIL_DIR    = _AGENTS_DIR / "손절실패"
from analysis.common.paths import MIN1_DIR as _MIN1_DIR          # 실 1분봉 (에이전트 피처용, MIRAE_DATA_ROOT)

# 각 vendored 에이전트가 점유하는 최상위 모듈명 (격리 대상)
_STOP_FAIL_MODULES = [
    "agent", "schema", "config", "cycles", "path_features",
    "rules", "scoring", "report", "data_loader",
]
_ENTRY_ERROR_MODULES = [
    "src", "src.feature_engineering", "src.min1_classifier",
    "src.min1_labeler", "src.data_loader", "src.data_quality",
    "src.schema_mapper", "src.entry_classifier",
]

AGENT_ENTRY_ERROR       = "entry_error"
AGENT_STOP_LOSS_FAILURE = "stop_loss_failure"

# 각 도메인이 흡수하는 심리 패턴
PSYCH_PATTERN_BY_AGENT = {
    AGENT_ENTRY_ERROR:       "revenge",
    AGENT_STOP_LOSS_FAILURE: "disposition",
}


# ──────────────────────────────────────────────
# 영현: 손절실패 엔진 (전체 1회 실행 — 룰, 토큰 0)
# ──────────────────────────────────────────────

def run_stop_fail_engine(transactions_kwargs: List[Dict[str, Any]]) -> List[dict]:
    """손절실패 엔진을 전체 거래에 대해 1회 실행하고 사이클별 리포트 리스트 반환.

    Args:
        transactions_kwargs: common.adapters.to_younghyun_transaction() 결과 dict 리스트
    """
    with vendored_agent(_STOP_FAIL_DIR, _STOP_FAIL_MODULES):
        from agent import analyze_real      # type: ignore
        from schema import Transaction      # type: ignore

        txns = [Transaction(**t) for t in transactions_kwargs]
        return analyze_real(txns)


def stop_fail_report_to_result(run_id: str, trade_id: str, report: dict) -> AgentResult:
    """손절실패 리포트 dict → AgentResult."""
    score = float(report.get("score", 0.0) or 0.0)
    return AgentResult(
        run_id=run_id,
        trade_id=trade_id,
        agent_id=AGENT_STOP_LOSS_FAILURE,
        output_status="ok",
        score=round(score, 4),
        severity=_score_to_severity(score),
        result={
            "label":     report.get("judgment_type", "해당없음"),
            "narrative": report.get("narrative", ""),
            "signals":   report.get("signals", {}),
            "flags":     report.get("flags", {}),
        },
    )


# ──────────────────────────────────────────────
# 수빈: 진입오류 에이전트 (라우팅된 사이클만 개별 호출)
# ──────────────────────────────────────────────

def run_entry_error(run_id: str, trade_id: str, cycle_data: Dict[str, Any]) -> AgentResult:
    try:
        with vendored_agent(_ENTRY_ERROR_DIR, _ENTRY_ERROR_MODULES):
            from src.feature_engineering import (                       # type: ignore
                build_feature_result, build_feature_result_from_min1_window,
            )
            from src.data_loader import load_symbol_min1, extract_trade_window  # type: ignore
            from src.min1_classifier import classify_min1_market_state  # type: ignore
            from src.min1_labeler import (                              # type: ignore
                classify_min1_entry_labels, score_min1_labels,
            )

            # 실 min1 윈도우 피처 우선 — 라벨러가 구체 패턴(추격·과열 등)을 내려면 필수.
            # min1 없거나 봉 부족하면 mock 단일행으로 폴백 → 안 깨짐.
            feature_result = build_feature_result(cycle_data)
            code, buy_time = cycle_data.get("code"), cycle_data.get("entry_dt")
            if code and buy_time and _MIN1_DIR.exists():
                try:
                    mdf = load_symbol_min1(code, data_dir=str(_MIN1_DIR))
                    window = extract_trade_window(mdf, buy_time, pre_minutes=200, post_minutes=30)
                    m1 = build_feature_result_from_min1_window(
                        window, code=code, buy_price=cycle_data.get("entry_price"))
                    if m1.get("feature_status") in ("ok", "partial"):
                        feature_result = m1
                except Exception:
                    pass

            state_result   = classify_min1_market_state(feature_result)
            labels         = classify_min1_entry_labels(feature_result, state_result)
            risk           = score_min1_labels(labels)

        skip = {
            "normal_entry", "insufficient_data", "low_confidence",
            "raw_data_absent", "pre_entry_history_short", "feature_missing_or_invalid",
        }
        triggered = [l for l in labels if l.get("triggered") and l["label_id"] not in skip]
        top_label = triggered[0]["label_id"] if triggered else "normal_entry"
        raw_score = risk.get("entry_error_risk_score", 0) or 0

        return AgentResult(
            run_id=run_id,
            trade_id=trade_id,
            agent_id=AGENT_ENTRY_ERROR,
            output_status="ok",
            score=round(raw_score / 100, 4),
            severity=risk.get("severity"),
            result={
                "label": top_label,
                "risk_score_result": risk,
                "state_classification": state_result,
                "label_results": labels,
            },
        )
    except Exception as e:
        return _error_result(run_id, trade_id, AGENT_ENTRY_ERROR, e)


# ──────────────────────────────────────────────
# 심리 evidence 첨부 (도메인에 흡수된 심리 패턴)
# ──────────────────────────────────────────────

_SEVERITY_BY_SCORE = [(0.7, "strong"), (0.4, "moderate"), (0.1, "weak")]


def attach_psych_evidence(result: AgentResult, attribution: Optional[dict]) -> AgentResult:
    """라우팅된 도메인 에이전트 결과에 흡수된 심리 패턴 신호를 첨부한다.

    entry_error → revenge, stop_loss_failure → disposition.
    심리 점수(0~3 → 0~1)는 참고용으로 result.result["psych"] 에만 싣고,
    base 점수(result.score)는 덮어쓰지 않는다.
    """
    pattern = PSYCH_PATTERN_BY_AGENT.get(result.agent_id)
    if not pattern or not attribution:
        return result

    sub = attribution.get(pattern, {})
    raw = float(sub.get("score", 0.0) or 0.0)        # focus 점수는 0~3 스케일
    result.result["psych"] = {
        "pattern":  pattern,
        "detected": bool(sub.get("detected", False)),
        "score":    round(min(raw / 3.0, 1.0), 4),
        "evidence": sub.get("evidence", []),
    }
    return result


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _score_to_severity(score: float) -> str:
    for threshold, label in _SEVERITY_BY_SCORE:
        if score >= threshold:
            return label
    return "none"


def _error_result(run_id: str, trade_id: str, agent_id: str, exc: Exception) -> AgentResult:
    return AgentResult(
        run_id=run_id,
        trade_id=trade_id,
        agent_id=agent_id,
        output_status="error",
        score=None,
        severity=None,
        result={"error": str(exc)},
    )
