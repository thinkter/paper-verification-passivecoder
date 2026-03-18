from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scraper import ExamCookerScraper
from .service import AuditService
from .settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit ExamCooker papers with OCR.")
    parser.add_argument("--limit", type=int, default=None, help="Only scan the first N papers.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final JSON payload after the scan completes.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    settings, paths = load_settings(Path.cwd())
    service = AuditService(settings=settings, paths=paths, scraper=ExamCookerScraper(settings))

    def on_progress(event: dict) -> None:
        if event["stage"] == "listing":
            print(event["message"])
            return
        print(
            f"Checked {event['checked']}/{event['total']} papers "
            f"(invalid: {event['invalid']})"
        )

    result = service.run_scan(limit=args.limit, progress=on_progress)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(
            f"Finished. Invalid papers: {result.summary.invalid_papers} "
            f"of {result.summary.checked_papers}. Results saved to {paths.latest_result_path}"
        )
