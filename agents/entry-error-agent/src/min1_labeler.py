
"""Minimal min1 entry-error labeler."""

LABEL_KO = {
    "normal_entry": "명확한 진입오류 없음",
    "insufficient_data": "데이터 부족",
    "raw_data_absent": "Raw data absent",
    "pre_entry_history_short": "Pre-entry history short",
    "feature_missing_or_invalid": "Feature missing or invalid",
    "low_confidence": "Low confidence state",
    "gap_up_chase": "상승 구간 내 단기 추격 진입",
    "weak_flow_near_high": "고점 근처 수급 확인 부족 진입",
    "short_term_overheat": "단기 과열 연장 구간 진입",
    "early_pullback_entry": "지지 확인 없는 눌림목 조기 진입",
    "unstable_pullback_flow": "수급 안정 없는 눌림목 진입",
    "premature_bottom_fishing": "하락 추세 중 성급한 저가 매수",
    "downtrend_without_reversal": "반등 확인 없는 하락 추세 진입",
    "range_top_chase": "박스권 상단 추격 진입",
    "low_liquidity_range_chase": "저유동성 박스권 추격 진입",
}

WEIGHT = {
    "normal_entry": 0,
    "insufficient_data": 0,
    "raw_data_absent": 0,
    "pre_entry_history_short": 0,
    "feature_missing_or_invalid": 0,
    "low_confidence": 0,
    "gap_up_chase": 16,
    "weak_flow_near_high": 18,
    "short_term_overheat": 22,
    "early_pullback_entry": 18,
    "unstable_pullback_flow": 18,
    "premature_bottom_fishing": 24,
    "downtrend_without_reversal": 22,
    "range_top_chase": 16,
    "low_liquidity_range_chase": 18,
}

def _ev(feature, value, message):
    return {"feature": feature, "value": value, "message": message}

def _lab(label_id, confidence, reason, evidence=None):
    return {
        "label_id": label_id,
        "label_name_ko": LABEL_KO[label_id],
        "triggered": True,
        "confidence": round(float(confidence), 3),
        "weight": WEIGHT[label_id],
        "reason": reason,
        "evidence": evidence or [],
    }


def _classify_breakout(f):
    labels = []

    pos = f.get("entry_position_in_bar")
    eopen = f.get("entry_vs_open_pct")
    rsi = f.get("rsi_14")
    r20 = f.get("ret_20m")
    vol = f.get("volume_ratio_20m")
    high20 = f.get("entry_vs_high20_ratio")
    range_pos = f.get("range_position_20m")

    if (
        range_pos is not None and range_pos >= 0.85
        and rsi is not None and rsi >= 68
        and r20 is not None and r20 >= 0.015
    ):
        labels.append(_lab("short_term_overheat", 0.70, "breakout_overheat", [
            _ev("range_position_20m", range_pos, "최근 20분 범위 상단부 진입"),
            _ev("rsi_14", rsi, "RSI 과열"),
            _ev("ret_20m", r20, "최근 20분 상승폭 큼"),
        ]))

    if (
        high20 is not None and high20 >= 0.992
        and vol is not None and vol < 0.85
    ):
        labels.append(_lab("weak_flow_near_high", 0.60, "near_high_weak_volume", [
            _ev("entry_vs_high20_ratio", high20, "최근 20분 고점 근처 진입"),
            _ev("volume_ratio_20m", vol, "거래량 확인 부족"),
        ]))

    if (
        pos is not None and pos >= 0.90
        and eopen is not None and eopen > 0.003
    ):
        labels.append(_lab("gap_up_chase", 0.45, "minute_high_chase", [
            _ev("entry_position_in_bar", pos, "진입봉 고가 근처 진입"),
            _ev("entry_vs_open_pct", eopen, "진입가가 시가보다 높음"),
        ]))

    return labels


def _classify_pullback(f):
    labels = []

    r3 = f.get("ret_3m")
    r5 = f.get("ret_5m")
    vol = f.get("volume_ratio_20m")
    bar_ret = f.get("bar_return_pct")

    if (
        r5 is not None and r5 < -0.004
        and bar_ret is not None and bar_ret <= 0
    ):
        labels.append(_lab("early_pullback_entry", 0.60, "no_support_confirmation", [
            _ev("ret_5m", r5, "최근 5분 하락 흐름 지속"),
            _ev("bar_return_pct", bar_ret, "진입봉 반등 확인 부족"),
        ]))

    if (
        vol is not None and vol < 0.75
        and r3 is not None and r3 < 0
    ):
        labels.append(_lab("unstable_pullback_flow", 0.55, "weak_pullback_flow", [
            _ev("volume_ratio_20m", vol, "거래량이 최근 평균보다 약함"),
            _ev("ret_3m", r3, "초단기 흐름이 아직 약함"),
        ]))

    return labels


