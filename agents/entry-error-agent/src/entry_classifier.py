"""Placeholder market state classification and entry-error labeling.

Post-trade values must not be used as direct evidence for entry-error labeling
or scoring. trade_return_pct is allowed only as review context. Protected
features must be removed from evidence before label scoring. If protected
features appear in evidence or raw_values, the score calculation should warn
and avoid using them. Real entry-error risk scoring requires sufficient
pre-entry OHLCV history. Mock placeholder rules are not final trading judgments.
"""

from typing import Any, Dict, List, Optional


STATE_BREAKOUT = "breakout"
STATE_PULLBACK = "pullback"
STATE_DOWNTREND = "downtrend"
STATE_RANGE = "range"
STATE_UNKNOWN = "unknown"
STATE_INSUFFICIENT_DATA = "insufficient_data"

MARKET_STATES = [
    STATE_BREAKOUT,
    STATE_PULLBACK,
    STATE_DOWNTREND,
    STATE_RANGE,
    STATE_UNKNOWN,
    STATE_INSUFFICIENT_DATA,
]

LABEL_NORMAL_ENTRY = "normal_entry"
LABEL_GAP_UP_CHASE = "gap_up_chase"
LABEL_WEAK_FLOW_NEAR_HIGH = "weak_flow_near_high"
LABEL_SHORT_TERM_OVERHEAT = "short_term_overheat"
LABEL_EARLY_PULLBACK_ENTRY = "early_pullback_entry"
LABEL_UNSTABLE_PULLBACK_FLOW = "unstable_pullback_flow"
LABEL_PREMATURE_BOTTOM_FISHING = "premature_bottom_fishing"
LABEL_DOWNTREND_WITHOUT_REVERSAL = "downtrend_without_reversal"
LABEL_RANGE_TOP_CHASE = "range_top_chase"
LABEL_LOW_LIQUIDITY_RANGE_CHASE = "low_liquidity_range_chase"
LABEL_INSUFFICIENT_DATA = "insufficient_data"

ENTRY_LABELS = [
    LABEL_NORMAL_ENTRY,
    LABEL_GAP_UP_CHASE,
    LABEL_WEAK_FLOW_NEAR_HIGH,
    LABEL_SHORT_TERM_OVERHEAT,
    LABEL_EARLY_PULLBACK_ENTRY,
    LABEL_UNSTABLE_PULLBACK_FLOW,
    LABEL_PREMATURE_BOTTOM_FISHING,
    LABEL_DOWNTREND_WITHOUT_REVERSAL,
    LABEL_RANGE_TOP_CHASE,
    LABEL_LOW_LIQUIDITY_RANGE_CHASE,
    LABEL_INSUFFICIENT_DATA,
]

LABEL_DISPLAY_NAMES = {
    LABEL_NORMAL_ENTRY: "Normal entry",
    LABEL_GAP_UP_CHASE: "Gap-up chase entry",
    LABEL_WEAK_FLOW_NEAR_HIGH: "Weak flow near high entry",
    LABEL_SHORT_TERM_OVERHEAT: "Short-term overheat entry",
    LABEL_EARLY_PULLBACK_ENTRY: "Early pullback entry",
    LABEL_UNSTABLE_PULLBACK_FLOW: "Unstable pullback flow entry",
    LABEL_PREMATURE_BOTTOM_FISHING: "Premature bottom fishing",
    LABEL_DOWNTREND_WITHOUT_REVERSAL: "Downtrend entry without reversal",
    LABEL_RANGE_TOP_CHASE: "Range top chase entry",
    LABEL_LOW_LIQUIDITY_RANGE_CHASE: "Low-liquidity range chase entry",
    LABEL_INSUFFICIENT_DATA: "Insufficient data",
}

