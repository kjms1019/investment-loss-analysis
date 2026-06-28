from pathlib import Path

from src.data_quality import build_data_quality_report
from src.data_loader import load_tiny_mock_data, summarize_rows
from src.entry_classifier import build_entry_classification_result
from src.feature_engineering import build_feature_result
from src.schema_mapper import (
    MARKET_REQUIRED_COLUMNS,
    TRADE_REQUIRED_COLUMNS,
    validate_required_columns,
)


REQUIRED_PATHS = [
    "README.md",
    "AGENTS.md",
    "SPEC.md",
    "requirements.txt",
    "src",
    "src/data_loader.py",
    "src/data_quality.py",
    "src/schema_mapper.py",
    "src/feature_engineering.py",
    "src/entry_classifier.py",
    "sample_data",
    "sample_data/tiny_mock.csv",
    "reports",
]


def find_missing_project_paths(project_root):
    """Return required project files or folders that do not exist."""
    return [
        required_path
        for required_path in REQUIRED_PATHS
        if not (project_root / required_path).exists()
    ]


def print_missing_project_paths(missing_paths):
    """Print missing project files or folders."""
    print("Missing required files or folders:")
    print()
    for missing_path in missing_paths:
        print("* {0}".format(missing_path))


def print_schema_failure(missing_trade_columns, missing_market_columns):
    """Print missing standard schema columns."""
    print("Schema check: failed")
    print("Missing trade columns:")
    print()
    for column in missing_trade_columns:
        print("* {0}".format(column))
    print("Missing market columns:")
    for column in missing_market_columns:
        print("* {0}".format(column))


def print_data_quality_failure(data_quality_report):
    """Print a compact data quality failure summary."""
    print("Data quality check: failed")
    print("Data quality score: {0:.2f}".format(data_quality_report["quality_score"]))
    print("Errors:")
    print()
    for error in data_quality_report["errors"]:
        print(
            "* row {0}: {1}".format(
                error["row_index"] + 1,
                error["error_type"],
            )
        )


def main():
    """Check project structure, mock CSV schema, and data quality."""
    project_root = Path(__file__).resolve().parent
    missing_paths = find_missing_project_paths(project_root)

    if missing_paths:
        print_missing_project_paths(missing_paths)
        return

    rows = load_tiny_mock_data(project_root)
    summary = summarize_rows(rows)
    first_row = summary["first_row"] or {}

    missing_trade_columns = validate_required_columns(
        first_row, TRADE_REQUIRED_COLUMNS
    )
    missing_market_columns = validate_required_columns(
        first_row, MARKET_REQUIRED_COLUMNS
    )

    if missing_trade_columns or missing_market_columns:
        print_schema_failure(missing_trade_columns, missing_market_columns)
        return

    data_quality_report = build_data_quality_report(rows)

    print("Project structure is ready.")
    print("Mock CSV rows: {0}".format(summary["row_count"]))
    print("Schema check: passed")

    if data_quality_report["has_errors"]:
        print_data_quality_failure(data_quality_report)
        return

    print("Data quality check: passed")
    print("Data quality score: {0:.1f}".format(data_quality_report["quality_score"]))

    feature_result = build_feature_result(first_row)
    feature_keys = [
        key
        for key in feature_result["features"].keys()
        if key not in ["feature_scope", "look_ahead_warning"]
    ]
    print("Feature status: {0}".format(feature_result["feature_status"]))
    print("Feature keys: {0}".format(", ".join(feature_keys)))

    classification_result = build_entry_classification_result(
        feature_result,
        data_quality_report=data_quality_report,
    )
    triggered_labels = [
        label_result
        for label_result in classification_result["label_results"]
        if label_result.get("triggered")
    ]
    print(
        "Classification status: {0}".format(
            classification_result["classification_status"]
        )
    )
    print(
        "Primary state: {0}".format(
            classification_result["state_classification"]["primary_state"]
        )
    )
    print("Triggered labels: {0}".format(len(triggered_labels)))
    print(
        "Protected features: {0}".format(
            ", ".join(classification_result["protected_features"])
        )
    )

    if triggered_labels:
        print("Triggered label details:")
        print()
        for label_result in triggered_labels:
            print(
                "* {0}: confidence={1:.2f}".format(
                    label_result["label_id"],
                    label_result["confidence"],
                )
            )

    risk_score_result = classification_result["risk_score_result"]
    print("Risk score: {0}".format(risk_score_result["entry_error_risk_score"]))
    print("Severity: {0}".format(risk_score_result["severity"]))
    print("Score status: {0}".format(risk_score_result["score_status"]))

    if risk_score_result["contributions"]:
        print("Score contributions:")
        print()
        for contribution in risk_score_result["contributions"]:
            print(
                "* {0}: contribution={1}".format(
                    contribution["label_id"],
                    contribution["contribution_to_score"],
                )
            )


if __name__ == "__main__":
    main()
