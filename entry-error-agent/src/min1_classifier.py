"""Real 1-minute OHLCV based market state classifier.

This module is for real parquet min1 data.
It avoids fitting thresholds to one ticker/date and uses conservative rules.
"""

STATE_BREAKOUT = "breakout"          # 상승/돌파
STATE_PULLBACK = "pullback"          # 눌림목/조정
STATE_DOWNTREND = "downtrend"        # 하락/역배열
STATE_RANGE = "range"                # 횡보/박스권
STATE_UNKNOWN = "unknown"
STATE_INSUFFICIENT_DATA = "insufficient_data"
STATE_RAW_DATA_ABSENT = "raw_data_absent"
STATE_PRE_ENTRY_HISTORY_SHORT = "pre_entry_history_short"
STATE_FEATURE_MISSING_OR_INVALID = "feature_missing_or_invalid"
STATE_LOW_CONFIDENCE = "low_confidence"

DATA_ISSUE_STATES = [
    STATE_RAW_DATA_ABSENT,
    STATE_PRE_ENTRY_HISTORY_SHORT,
    STATE_FEATURE_MISSING_OR_INVALID,
    STATE_INSUFFICIENT_DATA,
]


def _evidence(feature, value, message):
    return {
        "feature": feature,
        "value": value,
        "message": message,
    }


def _candidate(state, score, reason, evidence):
    return {
        "state": state,
        "confidence": round(min(float(score), 0.85), 3),
        "reason": reason,
        "evidence": evidence,
    }


def _between(value, low, high):
    return value is not None and low <= value <= high


