"""Classifier scores and top-level routing policy.

The classifier no longer chooses an agent directly. It produces comparable
entry-error and stop-loss-failure candidate scores. The orchestrator policy then
chooses one primary agent and records secondary factors as evidence.

All temporary behavioral thresholds below are expressed in a 1-minute-friendly
language so the same concepts can be reused by the live monitor. Batch data that
only has day-level stop information is converted to minutes at the pipeline edge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

AGENT_ENTRY_ERROR = "entry_error"
AGENT_STOP_LOSS_FAILURE = "stop_loss_failure"

TRADING_MINUTES_PER_DAY = 390


@dataclass(frozen=True)
class MinuteFeatureThresholds:
    """Baseline 1-minute thresholds that must be calibrated with real data."""

    # Entry-error feature thresholds
    range_upper_entry: float = 0.85
    range_upper_weak_flow: float = 0.75
    near_high_ratio: float = 0.992
    ret_20m_overheat: float = 0.012
    rsi_overheat: float = 68.0
    volume_weak_ratio: float = 0.80
    volume_dry_ratio: float = 0.75
    ma20_down_slope: float = -0.002
    ret_5m_pullback: float = -0.004
    # (loss_early_ratio_primary 0.70 제거 — 데이터 미지지 고정컷. 분류기가 대체)

    # Stop-loss-failure thresholds, expressed for minute-level monitoring.
    breach_warn_minutes: int = 30
    breach_severe_minutes: int = 60
    loss_expansion_warn_pp: float = 1.5
    loss_expansion_severe_pp: float = 3.0
    loss_expansion_warn_ratio: float = 1.5
    loss_expansion_severe_ratio: float = 2.0
    avg_down_warn_count: int = 1
    avg_down_severe_count: int = 2
    avg_down_severe_qty_ratio: float = 1.0
    failed_recovery_warn_minutes: int = 30


@dataclass(frozen=True)
class OrchestratorPolicy:
    """Decision policy used after classifier scores are produced."""

    min_route_score: float = 0.55
    strong_route_score: float = 0.70
    min_score_margin: float = 0.15
    ambiguous_margin: float = 0.10
    secondary_factor_score: float = 0.45
    review_min_score: float = 0.45
    abstain_threshold: float = 0.35
    profile_update_min_confidence: float = 0.60


@dataclass
class CandidateScores:
    trade_id: str
    entry_error_score: float
    stop_loss_failure_score: float
    entry_evidence: List[Dict[str, Any]] = field(default_factory=list)
    stop_evidence: List[Dict[str, Any]] = field(default_factory=list)
    feature_scope: str = "batch_or_min1"

    def top_agent(self) -> str:
        if self.stop_loss_failure_score >= self.entry_error_score:
            return AGENT_STOP_LOSS_FAILURE
        return AGENT_ENTRY_ERROR

    def second_agent(self) -> str:
        return (
            AGENT_ENTRY_ERROR
            if self.top_agent() == AGENT_STOP_LOSS_FAILURE
            else AGENT_STOP_LOSS_FAILURE
        )

    def score_for(self, agent_id: str) -> float:
        if agent_id == AGENT_STOP_LOSS_FAILURE:
            return self.stop_loss_failure_score
        return self.entry_error_score

    def evidence_for(self, agent_id: str) -> List[Dict[str, Any]]:
        if agent_id == AGENT_STOP_LOSS_FAILURE:
            return self.stop_evidence
        return self.entry_evidence

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CycleRouteDecision:
    trade_id: str
    agent_id: str
    route_status: str
    confidence: float
    reason: str
    route_type: str = "single_primary"
    primary_agent: Optional[str] = None
    secondary_agent: Optional[str] = None
    secondary_factors: List[str] = field(default_factory=list)
    classifier_scores: Optional[CandidateScores] = None
    profile_eligible: bool = False

    def to_dict(self) -> dict:
        data = {
            "trade_id": self.trade_id,
            "agent_id": self.agent_id,
            "route_status": self.route_status,
            "confidence": self.confidence,
            "reason": self.reason,
            "route_type": self.route_type,
            "primary_agent": self.primary_agent or self.agent_id,
            "secondary_agent": self.secondary_agent,
            "secondary_factors": self.secondary_factors,
            "profile_eligible": self.profile_eligible,
        }
        if self.classifier_scores is not None:
            data["classifier_scores"] = self.classifier_scores.to_dict()
        return data


def score_cycle_candidates(
    trade_id: str,
    *,
    psych_dominant: Optional[str],
    breached: bool,
    delay_minutes: Optional[int] = None,
    delay_days: Optional[int] = None,
    loss_early_ratio: Optional[float],
    stop_report_score: Optional[float] = None,
    stop_signals: Optional[dict] = None,
    entry_min1_score: Optional[float] = None,
    entry_features: Optional[dict] = None,
    classifier_entry_score: Optional[float] = None,
    classifier_stop_score: Optional[float] = None,
    classifier_result: Optional[Dict[str, Any]] = None,
    thresholds: MinuteFeatureThresholds = MinuteFeatureThresholds(),
) -> CandidateScores:
    """Produce candidate scores for both failure types.

    Args:
        entry_min1_score: Optional 0~1 score from the 1-minute entry classifier.
        stop_report_score: Optional 0~1 score from the stop-loss agent.
        delay_days: Backward-compatible batch input. Converted to trading minutes.
    """
    if delay_minutes is None and delay_days is not None:
        delay_minutes = int(delay_days * TRADING_MINUTES_PER_DAY)
    delay_minutes = int(delay_minutes or 0)

    entry_score = 0.0
    stop_score = 0.0
    entry_evidence: List[Dict[str, Any]] = []
    stop_evidence: List[Dict[str, Any]] = []

    # ── 라우팅은 '분류기 단독'으로 결정한다 (설계 의도) ──────────────────────
    #   entry/stop 점수 = 전체피처 분류기의 두 점수. 그게 전부다.
    #   · 심리귀속(리벤지/처분효과) → 라우팅에 가산하지 않는다. 도메인 에이전트의
    #     '해석/설명'에 피처로 들어간다(attach_psych_evidence).
    #   · 손절엔진(breach/delay) → 라우팅에 가산하지 않는다. 손절 에이전트의 '분석'에만.
    #   아래 신호들은 라우팅 미반영 — 참고용 context evidence 로만 기록한다.
    if classifier_entry_score is not None:
        entry_score = min(max(float(classifier_entry_score), 0.0), 1.0)
        entry_evidence.append(_ev("learned_classifier_entry_score", classifier_entry_score, entry_score))
    if classifier_stop_score is not None:
        stop_score = min(max(float(classifier_stop_score), 0.0), 1.0)
        stop_evidence.append(_ev("learned_classifier_stop_score", classifier_stop_score, stop_score))
    if classifier_result:
        entry_evidence.append(_ev("learned_classifier_result", classifier_result, 0.0))
        stop_evidence.append(_ev("learned_classifier_result", classifier_result, 0.0))

    # 라우팅 미반영(참고용). 심리는 에이전트 해석으로, 손절신호는 손절 에이전트 분석으로 전달됨.
    if psych_dominant in ("revenge", "disposition"):
        target = entry_evidence if psych_dominant == "revenge" else stop_evidence
        target.append(_ev("psych_dominant(routing_excluded)", psych_dominant, 0.0))
    if loss_early_ratio is not None:
        entry_evidence.append(_ev("loss_early_ratio(routing_excluded)", loss_early_ratio, 0.0))
    if breached:
        stop_evidence.append(_ev("stop_breached(routing_excluded)", True, 0.0))

    return CandidateScores(
        trade_id=trade_id,
        entry_error_score=round(_clamp(entry_score), 4),
        stop_loss_failure_score=round(_clamp(stop_score), 4),
        entry_evidence=entry_evidence,
        stop_evidence=stop_evidence,
    )


def decide_primary_route(
    scores: CandidateScores,
    *,
    policy: OrchestratorPolicy = OrchestratorPolicy(),
) -> CycleRouteDecision:
    """Choose one primary route and preserve secondary evidence."""
    top = scores.top_agent()
    second = scores.second_agent()
    top_score = scores.score_for(top)
    second_score = scores.score_for(second)
    margin = top_score - second_score

    if top_score < policy.abstain_threshold:
        return _decision(
            scores,
            AGENT_ENTRY_ERROR,
            "abstain_low_signal",
            confidence=round(top_score, 4),
            route_type="abstain",
            secondary_agent=None,
            policy=policy,
        )

    if top_score >= policy.min_route_score and margin >= policy.min_score_margin:
        route_type = "single_primary"
        secondary = None
        factors: List[str] = []
        if second_score >= policy.secondary_factor_score:
            route_type = "single_primary_with_secondary"
            secondary = second
            factors = [second]
        return _decision(
            scores,
            top,
            f"primary_{top}_margin_{margin:.2f}",
            confidence=_confidence(top_score, margin),
            route_type=route_type,
            secondary_agent=secondary,
            secondary_factors=factors,
            policy=policy,
        )

    if top_score >= policy.min_route_score and second_score >= policy.min_route_score:
        return _decision(
            scores,
            top,
            f"primary_{top}_with_secondary_{second}_balanced_scores",
            confidence=_confidence(top_score, margin),
            route_type="single_primary_with_secondary",
            secondary_agent=second,
            secondary_factors=[second],
            policy=policy,
        )

    if top_score >= policy.review_min_score and margin <= policy.ambiguous_margin:
        return _decision(
            scores,
            top,
            f"review_required_ambiguous_margin_{margin:.2f}",
            confidence=_confidence(top_score, margin),
            route_type="review_required",
            secondary_agent=second,
            secondary_factors=[second],
            policy=policy,
        )

    if top_score >= policy.min_route_score:
        return _decision(
            scores,
            top,
            f"primary_{top}_weak_margin_{margin:.2f}",
            confidence=_confidence(top_score, margin),
            route_type="single_primary_with_secondary",
            secondary_agent=second if second_score >= policy.secondary_factor_score else None,
            secondary_factors=[second] if second_score >= policy.secondary_factor_score else [],
            policy=policy,
        )

    return _decision(
        scores,
        top,
        f"review_required_mid_signal_{top_score:.2f}",
        confidence=_confidence(top_score, margin),
        route_type="review_required",
        secondary_agent=second if second_score >= policy.secondary_factor_score else None,
        secondary_factors=[second] if second_score >= policy.secondary_factor_score else [],
        policy=policy,
    )


def route_cycle(
    trade_id: str,
    *,
    psych_dominant: Optional[str],
    breached: bool,
    delay_days: int = 0,
    delay_minutes: Optional[int] = None,
    loss_early_ratio: Optional[float],
    stop_report_score: Optional[float] = None,
    stop_signals: Optional[dict] = None,
    entry_min1_score: Optional[float] = None,
    entry_features: Optional[dict] = None,
    classifier_entry_score: Optional[float] = None,
    classifier_stop_score: Optional[float] = None,
    classifier_result: Optional[Dict[str, Any]] = None,
) -> CycleRouteDecision:
    """Backward-compatible route entry point used by the pipeline and tests."""
    scores = score_cycle_candidates(
        trade_id,
        psych_dominant=psych_dominant,
        breached=breached,
        delay_minutes=delay_minutes,
        delay_days=delay_days,
        loss_early_ratio=loss_early_ratio,
        stop_report_score=stop_report_score,
        stop_signals=stop_signals,
        entry_min1_score=entry_min1_score,
        entry_features=entry_features,
        classifier_entry_score=classifier_entry_score,
        classifier_stop_score=classifier_stop_score,
        classifier_result=classifier_result,
    )
    return decide_primary_route(scores)


def _score_entry_minute_features(
    features: dict,
    thresholds: MinuteFeatureThresholds,
    evidence: List[Dict[str, Any]],
) -> float:
    score = 0.0
    if _ge(features.get("range_position_20m"), thresholds.range_upper_entry):
        score += 0.10
        evidence.append(_ev("range_position_20m", features.get("range_position_20m"), 0.10))
    if _ge(features.get("entry_vs_high20_ratio"), thresholds.near_high_ratio):
        score += 0.10
        evidence.append(_ev("entry_vs_high20_ratio", features.get("entry_vs_high20_ratio"), 0.10))
    if _ge(features.get("ret_20m"), thresholds.ret_20m_overheat):
        score += 0.10
        evidence.append(_ev("ret_20m", features.get("ret_20m"), 0.10))
    if _ge(features.get("rsi_14"), thresholds.rsi_overheat):
        score += 0.08
        evidence.append(_ev("rsi_14", features.get("rsi_14"), 0.08))
    if _le(features.get("volume_ratio_20m"), thresholds.volume_weak_ratio):
        score += 0.07
        evidence.append(_ev("volume_ratio_20m", features.get("volume_ratio_20m"), 0.07))
    if _le(features.get("ma_20_slope"), thresholds.ma20_down_slope):
        score += 0.10
        evidence.append(_ev("ma_20_slope", features.get("ma_20_slope"), 0.10))
    if _le(features.get("ret_5m"), thresholds.ret_5m_pullback):
        score += 0.08
        evidence.append(_ev("ret_5m", features.get("ret_5m"), 0.08))
    return min(score, 0.35)


def _score_stop_minute_features(
    signals: dict,
    thresholds: MinuteFeatureThresholds,
    evidence: List[Dict[str, Any]],
) -> float:
    score = 0.0
    expansion_pp = signals.get("loss_expansion_pct")
    expansion_ratio = signals.get("loss_expansion_ratio")
    avg_down_count = signals.get("avg_down_count_after_loss")
    avg_down_qty_ratio = signals.get("avg_down_qty_ratio")
    failed_recovery = signals.get("failed_recovery_minutes")

    if _ge(expansion_pp, thresholds.loss_expansion_severe_pp) or _ge(
        expansion_ratio, thresholds.loss_expansion_severe_ratio
    ):
        score += 0.20
        evidence.append(_ev("loss_expansion", signals, 0.20))
    elif _ge(expansion_pp, thresholds.loss_expansion_warn_pp) or _ge(
        expansion_ratio, thresholds.loss_expansion_warn_ratio
    ):
        score += 0.12
        evidence.append(_ev("loss_expansion", signals, 0.12))

    if _ge(avg_down_count, thresholds.avg_down_severe_count) or _ge(
        avg_down_qty_ratio, thresholds.avg_down_severe_qty_ratio
    ):
        score += 0.15
        evidence.append(_ev("avg_down", signals, 0.15))
    elif _ge(avg_down_count, thresholds.avg_down_warn_count):
        score += 0.08
        evidence.append(_ev("avg_down", signals, 0.08))

    if _ge(failed_recovery, thresholds.failed_recovery_warn_minutes):
        score += 0.08
        evidence.append(_ev("failed_recovery_minutes", failed_recovery, 0.08))
    return min(score, 0.30)


def _decision(
    scores: CandidateScores,
    agent_id: str,
    reason: str,
    *,
    confidence: float,
    route_type: str,
    policy: OrchestratorPolicy,
    secondary_agent: Optional[str] = None,
    secondary_factors: Optional[List[str]] = None,
) -> CycleRouteDecision:
    return CycleRouteDecision(
        trade_id=scores.trade_id,
        agent_id=agent_id,
        route_status="routed" if route_type != "abstain" else "abstained",
        confidence=round(_clamp(confidence), 4),
        reason=reason,
        route_type=route_type,
        primary_agent=agent_id,
        secondary_agent=secondary_agent,
        secondary_factors=secondary_factors or [],
        classifier_scores=scores,
        profile_eligible=confidence >= policy.profile_update_min_confidence
        and route_type in {"single_primary", "single_primary_with_secondary"},
    )


def _confidence(top_score: float, margin: float) -> float:
    return _clamp(top_score * 0.75 + min(max(margin, 0.0), 0.4) * 0.625)


def _ev(feature: str, value: Any, contribution: float) -> Dict[str, Any]:
    return {"feature": feature, "value": value, "contribution": round(contribution, 4)}


def _ge(value: Any, threshold: float) -> bool:
    try:
        return value is not None and float(value) >= threshold
    except (TypeError, ValueError):
        return False


def _le(value: Any, threshold: float) -> bool:
    try:
        return value is not None and float(value) <= threshold
    except (TypeError, ValueError):
        return False


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
