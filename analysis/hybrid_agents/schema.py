"""Shared contracts for the two new hybrid agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from psych_agent.schema import Preprocessed, TypeFinding


SEVERITY_RANK = {"none": 0, "weak": 1, "moderate": 2, "strong": 3}


@dataclass(frozen=True)
class PsychAssignment:
    """One psych-agent signal assigned to a target domain."""

    type_key: str
    target_agent_id: str
    rationale: str
    included: bool = True


@dataclass
class HybridAgentReport:
    """Machine-readable result returned by a hybrid agent."""

    agent_id: str
    base_agent_id: str
    psych_assignments: list[PsychAssignment]
    findings: list[TypeFinding]
    preprocessed: Preprocessed = field(repr=False)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Return a simple 0-100 score from included psych findings."""
        if not self.findings:
            return 0.0
        strongest = max(SEVERITY_RANK.get(f.severity, 0) for f in self.findings)
        return round((strongest / 3.0) * 100.0, 2)

    @property
    def severity(self) -> str:
        if not self.findings:
            return "none"
        strongest = max(self.findings, key=lambda f: SEVERITY_RANK.get(f.severity, 0))
        return strongest.severity

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "base_agent_id": self.base_agent_id,
            "score": self.score,
            "severity": self.severity,
            "summary": self.summary,
            "psych_assignments": [asdict(a) for a in self.psych_assignments],
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
            "recommendations": self.recommendations,
        }
