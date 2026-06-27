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


@dataclass(frozen=True)
class PredictorScoringConfig:
    """Tunable scoring thresholds for runtime alerts.

    Label definitions stay fixed. These values only control alert sensitivity
    and risk bands, so they can be calibrated with production data later.
    """

    risk_medium: float = 0.45
    risk_high: float = 0.75
    entry_base_score: float = 0.15
    live_base_score: float = 0.12
    profile_prior_weight: float = 0.25
    profile_average_weight: float = 0.20
    entry_profile_max_add: float = 0.35
    live_profile_max_add: float = 0.20
    low_recent_win_rate: float = 0.35
    high_recent_win_rate: float = 0.65
    quick_reentry_minutes: float = 60.0
    large_previous_loss_pct: float = -5.0
    high_same_day_trade_count: int = 4
    weak_market_mood: float = -0.4
    position_loss_pct: float = -3.0
    large_unrealized_loss_pct: float = -7.0
    stop_breach_delay_minutes: float = 30.0
    early_holding_minutes: float = 60.0
    early_loss_pct: float = -2.0
    sharp_drawdown_pct: float = -5.0
    fast_drop_5m_pct: float = -2.0
    high_volatility_30m_pct: float = 3.0
    entry_range_top: float = 0.85
    entry_rsi_overheated: float = 70.0
    entry_near_high20: float = 0.99
    entry_ret120_surge: float = 0.05
    entry_volume_chase: float = 1.8
    entry_volume_range_min: float = 0.7
    entry_context_max_add: float = 0.30

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
        scoring_config: Optional[PredictorScoringConfig] = None,
    ) -> None:
        self.storage = storage
        self.profile = profile
        self.notification_policy = notification_policy or NotificationPolicy()
        self.min_ml_examples = min_ml_examples
        self.scoring_config = scoring_config or PredictorScoringConfig()
        self._models: dict[str, object] = {}
        self._feature_names: dict[str, list[str]] = {}

    @classmethod
    def from_sqlite(
        cls,
        db_path: str,
        user_id: str = "default",
        profile_db_path: str | None = None,
        notification_policy: Optional[NotificationPolicy] = None,
        scoring_config: Optional[PredictorScoringConfig] = None,
    ) -> "TradeRiskPredictor":
        if profile_db_path is None:
            storage = PredictorStorage(db_path=db_path)
        else:
            storage = PredictorStorage(db_path=db_path, profile_db_path=profile_db_path)
        profile = storage.load_user_profile(user_id=user_id)
        return cls(
            storage=storage,
            profile=profile,
            notification_policy=notification_policy,
            scoring_config=scoring_config,
        )

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
        config = self.scoring_config
        score = config.entry_base_score
        reasons: list[str] = []
        problem_type: ProblemType = _dominant_or_unknown(profile)

        if profile.total_analyzed_trades > 0:
            prior = max(profile.prior_for(ENTRY_ERROR), profile.prior_for(STOP_LOSS_FAILURE))
            avg_score = profile.average_score_for(problem_type) if problem_type != "unknown" else 0.0
            score += min(prior * config.profile_prior_weight + avg_score * config.profile_average_weight, config.entry_profile_max_add)
            reasons.append(f"profile_prior:{problem_type}")

        if context.recent_win_rate is not None and context.recent_trade_count >= 3:
            if context.recent_win_rate < config.low_recent_win_rate:
                score += 0.18
                reasons.append("low_recent_win_rate")
            elif context.recent_win_rate > config.high_recent_win_rate:
                score -= 0.05

        if context.minutes_since_last_loss is not None and context.minutes_since_last_loss <= config.quick_reentry_minutes:
            score += 0.22
            problem_type = ENTRY_ERROR
            reasons.append("quick_reentry_after_loss")

        if context.last_loss_pct is not None and context.last_loss_pct <= config.large_previous_loss_pct:
            score += 0.16
            reasons.append("large_previous_loss")

        if context.same_day_trade_count >= config.high_same_day_trade_count:
            score += 0.12
            problem_type = ENTRY_ERROR
            reasons.append("high_same_day_trade_count")

        if context.market_mood_score is not None and context.market_mood_score < config.weak_market_mood:
            score += 0.08
            reasons.append("weak_market_mood")

        # ?꿔꺂?????鶯ㅼ룆?븀뙼???min1) ????縕???怨뺤깓????ㅻ쿋??????????꿔꺂????????怨몄뵒 ????꾣뤃????醫딆쓧???
        # ???곗뒩泳??????곗뒩泳?봺異??녿옐??좊펳?? ????怨뺣윞 ??濚밸Ŧ?녘キ?entry_features_window)????欲꼲??"???곗뒩泳?봺異???????筌?= ???? ??????筌? ???.
        ctx_score, ctx_reasons = _entry_context_risk(context.features, config)
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
        config = self.scoring_config
        score = config.live_base_score
        reasons: list[str] = []
        problem_type: ProblemType = _dominant_or_unknown(profile)

        if profile.total_analyzed_trades > 0:
            stop_prior = profile.prior_for(STOP_LOSS_FAILURE)
            entry_prior = profile.prior_for(ENTRY_ERROR)
            score += min(max(stop_prior, entry_prior) * config.profile_average_weight, config.live_profile_max_add)
            reasons.append(f"profile_prior:{problem_type}")

        pnl = snapshot.unrealized_return_pct
        if pnl <= config.position_loss_pct:
            score += 0.14
            reasons.append("position_in_loss")
        if pnl <= config.large_unrealized_loss_pct:
            score += 0.2
            problem_type = STOP_LOSS_FAILURE
            reasons.append("large_unrealized_loss")

        if snapshot.stop_breached:
            score += 0.25
            problem_type = STOP_LOSS_FAILURE
            reasons.append("stop_loss_breached")

        if snapshot.minutes_since_stop_breach is not None and snapshot.minutes_since_stop_breach >= config.stop_breach_delay_minutes:
            score += 0.15
            problem_type = STOP_LOSS_FAILURE
            reasons.append("delayed_action_after_stop_breach")

        if snapshot.holding_minutes <= config.early_holding_minutes and pnl <= config.early_loss_pct:
            score += 0.12
            if problem_type != STOP_LOSS_FAILURE:
                problem_type = ENTRY_ERROR
            reasons.append("early_loss_after_entry")

        if snapshot.drawdown_from_high_pct <= config.sharp_drawdown_pct:
            score += 0.1
            reasons.append("sharp_drawdown_from_high")

        if snapshot.price_change_5m_pct is not None and snapshot.price_change_5m_pct <= config.fast_drop_5m_pct:
            score += 0.08
            reasons.append("fast_short_term_drop")

        if snapshot.volatility_30m_pct is not None and snapshot.volatility_30m_pct >= config.high_volatility_30m_pct:
            score += 0.05
            reasons.append("high_intraday_volatility")

        if snapshot.market_mood_score is not None and snapshot.market_mood_score < config.weak_market_mood:
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
        level = _risk_level(score, self.scoring_config)
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
            # ??????熬곣뫖利든뜏類ｋ렱????嶺?獄?툦??LLM ???戮?뜪?????꾩룆????????癲ル슢?????熬곣뫖?삥납?). ??????ㅼ굡?類㎮뵾????????萸???????
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