LABEL_WEIGHTS = {
    LABEL_GAP_UP_CHASE: 20.0,
    LABEL_WEAK_FLOW_NEAR_HIGH: 18.0,
    LABEL_SHORT_TERM_OVERHEAT: 22.0,
    LABEL_EARLY_PULLBACK_ENTRY: 18.0,
    LABEL_UNSTABLE_PULLBACK_FLOW: 20.0,
    LABEL_PREMATURE_BOTTOM_FISHING: 24.0,
    LABEL_DOWNTREND_WITHOUT_REVERSAL: 22.0,
    LABEL_RANGE_TOP_CHASE: 16.0,
    LABEL_LOW_LIQUIDITY_RANGE_CHASE: 20.0,
    LABEL_INSUFFICIENT_DATA: 0.0,
    LABEL_NORMAL_ENTRY: 0.0,
}


def get_protected_feature_names() -> List[str]:
    """Return features excluded from direct entry-error label evidence.

    trade_return_pct is post-trade information. It can be used for review
    context, but must not be used as direct evidence for entry-error labeling.
    """
    return ["trade_return_pct"]


def is_protected_feature(feature_name: str) -> bool:
    """Return True when a feature must not be used as label evidence."""
    return feature_name in get_protected_feature_names()


def remove_protected_features_from_evidence(
    evidence: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Remove protected features from evidence items."""
    cleaned_evidence = []
    for evidence_item in evidence:
        feature_name = evidence_item.get("feature")
        if is_protected_feature(feature_name):
            continue
        cleaned_evidence.append(evidence_item)
    return cleaned_evidence


def get_label_display_name(label_id: str) -> str:
    """Return display name for a label id."""
    return LABEL_DISPLAY_NAMES.get(label_id, label_id)


def get_label_weight(label_id: str) -> float:
    """Return the placeholder score weight for a label id."""
    return LABEL_WEIGHTS.get(label_id, 0.0)


def check_no_protected_features_in_evidence(
    label_results: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Return warnings when protected features appear in label evidence."""
    warnings = []
    for label_result in label_results:
        label_id = label_result.get("label_id")
        for evidence_item in label_result.get("evidence") or []:
            feature_name = evidence_item.get("feature")
            if is_protected_feature(feature_name):
                warnings.append(
                    {
                        "label_id": label_id,
                        "protected_feature": feature_name,
                        "reason": "protected_feature_found_in_evidence",
                    }
                )
    return warnings


def check_no_protected_features_in_score(
    label_results: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Return warnings when protected features may affect score calculation."""
    warnings = []
    for label_result in label_results:
        label_id = label_result.get("label_id")
        raw_values = label_result.get("raw_values") or {}
        for feature_name in raw_values.keys():
            if is_protected_feature(feature_name):
                warnings.append(
                    {
                        "label_id": label_id,
                        "protected_feature": feature_name,
                        "reason": "protected_feature_found_in_raw_values",
                    }
                )
        for evidence_item in label_result.get("evidence") or []:
            feature_name = evidence_item.get("feature")
            if is_protected_feature(feature_name):
                warnings.append(
                    {
                        "label_id": label_id,
                        "protected_feature": feature_name,
                        "reason": "protected_feature_found_in_evidence",
                    }
                )
    return warnings


def classify_market_state(feature_result: Dict[str, Any]) -> Dict[str, Any]:
    """Return placeholder market state classification."""
    primary_state = STATE_UNKNOWN
    if feature_result.get("feature_status") == STATE_INSUFFICIENT_DATA:
        primary_state = STATE_INSUFFICIENT_DATA

    return {
        "primary_state": primary_state,
        "secondary_state": None,
        "state_confidence": 0.0,
        "candidate_states": [
            {
                "state": primary_state,
                "confidence": 0.0,
                "reason": "Real market state classification requires pre-entry OHLCV history.",
            }
        ],
        "evidence": [],
        "status": "placeholder",
        "notes": [
            "Market state classification is not implemented yet.",
            "Breakout, pullback, downtrend, and range states require historical OHLCV features.",
        ],
    }


def build_label_result(
    label_id: str,
    triggered: bool = False,
    confidence: float = 0.0,
    weight: float = 0.0,
    evidence: Optional[List[Dict[str, Any]]] = None,
    raw_values: Optional[Dict[str, Any]] = None,
    reason: str = "not_evaluated",
) -> Dict[str, Any]:
    """Build the standard label result structure."""
    if evidence is None:
        evidence = []
    if raw_values is None:
        raw_values = {}
    cleaned_evidence = remove_protected_features_from_evidence(evidence)
    if weight is None or weight == 0.0:
        weight = get_label_weight(label_id)

    return {
        "label_id": label_id,
        "label_name": get_label_display_name(label_id),
        "triggered": triggered,
        "confidence": confidence,
        "weight": weight,
        "contribution_to_score": 0.0,
        "evidence": cleaned_evidence,
        "raw_values": raw_values,
        "reason": reason,
    }


def _has_low_information(features: Dict[str, Any]) -> bool:
    """Return True when most mock features are missing."""
    required_feature_names = [
        "entry_position_in_bar",
        "entry_vs_open_pct",
        "bar_return_pct",
        "volume_value",
    ]
    if not features:
        return True

    available_count = 0
    for feature_name in required_feature_names:
        if features.get(feature_name) is not None:
            available_count += 1
    return available_count <= 1


def evaluate_mock_placeholder_rules(features: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate conservative mock-only placeholder rules.

    These rules use only entry_position_in_bar, entry_vs_open_pct,
    bar_return_pct, and volume_value. They do not use trade_return_pct.
    """
    if _has_low_information(features):
        return [
            build_label_result(
                LABEL_INSUFFICIENT_DATA,
                triggered=True,
                confidence=1.0,
                reason="insufficient_mock_features",
            )
        ]

    label_results = []
    entry_position_in_bar = features.get("entry_position_in_bar")
    entry_vs_open_pct = features.get("entry_vs_open_pct")
    bar_return_pct = features.get("bar_return_pct")

    if entry_position_in_bar is not None and entry_position_in_bar >= 0.85:
        label_results.append(
            build_label_result(
                LABEL_RANGE_TOP_CHASE,
                triggered=True,
                confidence=0.25,
                reason="mock_near_bar_high_candidate",
                evidence=[
                    {
                        "feature": "entry_position_in_bar",
                        "value": entry_position_in_bar,
                        "message": "Entry price is near the high of the available mock bar.",
                    }
                ],
                raw_values={
                    "entry_position_in_bar": entry_position_in_bar,
                },
            )
        )

    if (
        entry_vs_open_pct is not None
        and bar_return_pct is not None
        and entry_vs_open_pct > 0
        and bar_return_pct < 0
    ):
        label_results.append(
            build_label_result(
                LABEL_GAP_UP_CHASE,
                triggered=True,
                confidence=0.20,
                reason="mock_positive_entry_vs_open_but_weak_bar_candidate",
                evidence=[
                    {
                        "feature": "entry_vs_open_pct",
                        "value": entry_vs_open_pct,
                        "message": "Entry price is above the open in the mock bar.",
                    },
                    {
                        "feature": "bar_return_pct",
                        "value": bar_return_pct,
                        "message": "The mock bar closed below the open.",
                    },
                ],
                raw_values={
                    "entry_vs_open_pct": entry_vs_open_pct,
                    "bar_return_pct": bar_return_pct,
                },
            )
        )

    return label_results


def classify_entry_labels(
    feature_result: Dict[str, Any], state_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Return placeholder entry label results."""
    if feature_result.get("feature_status") == STATE_INSUFFICIENT_DATA:
        return [
            build_label_result(
                LABEL_INSUFFICIENT_DATA,
                triggered=True,
                reason="feature_result_insufficient_data",
            )
        ]

    if state_result.get("primary_state") == STATE_INSUFFICIENT_DATA:
        return [
            build_label_result(
                LABEL_INSUFFICIENT_DATA,
                triggered=True,
                reason="state_insufficient_data",
            )
        ]

    features = feature_result.get("features") or {}
    return evaluate_mock_placeholder_rules(features)


def _label_result_has_protected_evidence(label_result: Dict[str, Any]) -> bool:
    """Return True when one label result still contains protected evidence."""
    for evidence_item in label_result.get("evidence") or []:
        if is_protected_feature(evidence_item.get("feature")):
            return True
    return False


def compute_label_contribution(label_result: Dict[str, Any]) -> float:
    """Compute one label contribution for placeholder risk scoring."""
    if not label_result.get("triggered"):
        return 0.0
    if label_result.get("label_id") == LABEL_INSUFFICIENT_DATA:
        return 0.0
    if _label_result_has_protected_evidence(label_result):
        return 0.0

    label_id = label_result.get("label_id")
    weight = label_result.get("weight")
    if weight is None or weight == 0.0:
        weight = get_label_weight(label_id)
    confidence = label_result.get("confidence") or 0.0
    return float(weight) * float(confidence)


def _get_severity(score: float) -> str:
    """Return severity bucket for a placeholder score."""
    if score < 20:
        return "low"
    if score < 40:
        return "moderate"
    if score < 70:
        return "high"
    return "very_high"


def compute_entry_error_score(
    label_results: List[Dict[str, Any]],
    data_quality_report: Optional[Dict[str, Any]] = None,
    state_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute a placeholder entry-error risk score from label results."""
    quality_score = 1.0
    if data_quality_report is not None:
        quality_score = data_quality_report.get("quality_score", 1.0)
        if quality_score is None:
            quality_score = 1.0

    warnings = []
    warnings.extend(check_no_protected_features_in_evidence(label_results))
    warnings.extend(check_no_protected_features_in_score(label_results))

    contributions = []
    raw_score = 0.0
    only_insufficient_data = False
    triggered_results = [
        label_result for label_result in label_results if label_result.get("triggered")
    ]
    if triggered_results:
        only_insufficient_data = all(
            label_result.get("label_id") == LABEL_INSUFFICIENT_DATA
            for label_result in triggered_results
        )

    for label_result in label_results:
        contribution = compute_label_contribution(label_result)
        label_id = label_result.get("label_id")
        weight = label_result.get("weight")
        if weight is None or weight == 0.0:
            weight = get_label_weight(label_id)
        confidence = label_result.get("confidence") or 0.0
        if contribution > 0.0:
            contributions.append(
                {
                    "label_id": label_id,
                    "weight": weight,
                    "confidence": confidence,
                    "contribution_to_score": round(contribution, 2),
                }
            )
        raw_score += contribution

    adjusted_score = raw_score * float(quality_score)
    risk_score = min(100.0, adjusted_score)
    risk_score = round(risk_score, 2)
    raw_score = round(raw_score, 2)
    adjusted_score = round(adjusted_score, 2)

    score_status = "placeholder_score"
    if only_insufficient_data:
        score_status = "insufficient_data"
    if warnings:
        score_status = "protected_feature_warning"

    return {
        "entry_error_risk_score": risk_score,
        "severity": _get_severity(risk_score),
        "score_status": score_status,
        "raw_score": raw_score,
        "quality_score": round(float(quality_score), 2),
        "adjusted_score": adjusted_score,
        "contributions": contributions,
        "warnings": warnings,
        "notes": [
            "This is a placeholder risk score based on mock features only.",
            "Final risk scoring requires sufficient pre-entry OHLCV history.",
            "Post-trade features are excluded from score evidence.",
        ],
    }


def build_entry_classification_result(
    feature_result: Dict[str, Any],
    data_quality_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the placeholder classification result for one feature result."""
    state_result = classify_market_state(feature_result)
    label_results = classify_entry_labels(feature_result, state_result)
    risk_score_result = compute_entry_error_score(
        label_results,
        data_quality_report=data_quality_report,
        state_result=state_result,
    )

    return {
        "classification_status": "placeholder_rules",
        "state_classification": state_result,
        "label_results": label_results,
        "risk_score_result": risk_score_result,
        "protected_features": get_protected_feature_names(),
        "notes": [
            "Only conservative mock placeholder rules are evaluated in this step.",
            "Risk score is a placeholder and should remain low until real OHLCV features are available.",
            "trade_return_pct is excluded from label evidence and score.",
        ],
    }
