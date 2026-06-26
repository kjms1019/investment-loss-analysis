"""데모 사용자 xlsx 기반 B 루프(사전 경고) 실행기.

흐름:
  1. 종결거래 시트 -> 사용자별 BUY/SELL 합성(min1 종가) -> run_pipeline 백필
     (analysis/data/user_profiles.sqlite3 에 9명 프로파일/패턴 적재)
  2. 투자계획 시트 -> 같은 사용자의 백필된 거래 이력으로 EntryContext 계산
     -> predict_entry_risk() -> 진입 전 경고
  3. 현재보유 시트 -> Min1HoldingMarketDataProvider + 백필된 프로파일
     -> evaluate_current_holdings() -> 손절실패 경고

Supabase 연동은 아직 키가 없어 만들지 않는다. 대신 모든 출력은
RiskSignal/predictor_alerts 컬럼과 동일한 평평한 dict 모양을 유지해,
나중에 PredictorStorage 를 Supabase 클라이언트로 갈아끼우기만 하면 되게 한다.
"""
from __future__ import annotations

import csv
import os
import tempfile
from datetime import date, datetime, time
from typing import Callable, Optional

from common.parser import build_cycles
from common.schema import RawTrade, TradeCycle

from analysis.common.min1_lookup import load_min1, load_name_to_code, price_at
from analysis.predictor import (
    EntryContext,
    NotificationPolicy,
    PredictorStorage,
    RiskSignal,
    TradeRiskPredictor,
)
from analysis.user_profile import UserProfileStorage

from .demo_workbook import load_closed_trades, load_current_holdings, load_investment_plans
from .holding_market_min1 import Min1HoldingMarketDataProvider
from .holding_predictor import _parse_datetime as _parse_demo_datetime
from .holding_predictor import evaluate_current_holdings
from .pipeline import run_pipeline
from .storage import DEFAULT_DB_PATH
from analysis.user_profile import DEFAULT_PROFILE_DB_PATH

PROBLEM_LABELS: dict[str, str] = {
    "entry_error": "진입오류(고점 추격매수 등)",
    "stop_loss_failure": "손절실패(물타기·버티기)",
}

PriceLookup = Callable[[str, datetime], Optional[float]]


def _default_price_lookup(code: str, when: datetime) -> Optional[float]:
    return price_at(load_min1(code), when)


# ──────────────────────────────────────────────
# 종결거래 시트 -> BUY/SELL RawTrade 합성
# ──────────────────────────────────────────────

def _build_trade_rows(
    rows: list[dict],
    name_to_code: dict,
    *,
    price_lookup: Optional[PriceLookup] = None,
) -> tuple[list[RawTrade], list[str]]:
    """종결거래 행마다 매수/매도 시점 min1 종가로 BUY/SELL 한 쌍을 합성.

    코드 매칭 실패·시세 조회 실패 행은 건너뛰고 사유를 같이 반환한다.
    """
    lookup = price_lookup or _default_price_lookup
    raw_trades: list[RawTrade] = []
    skipped: list[str] = []

    for row in rows:
        name = str(row["종목명"])
        trade_id = str(row.get("거래ID", ""))
        code = name_to_code.get(name)
        if not code:
            skipped.append(f"{trade_id}: 종목코드 매칭 실패 ({name})")
            continue

        buy_at = _parse_demo_datetime(row["매수일시"])
        sell_at = _parse_demo_datetime(row["매도일시"])
        buy_price = lookup(code, buy_at)
        sell_price = lookup(code, sell_at)
        if buy_price is None or sell_price is None:
            skipped.append(f"{trade_id}: min1 가격 조회 실패 ({name}/{code})")
            continue

        qty = int(row["수량"])
        raw_trades.append(RawTrade(datetime=buy_at, code=code, name=name, side="BUY", qty=qty, price=buy_price))
        raw_trades.append(RawTrade(datetime=sell_at, code=code, name=name, side="SELL", qty=qty, price=sell_price))

    return raw_trades, skipped


# ──────────────────────────────────────────────
# 1. 백필: 종결거래 -> run_pipeline -> 프로파일/패턴
# ──────────────────────────────────────────────

