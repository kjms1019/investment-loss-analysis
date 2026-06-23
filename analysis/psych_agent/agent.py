"""준모 심리·과매매 분석 에이전트 (서브 오케스트레이터).

전체 '왜 잃었지?' 시스템에서 심리 매매 한 갈래를 담당한다.
매핑은 AI 판단이 아니라 '데이터 존재 여부 필터 + 조건부 병렬 실행':
  · 거래내역이 있으면         → 리벤지·과매매 (결정 축)
  · 매도 이벤트가 있으면      → 처분효과 (포지션 축)
검출기는 서로 독립이라 누락 없이 모두 돌린 뒤, 마지막에 LLM이 문장만 입힌다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import Config
from .detectors import detect_disposition, detect_overtrading, detect_revenge
from .diagnose import diagnose
from .preprocess import preprocess, trades_from_df
from .prices import PriceLookup
from .schema import Preprocessed, Trade, TypeFinding


@dataclass
class PsychReport:
    findings: list[TypeFinding]
    diagnosis: dict
    preprocessed: Preprocessed = field(repr=False)

    def to_dict(self) -> dict:
        return {
            "findings": [
                {
                    "type": f.type_key,
                    "label": f.type_label,
                    "detected": f.detected,
                    "severity": f.severity,
                    "metrics": f.metrics,
                    "evidence": f.evidence,
                    "reference": f.reference,
                }
                for f in self.findings
            ],
            "diagnosis": self.diagnosis,
        }


class PsychAgent:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.prices = PriceLookup(self.config)

    def analyze(self, trades: list[Trade]) -> PsychReport:
        pre = preprocess(trades, self.config)

        findings: list[TypeFinding] = []
        # 조건부 실행: 데이터가 존재하는 축만 (누락 방지 — 없는 건 명시적으로 스킵)
        if pre.trades:
            findings.append(detect_revenge(pre, self.config))
            findings.append(detect_overtrading(pre, self.config))
        if pre.sell_events:
            findings.append(detect_disposition(pre, self.config, self.prices))

        diag = diagnose(findings, self.config)
        return PsychReport(findings=findings, diagnosis=diag, preprocessed=pre)

    def analyze_df(self, df: pd.DataFrame) -> PsychReport:
        return self.analyze(trades_from_df(df))


def run(trades: list[Trade] | pd.DataFrame, config: Config | None = None) -> PsychReport:
    agent = PsychAgent(config)
    if isinstance(trades, pd.DataFrame):
        return agent.analyze_df(trades)
    return agent.analyze(trades)
