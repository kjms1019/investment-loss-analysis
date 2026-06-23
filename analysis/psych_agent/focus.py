"""손실 거래 단위 심리 귀속 (attribution).

오케스트레이션이 선별한 '복기 대상 손실 거래' 각각에 대해, 전체 거래 맥락
(Preprocessed) 위에서 리벤지/과매매/처분효과 중 무엇이 그 손실을 설명하는지
귀속시킨다. 핵심: 손실 거래는 '설명 대상(anchor)', 전체 거래는 '계산용 context'.

이 귀속 점수가 곧 다중분류기 입력(어느 에이전트/어느 심리유형으로 보낼지)이 된다.

psych_agent 외부(스크리너)에 의존하지 않는다 — 입력은 PositionCycle 키 목록뿐.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import pandas as pd

from .config import Config
from .schema import Preprocessed, PositionCycle


@dataclass
class SubSignal:
    detected: bool
    score: float          # 0~3 정규화 강도
    evidence: list[str] = field(default_factory=list)


@dataclass
class LossAttribution:
    code: str
    name: str
    entry_time: str
    exit_time: str
    return_pct: float
    holding_min: float | None
    revenge: SubSignal
    overtrading: SubSignal
    disposition: SubSignal
    dominant: str | None  # 'revenge'|'overtrading'|'disposition'|None('기타')

    def to_dict(self) -> dict:
        def s(x: SubSignal):
            return {"detected": x.detected, "score": round(x.score, 2), "evidence": x.evidence}
        return {
            "code": self.code, "name": self.name,
            "entry_time": self.entry_time, "exit_time": self.exit_time,
            "return_pct": self.return_pct, "holding_min": self.holding_min,
            "dominant": self.dominant,
            "revenge": s(self.revenge),
            "overtrading": s(self.overtrading),
            "disposition": s(self.disposition),
        }


def _cycle_id(c: PositionCycle) -> str:
    return f"{c.code}@{c.entry_time}"


# ── 리벤지 귀속: 이 손실거래가 '직전 손절 후 충동 재진입'이었나 ──────────────
def _attr_revenge(
    target: PositionCycle, prev: PositionCycle | None, config: Config
) -> SubSignal:
    if prev is None or not prev.closed or prev.return_pct >= 0:
        return SubSignal(False, 0.0)
    gap = (target.entry_time - prev.exit_time).total_seconds() / 60.0
    if gap < 0 or gap >= config.revenge_window_min:
        return SubSignal(False, 0.0)

    score = 1.0
    ev = [f"직전 {prev.name} {prev.return_pct * 100:.1f}% 손절 후 {gap:.0f}분 만에 재진입"]
    expanded = target.invested > prev.invested
    if expanded:
        score = 2.0
        ev.append(f"투입금 {target.invested / prev.invested:.1f}배 확대(포지션 키움)")
    if expanded and target.return_pct < 0:
        score = 3.0
        ev.append("그 재진입도 재손실 → 전형적 리벤지")
    return SubSignal(True, score, ev)


# ── 처분효과 귀속: 이 손실을 유독 오래 들고 있었나 / 그동안 수익은 익절했나 ──
def _attr_disposition(
    target: PositionCycle, pre: Preprocessed, avg_win_hold: float | None, config: Config
) -> SubSignal:
    if target.return_pct >= 0 or target.holding_minutes is None:
        return SubSignal(False, 0.0)

    ev = []
    score = 0.0
    # (1) 평균 수익거래 대비 보유기간 비대칭
    if avg_win_hold and avg_win_hold > 0:
        ratio = target.holding_minutes / avg_win_hold
        if ratio >= 1.5:
            score = max(score, 1.0 + min(ratio / 3.0, 2.0))  # 1.5x→1.5, 4.5x↑→3
            ev.append(f"평균 수익거래({avg_win_hold:.0f}분)의 {ratio:.1f}배 보유(손실을 오래 끌었음)")
    # (2) 이 손실을 들고 있는 동안 '수익 종목'을 익절한 횟수 (전형적 처분효과 행동)
    held_start, held_end = target.entry_time, target.exit_time
    sold_winners = sum(
        1
        for c in pre.closed_cycles
        if c.is_win and c.exit_time is not None and held_start <= c.exit_time <= held_end
    )
    if sold_winners >= 1:
        score = max(score, min(1.0 + sold_winners * 0.5, 3.0))
        ev.append(f"이 손실 보유 중 수익 종목 {sold_winners}건 익절(이익은 빨리, 손실은 길게)")

    return SubSignal(score > 0, score, ev)


# ── 과매매 귀속: 이 손실이 거래 폭주 군집 안에서 났나 ──────────────────────
def _attr_overtrading(
    target: PositionCycle, daily_counts: pd.Series, median_daily: float, config: Config
) -> SubSignal:
    day = pd.Timestamp(target.entry_time).normalize()
    same_day = int(daily_counts.get(day, 0))
    score = 0.0
    ev = []
    # 그 날 거래 건수가 개인 일중앙값의 N배 이상이면 군집
    if median_daily > 0 and same_day >= max(4, median_daily * config.overtrade_freq_multiple):
        ratio = same_day / median_daily
        score = min(1.0 + ratio / 2.0, 3.0)
        ev.append(f"진입일에 {same_day}건 매매 = 평소 하루({median_daily:.0f}건)의 {ratio:.1f}배(과매매 군집)")
    elif same_day >= 6:
        score = 1.0
        ev.append(f"진입일에 {same_day}건 매매(거래 폭주일)")
    return SubSignal(score > 0, score, ev)


def attribute_losses(
    pre: Preprocessed,
    focus_cycles: list[PositionCycle],
    config: Config | None = None,
) -> list[LossAttribution]:
    config = config or Config()
    cycles_sorted = sorted(pre.cycles, key=lambda c: c.entry_time)
    prev_by_id = {}
    for i, c in enumerate(cycles_sorted):
        prev_by_id[_cycle_id(c)] = cycles_sorted[i - 1] if i > 0 else None

    # 맥락 통계 (전체 거래 기반)
    win_holds = [c.holding_minutes for c in pre.closed_cycles if c.is_win and c.holding_minutes is not None]
    avg_win_hold = statistics.mean(win_holds) if win_holds else None
    if pre.trades:
        days = pd.Series([pd.Timestamp(t.datetime).normalize() for t in pre.trades])
        daily_counts = days.value_counts()
        median_daily = float(daily_counts.median())
    else:
        daily_counts, median_daily = pd.Series(dtype=int), 0.0

    out: list[LossAttribution] = []
    for tc in focus_cycles:
        prev = prev_by_id.get(_cycle_id(tc))
        rev = _attr_revenge(tc, prev, config)
        disp = _attr_disposition(tc, pre, avg_win_hold, config)
        over = _attr_overtrading(tc, daily_counts, median_daily, config)

        ranked = sorted(
            [("revenge", rev), ("overtrading", over), ("disposition", disp)],
            key=lambda kv: kv[1].score,
            reverse=True,
        )
        dominant = ranked[0][0] if ranked[0][1].score > 0 else None

        out.append(
            LossAttribution(
                code=tc.code, name=tc.name,
                entry_time=str(tc.entry_time), exit_time=str(tc.exit_time),
                return_pct=round(tc.return_pct * 100, 2),
                holding_min=round(tc.holding_minutes, 1) if tc.holding_minutes is not None else None,
                revenge=rev, overtrading=over, disposition=disp,
                dominant=dominant,
            )
        )
    return out


# 손실거래 ↔ 사이클 매칭용 (스크리너가 주는 키와 동일 규약)
def cycle_id(code: str, entry_time) -> str:
    return f"{code}@{entry_time}"
