"""UI 전용 거래별 차트 DB 빌더.

※ 이 DB(analysis/data/ui_trade_charts.sqlite3)는 **데모 화면 구현 전용**이다.
   분석 아키텍처(오케스트레이터/에이전트/리포트)에는 필요 없으며, 거래별 탭 카드에
   "그 당시 실제 가격 차트 + 피쳐 위치 마커"를 그려 넣기 위한 보조 캐시일 뿐이다.

입력
  - analysis/data/orchestrator.sqlite3  : normalized_trades(거래 사이클) + agent_results(도메인·신호)
  - analysis/data/min1/<code>.parquet   : 종목별 1분봉(OHLCV)

출력
  - analysis/data/ui_trade_charts.sqlite3
      trade_charts(trade_id PK, code, name, agent_id, payload_json)
      payload_json = {
        series: [{t, c}],          # 보유구간(+여유) 종가 라인, 다운샘플
        entry:  {i, t, price},     # 진입 마커
        exit:   {i, t, price},     # 청산 마커
        stop:   price | null,      # 손절선(손절실패만)
        breach: {i, t} | null,     # 손절선 첫 돌파 시점(손절실패만)
        mae:    {i, t, price} | null,  # 최대낙폭 지점
        lo, hi,                    # y축 스케일용 최저/최고가
        pnl_pct, label             # 보조 라벨
      }

실행
  python -m analysis.ui.build_trade_charts
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

from analysis.common.paths import MIN1_DIR

ORCH_DB = "analysis/data/orchestrator.sqlite3"
OUT_DB = "analysis/data/ui_trade_charts.sqlite3"
MAX_POINTS = 80  # 카드 미니차트용 다운샘플 목표 점 개수


def _load_trades(conn: sqlite3.Connection) -> list[dict]:
    """손실 거래 사이클 + 채택 도메인/신호를 합친다."""
    # trade_id -> (agent_id, result_json)  (채택 결과 1건)
    ar: dict[str, tuple[str, dict]] = {}
    for tid, aid, rj in conn.execute(
        "select trade_id, agent_id, result_json from agent_results"
    ):
        try:
            res = json.loads(rj or "{}")
        except Exception:
            res = {}
        # 동일 trade 에 여러 결과가 있으면 라우팅 채택(primary) 우선
        dec = res.get("orchestrator_decision") or {}
        is_primary = dec.get("primary_agent") == aid
        if tid not in ar or is_primary:
            ar[tid] = (aid, res)

    out: list[dict] = []
    for tid, code, name, executed_at, qty, price, payload in conn.execute(
        "select trade_id, code, name, executed_at, qty, price, raw_payload_json "
        "from normalized_trades"
    ):
        p = json.loads(payload or "{}")
        agent_id, res = ar.get(tid, ("", {}))
        # 진입(BUY 체결)은 normalized_trades 컬럼(executed_at·price)에 있고,
        # payload 에는 청산(exit_dt)·실현손익만 담긴다.
        out.append({
            "trade_id": tid, "code": code, "name": name,
            "entry_dt": p.get("entry_dt") or executed_at, "exit_dt": p.get("exit_dt"),
            "entry_price": p.get("entry_price") or price, "exit_price": p.get("exit_price"),
            "pnl_pct": p.get("realized_pnl_pct"),
            "agent_id": agent_id,
            "signals": (res.get("signals") or {}),
            "label": res.get("label", ""),
        })
    return out


def _downsample(df: pd.DataFrame, max_points: int) -> pd.DataFrame:
    """행을 균등 간격으로 솎아 max_points 이하로 만든다(첫·끝 보존)."""
    n = len(df)
    if n <= max_points:
        return df.reset_index(drop=True)
    step = n / max_points
    idx = sorted({int(i * step) for i in range(max_points)} | {0, n - 1})
    return df.iloc[idx].reset_index(drop=True)


def _nearest_i(series_t: list[str], target: datetime) -> int:
    """series 의 t(iso) 중 target 에 가장 가까운 인덱스."""
    best_i, best_d = 0, None
    for i, t in enumerate(series_t):
        d = abs((datetime.fromisoformat(t) - target).total_seconds())
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i


def _build_one(tr: dict) -> dict | None:
    code = tr["code"]
    if not tr["entry_dt"] or not tr["exit_dt"]:
        return None
    fp = Path(MIN1_DIR) / f"{code}.parquet"
    if not fp.exists():
        return None

    entry_dt = datetime.fromisoformat(tr["entry_dt"])
    exit_dt = datetime.fromisoformat(tr["exit_dt"])
    span = exit_dt - entry_dt
    # 진입 전 맥락(피쳐가 진입 '직전'에서 나타나므로)과 청산 뒤 약간의 여유를 둔다.
    pad_before = max(span * 0.15, timedelta(days=1))
    pad_after = max(span * 0.05, timedelta(hours=2))
    lo_t, hi_t = entry_dt - pad_before, exit_dt + pad_after

    df = pd.read_parquet(fp, columns=["datetime", "close"])
    df = df[(df["datetime"] >= lo_t) & (df["datetime"] <= hi_t)]
    if len(df) < 2:
        return None
    df = _downsample(df.sort_values("datetime"), MAX_POINTS)

    series = [{"t": t.isoformat(), "c": int(c)} for t, c in zip(df["datetime"], df["close"])]
    series_t = [s["t"] for s in series]
    closes = [s["c"] for s in series]

    ei = _nearest_i(series_t, entry_dt)
    xi = _nearest_i(series_t, exit_dt)
    entry_price = int(tr["entry_price"] or closes[ei])
    exit_price = int(tr["exit_price"] or closes[xi])

    sig = tr["signals"]
    payload: dict = {
        "series": series,
        "entry": {"i": ei, "t": series_t[ei], "price": entry_price},
        "exit": {"i": xi, "t": series_t[xi], "price": exit_price},
        "stop": None, "breach": None, "mae": None,
        "lo": min(closes), "hi": max(closes),
        "pnl_pct": tr["pnl_pct"], "label": tr["label"],
    }

    # 손절실패: 손절선 + 돌파 시점 + 최대낙폭
    if tr["agent_id"] == "stop_loss_failure":
        stop_pct = sig.get("stop_pct")
        if stop_pct is not None:
            payload["stop"] = round(entry_price * (1 + stop_pct / 100.0))
        bd = sig.get("breach_date")
        if bd:
            try:
                bi = _nearest_i(series_t, datetime.fromisoformat(bd))
                payload["breach"] = {"i": bi, "t": series_t[bi]}
            except Exception:
                pass
        # 최대낙폭 = 보유구간 종가 최저점
        seg = closes[ei:xi + 1] or closes
        mi = ei + seg.index(min(seg))
        payload["mae"] = {"i": mi, "t": series_t[mi], "price": closes[mi]}

    return payload


def build(out_db: str = OUT_DB) -> int:
    src = sqlite3.connect(ORCH_DB)
    trades = _load_trades(src)
    src.close()

    out = sqlite3.connect(out_db)
    out.execute("""
        CREATE TABLE IF NOT EXISTS trade_charts (
            trade_id TEXT PRIMARY KEY,
            code TEXT, name TEXT, agent_id TEXT,
            payload_json TEXT
        )
    """)
    out.execute("DELETE FROM trade_charts")

    n_ok = 0
    for tr in trades:
        payload = _build_one(tr)
        if payload is None:
            continue
        out.execute(
            "INSERT OR REPLACE INTO trade_charts VALUES (?,?,?,?,?)",
            (tr["trade_id"], tr["code"], tr["name"], tr["agent_id"],
             json.dumps(payload, ensure_ascii=False)),
        )
        n_ok += 1
    out.commit()
    out.close()
    return n_ok


if __name__ == "__main__":
    n = build()
    print(f"trade_charts 빌드 완료: {n}건 → {OUT_DB}")
