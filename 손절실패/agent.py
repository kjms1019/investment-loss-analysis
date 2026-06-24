"""
손절실패 에이전트 — 진입점

더미 모드:
    from agent import analyze_all
    from data.dummy import TRANSACTIONS, OHLCV_DATA
    results = analyze_all(TRANSACTIONS, OHLCV_DATA)

실데이터 모드 (분봉 parquet 있을 때):
    from agent import analyze_real
    from data.dummy import TRANSACTIONS          # 거래내역은 아직 더미
    results = analyze_real(TRANSACTIONS)
"""
from pathlib import Path
from typing import Optional

from schema import Transaction, OHLCV
from cycles import build_cycles
from path_features import attach_path_features
from rules import compute_signals
from scoring import compute_score
from report import generate_report
from config import Config, DEFAULT_CONFIG
from data_loader import load_daily_ohlcv, load_minute_df, _DEFAULT_DATA_DIR


def _run_pipeline(cycles, all_ohlcv, user_stop_pct, config, minute_dfs: dict) -> list:
    results = []
    for cycle in cycles:
        minute_df = minute_dfs.get(cycle.ticker)
        cycle = attach_path_features(cycle, all_ohlcv, user_stop_pct, config, minute_df)
        signals = compute_signals(cycle, config)
        score = compute_score(cycle, signals, config)
        report = generate_report(cycle, signals, score, config)
        results.append(report)
    return results


def analyze_all(
    transactions: list,
    ohlcv: list,
    user_stop_pct: Optional[float] = None,
    config: Config = DEFAULT_CONFIG,
) -> list:
    """더미/테스트용 — 일봉 OHLCV 직접 전달, 분봉 없음."""
    cycles = build_cycles(transactions)
    return _run_pipeline(cycles, ohlcv, user_stop_pct, config, minute_dfs={})


def analyze_real(
    transactions: list,
    data_dir: Path = _DEFAULT_DATA_DIR,
    user_stop_pct: Optional[float] = None,
    config: Config = DEFAULT_CONFIG,
) -> list:
    """
    실데이터용 — parquet에서 일봉/분봉을 자동으로 불러와 엔진에 넣는다.
    거래내역에 등장하는 ticker만 로드한다.
    """
    cycles = build_cycles(transactions)
    tickers = {c.ticker for c in cycles}

    all_ohlcv: list = []
    minute_dfs: dict = {}
    for ticker in tickers:
        all_ohlcv.extend(load_daily_ohlcv(ticker, data_dir))
        mdf = load_minute_df(ticker, data_dir)
        if not mdf.empty:
            minute_dfs[ticker] = mdf

    return _run_pipeline(cycles, all_ohlcv, user_stop_pct, config, minute_dfs)