def backfill_user_profiles(
    xlsx_path: str,
    *,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    name_to_code: Optional[dict] = None,
    price_lookup: Optional[PriceLookup] = None,
) -> dict[str, dict]:
    """종결거래 시트를 사용자별로 기존 run_pipeline에 흘려보내 프로파일을 채운다."""
    mapping = name_to_code if name_to_code is not None else load_name_to_code()
    closed_by_user = load_closed_trades(xlsx_path)

    report: dict[str, dict] = {}
    for user_id, rows in closed_by_user.items():
        raw_trades, skipped = _build_trade_rows(rows, mapping, price_lookup=price_lookup)
        if not raw_trades:
            report[user_id] = {"status": "skipped", "reason": "no_valid_trades", "skipped_rows": skipped}
            continue

        raw_trades.sort(key=lambda t: t.datetime)
        csv_path = _write_generic_csv(raw_trades)
        try:
            result = run_pipeline(
                csv_path,
                broker="generic",
                db_path=db_path,
                user_id=user_id,
                profile_db_path=profile_db_path,
            )
            report[user_id] = {
                "status": "ok",
                "run_id": result.run_id,
                "loss_cycles": result.normalized_count,
                "skipped_rows": skipped,
            }
        finally:
            os.unlink(csv_path)

    return report


def _write_generic_csv(raw_trades: list[RawTrade]) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8-sig",
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "code", "name", "side", "qty", "price", "fee"])
        for t in raw_trades:
            writer.writerow(
                [t.datetime.strftime("%Y-%m-%d %H:%M:%S"), t.code, t.name, t.side, t.qty, t.price, t.fee]
            )
        return f.name


# ──────────────────────────────────────────────
# 2. 투자계획 -> 진입 전 경고
# ──────────────────────────────────────────────

def _build_entry_context(
    *,
    user_id: str,
    trade_id: str,
    code: str,
    entered_at: datetime,
    closed_cycles: list[TradeCycle],
) -> EntryContext:
    """같은 사용자의 과거 종결거래에서 진입 시점 직전 행동 지표를 계산."""
    prior = sorted(
        (c for c in closed_cycles if c.exit_dt and c.exit_dt <= entered_at),
        key=lambda c: c.exit_dt,
    )
    recent = prior[-5:]
    recent_trade_count = len(recent)
    recent_win_rate = (
        sum(1 for c in recent if c.realized_pnl > 0) / recent_trade_count
        if recent_trade_count else None
    )
    last_loss = next((c for c in reversed(prior) if c.realized_pnl < 0), None)
    minutes_since_last_loss = (
        (entered_at - last_loss.exit_dt).total_seconds() / 60.0 if last_loss else None
    )
    same_day_trade_count = sum(
        1 for c in prior if c.entry_dt and c.entry_dt.date() == entered_at.date()
    )

    return EntryContext(
        user_id=user_id,
        trade_id=trade_id,
        code=code,
        entered_at=entered_at,
        recent_trade_count=recent_trade_count,
        recent_win_rate=recent_win_rate,
        minutes_since_last_loss=minutes_since_last_loss,
        last_loss_pct=last_loss.realized_pnl_pct if last_loss else None,
        same_day_trade_count=same_day_trade_count,
    )


def check_entry_warnings(
    xlsx_path: str,
    as_of: datetime,
    *,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    name_to_code: Optional[dict] = None,
    price_lookup: Optional[PriceLookup] = None,
    notification_policy: Optional[NotificationPolicy] = None,
) -> list[dict]:
    """예정일시 >= as_of 인 투자계획 행에 대해 진입오류 사전 경고를 계산."""
    mapping = name_to_code if name_to_code is not None else load_name_to_code()
    plans_by_user = load_investment_plans(xlsx_path)
    closed_by_user = load_closed_trades(xlsx_path)

    storage = PredictorStorage(db_path=db_path, profile_db_path=profile_db_path)
    alerts: list[dict] = []
    try:
        for user_id, plan_rows in plans_by_user.items():
            raw_trades, _skipped = _build_trade_rows(
                closed_by_user.get(user_id, []), mapping, price_lookup=price_lookup,
            )
            cycles = build_cycles(raw_trades)
            profile = storage.load_user_profile(user_id=user_id)
            predictor = TradeRiskPredictor(
                storage=storage,
                profile=profile,
                notification_policy=notification_policy or NotificationPolicy(),
            )

            for plan_row in plan_rows:
                entered_at = _parse_demo_datetime(plan_row["예정일시"])
                if entered_at < as_of:
                    continue
                name = str(plan_row["종목명"])
                code = mapping.get(name)
                if not code:
                    continue

                context = _build_entry_context(
                    user_id=user_id,
                    trade_id=str(plan_row.get("계획ID")),
                    code=code,
                    entered_at=entered_at,
                    closed_cycles=cycles,
                )
                signal = predictor.predict_entry_risk(context)
                if signal.should_alert:
                    alerts.append(_format_entry_alert(user_id, name, plan_row, signal, profile_db_path))
    finally:
        storage.close()

    return alerts


