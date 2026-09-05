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

import collections
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
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

def _warm_caches() -> None:
    """무거운 프로세스 캐시를 미리 채운다. 별도 스레드에서 돈다.

    _all_alerts() 는 분봉을 전수 평가해 최초 1회가 수십 초 걸린다. 그대로 두면
    배포 직후 처음 알림 화면을 연 사람이 그 시간을 통째로 기다리게 된다.
    기동 직후 미리 계산해 두면 실제 사용자는 캐시된 결과만 받는다.
    """
    for name, fn in (("alerts", _all_alerts), ("trade_charts", _trade_charts)):
        t0 = time.time()
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            # 워밍업 실패가 서비스 기동을 막지는 않는다. 요청 시점에 다시 시도된다.
            print(f"[warmup] {name} 실패: {exc!r}", flush=True)
            continue
        print(f"[warmup] {name} 준비 완료 ({time.time() - t0:.1f}s)", flush=True)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # 헬스체크를 막지 않도록 데몬 스레드로 띄운다.
    threading.Thread(target=_warm_caches, name="warmup", daemon=True).start()
    yield


app = FastAPI(title="왜 잃었지? API", version="0.1.0", lifespan=_lifespan)

# CORS — 로컬 개발용 origin 은 항상 열고, 배포 도메인은 CORS_ORIGINS 로 추가한다.
# (쉼표 구분. 예: CORS_ORIGINS=https://why-did-i-lose.vercel.app)
_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ENV_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS + _ENV_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",   # Vercel 프리뷰 배포
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


def _norm_sev(raw: Optional[str]) -> str:
    """에이전트별로 제각각인 심각도 어휘(none/low/insufficient_data/medium 등)를
    UI 필터 3단계(강함/보통/약함)로 통일한다. 약한 것·미상은 모두 '약함'."""
    s = (raw or "").lower()
    if s in ("strong", "high"):
        return "strong"
    if s in ("moderate", "medium"):
        return "moderate"
    return "weak"  # weak, low, none, insufficient_data, "" …


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


@lru_cache(maxsize=1)
def _trade_charts() -> dict:
    """trade_id → 거래별 미니차트 페이로드. (UI 전용 DB, analysis.ui.build_trade_charts 산출물)

    분석 아키텍처와 무관한 화면 구현용 캐시. 파일이 없으면 빈 dict(차트 없이 동작).
    """
    import json as _json
    import sqlite3
    out: dict[str, dict] = {}
    try:
        from analysis.common.paths import DATA_DIR

        conn = sqlite3.connect(DATA_DIR / "ui_trade_charts.sqlite3")
        for tid, payload in conn.execute("select trade_id, payload_json from trade_charts"):
            out[tid] = _json.loads(payload)
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
_PSYCH_KO = {
    "disposition": {"name": "처분효과", "desc": "이익은 빨리 실현하고 손실은 오래 끄는 심리"},
    "revenge": {"name": "리벤지 트레이딩", "desc": "직전 손실을 빨리 만회하려는 충동 매매"},
    "overtrading": {"name": "과매매", "desc": "근거 없이 매매 빈도가 과도해지는 심리"},
}
_STATE_KO = {
    "downtrend": "하락 추세", "uptrend": "상승 추세", "range": "박스권",
    "pullback": "눌림목", "breakout": "돌파", "reversal": "반전",
}


def _was(word: str) -> str:
    """받침 유무에 따라 '이었어요'/'였어요' 선택 (박스권→이었어요, 추세→였어요)."""
    if not word:
        return "였어요"
    ch = word[-1]
    if "가" <= ch <= "힣":
        return "이었어요" if (ord(ch) - 0xAC00) % 28 else "였어요"
    return "였어요"


