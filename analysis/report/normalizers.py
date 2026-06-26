"""에이전트별 result_json → 공통 리포트 필드(narrative, evidence) 정규화.

agent_results.result_json 의 구조는 에이전트마다 다르다
(손절실패: narrative/signals/flags, entry_error: risk_score_result/label_results, ...).
새 에이전트가 완성될 때마다 여기에 normalizer 함수 하나만 추가하면 되고,
query.py / builder.py / formatter.py 는 손댈 필요가 없다.

아직 구현되지 않은 에이전트는 _fallback_normalizer 가 raw_result 를 그대로
노출하는 안전한 기본값을 돌려준다 — 상류가 미완성이어도 리포트 레이어가 깨지지 않는다.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

NormalizerOutput = Tuple[str, list]  # (narrative, evidence)


def normalize_stop_loss_failure(result: Dict[str, Any]) -> NormalizerOutput:
    narrative = result.get("narrative", "")
    signals = result.get("signals", {})
    evidence = [{"feature": k, "value": v} for k, v in signals.items()]
    return narrative, evidence


def normalize_entry_error(result: Dict[str, Any]) -> NormalizerOutput:
    """TODO: entry-error-agent 의 narrative 필드가 아직 없다 (label_results/risk_score_result 뿐).

    완성되면 label_results 의 triggered 라벨들을 한국어 narrative 로 합성한다.
    지금은 top label 만 노출.
    """
    label = result.get("label", "")
    narrative = f"진입오류 패턴: {label}" if label else ""
    evidence = result.get("label_results", []) or []
    return narrative, evidence


def normalize_unclassified(result: Dict[str, Any]) -> NormalizerOutput:
    decision = result.get("orchestrator_decision", {})
    return "분류 보류 (신호 약함)", [decision] if decision else []


def _fallback_normalizer(result: Dict[str, Any]) -> NormalizerOutput:
    return "", []


_NORMALIZERS: Dict[str, Callable[[Dict[str, Any]], NormalizerOutput]] = {
    "stop_loss_failure": normalize_stop_loss_failure,
    "entry_error": normalize_entry_error,
    "unclassified": normalize_unclassified,
}


def normalize(agent_id: str, result: Dict[str, Any]) -> NormalizerOutput:
    fn = _NORMALIZERS.get(agent_id, _fallback_normalizer)
    return fn(result)
