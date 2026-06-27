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
    # 도메인별 평균 손실(=score 대용; α 정확분해는 추후) — 거래별 score 평균
    by_dom_scores: dict[str, list] = {"cut": [], "entry": []}
    for it in summ.items:
        dom = _domain_of(it.agent_id)
        if dom and it.score is not None:
            by_dom_scores[dom["id"]].append(it.score)
    avg = {k: (sum(v) / len(v) if v else 0.0) for k, v in by_dom_scores.items()}

    type_cards = []
    for key, agent in (("cut", "stop_loss_failure"), ("entry", "entry_error")):
        d = DOMAIN[agent]
        type_cards.append({"id": key, "name": d["name"], "def": d["def"], "count": counts[key],
                           "color": d["color"], "tint": d["tint"], "psychLabel": d["psych"] + " 흡수"})

    # focus 옵션: 빈도 최다 / (평균점수=심각도) 최대
    freq_dom = "cut" if counts["cut"] >= counts["entry"] else "entry"
    amount_dom = "cut" if avg["cut"] >= avg["entry"] else "entry"
    dominant = DOMAIN["stop_loss_failure"] if freq_dom == "cut" else DOMAIN["entry_error"]

    return {
        "user_id": summ.scope_id,
        "total_loss_trades": summ.total_loss_trades,
        "counts": counts,
        "avg_score": summ.avg_score,
        "dominant": {"id": dominant["id"], "name": dominant["name"], "count": counts[dominant["id"]]},
        "typeCards": type_cards,
        "dist": [
            {"id": "cut", **{k: DOMAIN["stop_loss_failure"][k] for k in ("name", "color", "psych")},
             "count": counts["cut"]},
            {"id": "entry", **{k: DOMAIN["entry_error"][k] for k in ("name", "color", "psych")},
             "count": counts["entry"]},
        ],
        "focus": {
            "byFreq": {"type": freq_dom, "name": DOMAIN["stop_loss_failure" if freq_dom == "cut" else "entry_error"]["name"],
                       "stat": f"{counts[freq_dom]}건 반복", "reasonLabel": "가장 자주 반복"},
            "byAmount": {"type": amount_dom, "name": DOMAIN["stop_loss_failure" if amount_dom == "cut" else "entry_error"]["name"],
                         "stat": f"평균 위험 {avg[amount_dom]:.2f}", "reasonLabel": "심각도 최대"},
        },
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