def _fmt_state_evidence(feature: str, value, message: str) -> Optional[str]:
    """진입 시점 state_classification evidence(피쳐·값·영문메시지)를 한국어 시황 문장으로."""
    v = value if isinstance(value, (int, float)) else None
    m = (message or "").lower()
    if feature == "ma_20_slope":
        if "positive" in m:
            return "20일 이동평균선이 상승 흐름이었어요"
        if "negative" in m:
            return "20일 이동평균선이 하락 흐름이었어요"
        return "20일 이동평균선이 거의 횡보 중이었어요"
    if feature == "ret_20m":
        if "negative" in m:
            return "진입 직전 20분 가격이 약세였어요"
        if "positive" in m:
            return "진입 직전 20분 반등 흐름이 있었어요"
        return "진입 직전 20분 가격 변화가 크지 않았어요"
    if feature == "rsi_14":
        return f"RSI {v:.0f} — 과열·침체 아닌 중립 구간이었어요" if v is not None else "RSI가 중립 구간이었어요"
    if feature == "range_position_20m":
        if v is not None:
            pct = round(v * 100)
            return (f"최근 변동범위 상단({pct}%)에서 진입했어요" if v >= 0.66
                    else f"최근 변동범위 안쪽({pct}%)에서 진입했어요")
        return "최근 변동범위 안에서 진입했어요"
    if feature == "entry_vs_high20_ratio":
        return "최근 20분 고점 부근에서 매수했어요"
    if feature == "entry_vs_ma20_pct":
        return f"20일선보다 {abs(v) * 100:.1f}% 아래에서 진입했어요" if v is not None else "20일선 아래에서 진입했어요"
    if feature in ("ret_3m", "ret_5m"):
        return "진입 직전 단기(3~5분) 흐름이 약했어요"
    if feature == "volume_ratio_20m":
        return f"평소보다 거래량이 {v:.1f}배 많았어요" if v is not None else "평소보다 거래량이 많았어요"
    return None


def _reasons_dto(it: LossReportItem) -> dict:
    """분류 근거(피쳐 기반) + 심리 심화. it.raw_result(원본 result_json)에서 사람이 읽을 문장으로 가공."""
    raw = it.raw_result or {}
    why: list[dict] = []

    if _domain_of(it.agent_id) and _domain_of(it.agent_id)["id"] == "cut":
        sig = raw.get("signals") or {}
        dd = sig.get("delay_days"); sp = sig.get("stop_pct"); mae = sig.get("MAE_pct")
        ret = sig.get("realized_return_pct"); adc = sig.get("avg_down_count") or 0
        if not sig.get("breached"):
            # 손절선까지 닿지도 않은 손실 — '손절실패'라 부르기엔 약하다. 정직하게 표기.
            band = (f"손절선({sp:.1f}%)까지는 닿지 않았어요"
                    + (f" (최대 {mae:.1f}%)" if mae is not None else ""))
            why.append({"text": band + " — 손절실패 강도는 약합니다", "strong": False})
            if ret is not None:
                why.append({"text": f"다만 {ret:.1f}%로 손실을 확정하고 마감했어요", "strong": False})
        else:
            if (sig.get("delay_score") or 0) > 0 and dd:
                why.append({"text": f"손절 기준을 넘긴 뒤 {dd}영업일 더 들고 있었어요", "strong": (sig.get("delay_score") or 0) >= 0.3})
            if (sig.get("excess_loss_score") or 0) > 0 and sp is not None and mae is not None:
                why.append({"text": f"손절선 {sp:.1f}% 대비 최대 {mae:.1f}%까지 손실이 커졌어요", "strong": (sig.get("excess_loss_score") or 0) >= 0.3})
            if (sig.get("expansion_score") or 0) > 0:
                why.append({"text": "보유하는 동안 손실폭이 계속 확대됐어요", "strong": (sig.get("expansion_score") or 0) >= 0.3})
            if adc > 0:
                why.append({"text": f"손실 중 {adc}회 추가 매수(물타기)했어요", "strong": True})
            if not why and ret is not None:
                why.append({"text": f"끊어야 할 지점을 지나 {ret:.1f}%까지 손실을 키웠어요", "strong": False})
    else:
        rr = raw.get("risk_score_result") or {}
        contribs = rr.get("contributions") or []
        for c in contribs:
            nm = c.get("label_name_ko")
            if nm:
                conf = c.get("confidence")
                tail = f" (신뢰도 {round(conf*100)}%)" if isinstance(conf, (int, float)) else ""
                why.append({"text": nm + tail, "strong": (c.get("contribution_to_score") or 0) >= 10})
        # 뚜렷한 진입오류 기여요인이 없으면(normal_entry) 솔직히 밝히고, 진입 시점 시황으로 보강.
        if not contribs:
            why.append({"text": "뚜렷한 진입오류 신호는 약했어요 — 대신 진입 시점 시황을 짚어볼게요", "strong": False})
        sc = raw.get("state_classification") or {}
        st = _STATE_KO.get(sc.get("primary_state"))  # 알 수 없는 상태(insufficient_data 등)는 숨김
        if st:
            why.append({"text": f"진입 시점 시장 상태는 ‘{st}’{_was(st)}", "strong": False})
        # state_classification evidence(MA·RSI·위치·거래량 등)를 시황 근거로 풀어 추가
        prim = sc.get("primary_state")
        cands = sc.get("candidate_states") or []
        ev = next((c.get("evidence") or [] for c in cands if c.get("state") == prim), [])
        if not ev and cands:
            ev = cands[0].get("evidence") or []
        seen: set[str] = set()
        for e in ev:
            if len(why) >= 4:  # 전체 근거 줄을 4줄로 제한 (너무 길지 않게)
                break
            txt = _fmt_state_evidence(e.get("feature"), e.get("value"), e.get("message"))
            if txt and txt not in seen:
                seen.add(txt)
                why.append({"text": txt, "strong": False})
        if not why:
            why.append({"text": "분류기가 진입 패턴(타이밍 오류) 쪽으로 판정했어요", "strong": False})

    psych = raw.get("psych") or {}
    pid = psych.get("pattern")
    ko = _PSYCH_KO.get(pid)
    psych_dto = {
        "name": ko["name"] if ko else (pid or ""),
        "desc": ko["desc"] if ko else "",
        "detected": bool(psych.get("detected")),
        "score": psych.get("score"),
        "evidence": psych.get("evidence") or [],
    } if pid else None

    return {"why": why, "psych": psych_dto}


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
        "sev": _norm_sev(it.severity),
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
        # 거래별 탭 카드용 미니차트(UI 전용 DB). 없으면 null.
        "chart": _trade_charts().get(it.trade_id),
        # 분류 근거(피쳐 기반 문장) + 심리 심화
        **_reasons_dto(it),
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


