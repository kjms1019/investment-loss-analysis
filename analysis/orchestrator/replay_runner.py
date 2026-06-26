"""분 단위 인트라데이 실시간 재생기 (B·C 루프).

"현재=2026-06-23 종가"를 기준으로 백필된 사용자 프로파일을 고정해두고,
미래 구간(기본 2026-06-24 09:00 ~ 06-26 15:30)의 1분봉을 한 틱씩 전진시키며
실시간 경고를 재생한다. 모델·아키텍처는 미래를 모르고, observed_at 가 가리키는
시점까지의 분봉만 본다(Min1HoldingMarketDataProvider 가 index_at 으로 컷).

재생 루프:
  · C 루프(현재보유 손절 감시): 매 틱마다 observed_at=틱 으로 보유종목 평가.
    같은 (problem_type, risk_level) 반복은 억제하고, 신규 경고·등급 변화만 로그.
  · B 루프(투자계획 사전경고): 예정일시를 시뮬레이션 시계가 처음 지나는 틱에 1회 발화.

산출물: 콘솔 알림 스트림 + JSONL 알림 로그(틱 시각 포함).

사용 예:
  python -m analysis.orchestrator.replay_runner \
      --xlsx tests/fixtures/demo_users_all_data.final_3sheets.xlsx
  python -m analysis.orchestrator.replay_runner --start "2026-06-24 09:00" \
      --end "2026-06-24 15:30" --out analysis/data/replay_alerts.jsonl
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, Optional

import pandas as pd

from common.parser import build_cycles

from analysis.common.min1_lookup import load_min1, load_name_to_code
from analysis.predictor import NotificationPolicy, PredictorStorage, TradeRiskPredictor

from .demo_alert_runner import (
    _build_entry_context,
    _build_trade_rows,
    _format_entry_alert,
    _format_stop_loss_alert,
    backfill_user_profiles,
)
from .demo_workbook import (
    load_closed_trades,
    load_current_holdings,
    load_investment_plans,
)
from .holding_market_min1 import Min1HoldingMarketDataProvider
from .holding_predictor import (
    CurrentHoldingInput,
    _parse_datetime,
    evaluate_current_holdings,
)
from .storage import DEFAULT_DB_PATH
from analysis.user_profile import DEFAULT_PROFILE_DB_PATH

# "현재" 컷오프와 미래 재생 구간 기본값
DEFAULT_CUTOFF = datetime(2026, 6, 23, 15, 30)  # 모델·아키텍처가 아는 마지막 시점
DEFAULT_START = datetime(2026, 6, 24, 9, 0)
DEFAULT_END = datetime(2026, 6, 26, 15, 30)

_LEVEL_ICON = {"high": "🔴", "critical": "🔴", "medium": "🟠", "low": "🟡"}


# ── 타임라인 ──────────────────────────────────────────────────────────────────
def _build_timeline(codes: Iterable[str], start: datetime, end: datetime) -> list[datetime]:
    """보유종목 1분봉 datetime 의 합집합을 [start, end] 로 잘라 정렬한 틱 스트림."""
    stamps: set[datetime] = set()
    for code in {c for c in codes if c}:
        df = load_min1(code)
        if df is None:
            continue
        dts = df["datetime"]
        mask = (dts >= pd.Timestamp(start)) & (dts <= pd.Timestamp(end))
        stamps.update(pd.Timestamp(x).to_pydatetime() for x in dts[mask].to_numpy())
    return sorted(stamps)


# ── 콘솔 포맷 ─────────────────────────────────────────────────────────────────
def _console_line(now: datetime, kind: str, alert: dict) -> str:
    tag = {"live": "C·손절실패", "resolved": "C·해소", "entry": "B·진입경고"}.get(kind, kind)
    icon = "✅" if kind == "resolved" else _LEVEL_ICON.get(
        str(alert.get("risk_level", "")).lower(), "⚠️")
    return (
        f"[{now:%Y-%m-%d %H:%M}] {icon} [{tag}] "
        f"{alert['user_id']} / {alert['name']}({alert['code']}) "
        f"{str(alert.get('problem_type',''))} "
        f"risk={str(alert.get('risk_level','')).upper()} "
        f"score={alert.get('risk_score')} — {alert.get('message','')}"
    )


# ── 재생기 ────────────────────────────────────────────────────────────────────
def simulate_realtime(
    xlsx_path: str,
    *,
    cutoff: datetime = DEFAULT_CUTOFF,
    start: datetime = DEFAULT_START,
    end: datetime = DEFAULT_END,
    confirm_ticks: int = 10,
    db_path: str = DEFAULT_DB_PATH,
    profile_db_path: str = DEFAULT_PROFILE_DB_PATH,
    out_path: Optional[str] = None,
    verbose: bool = True,
) -> list[dict]:
    """미래 구간을 분 단위로 재생하며 B·C 경고를 발화. 발화한 알림 리스트 반환.

    cutoff(=현재) 시점의 보유 위험 상태를 baseline 으로 먼저 확정하고,
    미래 구간에서는 baseline 대비 *변화*(신규 이탈·등급 상승·해소)만 발화한다.
    """
    mapping = load_name_to_code()

    # 0) "현재"(≤23일) 종결거래로 프로파일 백필 — 한 번만.
    if verbose:
        print(f"[setup] 프로파일 백필 (현재=2026-06-23 종가 기준)…")
    backfill_user_profiles(xlsx_path, db_path=db_path, profile_db_path=profile_db_path)

    holdings_by_user = load_current_holdings(xlsx_path)
    plans_by_user = load_investment_plans(xlsx_path)
    closed_by_user = load_closed_trades(xlsx_path)

    storage = PredictorStorage(db_path=db_path, profile_db_path=profile_db_path)
    profiles = {u: storage.load_user_profile(user_id=u) for u in holdings_by_user}

    # 보유종목 코드 → 타임라인 구성
    held = [
        CurrentHoldingInput.from_row(r)
        for rows in holdings_by_user.values()
        for r in rows
    ]
    held_codes = [h.code or mapping.get(h.name) for h in held]
    timeline = _build_timeline(held_codes, start, end)
    if verbose:
        print(f"[setup] 보유 {len(held)}건 · 틱 {len(timeline)}개 "
              f"({timeline[0]:%m-%d %H:%M} ~ {timeline[-1]:%m-%d %H:%M})"
              if timeline else "[setup] 타임라인 비어있음")

    # B 루프 준비: 사용자별 종결거래 사이클 + 예측기 (한 번만)
    user_predictors: dict[str, TradeRiskPredictor] = {}
    user_cycles: dict[str, list] = {}
    for user_id in plans_by_user:
        raw_trades, _ = _build_trade_rows(closed_by_user.get(user_id, []), mapping)
        user_cycles[user_id] = build_cycles(raw_trades)
        profile = profiles.get(user_id) or storage.load_user_profile(user_id=user_id)
        profiles[user_id] = profile
        user_predictors[user_id] = TradeRiskPredictor(
            storage=storage, profile=profile, notification_policy=NotificationPolicy(),
        )

    # 발화할 투자계획: (user_id, plan_row, entered_at, code)
    pending_plans = []
    for user_id, plan_rows in plans_by_user.items():
        for row in plan_rows:
            entered_at = _parse_demo_safe(row.get("예정일시"))
            code = mapping.get(str(row.get("종목명")))
            if entered_at is None or code is None:
                continue
            if start <= entered_at <= end:
                pending_plans.append([user_id, row, entered_at, code, False])

    emitted: list[dict] = []
    fp = open(out_path, "w", encoding="utf-8") if out_path else None
    # 확정 상태(committed): holding_id → (problem_type, risk_level) | None(경고없음)
    committed: dict[str, Optional[tuple]] = {}
    # 후보 상태(candidate): holding_id → (state, 연속틱수) — confirm_ticks 도달 시 확정
    candidate: dict[str, tuple] = {}

    # ── baseline: cutoff(=현재) 시점 보유 위험 상태를 확정(발화하지 않고 seed) ──
    base_provider = Min1HoldingMarketDataProvider(observed_at=cutoff, name_to_code=mapping)
    base_alerting = 0
    for user_id, rows in holdings_by_user.items():
        for res in evaluate_current_holdings(
            rows, profile=profiles.get(user_id),
            market_data_provider=base_provider, notification_policy=NotificationPolicy(),
        ):
            if res.signal.should_alert:
                committed[res.holding.holding_id] = (
                    res.signal.problem_type, res.signal.risk_level)
                base_alerting += 1
    if verbose:
        print(f"[baseline] 현재({cutoff:%Y-%m-%d %H:%M}) 이미 경고상태인 보유 {base_alerting}건 "
              f"— 미래 재생에서는 이 대비 {confirm_ticks}틱 지속된 변화만 발화\n")

    try:
        for now in timeline:
            # ── C 루프: 보유종목 손절 감시 ──
            provider = Min1HoldingMarketDataProvider(observed_at=now, name_to_code=mapping)
            for user_id, rows in holdings_by_user.items():
                results = evaluate_current_holdings(
                    rows, profile=profiles.get(user_id),
                    market_data_provider=provider, notification_policy=NotificationPolicy(),
                )
                for res in results:
                    sig = res.signal
                    hid = res.holding.holding_id
                    cur = (sig.problem_type, sig.risk_level) if sig.should_alert else None

                    if cur == committed.get(hid):
                        candidate.pop(hid, None)  # 변화 없음 → 후보 취소
                        continue
                    # 변화 후보 누적: 같은 후보가 confirm_ticks 연속 지속돼야 확정
                    cand = candidate.get(hid)
                    count = cand[1] + 1 if (cand and cand[0] == cur) else 1
                    candidate[hid] = (cur, count)
                    if count < confirm_ticks:
                        continue
                    committed[hid] = cur
                    candidate.pop(hid, None)
                    alert = _format_stop_loss_alert(user_id, res.holding.name, sig, profile_db_path)
                    if cur is None:
                        alert["message"] = f"{res.holding.name} 경고가 해소되었습니다(손절선 회복)."
                        _emit(alert, "resolved", now, emitted, fp, verbose)
                    else:
                        _emit(alert, "live", now, emitted, fp, verbose)

            # ── B 루프: 투자계획 사전경고 (예정시각 통과 시 1회) ──
            for plan in pending_plans:
                user_id, row, entered_at, code, fired = plan
                if fired or now < entered_at:
                    continue
                plan[4] = True
                predictor = user_predictors[user_id]
                context = _build_entry_context(
                    user_id=user_id, trade_id=str(row.get("계획ID")),
                    code=code, entered_at=entered_at,
                    closed_cycles=user_cycles[user_id],
                )
                sig = predictor.predict_entry_risk(context)
                if sig.should_alert:
                    alert = _format_entry_alert(
                        user_id, str(row.get("종목명")), row, sig, profile_db_path)
                    _emit(alert, "entry", now, emitted, fp, verbose)
    finally:
        storage.close()
        if fp:
            fp.close()

    if verbose:
        n_c = sum(1 for a in emitted if a["_kind"] == "live")
        n_r = sum(1 for a in emitted if a["_kind"] == "resolved")
        n_b = sum(1 for a in emitted if a["_kind"] == "entry")
        print(f"\n[done] 미래구간 변화 알림 {len(emitted)}건 "
              f"(C·신규손절 {n_c} / C·해소 {n_r} / B·진입 {n_b})"
              + (f" → {out_path}" if out_path else ""))
    return emitted


def _emit(alert: dict, kind: str, now: datetime, sink: list, fp, verbose: bool) -> None:
    record = {"sim_time": now.isoformat(timespec="minutes"), "_kind": kind, **alert}
    sink.append(record)
    if fp:
        fp.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    if verbose:
        print(_console_line(now, kind, alert))


def _parse_demo_safe(value) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return _parse_datetime(value)
    except (ValueError, TypeError):
        return None


def _parse_cli_dt(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(value)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="분 단위 실시간 재생기 (B·C 루프)")
    parser.add_argument("--xlsx", default="tests/fixtures/demo_users_all_data.final_3sheets.xlsx")
    parser.add_argument("--cutoff", default="2026-06-23 15:30", help="'현재' 컷오프 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--start", default="2026-06-24 09:00", help="재생 시작 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end", default="2026-06-26 15:30", help="재생 종료 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--confirm-ticks", type=int, default=10, help="변화 확정에 필요한 연속 틱(분) 수")
    parser.add_argument("--out", default="analysis/data/replay_alerts.jsonl", help="JSONL 알림 로그 경로")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--profile-db-path", default=DEFAULT_PROFILE_DB_PATH)
    parser.add_argument("--quiet", action="store_true", help="콘솔 스트림 끄기")
    args = parser.parse_args()

    simulate_realtime(
        args.xlsx,
        cutoff=_parse_cli_dt(args.cutoff),
        start=_parse_cli_dt(args.start),
        end=_parse_cli_dt(args.end),
        confirm_ticks=args.confirm_ticks,
        db_path=args.db_path,
        profile_db_path=args.profile_db_path,
        out_path=args.out,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
