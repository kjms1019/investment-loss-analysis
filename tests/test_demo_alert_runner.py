import hashlib
from datetime import datetime
from pathlib import Path

from common.schema import TradeCycle

from analysis.orchestrator.demo_alert_runner import (
    _build_entry_context,
    _build_trade_rows,
    backfill_user_profiles,
    check_entry_warnings,
    check_stop_loss_warnings,
)
from analysis.orchestrator.demo_workbook import load_closed_trades, load_investment_plans
from analysis.orchestrator.holding_predictor import HoldingMarketSnapshot

FIXTURE = str(Path(__file__).parent / "fixtures" / "demo_users_all_data.final_3sheets.xlsx")


def _fake_price_lookup(code: str, when: datetime) -> float:
    """결정론적 가짜 시세. 실제 min1 parquet 데이터에 의존하지 않는다."""
    seed = int(hashlib.sha256(f"{code}{when.isoformat()}".encode("utf-8")).hexdigest()[:6], 16)
    return 1000.0 + (seed % 500)


def _synthetic_name_to_code(xlsx_path: str) -> dict:
    """픽스처에 등장하는 모든 종목명에 합성 코드를 부여 (실 kospi_codes.csv 불필요).

    실제 종목코드는 6자리 숫자뿐이므로, 알파벳을 섞어 analysis/data/min1 의 진짜
    parquet 파일과 절대 겹치지 않게 한다 (겹치면 다른 종목의 실 시세/분류기 입력이
    뒤섞여 들어가 테스트가 실제 데이터에 암묵적으로 의존하게 됨).
    """
    names: set[str] = set()
    for loader in (load_closed_trades, load_investment_plans):
        for rows in loader(xlsx_path).values():
            for row in rows:
                names.add(str(row["종목명"]))
    return {name: f"ZZ{i:04d}" for i, name in enumerate(sorted(names), start=1)}


def test_build_trade_rows_pairs_buy_sell_and_skips_unmatched_code():
    rows = [
        {
            "거래ID": "T01", "종목명": "삼성전자",
            "매수일시": "2025-07-07 09:30:00", "매도일시": "2025-07-08 09:30:00", "수량": 10,
        },
        {
            "거래ID": "T02", "종목명": "없는종목",
            "매수일시": "2025-07-07 09:30:00", "매도일시": "2025-07-08 09:30:00", "수량": 5,
        },
    ]
    name_to_code = {"삼성전자": "005930"}

    def lookup(code, when):
        return 10000.0 if when.day == 7 else 9000.0

    raw_trades, skipped = _build_trade_rows(rows, name_to_code, price_lookup=lookup)

    assert [t.side for t in raw_trades] == ["BUY", "SELL"]
    assert raw_trades[0].price == 10000.0
    assert raw_trades[1].price == 9000.0
    assert len(skipped) == 1
    assert "없는종목" in skipped[0]


def test_build_entry_context_reflects_recent_loss_before_planned_entry():
    cycles = [
        TradeCycle(
            trade_id="c1", code="005930", name="삼성전자",
            entry_dt=datetime(2026, 6, 20, 9, 0), exit_dt=datetime(2026, 6, 23, 9, 0),
            entry_price=10000, exit_price=9000, qty=10,
            realized_pnl=-10000, realized_pnl_pct=-10.0,
        ),
    ]

    context = _build_entry_context(
        user_id="u1", trade_id="p1", code="000660",
        entered_at=datetime(2026, 6, 23, 9, 30), closed_cycles=cycles,
    )

    assert context.recent_trade_count == 1
    assert context.recent_win_rate == 0.0
    assert context.minutes_since_last_loss == 30.0
    assert context.last_loss_pct == -10.0
    assert context.same_day_trade_count == 0


def test_build_entry_context_ignores_cycles_not_yet_closed_at_entry_time():
    cycles = [
        TradeCycle(
            trade_id="c1", code="005930", name="삼성전자",
            entry_dt=datetime(2026, 6, 23, 9, 0), exit_dt=datetime(2026, 6, 24, 9, 0),
            entry_price=10000, exit_price=11000, qty=10,
            realized_pnl=10000, realized_pnl_pct=10.0,
        ),
    ]

    context = _build_entry_context(
        user_id="u1", trade_id="p1", code="000660",
        entered_at=datetime(2026, 6, 23, 9, 30), closed_cycles=cycles,
    )

    assert context.recent_trade_count == 0
    assert context.recent_win_rate is None
    assert context.minutes_since_last_loss is None


def test_run_demo_alerts_pipeline_wires_together_with_fake_market_data(tmp_path):
    db_path = str(tmp_path / "orchestrator.sqlite3")
    profile_db_path = str(tmp_path / "user_profiles.sqlite3")
    name_to_code = _synthetic_name_to_code(FIXTURE)

    backfilled = backfill_user_profiles(
        FIXTURE,
        db_path=db_path,
        profile_db_path=profile_db_path,
        name_to_code=name_to_code,
        price_lookup=_fake_price_lookup,
    )
    assert len(backfilled) == 10
    assert all(v["status"] == "ok" for v in backfilled.values())

    entry_alerts = check_entry_warnings(
        FIXTURE,
        datetime(2026, 6, 23, 0, 0, 0),
        db_path=db_path,
        profile_db_path=profile_db_path,
        name_to_code=name_to_code,
        price_lookup=_fake_price_lookup,
    )
    assert isinstance(entry_alerts, list)
    for alert in entry_alerts:
        assert alert["mode"] == "entry"
        assert alert["message"]

    def crash_provider(holding):
        return HoldingMarketSnapshot(
            entry_price=10000,
            current_price=9000,
            observed_at=datetime(2026, 6, 23, 15, 30),
            stop_loss_price=9500,
            highest_price_since_entry=10500,
            price_change_5m_pct=-3.0,
            volatility_30m_pct=4.0,
        )

    stop_loss_alerts = check_stop_loss_warnings(
        FIXTURE,
        datetime(2026, 6, 23, 15, 30),
        db_path=db_path,
        profile_db_path=profile_db_path,
        market_data_provider=crash_provider,
    )
    assert len(stop_loss_alerts) > 0
    for alert in stop_loss_alerts:
        assert alert["mode"] == "live"
        assert alert["problem_type"] == "stop_loss_failure"
        assert "stop_loss_breached" in alert["reasons"]
