"""리포트 생성 CLI 진입점.

사용 예:
    python -m analysis.report.run --run-id <run_id>
"""

from __future__ import annotations

import argparse

from . import builder, formatter


def main() -> None:
    parser = argparse.ArgumentParser(description="손실 진단 리포트 생성")
    parser.add_argument("--run-id", help="orchestrator run_id 기준 리포트")
    parser.add_argument("--user-id", help="user_id 기준 리포트 (TODO: query.fetch_results_for_user 구현 필요)")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    if not args.run_id and not args.user_id:
        parser.error("--run-id 또는 --user-id 중 하나는 필요합니다")

    if args.run_id:
        summary = builder.build_run_summary(args.run_id)
    else:
        summary = builder.build_user_summary(args.user_id)

    output = formatter.to_json(summary) if args.format == "json" else formatter.to_markdown(summary)
    print(output)


if __name__ == "__main__":
    main()