# ── ⑤ 내 성향: 모집단(10명) 대비 피쳐 시그니처 + 솔루션 ──────────────────────
# "이 사람이 다른 사람들보다 유독 잘 걸리는 피쳐"를 뽑아 최종 성향 + 교정안을 만든다.
_CUT_FEATS_KO = {"delay": "손절을 미루는 습관", "excess": "손절선 넘겨 버티기",
                 "expansion": "손실 확대 방치", "avgdown": "손실 종목 물타기"}
_CUT_FEAT_FIELD = {"delay": "delay_score", "excess": "excess_loss_score",
                   "expansion": "expansion_score", "avgdown": "avg_down_score"}
_ENTRY_FEATS_KO = {
    "weak_flow_near_high": "고점 부근 수급 부족 진입",
    "range_top_chase": "박스권 상단 추격 진입",
    "gap_up_chase": "신고가권 추격 매수",
    "downtrend_without_reversal": "반등 없는 하락추세 진입",
    "unstable_pullback_flow": "불안정한 눌림목 진입",
}
_FEAT_SOLUTION = {
    "delay": "손절선을 숫자로 못 박고, 닿으면 ‘내일’이 아니라 그 자리에서 끊는 규칙을 만드세요.",
    "excess": "손절선 도달 시 자동 청산되도록 역지정가(스톱) 주문을 미리 걸어두세요.",
    "expansion": "손실이 커지는 종목은 장중 알림으로 즉시 대응해 방치 시간을 없애세요.",
    "avgdown": "손실 종목 추가매수는 금지 규칙으로. 평단 낮추기보다 손절을 우선하세요.",
    "weak_flow_near_high": "고점 부근에선 거래량·수급을 먼저 확인하고, 안 되면 진입을 미루세요.",
    "range_top_chase": "박스권에선 상단 추격 대신 하단 지지에서만 분할 진입하세요.",
    "gap_up_chase": "신고가 추격은 손절폭을 좁히거나 눌림을 확인한 뒤 들어가세요.",
    "downtrend_without_reversal": "하락 추세에선 반등 확인(거래량 동반 양봉 등) 전까지 진입을 보류하세요.",
    "unstable_pullback_flow": "눌림목은 되돌림이 안정된 신호를 확인한 뒤 진입하세요.",
}


