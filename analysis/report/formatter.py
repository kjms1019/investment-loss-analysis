"""LossReportSummary 출력 포맷 어댑터.

builder.py 는 포맷을 모른다 — 소비처(웹 대시보드/노트북/CLI)가 늘어나면
여기에 to_* 함수만 추가한다.
"""

from __future__ import annotations

import json

from .schema import LossReportSummary


def to_json(summary: LossReportSummary, *, indent: int = 2) -> str:
    return json.dumps(summary.to_dict(), ensure_ascii=False, indent=indent)


def to_markdown(summary: LossReportSummary) -> str:
    """TODO: 노트북/슬랙 공유용 요약. 우선 상위 항목 narrative 만 나열."""
    lines = [f"# 손실 리포트 ({summary.scope}={summary.scope_id})", ""]
    lines.append(f"- 대상 사이클 수: {summary.total_loss_trades}")
    lines.append(f"- 평균 점수: {summary.avg_score}")
    lines.append("")
    for item in summary.items:
        lines.append(f"## {item.name}({item.code}) · {item.agent_id} / {item.label}")
        lines.append(item.narrative or "(narrative 없음)")
        if item.classifier_entry_score is not None or item.classifier_stop_score is not None:
            lines.append(
                f"- 분류기: entry_error={item.classifier_entry_score} · "
                f"stop_loss_failure={item.classifier_stop_score} "
                f"(label={item.classifier_label}, confidence={item.classifier_confidence})"
            )
        lines.append("")
    return "\n".join(lines)
