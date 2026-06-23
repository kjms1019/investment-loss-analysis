"""리벤지 트레이딩 검출 (결정/시간 축).

정의: 직전 손실을 만회하려는 동기로, 진짜 시그널이 아니라 손실 직후
      충동적으로 재진입하는 것. 문헌상 측정 신호 = (1) 손실 직후 빠른
      재진입, (2) 포지션 크기 확대.

측정 (사이클을 진입시각 순으로 훑으며 직전→다음 쌍 검사):
  직전 사이클 손실(수익률<0) AND 다음 진입까지 간격 < window  → 시간조건(1점)
  + 다음 사이클 투입금 > 직전 투입금 (포지션 확대)              → (2점)
  + 다음 사이클도 손실 (재손실)                                 → (3점)
유형 강도 = 기간 내 '강(3점)' 신호 건수 기반.
"""

from __future__ import annotations

from ..config import Config
from ..schema import Preprocessed, TypeFinding

REFERENCE = "리벤지 트레이딩: 손실 직후 충동적 재진입 + 포지션 확대 (행동재무 문헌)"

_SEVERITY = {0: "none", 1: "weak", 2: "moderate", 3: "strong"}


def detect_revenge(pre: Preprocessed, config: Config | None = None) -> TypeFinding:
    config = config or Config()
    cycles = sorted(pre.cycles, key=lambda c: c.entry_time)

    events: list[dict] = []
    for prev, curr in zip(cycles, cycles[1:]):
        if prev.exit_time is None:        # 직전이 미청산이면 손익 미확정 → 스킵
            continue
        if prev.return_pct >= 0:          # 직전이 손실이 아니면 리벤지 전제 불성립
            continue
        gap_min = (curr.entry_time - prev.exit_time).total_seconds() / 60.0
        if gap_min < 0 or gap_min >= config.revenge_window_min:
            continue

        score = 1  # 시간조건
        expanded = curr.invested > prev.invested
        if expanded:
            score = 2
        re_loss = curr.closed and curr.return_pct < 0
        if expanded and re_loss:
            score = 3

        events.append(
            {
                "prev_code": prev.code,
                "prev_name": prev.name,
                "prev_return_pct": round(prev.return_pct * 100, 2),
                "next_code": curr.code,
                "next_name": curr.name,
                "gap_min": round(gap_min, 1),
                "position_expanded": expanded,
                "size_ratio": round(curr.invested / prev.invested, 2)
                if prev.invested
                else None,
                "re_loss": bool(re_loss),
                "score": score,
                "entry_time": str(curr.entry_time),
            }
        )

    strong = [e for e in events if e["score"] >= config.revenge_strong_score]
    moderate = [e for e in events if e["score"] == 2]

    if strong:
        severity = "strong"
    elif moderate:
        severity = "moderate"
    elif events:
        severity = "weak"
    else:
        severity = "none"

    evidence = []
    for e in sorted(events, key=lambda x: -x["score"])[:5]:
        tag = {3: "강", 2: "중", 1: "약"}[e["score"]]
        line = (
            f"[{tag}] {e['prev_name']} {e['prev_return_pct']}% 손절 후 "
            f"{e['gap_min']:.0f}분 만에 {e['next_name']} 재진입"
        )
        if e["position_expanded"]:
            line += f" (투입금 {e['size_ratio']}배 확대)"
        if e["re_loss"]:
            line += " → 재손실"
        evidence.append(line)

    return TypeFinding(
        type_key="revenge",
        type_label="리벤지 트레이딩",
        detected=bool(events),
        severity=severity,
        metrics={
            "signal_count": len(events),
            "strong_count": len(strong),
            "moderate_count": len(moderate),
            "weak_count": len(events) - len(strong) - len(moderate),
            "window_min": config.revenge_window_min,
        },
        evidence=evidence,
        reference=REFERENCE,
    )