def _user_incidence(rows: list) -> dict:
    """한 사용자의 [(agent_id, result)] → 피쳐 발생수 + 도메인별 거래수 + 심리 감지수."""
    fired = collections.Counter()
    cut_total = entry_total = disp = rev = 0
    for aid, r in rows:
        if aid == "stop_loss_failure":
            cut_total += 1
            sig = r.get("signals") or {}
            for key, field in _CUT_FEAT_FIELD.items():
                if (sig.get(field) or 0) > 0.05:
                    fired[("cut", key)] += 1
            ps = r.get("psych") or {}
            if ps.get("pattern") == "disposition" and ps.get("detected"):
                disp += 1
        elif aid == "entry_error":
            entry_total += 1
            for cc in (r.get("risk_score_result", {}).get("contributions") or []):
                lid = cc.get("label_id")
                if lid in _ENTRY_FEATS_KO:
                    fired[("entry", lid)] += 1
            ps = r.get("psych") or {}
            if ps.get("pattern") == "revenge" and ps.get("detected"):
                rev += 1
    return {"fired": fired, "cut_total": cut_total, "entry_total": entry_total,
            "total": cut_total + entry_total, "disp": disp, "rev": rev}


@lru_cache(maxsize=1)
def _population() -> dict:
    """user_profile_trade_labels 전체 → 사용자별 발생률 + 모집단(도메인 보유자) 평균."""
    import json as _json
    import sqlite3
    by_user: dict[str, list] = collections.defaultdict(list)
    try:
        conn = sqlite3.connect(_PROFILE_DB)
        for uid, aid, rj in conn.execute(
            "select user_id, agent_id, result_json from user_profile_trade_labels"
        ):
            try:
                by_user[uid].append((aid, _json.loads(rj or "{}")))
            except Exception:
                pass
        conn.close()
    except Exception:  # noqa: BLE001
        pass

    stats = {u: _user_incidence(v) for u, v in by_user.items()}
    # 피쳐별 사용자 발생률(도메인 상대) + 모집단 평균(해당 도메인 보유자 기준)
    rates: dict = collections.defaultdict(dict)
    for u, s in stats.items():
        for key in _CUT_FEATS_KO:
            if s["cut_total"] > 0:
                rates[("cut", key)][u] = s["fired"].get(("cut", key), 0) / s["cut_total"]
        for lid in _ENTRY_FEATS_KO:
            if s["entry_total"] > 0:
                rates[("entry", lid)][u] = s["fired"].get(("entry", lid), 0) / s["entry_total"]
    pop = {feat: (sum(d.values()) / len(d) if d else 0.0) for feat, d in rates.items()}
    return {"stats": stats, "rates": rates, "pop": pop}


def _feat_ko(feat: tuple) -> str:
    dom_id, key = feat
    return _CUT_FEATS_KO.get(key) if dom_id == "cut" else _ENTRY_FEATS_KO.get(key, key)


