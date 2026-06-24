"""총괄 오케스트레이션 파이프라인.

흐름:
  CSV → RawTrade → TradeCycle(사이클 묶기)
  → 손실 필터링
  → 심리 귀속(psych focus)
  → 사이클별 라우팅
  → 에이전트 실행
  → AgentResult 저장 + 반환
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

# 프로젝트 루트 sys.path 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ANALYSIS_DIR = _PROJECT_ROOT / "analysis"
for _p in [str(_PROJECT_ROOT), str(_ANALYSIS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.parser import build_cycles, filter_loss_cycles, parse_csv
from common.schema import RawTrade, TradeCycle

from .agent_registry import AgentRegistry, build_default_registry
from .router import CycleRouteDecision, route_cycle
from .schema import AgentResult, OrchestratorRunResult
from .storage import DEFAULT_DB_PATH, OrchestratorStorage


def _compute_loss_early_ratio(cycle: TradeCycle, raw_trades: List[RawTrade]) -> Optional[float]:
    """보유 초반 20% 구간에서 발생한 손실 비율 계산 (분봉 없을 때 근사치).

    체결 데이터만으로 근사: 진입 직후 첫 체결가 대비 하락폭 비율.
    """
    if not cycle.entry_dt or not cycle.exit_dt:
        return None

    total_duration = (cycle.exit_dt - cycle.entry_dt).total_seconds()
    if total_duration <= 0:
        return None

    cutoff = cycle.entry_dt.timestamp() + total_duration * 0.2
    early_trades = [
        t for t in raw_trades
        if t.code == cycle.code
        and cycle.entry_dt.timestamp() <= t.datetime.timestamp() <= cutoff
    ]
    if not early_trades or cycle.realized_pnl >= 0:
        return None

    early_prices = [t.price for t in early_trades]
    early_low    = min(early_prices)
    entry_price  = cycle.entry_price
    early_loss   = (entry_price - early_low) / entry_price if entry_price > 0 else 0
    total_loss   = abs(cycle.realized_pnl_pct) / 100

    return round(early_loss / total_loss, 4) if total_loss > 0 else None


def _get_psych_dominant(cycle: TradeCycle, psych_attribution: dict) -> Optional[str]:
    """psych focus 결과에서 사이클의 dominant 심리 유형 추출."""
    key = f"{cycle.code}_{cycle.entry_dt.strftime('%Y%m%d%H%M%S') if cycle.entry_dt else ''}"
    attribution = psych_attribution.get(key)
    if attribution is None:
        return None
    return attribution.get("dominant")


def run_pipeline(
    trade_csv_path: str,
    broker: str = "generic",
    db_path: str = DEFAULT_DB_PATH,
    registry: Optional[AgentRegistry] = None,
) -> OrchestratorRunResult:
    """CSV 한 파일을 받아 전체 파이프라인을 실행하고 결과를 반환."""

    registry = registry or build_default_registry()
    run_id   = str(uuid.uuid4())
    storage  = OrchestratorStorage(db_path=db_path)

    agent_results: List[AgentResult] = []
    notes: List[str] = []

    try:
        # 1. CSV 파싱
        raw_trades = parse_csv(trade_csv_path, broker=broker)
        cycles     = build_cycles(raw_trades)
        loss_cycles = filter_loss_cycles(cycles)
        notes.append(f"전체 {len(cycles)}사이클, 손실 {len(loss_cycles)}사이클 대상")

        # 2. 심리 귀속 (계좌 전체 맥락)
        psych_attribution: Dict[str, dict] = {}
        try:
            import pandas as pd
            from psych_agent.preprocess import preprocess, trades_from_df
            from psych_agent.focus import attribute_losses, cycle_id
            from psych_agent.config import Config
            from psych_agent.prices import PriceLookup

            df = pd.DataFrame([{
                "datetime": t.datetime, "code": t.code,
                "name": t.name, "side": t.side, "qty": t.qty, "price": t.price,
            } for t in raw_trades])
            df["datetime"] = pd.to_datetime(df["datetime"])

            config = Config()
            pre    = preprocess(trades_from_df(df), config)
            cyc_by_id = {
                cycle_id(c.code, c.entry_time): c for c in pre.closed_cycles
            }
            focus_cycles_psych = [
                cyc_by_id[cycle_id(c.code, c.entry_dt)]
                for c in loss_cycles
                if c.entry_dt and cycle_id(c.code, c.entry_dt) in cyc_by_id
            ]
            attributions = attribute_losses(pre, focus_cycles_psych, config)
            for a in attributions:
                key = f"{a.code}_{a.entry_time.replace('-', '').replace(':', '').replace(' ', '')[:14]}"
                psych_attribution[key] = {"dominant": a.dominant}
        except Exception as e:
            notes.append(f"심리 귀속 스킵 (psych 데이터 없음): {e}")

        # 3. 사이클별 라우팅 → 에이전트 실행
        batch_id = str(uuid.uuid4())
        storage.create_batch(
            batch_id=batch_id,
            source_name="user_csv",
            raw_file_path=trade_csv_path,
            row_count=len(raw_trades),
        )
        storage.create_run(run_id=run_id, batch_id=batch_id)

        for cycle in loss_cycles:
            trade_id = cycle.trade_id

            psych_dom    = _get_psych_dominant(cycle, psych_attribution)
            early_ratio  = _compute_loss_early_ratio(cycle, raw_trades)

            # 영현 에이전트 stop_fail 신호 (간단 규칙으로 근사)
            breached   = cycle.realized_pnl_pct < -5.0   # -5% 이하를 손절선 이탈로 근사
            delay_days = 0                                # 분봉 없으면 0 (실제 연동 시 교체)

            decision: CycleRouteDecision = route_cycle(
                trade_id,
                psych_dominant=psych_dom,
                breached=breached,
                delay_days=delay_days,
                loss_early_ratio=early_ratio,
            )

            adapter = registry.get(decision.agent_id)
            if adapter is None:
                continue

            cycle_data = {
                "trade_id":      trade_id,
                "code":          cycle.code,
                "name":          cycle.name,
                "entry_dt":      cycle.entry_dt.isoformat() if cycle.entry_dt else None,
                "exit_dt":       cycle.exit_dt.isoformat()  if cycle.exit_dt  else None,
                "entry_price":   cycle.entry_price,
                "exit_price":    cycle.exit_price,
                "qty":           cycle.qty,
                "realized_pnl":  cycle.realized_pnl,
                "realized_pnl_pct": cycle.realized_pnl_pct,
                "trades": [{
                    "datetime": t.datetime.isoformat(),
                    "code": t.code, "name": t.name,
                    "side": t.side, "qty": t.qty, "price": t.price,
                } for t in raw_trades if t.code == cycle.code],
            }

            result = adapter.run(run_id=run_id, trade_id=trade_id, cycle_data=cycle_data)
            result.route_reason = decision.reason
            storage.insert_agent_result(result)
            agent_results.append(result)

        storage.complete_run(run_id=run_id, status="completed")
        status = "completed"

    except Exception:
        storage.complete_run(run_id=run_id, status="failed")
        raise
    finally:
        storage.close()

    return OrchestratorRunResult(
        run_id=run_id,
        batch_id=batch_id,
        status=status,
        normalized_count=len(loss_cycles),
        agent_results=agent_results,
        notes=notes,
    )
