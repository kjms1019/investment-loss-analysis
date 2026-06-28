"""처분효과 검출 (포지션/보유기간 축).

명명: Shefrin & Statman (1985). 표준 측정법: Odean (1998).
정의: 손실 자산은 너무 오래 보유하고, 수익 자산은 너무 빨리 판다.

측정 (Odean 1998 의 PGR vs PLR):
  매도(실현)가 일어난 시점마다,
    · 판 종목 → 실현이익(realized gain) 또는 실현손실(realized loss)
    · 그 순간 보유 중인 '다른' 종목들 → 시장가 대비 평가이익/평가손실
  PGR = 실현이익 / (실현이익 + 평가이익)
  PLR = 실현손실 / (실현손실 + 평가손실)
  PGR > PLR (유의하게) → 처분효과.
보조: 손실 포지션 vs 수익 포지션의 평균 보유기간 격차.

이 비율 비교는 '가용 기회 대비 실제 행동'을 보므로 시장 상황·개인차가
자동 보정된다 → 임계값을 따로 정하지 않아도 견고하다 (MVP 핵심 유형).
"""

from __future__ import annotations

import statistics

from ..config import Config
from ..prices import PriceLookup
from ..schema import Preprocessed, TypeFinding

REFERENCE = "Shefrin & Statman (1985) 명명, Odean (1998) PGR/PLR 측정법"


def detect_disposition(
    pre: Preprocessed,
    config: Config | None = None,
    prices: PriceLookup | None = None,
) -> TypeFinding:
    config = config or Config()
    prices = prices or PriceLookup(config)

    realized_gain = realized_loss = 0
    paper_gain = paper_loss = 0

    for ev in pre.sell_events:
        if ev.sold_is_gain:
            realized_gain += 1
        else:
            realized_loss += 1
        # 그 순간 보유 중이던 '다른' 종목들의 평가손익 (시장가 대비)
        for code, avg_cost in ev.open_others:
            mkt = prices.price_at(code, ev.datetime)
            if mkt is None:
                continue  # 1분봉 없는 종목은 평가 불가 → 제외
            if mkt > avg_cost:
                paper_gain += 1
            elif mkt < avg_cost:
                paper_loss += 1

    pgr = realized_gain / (realized_gain + paper_gain) if (realized_gain + paper_gain) else None
    plr = realized_loss / (realized_loss + paper_loss) if (realized_loss + paper_loss) else None
    gap = (pgr - plr) if (pgr is not None and plr is not None) else None

    # 보조 지표: 보유기간 격차 (청산된 사이클 기준)
    win_hold = [c.holding_minutes for c in pre.closed_cycles if c.is_win and c.holding_minutes is not None]
    loss_hold = [c.holding_minutes for c in pre.closed_cycles if (not c.is_win) and c.holding_minutes is not None]
    avg_win_hold = statistics.mean(win_hold) if win_hold else None
    avg_loss_hold = statistics.mean(loss_hold) if loss_hold else None

    if gap is None:
        severity = "none"
        detected = False
    elif gap >= 2 * config.disposition_min_gap:
        severity = "strong"
        detected = True
    elif gap >= config.disposition_min_gap:
        severity = "moderate"
        detected = True
    elif gap > 0:
        severity = "weak"
        detected = True
    else:
        severity = "none"
        detected = False

    evidence = []
    if gap is not None:
        evidence.append(
            f"PGR(이익실현 성향) {pgr:.2f} vs PLR(손실실현 성향) {plr:.2f} "
            f"→ 차이 {gap:+.2f} ({'처분효과 양(+)' if gap > 0 else '역방향'})"
        )
    if avg_win_hold is not None and avg_loss_hold is not None:
        ratio = avg_loss_hold / avg_win_hold if avg_win_hold else None
        line = (
            f"평균 보유: 수익 {avg_win_hold:.0f}분 vs 손실 {avg_loss_hold:.0f}분"
        )
        if ratio:
            line += f" (손실을 {ratio:.1f}배 오래 보유)"
        evidence.append(line)

    return TypeFinding(
        type_key="disposition",
        type_label="처분효과",
        detected=detected,
        severity=severity,
        metrics={
            "pgr": round(pgr, 3) if pgr is not None else None,
            "plr": round(plr, 3) if plr is not None else None,
            "pgr_minus_plr": round(gap, 3) if gap is not None else None,
            "realized_gain": realized_gain,
            "realized_loss": realized_loss,
            "paper_gain": paper_gain,
            "paper_loss": paper_loss,
            "avg_win_hold_min": round(avg_win_hold, 1) if avg_win_hold is not None else None,
            "avg_loss_hold_min": round(avg_loss_hold, 1) if avg_loss_hold is not None else None,
        },
        evidence=evidence,
        reference=REFERENCE,
    )