@app.get("/api/disposition/{user_id}")
def disposition(user_id: str) -> dict:
    """최종 성향: 주된 실수 도메인 + 모집단 대비 유독 잘 걸리는 피쳐 + 심리 + 솔루션."""
    pf = _population()
    s = pf["stats"].get(user_id)
    if not s or s["total"] == 0:
        raise HTTPException(status_code=404, detail="no disposition data")

    cut, entry = s["cut_total"], s["entry_total"]
    dom = "cut" if cut >= entry else "entry"

    # 시그니처: (사용자 발생률 / 모집단 평균) 비율이 높은 = 남보다 유독 잘 걸리는 피쳐
    sig = []
    for feat, cnt in s["fired"].items():
        if cnt == 0:
            continue
        ur = pf["rates"].get(feat, {}).get(user_id, 0.0)
        pr = pf["pop"].get(feat, 0.0)
        ratio = (ur / pr) if pr > 0 else (2.0 if ur > 0 else 0.0)
        sig.append({
            "key": feat[1], "domain": feat[0], "label": _feat_ko(feat),
            "count": cnt, "user_pct": round(ur * 100), "pop_pct": round(pr * 100),
            "ratio": round(ratio, 1), "reliable": cnt >= 2,  # 표본 2건 미만이면 'N배' 주장 보류
            "solution": _FEAT_SOLUTION.get(feat[1], ""),
        })
    # 표본 가중 정렬(비율×건수): 1건짜리 고배율이 헤드라인을 지배하지 않게.
    sig.sort(key=lambda x: (x["ratio"] * x["count"], x["count"]), reverse=True)
    over = [x for x in sig if x["ratio"] >= 1.15]
    signature = (over or sig)[:4]

    # 심리: 사용자 감지율 vs 모집단 평균
    def _rate(num: int, den: int) -> float:
        return num / den if den else 0.0
    disp_users = [st for st in pf["stats"].values() if st["cut_total"]]
    rev_users = [st for st in pf["stats"].values() if st["entry_total"]]
    pop_disp = sum(_rate(st["disp"], st["cut_total"]) for st in disp_users) / max(len(disp_users), 1)
    pop_rev = sum(_rate(st["rev"], st["entry_total"]) for st in rev_users) / max(len(rev_users), 1)
    psych = {
        "disposition": {"user_pct": round(_rate(s["disp"], cut) * 100), "pop_pct": round(pop_disp * 100)},
        "revenge": {"user_pct": round(_rate(s["rev"], entry) * 100), "pop_pct": round(pop_rev * 100)},
    }

    # 헤드라인 + 솔루션
    name = user_id
    top = signature[0] if signature else None
    if top and top["reliable"] and top["ratio"] >= 1.3:
        headline = (f"{name}님은 전체 손실 {s['total']}건 중 {_domain_name(dom)}가 가장 잦고, "
                    f"그중에서도 ‘{top['label']}’을 다른 사람보다 {top['ratio']}배 자주 합니다.")
    elif top:
        headline = (f"{name}님의 주된 실수는 {_domain_name(dom)}이고, "
                    f"가장 두드러진 신호는 ‘{top['label']}’입니다.")
    else:
        headline = f"{name}님의 주된 실수는 {_domain_name(dom)}입니다."
    solutions = [x["solution"] for x in signature if x["solution"]][:3]

    return {
        "user_id": user_id,
        "total": s["total"],
        "dominant": {"id": dom, "name": _domain_name(dom),
                     "pct": round(_rate(cut if dom == "cut" else entry, s["total"]) * 100)},
        "counts": {"cut": cut, "entry": entry},
        "headline": headline,
        "signature": signature,
        "psych": psych,
        "solutions": solutions,
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
    items = sorted(summ.items, key=lambda i: (_SEV_ORDER.get(_norm_sev(i.severity), 0), i.score or 0), reverse=True)
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
        key=lambda i: (_SEV_ORDER.get(_norm_sev(i.severity), 0), i.score or 0),
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


# 실시간(미래 23~26일) 평가 기준 시각 — 현재=23일 컷오프 가정.
from datetime import datetime as _dt, timedelta as _td  # noqa: E402
_STOP_ASOF = _dt(2026, 6, 25, 11, 0)   # 보유 종목 급락 평가 시점
_ENTRY_ASOF = _dt(2026, 6, 24, 0, 0)   # 다가오는 매수 평가 기준
_STOP_LOSS_PCT = 0.05                  # holding_market_min1 기본 손절폭과 일치


@lru_cache(maxsize=1)
def _holding_entry_at() -> dict:
    """(user_id, 종목명) → 매수일시 (현재보유 시트). 손절 차트의 진입가·손절선 산출용."""
    import pandas as pd
    out: dict = {}
    try:
        df = pd.ExcelFile(_FIXTURE).parse("현재보유")
        for _, r in df.iterrows():
            out[(str(r["사용자명"]), str(r["종목명"]))] = pd.to_datetime(r["매수일시"]).to_pydatetime()
    except Exception:  # noqa: BLE001
        pass
    return out


def _downsample_df(df, max_points: int = 70):
    n = len(df)
    if n <= max_points:
        return df.reset_index(drop=True)
    step = n / max_points
    idx = sorted({int(i * step) for i in range(max_points)} | {0, n - 1})
    return df.iloc[idx].reset_index(drop=True)


def _alert_chart(code: str, *, kind: str, at: _dt, entry_at=None) -> Optional[dict]:
    """실시간 주식창 차트: 이벤트 직전 구간 분봉 + 마커.

    kind='stop' : 보유종목 급락 → 손절선 접근. 마커=현재가, 손절선, 최근 고점.
    kind='entry': 다가오는 매수 → 진입 시점. 마커=매수 예정점, 최근 고점.
    """
    from analysis.common.min1_lookup import load_min1, price_at
    df = load_min1(code)
    if df is None or df.empty:
        return None
    # 손절 차트는 진입~현재 전체를 그려 손절선 돌파→현재가까지 보이게(이미 깊은 손실이라 최근창엔 손절선이 화면 밖).
    if kind == "stop" and entry_at is not None:
        lo_t = entry_at
    else:
        lo_t = at - (_td(days=3) if kind == "entry" else _td(days=4))
    win = df[(df["datetime"] >= lo_t) & (df["datetime"] <= at)]
    if len(win) < 2:
        return None
    win = _downsample_df(win.sort_values("datetime"))
    series = [{"t": t.isoformat(), "c": int(round(c))} for t, c in zip(win["datetime"], win["close"])]
    closes = [s["c"] for s in series]
    hi_i = closes.index(max(closes))
    out = {
        "kind": kind, "series": series,
        "marker": {"i": len(series) - 1, "t": series[-1]["t"], "price": closes[-1]},  # 현재가/매수점
        "entry": None, "stop": None, "breach": None,
        "high": {"i": hi_i, "price": closes[hi_i]},
        "lo": min(closes), "hi": max(closes), "breached": False,
    }
    if kind == "stop" and entry_at is not None:
        ep = price_at(df, entry_at)
        if ep:
            out["entry"] = {"i": 0, "t": series[0]["t"], "price": int(round(ep))}
            stop = round(ep * (1 - _STOP_LOSS_PCT))
            out["stop"] = stop
            out["breached"] = closes[-1] <= stop
            bi = next((i for i, c in enumerate(closes) if c <= stop), None)
            if bi is not None:
                out["breach"] = {"i": bi, "t": series[bi]["t"]}
    return out


@lru_cache(maxsize=1)
def _all_alerts() -> dict:
    """데모 fixture 의 B(진입)·C(손절) 알림을 전 사용자 1회 계산해 캐시.

    매 요청마다 재평가하면 수십 초 걸리므로(분봉 전수 평가) 프로세스 캐시한다.
    각 알림에 '실시간 주식창' 차트(이벤트 직전 분봉 + 마커)를 함께 붙인다.
    """
    from analysis.orchestrator.demo_alert_runner import check_entry_warnings, check_stop_loss_warnings

    xlsx = str(_FIXTURE)
    eat = _holding_entry_at()
    by_user: dict[str, list] = {}
    for a in check_stop_loss_warnings(xlsx, _STOP_ASOF):
        chart = _alert_chart(a.get("code"), kind="stop", at=_STOP_ASOF,
                             entry_at=eat.get((a.get("user_id"), a.get("name"))))
        by_user.setdefault(a.get("user_id"), []).append(
            {"kind": "보유 점검", "type": "cut", "chart": chart, **_alert_common(a)})
    for a in check_entry_warnings(xlsx, _ENTRY_ASOF):
        sched = a.get("scheduled_at")
        try:
            sched_dt = _dt.fromisoformat(str(sched)) if sched else _ENTRY_ASOF
        except Exception:  # noqa: BLE001
            sched_dt = _ENTRY_ASOF
        chart = _alert_chart(a.get("code"), kind="entry", at=sched_dt)
        by_user.setdefault(a.get("user_id"), []).append(
            {"kind": "매수 시점", "type": "entry", "chart": chart, **_alert_common(a)})
    return by_user


@app.get("/api/alerts/{user_id}")
def alerts(user_id: str) -> dict:
    """실시간 알림(B 진입 + C 손절) — 데모 fixture 를 미래 시점으로 평가(캐시)."""
    return {"user_id": user_id, "alerts": _all_alerts().get(user_id, [])}


# 포트폴리오를 풍성하게 채울 우량주(있으면 우선). fixture 보유가 1~5종목뿐이라 데모용으로 보강.
_PORTFOLIO_FILL = [
    "삼성전자", "SK하이닉스", "현대차", "기아", "NAVER", "카카오", "LG에너지솔루션",
    "삼성바이오로직스", "셀트리온", "POSCO홀딩스", "현대모비스", "KB금융", "신한지주",
    "삼성SDI", "LG화학", "삼성물산", "하나금융지주", "SK이노베이션", "KT&G", "한국전력",
    "포스코퓨처엠", "크래프톤", "삼성생명", "두산에너빌리티", "HMM", "S-Oil", "고려아연",
]
_SYNTH_ENTRY_DATES = [
    "2025-08-12 10:00", "2025-09-24 13:00", "2025-10-15 11:00", "2025-11-07 09:30",
    "2025-12-03 14:00", "2026-01-20 10:00", "2026-02-11 13:00", "2025-09-05 10:30",
]


@lru_cache(maxsize=1)
def _all_demo_users() -> tuple:
    """데모 사용자 전체(현재보유 0인 사람도 포함). 합성 보유를 모두에게 주려고."""
    import sqlite3
    try:
        conn = sqlite3.connect(_PROFILE_DB)
        rows = conn.execute("select distinct user_id from user_profiles order by user_id").fetchall()
        conn.close()
        return tuple(r[0] for r in rows)
    except Exception:  # noqa: BLE001
        return tuple()


def _synthetic_holdings(user: str, exclude: set, want: int) -> list:
    """실제 주가(min1) 기반 합성 보유 — 우량주에 2025 매수일·수량 부여. 이익/손실은 실제 등락대로."""
    if want <= 0:
        return []
    import random
    from datetime import datetime as _dtm
    from analysis.common.min1_lookup import load_name_to_code, load_min1, price_at
    n2c = load_name_to_code()
    seed = sum(ord(c) for c in user) * 7 + 13
    rnd = random.Random(seed)
    names = [n for n in _PORTFOLIO_FILL if n in n2c]
    rnd.shuffle(names)
    out: list = []
    used = set(exclude)
    for name in names:
        if len(out) >= want:
            break
        code = n2c.get(name)
        if not code or code in used:
            continue
        m = load_min1(code)
        edt = _dtm.fromisoformat(_SYNTH_ENTRY_DATES[(seed + len(out)) % len(_SYNTH_ENTRY_DATES)])
        ep = price_at(m, edt); cur = price_at(m, _STOP_ASOF)
        if not ep or not cur:
            continue
        pct = (cur - ep) / ep * 100.0
        if pct < -55 or pct > 55:  # 데이터 특이값(비현실적 등락) 제외 — 믿을 만한 범위만
            continue
        used.add(code)
        stop = round(ep * (1 - _STOP_LOSS_PCT))
        out.append({
            "name": name, "code": code, "qty": max(1, round(1_500_000 / cur)),
            "entry_price": round(ep), "current_price": round(cur), "pct": round(pct, 1),
            "stop": stop, "breached": cur <= stop,
            "chart": _alert_chart(code, kind="stop", at=_STOP_ASOF, entry_at=edt),
            "status": "ok", "risk": None,
        })
    return out


def _near_stop(cur: float, stop: Optional[float]) -> bool:
    """현재가가 손절선에 '닿을락말락'(−4%~+6%) 인가 — 이때 경고해야 의미 있다.
    이미 손절선을 한참 지난(−10%++) 종목은 '이미 손절실패'라 라이브 경고 대상이 아니다."""
    return bool(stop) and (stop * 0.96) <= cur <= (stop * 1.06)


def _stop_alert_risk(h: dict) -> dict:
    name, stop, pct = h["name"], h["stop"], h["pct"]
    above = h["current_price"] > stop
    if above:
        msg = f"{name}이(가) 손절선 ₩{stop:,}에 가까워지고 있어요. 당신은 손절을 미루는 경향이 있어요 — 이번엔 미리 정한 손절선을 꼭 지키세요."
    else:
        msg = f"{name}이(가) 손절선 ₩{stop:,}을 막 건드렸어요. 더 버티지 말고 지금 손절선을 지키세요."
    return {"level": "high", "score": 88,
            "reasons": ["손절선 근접", "최근 하락 추세", f"보유 손익 {pct:+.1f}%"], "message": msg}


def _danger_holding(user: str, exclude: set) -> Optional[dict]:
    """손절선으로 '내려가며' 막 닿은 보유를 실거래 주가로 합성 — 라이브 경고용.

    조건: 진입(최근 고점)에서 하락해 현재가가 ① 최근 저점 근처(=계속 내려가는 중, 반등 아님)
    ② 고점 대비 −5% 안팎(손절선 ≈ 현재가). 차트가 '고점→하락→손절선 터치'로 보이게."""
    import random
    from datetime import timedelta
    from analysis.common.min1_lookup import load_name_to_code, load_min1, price_at
    n2c = load_name_to_code()
    rnd = random.Random(sum(ord(c) for c in user) * 11 + 5)
    pref = [n for n in _PORTFOLIO_FILL if n in n2c]
    rest = [n for n in n2c if n not in _PORTFOLIO_FILL]
    rnd.shuffle(pref); rnd.shuffle(rest)
    names = pref + rest  # 우량주 우선, 없으면 전체 종목에서 '손절선으로 내려가는' 종목 탐색
    for name in names:
        code = n2c.get(name)
        if not code or code in exclude:
            continue
        m = load_min1(code)
        if m is None or m.empty:
            continue
        cur = price_at(m, _STOP_ASOF)
        if not cur:
            continue
        win = m[(m["datetime"] >= _STOP_ASOF - timedelta(days=50)) & (m["datetime"] <= _STOP_ASOF)]
        win = win.sort_values("datetime").reset_index(drop=True)
        if len(win) < 10:
            continue
        lo = float(win["close"].min())
        lo_pos = int(win["close"].idxmin())
        if cur > lo * 1.03:           # 현재가가 최근 저점 근처가 아니면(반등) 제외
            continue
        if lo_pos < len(win) * 0.5:    # 저점이 최근(뒤쪽 절반)이어야 = 내려가는 중
            continue
        before = win.iloc[: lo_pos + 1]
        hi = float(before["close"].max())
        hi_pos = int(before["close"].idxmax())
        if not (1.035 <= hi / cur <= 1.10):   # 고점이 현재가 대비 +3.5~10% (≈ −5% 하락폭)
            continue
        if hi_pos > len(win) * 0.65:   # 고점은 앞쪽이어야 = 하락 구간 확보
            continue
        edt = before.iloc[hi_pos]["datetime"].to_pydatetime()
        stop = round(hi * (1 - _STOP_LOSS_PCT))
        h = {"name": name, "code": code, "qty": max(1, round(1_500_000 / cur)),
             "entry_price": round(hi), "current_price": round(cur), "pct": round((cur - hi) / hi * 100, 1),
             "stop": stop, "breached": cur <= stop,
             "chart": _alert_chart(code, kind="stop", at=_STOP_ASOF, entry_at=edt), "status": "alert"}
        h["risk"] = _stop_alert_risk(h)
        return h
    return None


@lru_cache(maxsize=1)
def _all_holdings() -> dict:
    """현재보유 전체 포트폴리오(이익+손실 혼재)를 실시간 추적 대상으로 반환.

    손실난 종목만이 아니라 보유 중 전부를 트래킹한다. 라이브 손절 경고는 '손절선에 막 닿은'
    종목에만 띄운다(이미 한참 지난 깊은 손실은 추적만). fixture 보유가 사람당 1~5종목뿐이라
    우량주 합성 보유로 7종목까지 채우고, 손절선 근접 종목이 없으면 하나 합성해 경고를 만든다.
    """
    import pandas as pd
    from analysis.common.min1_lookup import load_name_to_code, load_min1, price_at

    n2c = load_name_to_code()
    out: dict = {}
    try:
        df = pd.ExcelFile(_FIXTURE).parse("현재보유")
    except Exception:  # noqa: BLE001
        return out
    for _, r in df.iterrows():
        user = str(r["사용자명"]); name = str(r["종목명"]); code = n2c.get(name)
        if not code:
            continue
        m = load_min1(code)
        entry_at = pd.to_datetime(r["매수일시"]).to_pydatetime()
        ep = price_at(m, entry_at); cur = price_at(m, _STOP_ASOF)
        if not ep or not cur:
            continue
        pct = (cur - ep) / ep * 100.0
        stop = round(ep * (1 - _STOP_LOSS_PCT))
        chart = _alert_chart(code, kind="stop", at=_STOP_ASOF, entry_at=entry_at)
        out.setdefault(user, []).append({
            "name": name, "code": code, "qty": int(r["현재보유수량"]),
            "entry_price": round(ep), "current_price": round(cur), "pct": round(pct, 1),
            "stop": stop, "breached": cur <= stop, "chart": chart,
            "status": "ok", "risk": None,  # 라이브 경고 여부는 아래 손절선 근접 판정에서 결정
        })
    # 사용자별: 손절선 근접 판정 → 경고, 없으면 근접 종목 합성, 그다음 우량주로 7종목까지 채움.
    TARGET = 7
    for user in set(out) | set(_all_demo_users()):
        base = out.setdefault(user, [])
        for h in base:  # 실제 보유 중 손절선 '근접'한 것만 라이브 경고로
            if _near_stop(h["current_price"], h["stop"]):
                h["status"] = "alert"; h["risk"] = _stop_alert_risk(h)
        if not any(h["status"] == "alert" for h in base):  # 근접 종목이 없으면 하나 합성
            d = _danger_holding(user, {h["code"] for h in base})
            if d:
                base.insert(0, d)
        exclude = {h["code"] for h in base}
        base.extend(_synthetic_holdings(user, exclude, TARGET - len(base)))
        base.sort(key=lambda h: (0 if h["status"] == "alert" else 1, h["pct"]))
    return out


@app.get("/api/holdings/{user_id}")
def holdings(user_id: str) -> dict:
    """실시간 추적 대상: 보유 전체(이익+손실) + 다가오는 매수 예정."""
    plans = [a for a in _all_alerts().get(user_id, []) if a.get("type") == "entry"]
    return {"user_id": user_id, "holdings": _all_holdings().get(user_id, []), "plans": plans}


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