def _risk_level(score: float, config: PredictorScoringConfig) -> str:
    if score >= config.risk_high:
        return "high"
    if score >= config.risk_medium:
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


def _entry_context_risk(features: Dict[str, float], config: PredictorScoringConfig) -> tuple[float, list[str]]:
    """?꿔꺂?????鶯ㅼ룆?븀뙼???min1) ??縕???怨뺤깓????ㅻ쿋???????ъ군濚????꿔꺂????????怨몄뵒 ????꾣뤃????醫딆쓧?????????? ????.

    features ??醫딆쓧? ????猷뱀쟼???繹먮겧嫄х솾???嶺??????붺몭?겹럷?룐뫕?⑶뇦猿뗫닔?? (0, []) ???熬곣뫖利???????뚯????????ㅻ깹壤???뚯???維◈????????????嶺뚮㉡???
    ??醫딆쓧???????브컯??0.30 ??????ㅻ깹壤???뚯???維◈??嚥▲굧?????꿸쑨????亦껋꺀?좉괴??????????꾤뙴??0.7) ????썹땟怨⒲뀋????????????⑸룎 ??縕?????熬곣뫖?삥납?.
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
    if rp20 is not None and rp20 >= config.entry_range_top:        # 20?????繹먮굝?꿰솾?レ뒩?? ????욱룏?????ㅻ쿋???
        add += 0.14
        reasons.append("range_top_chase")
    if rsi is not None and rsi >= config.entry_rsi_overheated:            # RSI ??縕???怨뺣샨???꿔꺂?????
        add += 0.12
        reasons.append("overheated_rsi")
    if vs_high20 is not None and vs_high20 >= config.entry_near_high20:  # 20?????쒙쭫? 1% ????????ㅻ쿋???
        add += 0.10
        reasons.append("near_high20_chase")
    if ret120 is not None and ret120 >= config.entry_ret120_surge:    # ?꿔꺂?????120??+5% ???궰?嶺뚮씞?쀧뵳??꿔꺂??????꿔꺂?????
        add += 0.08
        reasons.append("post_surge_entry")
    if volr is not None and volr >= config.entry_volume_chase and rp20 is not None and rp20 >= config.entry_volume_range_min:
        add += 0.06                              # ????욱룏??+ ?꿸쑨?????????궰?嶺뚮씚裕????????뼐 ???ㅻ쿋???
        reasons.append("volume_chase")
    return min(add, config.entry_context_max_add), reasons


def _random_forest_classifier():
    try:
        from sklearn.ensemble import RandomForestClassifier
    except Exception:  # pragma: no cover - exercised only when sklearn is absent
        return None
    return RandomForestClassifier