def _classify_downtrend(f):
    labels = []

    r1 = f.get("ret_1m")
    r5 = f.get("ret_5m")
    rsi = f.get("rsi_14")
    ma_slope = f.get("ma_20_slope")
    entry_vs_ma20 = f.get("entry_vs_ma20_pct")
    range_pos = f.get("range_position_20m")

    if (
        range_pos is not None and range_pos <= 0.35
        and rsi is not None and rsi <= 42
        and r1 is not None and r1 <= 0
    ):
        labels.append(_lab("premature_bottom_fishing", 0.65, "bottom_fishing_no_reversal", [
            _ev("range_position_20m", range_pos, "최근 범위 하단부 진입"),
            _ev("rsi_14", rsi, "RSI 약세"),
            _ev("ret_1m", r1, "직전 1분 반등 확인 부족"),
        ]))

    if (
        ma_slope is not None and ma_slope < -0.002
        and entry_vs_ma20 is not None and entry_vs_ma20 < 0
        and r5 is not None and r5 <= 0
    ):
        labels.append(_lab("downtrend_without_reversal", 0.70, "downtrend_no_reversal", [
            _ev("ma_20_slope", ma_slope, "20분 이동평균 기울기 하락"),
            _ev("entry_vs_ma20_pct", entry_vs_ma20, "진입가가 MA20 아래"),
            _ev("ret_5m", r5, "최근 5분 회복 확인 부족"),
        ]))

    return labels


def _classify_range(f):
    labels = []

    range_pos = f.get("range_position_20m")
    vol = f.get("volume_ratio_20m")

    if range_pos is not None and range_pos >= 0.82:
        labels.append(_lab("range_top_chase", 0.60, "range_top_entry", [
            _ev("range_position_20m", range_pos, "최근 박스권 상단부 진입"),
        ]))

    if (
        range_pos is not None and range_pos >= 0.65
        and vol is not None and vol < 0.70
    ):
        labels.append(_lab("low_liquidity_range_chase", 0.55, "range_low_volume", [
            _ev("range_position_20m", range_pos, "박스권 상단 쪽 진입"),
            _ev("volume_ratio_20m", vol, "거래량이 최근 평균보다 약함"),
        ]))

    return labels


def classify_min1_entry_labels(feature_result, state_result):
    """Classify entry-error labels by market state."""
    feature_status = feature_result.get("feature_status")
    data_issue_labels = [
        "raw_data_absent",
        "pre_entry_history_short",
        "feature_missing_or_invalid",
        "insufficient_data",
    ]
    if feature_status in data_issue_labels:
        return [_lab(feature_status, 1.0, "feature_not_usable")]

    state = state_result.get("primary_state")
    features = feature_result.get("features", {})

    if state in data_issue_labels:
        return [_lab(state, 1.0, "state_not_usable")]

    if state in [None, "unknown"] or state_result.get("status") == "low_confidence":
        return [_lab("low_confidence", 1.0, "state_low_confidence")]

    if state == "breakout":
        labels = _classify_breakout(features)
    elif state == "pullback":
        labels = _classify_pullback(features)
    elif state == "downtrend":
        labels = _classify_downtrend(features)
    elif state == "range":
        labels = _classify_range(features)
    else:
        labels = []

    if not labels:
        labels = [_lab("normal_entry", 0.40, "no_conservative_rule_triggered")]

    return labels


def score_min1_labels(labels):
    """Compute conservative entry-error risk score."""
    total = 0.0
    contributions = []

    for label in labels:
        label_id = label["label_id"]

        if label_id in [
            "normal_entry",
            "insufficient_data",
            "raw_data_absent",
            "pre_entry_history_short",
            "feature_missing_or_invalid",
            "low_confidence",
        ]:
            contribution = 0.0
        else:
            contribution = label["weight"] * label["confidence"]

        contribution = round(contribution, 3)
        label["contribution_to_score"] = contribution
        total += contribution

        if contribution > 0:
            contributions.append({
                "label_id": label_id,
                "label_name_ko": label["label_name_ko"],
                "confidence": label["confidence"],
                "weight": label["weight"],
                "contribution_to_score": contribution,
            })

    score = round(min(total, 100.0), 3)

    diagnostic_labels = [
        "insufficient_data",
        "raw_data_absent",
        "pre_entry_history_short",
        "feature_missing_or_invalid",
        "low_confidence",
    ]
    if any(label["label_id"] in diagnostic_labels for label in labels):
        severity = labels[0]["label_id"]
    elif score == 0:
        severity = "none"
    elif score < 15:
        severity = "low"
    elif score < 35:
        severity = "moderate"
    elif score < 60:
        severity = "high"
    else:
        severity = "very_high"

    return {
        "entry_error_risk_score": score,
        "severity": severity,
        "contributions": contributions,
        "notes": [
            "손익 결과는 진입오류 판단 근거로 사용하지 않음",
            "현재 기준값은 보수적 rule-based MVP이며 다수 거래로 검증 필요",
        ],
    }
