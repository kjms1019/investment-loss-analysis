"""FastAPI 앱 — 화면별 엔드포인트.

실행:  uvicorn analysis.api.main:app --reload --port 8000

화면 ↔ 엔드포인트
  ① 업로드        POST /api/analyze            (데모: 사용자 백필 결과 반환)
  ③ 대시보드      GET  /api/dashboard/{user}
  ④ 거래별 설명   GET  /api/trades/{user}
  ⑤ 내 성향       GET  /api/profile/{user}
  ⑥ 실시간 알림   GET  /api/alerts/{user}
  공통            GET  /api/users
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

# analysis/ 를 import 경로에 (common.* 모듈용)
_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analysis.report import builder
from analysis.report.schema import LossReportItem, LossReportSummary
from analysis.user_profile import UserProfileStorage

app = FastAPI(title="왜 잃었지? API", version="0.1.0")

# 프론트(Next dev) CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIXTURE = _ANALYSIS_DIR.parent / "tests" / "fixtures" / "demo_users_all_data.final_3sheets.xlsx"
_PROFILE_DB = "analysis/data/user_profiles.sqlite3"

# 도메인(에이전트) → UI 표기
DOMAIN = {
    "stop_loss_failure": {"id": "cut", "name": "손절실패", "def": "끊었어야 할 때 못 끊었다",
                           "psych": "처분효과", "color": "#0B2E59", "tint": "#E7ECF4"},
    "entry_error": {"id": "entry", "name": "진입오류", "def": "이 때부터 잘못 샀다",
                    "psych": "리벤지", "color": "#F0890C", "tint": "#FEF1DF"},
}
_SEV_ORDER = {"strong": 3, "moderate": 2, "weak": 1, None: 0}


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _code_to_name() -> dict:
    """종목코드 → 종목명 (report item 의 빈 name 보강용)."""
    try:
        from analysis.common.min1_lookup import load_name_to_code
        return {v: k for k, v in load_name_to_code().items()}
    except Exception:
        return {}


def _domain_of(agent_id: str) -> Optional[dict]:
    return DOMAIN.get(agent_id)


def _domain_name(dom_id: str) -> str:
    """도메인 id('entry'|'cut') → 한글 표기."""
    return {"cut": DOMAIN["stop_loss_failure"]["name"],
            "entry": DOMAIN["entry_error"]["name"]}.get(dom_id, dom_id)


@lru_cache(maxsize=1)
def _loss_by_trade() -> dict:
    """trade_id → 실현 손실금(원, 절대값). normalized_trades 의 price·qty·pct 로 계산.

    realized_pnl = entry_price * qty * (pct/100) 이므로 손절/진입 총손실금 집계에 쓴다.
    """
    import json as _json
    import sqlite3
    out: dict[str, float] = {}
    try:
        conn = sqlite3.connect("analysis/data/orchestrator.sqlite3")
        for tid, price, qty, payload in conn.execute(
            "select trade_id, price, qty, raw_payload_json from normalized_trades"
        ):
            pct = (_json.loads(payload or "{}") or {}).get("realized_pnl_pct")
            if price and qty and pct is not None:
                out[tid] = abs(float(price) * float(qty) * float(pct) / 100.0)
        conn.close()
    except Exception:  # noqa: BLE001
        pass
    return out


def _interaction_dto(summ: LossReportSummary) -> dict:
    """analysis/orchestrator/interaction.py 의 빈도·총손실금 판단을 리포트에서 재현.

    각 손실거래를 도메인(진입오류/손절실패)별로 빈도 count + 손실금 합을 내고,
    빈도 winner 와 금액 winner 가 같으면 선택 없이 자동 진행, 다르면 선택지를 준다.
    """
    loss = _loss_by_trade()
    stat = {"cut": {"count": 0, "amount": 0.0}, "entry": {"count": 0, "amount": 0.0}}
    for it in summ.items:
        dom = _domain_of(it.agent_id)
        if not dom:
            continue
        stat[dom["id"]]["count"] += 1
        stat[dom["id"]]["amount"] += loss.get(it.trade_id, 0.0)

    order = ["entry", "cut"]  # 동점 시 우선순위(진입오류 우선 — interaction.py 와 동일 인덱스 규칙)
    freq_winner = max(order, key=lambda k: (stat[k]["count"], stat[k]["amount"]))
    amt_winner = max(order, key=lambda k: (stat[k]["amount"], stat[k]["count"]))
    agree = freq_winner == amt_winner
    nm = {"cut": DOMAIN["stop_loss_failure"]["name"], "entry": DOMAIN["entry_error"]["name"]}

    def opt(basis: str, label: str, dom_id: str) -> dict:
        return {"basis": basis, "label": label, "type": dom_id, "name": nm[dom_id],
                "count": stat[dom_id]["count"], "amount": round(stat[dom_id]["amount"])}

    if agree:
        message = f"빈도와 총손실금 모두 ‘{nm[freq_winner]}’이 가장 큽니다. 이 문제부터 함께 볼게요."
    else:
        message = (f"가장 자주 반복된 문제는 ‘{nm[freq_winner]}’이고, "
                   f"손실 금액이 가장 컸던 문제는 ‘{nm[amt_winner]}’입니다. 어떤 걸 먼저 볼까요?")

    return {
        "stats": {k: {"count": v["count"], "amount": round(v["amount"])} for k, v in stat.items()},
        "frequency_winner": freq_winner,
        "amount_winner": amt_winner,
        "question_required": not agree,
        "message": message,
        "auto_selected": freq_winner if agree else None,
        "options": [opt("frequency", "자주 반복된 문제", freq_winner),
                    opt("amount", "손실 금액이 컸던 문제", amt_winner)] if not agree else [],
    }


def _resolve_choice(choice: str, interaction: dict) -> Optional[str]:
    """사용자 선택을 도메인 id('entry'|'cut')로 정규화.

    choice 는 도메인 id 그대로('entry'|'cut')이거나 선택 근거('frequency'|'amount').
    근거면 interaction 의 해당 winner 로 환원한다. 알 수 없으면 None.
    """
    choice = (choice or "").strip().lower()
    if choice in ("entry", "cut"):
        return choice
    if choice in ("frequency", "freq"):
        return interaction.get("frequency_winner")
    if choice in ("amount", "amt"):
        return interaction.get("amount_winner")
    return None


def _next_round(stats: dict, completed: list[str]) -> Optional[dict]:
    """아직 안 본 도메인이 남아 있으면 다음 라운드 제안, 없으면 None.

    stats: _interaction_dto()['stats'] (도메인별 count/amount).
    completed: 이미 본 도메인 id 리스트.
    """
    nm = {"cut": DOMAIN["stop_loss_failure"]["name"], "entry": DOMAIN["entry_error"]["name"]}
    remaining = [k for k in ("entry", "cut") if k not in completed and stats.get(k, {}).get("count", 0) > 0]
    if not remaining:
        return None
    nxt = remaining[0]
    return {
        "type": nxt,
        "name": nm[nxt],
        "count": stats[nxt]["count"],
        "amount": stats[nxt]["amount"],
        "prompt": f"{nm[nxt]} 분석도 이어서 확인해볼까요?",
    }


# ── 매퍼: report item → UI trade ─────────────────────────────────────────────
def _trade_dto(it: LossReportItem) -> dict:
    dom = _domain_of(it.agent_id) or DOMAIN["entry_error"]
    ev_feats = {e.get("feature"): e.get("value") for e in (it.evidence or []) if isinstance(e, dict)}
    name = it.name or _code_to_name().get(it.code, it.code)
    return {
        "trade_id": it.trade_id,
        "code": it.code,
        "name": name,
        "date": (it.executed_at or "")[:10],
        "loss": round(_loss_by_trade().get(it.trade_id, 0.0)),
        "type": dom["id"],                       # 'entry' | 'cut'
        "typeName": dom["name"],
        "sev": it.severity or "weak",
        "label": it.label,
        "desc": it.narrative or "",
        "evidence": [e.get("feature") if isinstance(e, dict) else str(e) for e in (it.evidence or [])],
        # 분류기 라우팅 점수 (합 1)
        "eScore": round(it.classifier_entry_score, 2) if it.classifier_entry_score is not None else None,
        "cScore": round(it.classifier_stop_score, 2) if it.classifier_stop_score is not None else None,
        "route": it.route_type,
        "conf": round(it.routing_confidence, 2) if it.routing_confidence is not None else None,
        "score": it.score,
        # 손절실패 신호 (가중합 입력) — evidence 의 *_score
        "signals": {
            "확대": ev_feats.get("expansion_score"),
            "지연": ev_feats.get("delay_score"),
            "물타기": ev_feats.get("avg_down_score"),
        } if dom["id"] == "cut" else None,
    }


# ── 매퍼: summary → 대시보드 ─────────────────────────────────────────────────
def _dashboard_dto(summ: LossReportSummary) -> dict:
    counts = {"cut": summ.count_by_agent.get("stop_loss_failure", 0),
              "entry": summ.count_by_agent.get("entry_error", 0)}
    interaction = _interaction_dto(summ)

    type_cards = []
    for key, agent in (("cut", "stop_loss_failure"), ("entry", "entry_error")):
        d = DOMAIN[agent]
        type_cards.append({"id": key, "name": d["name"], "def": d["def"], "count": counts[key],
                           "amount": interaction["stats"][key]["amount"],
                           "color": d["color"], "tint": d["tint"], "psychLabel": d["psych"] + " 흡수"})

    # 1순위: 빈도+금액 종합 winner (interaction 의 빈도 winner 기준)
    win = interaction["frequency_winner"]
    dominant = DOMAIN["stop_loss_failure" if win == "cut" else "entry_error"]

    return {
        "user_id": summ.scope_id,
        "total_loss_trades": summ.total_loss_trades,
        "counts": counts,
        "avg_score": summ.avg_score,
        "dominant": {"id": dominant["id"], "name": dominant["name"], "count": counts[dominant["id"]]},
        "typeCards": type_cards,
        "dist": [
            {"id": "cut", **{k: DOMAIN["stop_loss_failure"][k] for k in ("name", "color", "psych")},
             "count": counts["cut"], "amount": interaction["stats"]["cut"]["amount"]},
            {"id": "entry", **{k: DOMAIN["entry_error"][k] for k in ("name", "color", "psych")},
             "count": counts["entry"], "amount": interaction["stats"]["entry"]["amount"]},
        ],
        "interaction": interaction,
    }


# ── 매퍼: patterns → 성향 ────────────────────────────────────────────────────
def _pattern_dto(p: dict) -> dict:
    dom = _domain_of(p.get("domain", "")) or DOMAIN["entry_error"]
    return {
        "type": dom["id"], "typeName": dom["name"], "color": dom["color"], "tint": dom["tint"],
        "title": p.get("name_ko") or p.get("pattern_id"),
        "stat": f"{p.get('count', 0)}건",
        "tag": dom["psych"],
        "example": p.get("representative_trade", ""),
        "correction": p.get("correction", ""),
    }


# ── 전체 거래(이익+손실) 차트용 ─────────────────────────────────────────────
@lru_cache(maxsize=1)
def _fixture_trades_by_user() -> dict:
    """데모 픽스처(종결거래 시트) → {user_id: [거래…]}. 사용자당 10거래(이익+손실)."""
    import pandas as pd
    out: dict[str, list] = {}
    try:
        df = pd.ExcelFile(_FIXTURE).parse("종결거래")
        for _, r in df.iterrows():
            out.setdefault(str(r["사용자명"]), []).append({
                "name": str(r["종목명"]),
                "buy": pd.to_datetime(r["매수일시"]).to_pydatetime(),
                "sell": pd.to_datetime(r["매도일시"]).to_pydatetime(),
                "qty": float(r["수량"]),
            })
    except Exception:  # noqa: BLE001
        pass
    return out


def _all_trades_dto(user_id: str) -> dict:
    """사용자의 전체 거래 10건을 min1 시세로 pnl 계산하고, 손실엔 라우팅 도메인을 붙인다.

    type: 'entry'|'cut' = 손실선별·라우팅된 '본인 탓' 손실, None = 이익·비선별 거래.
    """
    from analysis.common.min1_lookup import load_name_to_code, load_min1, price_at

    rows = _fixture_trades_by_user().get(user_id, [])
    n2c = load_name_to_code()

    # (종목코드, 매수시각[:16]) → 도메인 id. 리포트의 손실거래에만 존재.
    summ = builder.build_user_summary(user_id, llm=False)
    dom_by_key: dict = {}
    for it in summ.items:
        dom = _domain_of(it.agent_id)
        if dom:
            dom_by_key[(it.code, (it.executed_at or "")[:16])] = dom["id"]

    trades = []
    for r in rows:
        code = n2c.get(r["name"])
        m = load_min1(code)
        ep = price_at(m, r["buy"]) if m is not None else None
        xp = price_at(m, r["sell"]) if m is not None else None
        if ep is None or xp is None:
            continue
        pnl = round((xp - ep) * r["qty"])
        typ = dom_by_key.get((code, r["buy"].isoformat()[:16]))
        trades.append({"code": code, "name": r["name"],
                       "date": r["buy"].isoformat()[:10], "pnl": pnl, "type": typ})
    return {"user_id": user_id, "count": len(trades), "trades": trades}


# ── 엔드포인트 ───────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/users")
def users() -> list[dict]:
    st = UserProfileStorage(db_path=_PROFILE_DB)
    try:
        rows = st.conn.execute("select distinct user_id from user_profiles order by user_id").fetchall()
    finally:
        st.close()
    return [{"id": r[0], "name": r[0]} for r in rows]


@app.get("/api/dashboard/{user_id}")
def dashboard(user_id: str) -> dict:
    summ = builder.build_user_summary(user_id)
    if summ.total_loss_trades == 0:
        raise HTTPException(404, f"'{user_id}' 분석 결과 없음")
    return _dashboard_dto(summ)


@app.get("/api/trades/{user_id}")
def trades(user_id: str) -> dict:
    summ = builder.build_user_summary(user_id, llm=False)
    items = sorted(summ.items, key=lambda i: (_SEV_ORDER.get(i.severity, 0), i.score or 0), reverse=True)
    return {"user_id": user_id, "count": len(items), "trades": [_trade_dto(i) for i in items]}


@app.get("/api/all-trades/{user_id}")
def all_trades(user_id: str) -> dict:
    """분석 차트용 — 이익 포함 전체 거래(사용자당 10건). 손실엔 라우팅 도메인 부착."""
    return _all_trades_dto(user_id)


@app.get("/api/interaction/{user_id}/select")
def interaction_select(user_id: str, choice: str, completed: str = "") -> dict:
    """사용자가 고른 문제 도메인으로 포커스 + 다음 라운드 제안.

    상호작용 플로우의 '응답 → 다음 라운드' 연결. 분석은 이미 끝나 있으므로
    (모든 손실거래가 라우팅·저장됨) 선택은 재분석이 아니라 '관점 포커스'다.

    query:
      choice    = 'entry' | 'cut' | 'frequency' | 'amount'
      completed = 이미 본 도메인 id CSV (멀티라운드 추적, 예: "entry")
    """
    summ = builder.build_user_summary(user_id, llm=False)
    if summ.total_loss_trades == 0:
        raise HTTPException(404, f"'{user_id}' 분석 결과 없음")

    interaction = _interaction_dto(summ)
    sel = _resolve_choice(choice, interaction)
    if sel is None:
        raise HTTPException(400, f"choice 는 entry|cut|frequency|amount 중 하나여야 합니다: {choice!r}")

    done = [c for c in (completed.split(",") if completed else []) if c in ("entry", "cut")]
    if sel not in done:
        done.append(sel)

    focus = sorted(
        [it for it in summ.items if (_domain_of(it.agent_id) or {}).get("id") == sel],
        key=lambda i: (_SEV_ORDER.get(i.severity, 0), i.score or 0),
        reverse=True,
    )
    stats = interaction["stats"]
    return {
        "user_id": user_id,
        "selected": {"type": sel, "name": _domain_name(sel), **stats.get(sel, {})},
        "trades": [_trade_dto(i) for i in focus],
        "completed": done,
        "next_round": _next_round(stats, done),
    }


@app.get("/api/profile/{user_id}")
def profile(user_id: str) -> dict:
    st = UserProfileStorage(db_path=_PROFILE_DB)
    try:
        pats = st.load_patterns(user_id)
    finally:
        st.close()
    return {"user_id": user_id, "patterns": [_pattern_dto(p) for p in pats]}


@lru_cache(maxsize=1)
def _all_alerts() -> dict:
    """데모 fixture 의 B(진입)·C(손절) 알림을 전 사용자 1회 계산해 캐시.

    매 요청마다 재평가하면 수십 초 걸리므로(분봉 전수 평가) 프로세스 캐시한다.
    """
    from datetime import datetime
    from analysis.orchestrator.demo_alert_runner import check_entry_warnings, check_stop_loss_warnings

    xlsx = str(_FIXTURE)
    by_user: dict[str, list] = {}
    for a in check_stop_loss_warnings(xlsx, datetime(2026, 6, 25, 11, 0)):
        by_user.setdefault(a.get("user_id"), []).append(
            {"kind": "보유 점검", "type": "cut", **_alert_common(a)})
    for a in check_entry_warnings(xlsx, datetime(2026, 6, 24, 0, 0)):
        by_user.setdefault(a.get("user_id"), []).append(
            {"kind": "매수 시점", "type": "entry", **_alert_common(a)})
    return by_user


@app.get("/api/alerts/{user_id}")
def alerts(user_id: str) -> dict:
    """실시간 알림(B 진입 + C 손절) — 데모 fixture 를 미래 시점으로 평가(캐시)."""
    return {"user_id": user_id, "alerts": _all_alerts().get(user_id, [])}


def _alert_common(a: dict) -> dict:
    score = a.get("risk_score") or 0.0
    return {
        "title": (a.get("message") or "")[:80] or f"{a.get('name')} 위험 신호",
        "body": a.get("message", ""),
        "name": a.get("name"),
        "code": a.get("code"),
        "risk": round(float(score) * 100),
        "level": a.get("risk_level"),
        "reasons": a.get("reasons", []),
        "basis": a.get("evidence") or "",
    }


@app.post("/api/analyze")
def analyze() -> dict:
    """① 업로드/분석 — 데모에선 백필이 이미 끝나 있어 사용자 목록만 반환.

    TODO(백엔드 갭): 실제 CSV 업로드 → run_pipeline 트리거 → run_id 반환.
    """
    return {"status": "demo_backfilled", "users": [u["id"] for u in users()]}
