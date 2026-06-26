"""총괄 오케스트레이션 파이프라인.

흐름:
  CSV → RawTrade → TradeCycle (사이클 묶기)
  → 손실 사이클 필터링
  → 심리 귀속(psych focus, 룰)        ┐  에이전트 해석/분석용 (라우팅 미반영, LLM 없음)
  → 손절실패 엔진 전체 실행(룰)       ┘
  → 전체피처 분류기로 사이클별 라우팅 (entry/stop 두 점수 '단독'으로 결정)
  → 라우팅된 에이전트 결과 채택 + 심리 evidence 첨부
  → AgentResult 저장 + 반환

라우팅은 분류기 단독으로 결정한다. psych/stop_fail은 LLM 없이 룰로 계산하되
라우팅엔 가산하지 않고, 도메인 에이전트의 해석(심리)·분석(손절)에만 쓴다.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트 / analysis 를 sys.path 에 추가 (common, psych_agent import 용)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ANALYSIS_DIR = _PROJECT_ROOT / "analysis"
for _p in (str(_PROJECT_ROOT), str(_ANALYSIS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.adapters import to_younghyun_transaction
from common.parser import build_cycles, filter_loss_cycles, parse_csv
from common.schema import RawTrade, TradeCycle

from analysis.classifier import classify_entry
from analysis.label_validation.label_pipeline import (
    CLASSIFIER_FEATURES,
    classifier_features_for_trade,
)
from . import agent_registry as registry
from .interaction import build_interaction_state
from .router import route_cycle
from .schema import AgentResult, OrchestratorRunResult
from .storage import DEFAULT_DB_PATH, OrchestratorStorage
from analysis.user_profile import (
    DEFAULT_PROFILE_DB_PATH,
    UserProfileStorage,
    build_profile,
    build_patterns,
)

# 라우터 손절 근사 폴백 임계값 (영현 엔진 신호를 못 얻을 때만 사용)
_FALLBACK_STOP_PCT = -5.0


# ──────────────────────────────────────────────
# 심리 귀속 (focus.py — cycle_id 로 키 통일)  [#1]
# ──────────────────────────────────────────────

def _run_psych_attribution(
    raw_trades: List[RawTrade],
    loss_cycles: List[TradeCycle],
) -> Dict[str, dict]:
    """손실 사이클별 심리 귀속. 키는 focus.cycle_id 로 통일."""
    import pandas as pd
    from psych_agent.preprocess import preprocess, trades_from_df
    from psych_agent.focus import attribute_losses, cycle_id
    from psych_agent.config import Config

    df = pd.DataFrame([{
        "datetime": t.datetime, "code": t.code, "name": t.name,
        "side": t.side, "qty": t.qty, "price": t.price,
    } for t in raw_trades])
    df["datetime"] = pd.to_datetime(df["datetime"])

    config = Config()
    pre = preprocess(trades_from_df(df), config)
    cyc_by_id = {cycle_id(c.code, c.entry_time): c for c in pre.closed_cycles}

    # 손실 사이클 ↔ psych PositionCycle 매칭 (동일 cycle_id 규약)
    focus_cycles = [
        cyc_by_id[cycle_id(c.code, c.entry_dt)]
        for c in loss_cycles
        if c.entry_dt and cycle_id(c.code, c.entry_dt) in cyc_by_id
    ]
    attributions = attribute_losses(pre, focus_cycles, config)

    # 조회 키와 저장 키를 동일한 cycle_id 로 통일 (핵심: 형식 일치)
    return {cycle_id(a.code, a.entry_time): a.to_dict() for a in attributions}


def _psych_key(cycle: TradeCycle) -> str:
    from psych_agent.focus import cycle_id
    return cycle_id(cycle.code, cycle.entry_dt)


# ──────────────────────────────────────────────
# 손절실패 신호 (영현 엔진 전체 1회 — 룰)  [#3]
# ──────────────────────────────────────────────

def _run_stop_fail_reports(raw_trades: List[RawTrade]) -> Dict[str, dict]:
    """손절실패 엔진을 전체 거래에 1회 실행하고 (code, entry_date) → 리포트 매핑 반환."""
    txn_kwargs = [to_younghyun_transaction(t) for t in raw_trades]
    try:
        reports = registry.run_stop_fail_engine(txn_kwargs)
    except Exception:
        return {}

    by_key: Dict[str, dict] = {}
    for rep in reports:
        key = f"{rep.get('ticker')}@{rep.get('entry_ts')}"   # entry_ts = ISO date
        by_key[key] = rep
    return by_key


def _stop_fail_key(cycle: TradeCycle) -> str:
    entry_date = cycle.entry_dt.date().isoformat() if cycle.entry_dt else ""
    return f"{cycle.code}@{entry_date}"


# ──────────────────────────────────────────────
# 파이프라인 진입점
# ──────────────────────────────────────────────

def run_pipeline(
    trade_csv_path: str,
    broker: str = "generic",
    db_path: str = DEFAULT_DB_PATH,
    user_id: str = "default",
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    classifier_features_by_trade_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> OrchestratorRunResult:
    """CSV 한 파일을 받아 전체 파이프라인을 실행하고 결과를 반환.

    classifier_features_by_trade_id:
        Optional mapping to the final classifier's entry-context features.
        Keys can be TradeCycle.trade_id or "{code}@{entry_dt.isoformat()}".
        When absent, the pipeline builds a sparse fallback from available
        execution rows.
    """

    run_id   = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())
    storage  = OrchestratorStorage(db_path=db_path)

    agent_results: List[AgentResult] = []
    notes: List[str] = []

    try:
        # 1. CSV → 사이클 → 손실 필터
        raw_trades  = parse_csv(trade_csv_path, broker=broker)
        cycles      = build_cycles(raw_trades)
        loss_cycles = filter_loss_cycles(cycles)
        notes.append(f"전체 {len(cycles)}사이클, 손실 {len(loss_cycles)}사이클 대상")

        # 2. 보조 신호 계산 (심리·손절, 룰, 토큰 0) — 라우팅 미반영, 에이전트 해석/분석용
        try:
            psych_attr = _run_psych_attribution(raw_trades, loss_cycles)
        except Exception as e:
            psych_attr = {}
            notes.append(f"심리 귀속 스킵: {e}")

        stop_reports = _run_stop_fail_reports(raw_trades)
        if not stop_reports:
            notes.append("손절실패 신호 없음 (분봉 데이터 부재) → 폴백 임계값 사용")

        # 3. 저장 헤더
        storage.create_batch(
            batch_id=batch_id, source_name="user_csv",
            raw_file_path=trade_csv_path, row_count=len(raw_trades),
        )
        storage.create_run(run_id=run_id, batch_id=batch_id)

        # 4. 사이클별 라우팅 → 결과 채택
        for cycle in loss_cycles:
            trade_id = cycle.trade_id

            attribution = psych_attr.get(_psych_key(cycle))
            psych_dom   = attribution.get("dominant") if attribution else None

            stop_rep = stop_reports.get(_stop_fail_key(cycle))
            stop_score = None
            stop_signals = None
            if stop_rep:
                sig        = stop_rep.get("signals", {})
                breached   = bool(sig.get("breached", False))
                delay_days = int(sig.get("delay_days", 0))
                stop_score = float(stop_rep.get("score", 0.0) or 0.0)
                stop_signals = _minute_stop_signals(sig)
            else:
                breached   = cycle.realized_pnl_pct < _FALLBACK_STOP_PCT
                delay_days = 0

            learned_classifier = _run_learned_classifier(
                cycle,
                raw_trades,
                classifier_features_by_trade_id or {},
            )
            prediction = learned_classifier.get("prediction") or {}

            decision = route_cycle(
                trade_id,
                psych_dominant=psych_dom,
                breached=breached,
                delay_days=delay_days,
                delay_minutes=delay_days * 390,
                loss_early_ratio=_loss_early_ratio(cycle, raw_trades),
                stop_report_score=stop_score,
                stop_signals=stop_signals,
                classifier_entry_score=prediction.get("entry_error_score"),
                classifier_stop_score=prediction.get("stop_loss_failure_score"),
                classifier_result=prediction or None,
            )

            # 총괄 판단 결과에 따라 primary 에이전트 하나만 실행한다.
            if decision.route_type == "abstain":
                result = AgentResult(
                    run_id=run_id,
                    trade_id=trade_id,
                    agent_id="unclassified",
                    output_status="skipped",
                    score=None,
                    severity=None,
                    result={
                        "label": "abstain_low_signal",
                        "orchestrator_decision": decision.to_dict(),
                        "learned_classifier": learned_classifier,
                    },
                    route_reason=decision.reason,
                )
                storage.insert_agent_result(result)
                agent_results.append(result)
                continue

            if decision.agent_id == registry.AGENT_STOP_LOSS_FAILURE and stop_rep:
                result = registry.stop_fail_report_to_result(run_id, trade_id, stop_rep)
            else:
                result = registry.run_entry_error(run_id, trade_id, _cycle_data(cycle, raw_trades))

            registry.attach_psych_evidence(result, attribution)
            result.route_reason = decision.reason
            result.result["orchestrator_decision"] = decision.to_dict()
            result.result["learned_classifier"] = learned_classifier
            result.result["secondary_factors"] = decision.secondary_factors
            storage.insert_agent_result(result)
            agent_results.append(result)

        profile_storage = UserProfileStorage(db_path=profile_db_path)
        try:
            profile_storage.insert_trade_labels(user_id, agent_results)
            profile_storage.upsert_profile(
                build_profile(user_id, agent_results),
                latest_run_id=run_id,
            )
            # 반복 실수 패턴 집계 (성향 리포트 '패턴 카드')
            profile_storage.upsert_patterns(
                user_id, run_id, build_patterns(agent_results),
            )
        finally:
            profile_storage.close()

        storage.complete_run(run_id=run_id, status="completed")
        status = "completed"

    except Exception:
        storage.complete_run(run_id=run_id, status="failed")
        raise
    finally:
        storage.close()

    interaction_state = build_interaction_state(agent_results, loss_cycles).to_dict()
    # 총괄 대화 문장(LLM). 키 없으면 템플릿 prompt_body 그대로 폴백.
    from .interaction_llm import llm_interaction_prompt
    interaction_state["llm_prompt_body"] = llm_interaction_prompt(
        interaction_state, fallback=interaction_state.get("prompt_body", ""))

    return OrchestratorRunResult(
        run_id=run_id, batch_id=batch_id, status=status,
        normalized_count=len(loss_cycles),
        interaction_state=interaction_state,
        agent_results=agent_results, notes=notes,
    )


# ──────────────────────────────────────────────
# 보조 계산
# ──────────────────────────────────────────────

def _loss_early_ratio(cycle: TradeCycle, raw_trades: List[RawTrade]) -> Optional[float]:
    """보유 초반 20% 구간에서 발생한 손실 비율 (체결 데이터 근사)."""
    if not cycle.entry_dt or not cycle.exit_dt or cycle.realized_pnl >= 0:
        return None
    duration = (cycle.exit_dt - cycle.entry_dt).total_seconds()
    if duration <= 0:
        return None

    cutoff = cycle.entry_dt.timestamp() + duration * 0.2
    early = [
        t.price for t in raw_trades
        if t.code == cycle.code
        and cycle.entry_dt.timestamp() <= t.datetime.timestamp() <= cutoff
    ]
    if not early or cycle.entry_price <= 0:
        return None

    early_loss = (cycle.entry_price - min(early)) / cycle.entry_price
    total_loss = abs(cycle.realized_pnl_pct) / 100
    return round(early_loss / total_loss, 4) if total_loss > 0 else None


def _run_learned_classifier(
    cycle: TradeCycle,
    raw_trades: List[RawTrade],
    classifier_features_by_trade_id: Dict[str, Dict[str, Any]],
) -> dict:
    provided = (
        classifier_features_by_trade_id.get(cycle.trade_id)
        or classifier_features_by_trade_id.get(_classifier_feature_key(cycle))
    )
    features = dict(provided or {})
    if features:
        feature_source = "provided_by_trade_id"
    else:
        # 분석단: 실 min1에서 전체경로 피처 계산(진입맥락 + 사후경로). 데이터 없으면 None.
        features = classifier_features_for_trade(cycle.code, cycle.entry_dt, cycle.exit_dt)
        feature_source = "min1_full_path"
        if not any(v is not None for v in features.values()):
            features = _classifier_features_from_executions(cycle, raw_trades)
            feature_source = "execution_path_fallback"

    normalized = {name: features.get(name) for name in CLASSIFIER_FEATURES}
    available = [
        name for name, value in normalized.items()
        if value is not None
    ]
    if not available:
        return {
            "status": "skipped",
            "reason": "classifier_features_unavailable",
            "feature_source": feature_source,
            "features": normalized,
        }

    try:
        prediction = classify_entry(normalized)
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "feature_source": feature_source,
            "available_features": available,
            "features": normalized,
        }

    return {
        "status": "ok",
        "feature_source": feature_source,
        "feature_lookup_keys": [cycle.trade_id, _classifier_feature_key(cycle)],
        "available_features": available,
        "features": normalized,
        "prediction": prediction,
    }


def _classifier_feature_key(cycle: TradeCycle) -> str:
    entry = cycle.entry_dt.isoformat() if cycle.entry_dt else ""
    return f"{cycle.code}@{entry}"


def _classifier_features_from_executions(
    cycle: TradeCycle,
    raw_trades: List[RawTrade],
) -> Dict[str, Any]:
    """Build sparse classifier features from available execution rows.

    The final classifier accepts missing features. This fallback keeps the
    architecture wired until real 1-minute entry-context features are supplied.
    """
    features = {name: None for name in CLASSIFIER_FEATURES}
    if not cycle.entry_dt or cycle.entry_price <= 0:
        return features

    rows = sorted(
        [
            trade for trade in raw_trades
            if trade.code == cycle.code and trade.datetime <= cycle.entry_dt
        ],
        key=lambda trade: trade.datetime,
    )
    if not rows:
        return features

    entry_price = float(cycle.entry_price)
    prior_prices = [float(trade.price) for trade in rows]
    prior_qty = [float(trade.qty) for trade in rows]

    for window in (20, 60):
        prices = prior_prices[-window:]
        if len(prices) < 2:
            continue
        high = max(prices)
        low = min(prices)
        if high > low:
            features[f"range_position_{window}"] = (entry_price - low) / (high - low)
        if high > 0:
            features[f"entry_vs_high{window}"] = entry_price / high

    for minutes in (5, 20, 60, 120):
        base = _price_at_or_before(rows, cycle.entry_dt, minutes)
        if base and base > 0:
            features[f"ret_{minutes}m"] = entry_price / base - 1

    ret_5m = features.get("ret_5m")
    ret_20m = features.get("ret_20m")
    if ret_5m is not None and ret_20m is not None:
        features["accel"] = ret_5m - ret_20m

    if len(prior_prices) >= 20:
        ma20 = sum(prior_prices[-20:]) / 20
        if ma20 > 0:
            features["entry_vs_ma20"] = entry_price / ma20 - 1
    if len(prior_prices) >= 40:
        ma20 = sum(prior_prices[-20:]) / 20
        prev_ma20 = sum(prior_prices[-40:-20]) / 20
        if prev_ma20 > 0:
            features["ma_20_slope"] = (ma20 - prev_ma20) / prev_ma20
    if len(prior_qty) >= 20:
        avg_qty = sum(prior_qty[-20:]) / 20
        if avg_qty > 0 and rows[-1].qty:
            features["volume_ratio_20"] = float(rows[-1].qty) / avg_qty

    return features


def _price_at_or_before(
    rows: List[RawTrade],
    entry_dt,
    minutes_before: int,
) -> Optional[float]:
    target_ts = entry_dt.timestamp() - minutes_before * 60
    candidates = [
        trade for trade in rows
        if trade.datetime.timestamp() <= target_ts
    ]
    if not candidates:
        return None
    return float(candidates[-1].price)


def _cycle_data(cycle: TradeCycle, raw_trades: List[RawTrade]) -> dict:
    """entry_error 어댑터 입력용 cycle dict."""
    return {
        "trade_id":         cycle.trade_id,
        "code":             cycle.code,
        "name":             cycle.name,
        "entry_dt":         cycle.entry_dt.isoformat() if cycle.entry_dt else None,
        "exit_dt":          cycle.exit_dt.isoformat()  if cycle.exit_dt  else None,
        "entry_price":      cycle.entry_price,
        "exit_price":       cycle.exit_price,
        "qty":              cycle.qty,
        "realized_pnl":     cycle.realized_pnl,
        "realized_pnl_pct": cycle.realized_pnl_pct,
    }


def _minute_stop_signals(signals: dict) -> dict:
    """Translate stop-loss report signals into minute-level policy fields.

    Current stop-loss reports are mostly day-level. This adapter keeps the new
    orchestrator policy in minute-oriented terms while preserving compatibility
    with the batch engine.
    """
    stop_pct = abs(float(signals.get("stop_pct", 0.0) or 0.0))
    mae_pct = abs(float(signals.get("MAE_pct", 0.0) or 0.0))
    realized = abs(float(signals.get("realized_return_pct", 0.0) or 0.0))
    delay_days = int(signals.get("delay_days", 0) or 0)

    expansion_pct = max(realized - stop_pct, 0.0)
    expansion_ratio = realized / stop_pct if stop_pct > 0 else 0.0

    return {
        "breach_minutes": delay_days * 390,
        "loss_expansion_pct": expansion_pct,
        "loss_expansion_ratio": expansion_ratio,
        "mae_expansion_pct": max(mae_pct - stop_pct, 0.0),
        "avg_down_count_after_loss": int(signals.get("avg_down_count", 0) or 0),
        "avg_down_qty_ratio": float(signals.get("avg_down_qty_ratio", 0.0) or 0.0),
        "failed_recovery_minutes": delay_days * 390 if signals.get("breached") else 0,
    }