def _format_entry_alert(
    user_id: str,
    name: str,
    plan_row: dict,
    signal: RiskSignal,
    profile_db_path: str,
) -> dict:
    label = PROBLEM_LABELS.get(signal.problem_type, "반복 실수")
    evidence = _top_pattern_text(profile_db_path, user_id)
    message = f"지금 사려는 {name}, 당신은 {label} 경향이 있어요. 한 번 더 생각해볼까요?"
    if evidence:
        message += f" (근거: 과거 '{evidence}' 패턴)"

    return {
        "user_id": user_id,
        "code": signal.code,
        "name": name,
        "plan_id": plan_row.get("계획ID"),
        "scheduled_at": plan_row.get("예정일시"),
        "mode": "entry",
        "problem_type": signal.problem_type,
        "risk_score": signal.risk_score,
        "risk_level": signal.risk_level,
        "reasons": signal.reasons,
        "evidence": evidence,
        "message": message,
    }


# ──────────────────────────────────────────────
# 3. 현재보유 -> 손절실패 경고
# ──────────────────────────────────────────────

def check_stop_loss_warnings(
    xlsx_path: str,
    as_of: datetime,
    *,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    market_data_provider=None,
    notification_policy: Optional[NotificationPolicy] = None,
) -> list[dict]:
    """현재보유 시트 종목을 as_of 시점 시세로 평가해 손절실패 경고를 계산."""
    holdings_by_user = load_current_holdings(xlsx_path)
    provider = market_data_provider or Min1HoldingMarketDataProvider(observed_at=as_of)

    storage = PredictorStorage(db_path=db_path, profile_db_path=profile_db_path)
    alerts: list[dict] = []
    try:
        for user_id, rows in holdings_by_user.items():
            profile = storage.load_user_profile(user_id=user_id)
            results = evaluate_current_holdings(
                rows,
                profile=profile,
                market_data_provider=provider,
                notification_policy=notification_policy or NotificationPolicy(),
            )
            for result in results:
                if result.signal.should_alert:
                    storage.insert_alert(result.signal)
                    alerts.append(
                        _format_stop_loss_alert(user_id, result.holding.name, result.signal, profile_db_path)
                    )
    finally:
        storage.close()

    return alerts


def _format_stop_loss_alert(
    user_id: str,
    name: str,
    signal: RiskSignal,
    profile_db_path: str,
) -> dict:
    label = PROBLEM_LABELS.get(signal.problem_type, "반복 실수")
    evidence = _top_pattern_text(profile_db_path, user_id)
    message = f"{name} 종목이 하락 중입니다. 당신은 {label} 경향이 있어요. 미리 정한 손절선을 지켜보세요."
    if evidence:
        message += f" (근거: 과거 '{evidence}' 패턴)"

    return {
        "user_id": user_id,
        "code": signal.code,
        "name": name,
        "mode": "live",
        "problem_type": signal.problem_type,
        "risk_score": signal.risk_score,
        "risk_level": signal.risk_level,
        "reasons": signal.reasons,
        "evidence": evidence,
        "message": message,
    }


def _top_pattern_text(profile_db_path: str, user_id: str) -> Optional[str]:
    storage = UserProfileStorage(db_path=profile_db_path)
    try:
        patterns = storage.load_patterns(user_id)
    finally:
        storage.close()
    if not patterns:
        return None
    return patterns[0].get("name_ko") or patterns[0].get("pattern_id")


# ──────────────────────────────────────────────
# 묶음 실행 + CLI
# ──────────────────────────────────────────────

def run_demo_alerts(
    xlsx_path: str,
    as_of_date: date,
    *,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
) -> dict:
    """백필 + 두 경고 시나리오를 모두 실행."""
    backfilled = backfill_user_profiles(xlsx_path, db_path=db_path, profile_db_path=profile_db_path)

    day_start = datetime.combine(as_of_date, time.min)
    market_now = datetime.combine(as_of_date, time(15, 30))

    entry_warnings = check_entry_warnings(
        xlsx_path, day_start, db_path=db_path, profile_db_path=profile_db_path,
    )
    stop_loss_warnings = check_stop_loss_warnings(
        xlsx_path, market_now, db_path=db_path, profile_db_path=profile_db_path,
    )

    return {
        "backfilled_users": backfilled,
        "entry_warnings": entry_warnings,
        "stop_loss_warnings": stop_loss_warnings,
    }


def _parse_cli_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="데모 사용자 xlsx 기반 사전 경고 데모 실행")
    parser.add_argument("--xlsx", required=True, help="demo_users_all_data.final_3sheets.xlsx 경로")
    parser.add_argument("--as-of", default="2026-06-23", help="기준일 (YYYY-MM-DD)")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--profile-db-path", default=DEFAULT_PROFILE_DB_PATH)
    args = parser.parse_args()

    result = run_demo_alerts(
        args.xlsx,
        _parse_cli_date(args.as_of),
        db_path=args.db_path,
        profile_db_path=args.profile_db_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
