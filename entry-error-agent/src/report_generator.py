"""Report generation placeholders.

Future versions will produce both machine-readable JSON and natural-language
review reports for completed trades.
"""


REPORT_FIELDS = [
    "trade_id",
    "symbol",
    "analysis_version",
    "analyzable",
    "analysis_status",
    "insufficient_reasons",
    "data_quality",
    "input_snapshot",
    "derived_features",
    "state_classification",
    "label_results",
    "rejected_labels_with_reason",
    "entry_error_risk_score",
    "severity",
    "summary",
    "review_rules",
    "disclaimers",
]

DEFAULT_DISCLAIMER = (
    "This report is a post-trade review for learning purposes only. "
    "It is not investment advice or a real-time trading recommendation."
)

REPORT_TEMPLATE = {
    "trade_id": None,
    "symbol": None,
    "analysis_version": None,
    "analyzable": None,
    "analysis_status": None,
    "insufficient_reasons": [],
    "data_quality": {},
    "input_snapshot": {},
    "derived_features": {},
    "state_classification": {},
    "label_results": [],
    "rejected_labels_with_reason": [],
    "entry_error_risk_score": None,
    "severity": None,
    "summary": None,
    "review_rules": [],
    "disclaimers": [DEFAULT_DISCLAIMER],
}


def build_json_report(analysis_result):
    """Build a JSON-ready report dictionary.

    Args:
        analysis_result: Future structured result from the classifier.

    TODO: Implement once analysis_result structure is defined.
    """
    raise NotImplementedError("JSON report generation is not implemented yet.")


def build_narrative_report(analysis_result):
    """Build a natural-language review report.

    Args:
        analysis_result: Future structured result from the classifier.

    TODO: Implement after the JSON report structure is stable.
    """
    raise NotImplementedError("Narrative report generation is not implemented yet.")
