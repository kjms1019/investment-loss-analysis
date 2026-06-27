"""Unified entry and live-position risk predictor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional

from .schema import (
    EntryContext,
    HistoricalTrainingExample,
    PositionSnapshot,
    PredictorEvent,
    ProblemType,
    RiskSignal,
    UserRiskProfile,
)
from .storage import PredictorStorage


ENTRY_ERROR = "entry_error"
STOP_LOSS_FAILURE = "stop_loss_failure"


@dataclass
class NotificationPolicy:
    """Deduplicate alerts while still allowing severity escalation."""

    threshold: float = 0.7
    cooldown_minutes: int = 30
    _last_alerts: Dict[tuple[str, str, str, str], tuple[datetime, str]] = field(default_factory=dict)

    def should_send(self, signal: RiskSignal, now: Optional[datetime] = None) -> bool:
        if signal.risk_score < self.threshold:
            return False
        now = now or signal.created_at
        key = (signal.user_id, signal.trade_id, signal.mode, signal.problem_type)
        previous = self._last_alerts.get(key)
        if previous is None:
            self._last_alerts[key] = (now, signal.risk_level)
            return True

        last_at, last_level = previous
        if _level_rank(signal.risk_level) > _level_rank(last_level):
            self._last_alerts[key] = (now, signal.risk_level)
            return True
        if now - last_at >= timedelta(minutes=self.cooldown_minutes):
            self._last_alerts[key] = (now, signal.risk_level)
            return True
        return False


class TradeRiskPredictor:
    """One predictor component with two modes: entry and live monitoring."""

    def __init__(
        self,
        storage: Optional[PredictorStorage] = None,
        profile: Optional[UserRiskProfile] = None,
        notification_policy: Optional[NotificationPolicy] = None,
        min_ml_examples: int = 20,
    ) -> None:
        self.storage = storage
        self.profile = profile
        self.notification_policy = notification_policy or NotificationPolicy()
        self.min_ml_examples = min_ml_examples
        self._models: dict[str, object] = {}
        self._feature_names: dict[str, list[str]] = {}

    @classmethod
    def from_sqlite(
        cls,
        db_path: str,
        user_id: str = "default",
        profile_db_path: str | None = None,
        notification_policy: Optional[NotificationPolicy] = None,
    ) -> "TradeRiskPredictor":
        if profile_db_path is None:
            storage = PredictorStorage(db_path=db_path)
        else:
            storage = PredictorStorage(db_path=db_path, profile_db_path=profile_db_path)
        profile = storage.load_user_profile(user_id=user_id)
        return cls(storage=storage, profile=profile, notification_policy=notification_policy)

    def fit(self, examples: Iterable[HistoricalTrainingExample]) -> None:
        """Train Random Forest models when enough labeled data is available."""
        random_forest = _random_forest_classifier()
        if random_forest is None:
            return

        by_mode: dict[str, list[HistoricalTrainingExample]] = {"entry": [], "live": []}
        for example in examples:
            by_mode[example.mode].append(example)

        for mode, mode_examples in by_mode.items():
            labels = [1 if item.repeated_mistake else 0 for item in mode_examples]
            if len(mode_examples) < self.min_ml_examples or len(set(labels)) < 2:
                continue

            names = sorted({key for item in mode_examples for key in item.features})
            matrix = [[float(item.features.get(name, 0.0)) for name in names] for item in mode_examples]
            model = random_forest(
                n_estimators=120,
                max_depth=5,
                random_state=42,
                class_weight="balanced",
            )
            model.fit(matrix, labels)
            self._models[mode] = model
            self._feature_names[mode] = names

    def evaluate(self, event: PredictorEvent) -> RiskSignal:
        if event.type == "ENTRY":
            if not isinstance(event.payload, EntryContext):
                raise TypeError("ENTRY events require EntryContext payload")
            return self.predict_entry_risk(event.payload)
        if event.type == "POSITION_UPDATE":
            if not isinstance(event.payload, PositionSnapshot):
                raise TypeError("POSITION_UPDATE events require PositionSnapshot payload")
            return self.monitor_live_position(event.payload)
        raise ValueError(f"Unsupported predictor event type: {event.type}")

    def predict_entry_risk(self, context: EntryContext) -> RiskSignal:
        profile = self._profile_for(context.user_id)
        features = context.to_feature_dict()
        rule_score, problem_type, reasons = self._entry_rule_score(context, profile)
        score, model_used = self._combine_with_model("entry", features, rule_score)

        signal = self._build_signal(
            user_id=context.user_id,
            trade_id=context.trade_id,
            code=context.code,
            mode="entry",
            score=score,
            problem_type=problem_type,
            reasons=reasons,
            model_used=model_used,
            features=features,
        )
        self._persist_if_alert(signal)
        return signal

    def monitor_live_position(self, snapshot: PositionSnapshot) -> RiskSignal:
        profile = self._profile_for(snapshot.user_id)
        features = snapshot.to_feature_dict()
        rule_score, problem_type, reasons = self._live_rule_score(snapshot, profile)
        score, model_used = self._combine_with_model("live", features, rule_score)

        signal = self._build_signal(
            user_id=snapshot.user_id,
            trade_id=snapshot.trade_id,
            code=snapshot.code,
            mode="live",
            score=score,
            problem_type=problem_type,
            reasons=reasons,
            model_used=model_used,
            features=features,
        )
        self._persist_if_alert(signal)
        return signal

    def evaluate_positions(self, snapshots: Iterable[PositionSnapshot]) -> list[RiskSignal]:
        return [self.monitor_live_position(snapshot) for snapshot in snapshots]

    def _entry_rule_score(
        self,
        context: EntryContext,
        profile: UserRiskProfile,
    ) -> tuple[float, ProblemType, list[str]]:
        score = 0.15
        reasons: list[str] = []
        problem_type: ProblemType = _dominant_or_unknown(profile)

        if profile.total_analyzed_trades > 0:
            prior = max(profile.prior_for(ENTRY_ERROR), profile.prior_for(STOP_LOSS_FAILURE))
            avg_score = profile.average_score_for(problem_type) if problem_type != "unknown" else 0.0
            score += min(prior * 0.25 + avg_score * 0.2, 0.35)
            reasons.append(f"profile_prior:{problem_type}")

        if context.recent_win_rate is not None and context.recent_trade_count >= 3:
            if context.recent_win_rate < 0.35:
                score += 0.18
                reasons.append("low_recent_win_rate")
            elif context.recent_win_rate > 0.65:
                score -= 0.05

        if context.minutes_since_last_loss is not None and context.minutes_since_last_loss <= 60:
            score += 0.22
            problem_type = ENTRY_ERROR
            reasons.append("quick_reentry_after_loss")

        if context.last_loss_pct is not None and context.last_loss_pct <= -5:
            score += 0.16
            reasons.append("large_previous_loss")

        if context.same_day_trade_count >= 4:
            score += 0.12
            problem_type = ENTRY_ERROR
            reasons.append("high_same_day_trade_count")

        if context.market_mood_score is not None and context.market_mood_score < -0.4:
            score += 0.08
            reasons.append("weak_market_mood")

        # 진입맥락(min1) — 과열·추격 자리는 진입오류 위험 가산.
        # 분석단 분류기와 동일 피처(entry_features_window)를 써서 "분류 근거 = 예측 근거" 유지.
        ctx_score, ctx_reasons = _entry_context_risk(context.features)
        if ctx_reasons:
            score += ctx_score
            problem_type = ENTRY_ERROR
            reasons.extend(ctx_reasons)

        if not reasons:
            reasons.append("no_strong_entry_risk_signal")

        return _clamp(score), problem_type, reasons

    def _live_rule_score(
        self,
        snapshot: PositionSnapshot,
        profile: UserRiskProfile,
    ) -> tuple[float, ProblemType, list[str]]:
        score = 0.12
        reasons: list[str] = []
        problem_type: ProblemType = _dominant_or_unknown(profile)

        if profile.total_analyzed_trades > 0:
            stop_prior = profile.prior_for(STOP_LOSS_FAILURE)
            entry_prior = profile.prior_for(ENTRY_ERROR)
            score += min(max(stop_prior, entry_prior) * 0.2, 0.2)
            reasons.append(f"profile_prior:{problem_type}")

        pnl = snapshot.unrealized_return_pct
        if pnl <= -3:
            score += 0.14
            reasons.append("position_in_loss")
        if pnl <= -7:
            score += 0.2
            problem_type = STOP_LOSS_FAILURE
            reasons.append("large_unrealized_loss")

        if snapshot.stop_breached:
            score += 0.25
            problem_type = STOP_LOSS_FAILURE
            reasons.append("stop_loss_breached")

        if snapshot.minutes_since_stop_breach is not None and snapshot.minutes_since_stop_breach >= 30:
            score += 0.15
            problem_type = STOP_LOSS_FAILURE
            reasons.append("delayed_action_after_stop_breach")

        if snapshot.holding_minutes <= 60 and pnl <= -2:
            score += 0.12
            if problem_type != STOP_LOSS_FAILURE:
                problem_type = ENTRY_ERROR
            reasons.append("early_loss_after_entry")

        if snapshot.drawdown_from_high_pct <= -5:
            score += 0.1
            reasons.append("sharp_drawdown_from_high")

        if snapshot.price_change_5m_pct is not None and snapshot.price_change_5m_pct <= -2:
            score += 0.08
            reasons.append("fast_short_term_drop")

        if snapshot.volatility_30m_pct is not None and snapshot.volatility_30m_pct >= 3:
            score += 0.05
            reasons.append("high_intraday_volatility")

        if snapshot.market_mood_score is not None and snapshot.market_mood_score < -0.4:
            score += 0.05
            reasons.append("weak_market_mood")

        if not reasons:
            reasons.append("no_strong_live_risk_signal")

        return _clamp(score), problem_type, reasons

    def _combine_with_model(
        self,
        mode: str,
        features: Dict[str, float],
        rule_score: float,
    ) -> tuple[float, str]:
        model = self._models.get(mode)
        names = self._feature_names.get(mode)
        if model is None or not names:
            return rule_score, "rules"

        row = [[float(features.get(name, 0.0)) for name in names]]
        probability = float(model.predict_proba(row)[0][1])  # type: ignore[attr-defined]
        return _clamp(probability * 0.65 + rule_score * 0.35), "random_forest"

    def _build_signal(
        self,
        *,
        user_id: str,
        trade_id: str,
        code: str,
        mode: str,
        score: float,
        problem_type: ProblemType,
        reasons: list[str],
        model_used: str,
        features: Dict[str, float],
    ) -> RiskSignal:
        level = _risk_level(score)
        signal = RiskSignal(
            user_id=user_id,
            trade_id=trade_id,
            code=code,
            mode=mode,  # type: ignore[arg-type]
            risk_score=round(score, 4),
            risk_level=level,
            problem_type=problem_type,
            should_alert=False,
            reasons=reasons,
            model_used=model_used,  # type: ignore[arg-type]
            features=features,
        )
        signal.should_alert = self.notification_policy.should_send(signal)
        if signal.should_alert:
            # 알림 발생 시에만 LLM 문장 생성(대량 호출 방지). 키 없으면 룰 템플릿 폴백.
            from .alert_message import build_alert_message
            signal.message = build_alert_message(signal)
        return signal

    def _persist_if_alert(self, signal: RiskSignal) -> None:
        if signal.should_alert and self.storage is not None:
            self.storage.insert_alert(signal)

    def _profile_for(self, user_id: str) -> UserRiskProfile:
        if self.profile is not None and self.profile.user_id == user_id:
            return self.profile
        if self.storage is not None:
            self.profile = self.storage.load_user_profile(user_id=user_id)
            return self.profile
        return UserRiskProfile(user_id=user_id, source="empty")


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _level_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


def _dominant_or_unknown(profile: UserRiskProfile) -> ProblemType:
    if profile.dominant_problem_type in {ENTRY_ERROR, STOP_LOSS_FAILURE}:
        return profile.dominant_problem_type
    return "unknown"


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _entry_context_risk(features: Dict[str, float]) -> tuple[float, list[str]]:
    """진입맥락(min1) 과열·추격 신호 → 진입오류 위험 가산치와 사유.

    features 가 비어있으면(시세 미연결) (0, []) 을 반환해 기존 행동기반 점수를 유지한다.
    가산 상한 0.30 — 행동기반 경계 거래를 알림 임계(0.7) 위로 올릴 수 있되 과적합 방지.
    """
    if not features:
        return 0.0, []
    rp20 = features.get("range_position_20")
    rsi = features.get("rsi_14")
    vs_high20 = features.get("entry_vs_high20")
    ret120 = features.get("ret_120m")
    volr = features.get("volume_ratio_20")

    add = 0.0
    reasons: list[str] = []
    if rp20 is not None and rp20 >= 0.85:        # 20봉 레인지 상단 추격
        add += 0.14
        reasons.append("range_top_chase")
    if rsi is not None and rsi >= 70:            # RSI 과열권 진입
        add += 0.12
        reasons.append("overheated_rsi")
    if vs_high20 is not None and vs_high20 >= 0.99:  # 20봉 고가 1% 이내 추격
        add += 0.10
        reasons.append("near_high20_chase")
    if ret120 is not None and ret120 >= 0.05:    # 직전 120분 +5% 급등 직후 진입
        add += 0.08
        reasons.append("post_surge_entry")
    if volr is not None and volr >= 1.8 and rp20 is not None and rp20 >= 0.7:
        add += 0.06                              # 상단 + 거래량 급증 동반 추격
        reasons.append("volume_chase")
    return min(add, 0.30), reasons


def _random_forest_classifier():
    try:
        from sklearn.ensemble import RandomForestClassifier
    except Exception:  # pragma: no cover - exercised only when sklearn is absent
        return None
    return RandomForestClassifier