def classify_min1_market_state(feature_result):
    """Classify one entry into breakout/pullback/downtrend/range.

    Uses only pre-entry 1-minute features.
    Does not use post-trade return.
    """
    feature_status = feature_result.get("feature_status")
    if feature_status in DATA_ISSUE_STATES:
        return {
            "primary_state": feature_status,
            "secondary_state": None,
            "state_confidence": 0.0,
            "candidate_states": [],
            "evidence": [],
            "status": feature_status,
            "data_issue_type": feature_status,
            "insufficient_reasons": feature_result.get("insufficient_reasons", []),
            "notes": [
                "Market state classification was skipped because input data/features were not usable.",
            ],
        }

    f = feature_result.get("features") or {}

    ma20_slope = f.get("ma_20_slope")
    rsi14 = f.get("rsi_14")
    ret3 = f.get("ret_3m")
    ret5 = f.get("ret_5m")
    ret20 = f.get("ret_20m")
    vol_ratio = f.get("volume_ratio_20m")
    entry_vs_ma20 = f.get("entry_vs_ma20_pct")
    entry_vs_high20 = f.get("entry_vs_high20_ratio")
    range_pos = f.get("range_position_20m")

    required = [ma20_slope, ret20, entry_vs_ma20, range_pos]
    if any(v is None for v in required):
        missing_required = [
            name for name, value in {
                "ma_20_slope": ma20_slope,
                "ret_20m": ret20,
                "entry_vs_ma20_pct": entry_vs_ma20,
                "range_position_20m": range_pos,
            }.items() if value is None
        ]
        return {
            "primary_state": STATE_FEATURE_MISSING_OR_INVALID,
            "secondary_state": None,
            "state_confidence": 0.0,
            "candidate_states": [],
            "evidence": [],
            "status": STATE_FEATURE_MISSING_OR_INVALID,
            "data_issue_type": STATE_FEATURE_MISSING_OR_INVALID,
            "missing_required": missing_required,
            "notes": [
                "Rows were available, but required state features were missing or invalid.",
            ],
        }

    candidates = []

    # 1. 상승/돌파: 최근 범위 상단 + 양의 추세
    score = 0
    ev = []
    if range_pos >= 0.72:
        score += 0.30
        ev.append(_evidence("range_position_20m", range_pos, "recent range upper area"))
    if entry_vs_high20 is not None and entry_vs_high20 >= 0.985:
        score += 0.25
        ev.append(_evidence("entry_vs_high20_ratio", entry_vs_high20, "near recent 20m high"))
    if ma20_slope > 0.002:
        score += 0.20
        ev.append(_evidence("ma_20_slope", ma20_slope, "positive MA20 slope"))
    if ret20 > 0.006:
        score += 0.15
        ev.append(_evidence("ret_20m", ret20, "positive recent 20m return"))
    if vol_ratio is not None and vol_ratio >= 1.2:
        score += 0.10
        ev.append(_evidence("volume_ratio_20m", vol_ratio, "above-average volume"))
    candidates.append(_candidate(STATE_BREAKOUT, score, "upper range with positive trend", ev))

    # 2. 눌림목/조정: 큰 흐름은 양호하지만 단기 되밀림
    score = 0
    ev = []
    if ma20_slope > 0.001:
        score += 0.25
        ev.append(_evidence("ma_20_slope", ma20_slope, "broader short-term trend positive"))
    if ret20 > 0:
        score += 0.15
        ev.append(_evidence("ret_20m", ret20, "recent 20m return still positive"))
    if ret5 is not None and ret5 < 0:
        score += 0.25
        ev.append(_evidence("ret_5m", ret5, "recent 5m pullback"))
    if _between(range_pos, 0.35, 0.75):
        score += 0.20
        ev.append(_evidence("range_position_20m", range_pos, "inside recent range"))
    if rsi14 is not None and 35 <= rsi14 <= 62:
        score += 0.10
        ev.append(_evidence("rsi_14", rsi14, "RSI not overheated"))
    candidates.append(_candidate(STATE_PULLBACK, score, "positive trend with short-term pullback", ev))

    # 3. 하락/역배열: 추세 하락 + 이평 아래 + 약세 수익률
    score = 0
    ev = []
    if ma20_slope < -0.002:
        score += 0.30
        ev.append(_evidence("ma_20_slope", ma20_slope, "negative MA20 slope"))
    if entry_vs_ma20 < -0.003:
        score += 0.25
        ev.append(_evidence("entry_vs_ma20_pct", entry_vs_ma20, "below MA20"))
    if ret20 < -0.006:
        score += 0.20
        ev.append(_evidence("ret_20m", ret20, "negative recent 20m return"))
    if range_pos <= 0.40:
        score += 0.15
        ev.append(_evidence("range_position_20m", range_pos, "lower recent range area"))
    if ret3 is not None and ret3 < 0:
        score += 0.10
        ev.append(_evidence("ret_3m", ret3, "very short-term weakness"))
    candidates.append(_candidate(STATE_DOWNTREND, score, "negative trend evidence", ev))

    # 4. 횡보/박스권: 추세와 수익률이 작고 범위 내부
    score = 0
    ev = []
    if abs(ma20_slope) <= 0.0025:
        score += 0.30
        ev.append(_evidence("ma_20_slope", ma20_slope, "flat MA20 slope"))
    if abs(ret20) <= 0.008:
        score += 0.25
        ev.append(_evidence("ret_20m", ret20, "small recent 20m return"))
    if _between(range_pos, 0.15, 0.85):
        score += 0.20
        ev.append(_evidence("range_position_20m", range_pos, "inside recent range"))
    if rsi14 is not None and 40 <= rsi14 <= 60:
        score += 0.15
        ev.append(_evidence("rsi_14", rsi14, "neutral RSI"))
    candidates.append(_candidate(STATE_RANGE, score, "flat and bounded movement", ev))

    candidates = sorted(candidates, key=lambda x: x["confidence"], reverse=True)
    primary = candidates[0]
    secondary = candidates[1] if len(candidates) > 1 else None

    if primary["confidence"] < 0.35:
        primary_state = STATE_UNKNOWN
        status = STATE_LOW_CONFIDENCE
    else:
        primary_state = primary["state"]
        status = "ok"

    return {
        "primary_state": primary_state,
        "secondary_state": secondary["state"] if secondary else None,
        "state_confidence": primary["confidence"],
        "candidate_states": candidates,
        "evidence": primary["evidence"],
        "status": status,
        "notes": [
            "Rule-based state classification using pre-entry 1-minute OHLCV features.",
            "Thresholds are conservative and should be validated across many trades.",
        ],
    }
