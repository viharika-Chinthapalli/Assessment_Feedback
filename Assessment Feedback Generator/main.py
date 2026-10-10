"""
Generate per-student assessment feedback as Google Docs + index subsheet.

Input:  sheet URL + source subsheet name
Output:
  - One Google Doc per student (shareable report)
  - New summary subsheet with scores + google_doc_url (source tab untouched)

Usage:
  python main.py --sheet-url "..." --sheet-name "Viharika_working"
  python main.py --limit 1
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from analyzer import analyze_student  # noqa: E402
from config import Cutoffs  # noqa: E402
from docs_client import create_feedback_doc  # noqa: E402
from feedback_builder import (  # noqa: E402
    OUTPUT_HEADERS,
    build_feedback_document,
    build_output_row,
)
from processor import compute_scores, group_students  # noqa: E402
from sheets_client import read_sheet_as_dicts, write_new_subsheet  # noqa: E402


def _provisional_status(overall: float | None, cutoffs: Cutoffs) -> str | None:
    if overall is None or cutoffs.overall is None:
        return None
    if overall >= cutoffs.overall:
        return "Qualified in this attempt"
    return "Not qualified in this attempt"


def run(
    sheet_url: str,
    sheet_name: str,
    output_title: str | None = None,
    limit: int | None = None,
    skip_docs: bool = False,
) -> dict:
    print(f"Reading '{sheet_name}' (original will not be modified)...", flush=True)
    rows = read_sheet_as_dicts(sheet_url, sheet_name)
    print(f"Loaded {len(rows)} submission row(s).", flush=True)

    students = group_students(rows)
    if limit is not None:
        students = students[:limit]
    print(f"Grouped into {len(students)} student(s).", flush=True)

    cutoffs = Cutoffs.from_env()
    if cutoffs.any_configured():
        print("Using configured cutoffs from .env", flush=True)
    else:
        print("No cutoffs configured — Cleared/Below the bar will show as Cutoff pending.", flush=True)

    out_rows: list[list[str]] = []
    doc_links: list[dict] = []
    failures: list[dict] = []

    for i, student in enumerate(students, start=1):
        print(f"[{i}/{len(students)}] {student.user_name} ({student.user_id}) ...", flush=True)
        try:
            scores = compute_scores(student)
            provisional = _provisional_status(scores.get("overall_score"), cutoffs)
            analysis = analyze_student(student, provisional_status=provisional)
            doc_text = build_feedback_document(student, analysis, cutoffs)
            row = build_output_row(student, analysis, cutoffs, doc_text)

            if not skip_docs:
                created = create_feedback_doc(student, analysis, cutoffs)
                row["google_doc_url"] = created["url"]
                doc_links.append(created)
                print(f"  Doc: {created['url']}", flush=True)
            else:
                row["google_doc_url"] = ""

            out_rows.append([row.get(h, "") for h in OUTPUT_HEADERS])
            time.sleep(0.4)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {"user_id": student.user_id, "user_name": student.user_name, "error": str(exc)}
            )
            print(f"  FAILED: {exc}", flush=True)

    title = output_title or f"Feedback_{sheet_name}"
    written = write_new_subsheet(sheet_url, title, OUTPUT_HEADERS, out_rows)
    print(f"Wrote index tab '{written}' with {len(out_rows)} row(s).", flush=True)
    if failures:
        print(f"{len(failures)} student(s) failed.", flush=True)

    return {
        "status": "ok" if not failures else "partial",
        "output_sheet": written,
        "students_written": len(out_rows),
        "google_docs": doc_links,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate student assessment feedback as Google Docs + index sheet tab."
    )
    parser.add_argument("--sheet-url", help="Google Sheet URL")
    parser.add_argument("--sheet-name", help="Source subsheet / tab name")
    parser.add_argument("--output-sheet", help="Name for the index feedback tab", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N students")
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Only write the index subsheet (no Google Docs)",
    )
    args = parser.parse_args()

    sheet_url = (args.sheet_url or input("Sheet URL: ").strip()).strip()
    sheet_name = (args.sheet_name or input("Sub sheet name: ").strip()).strip()
    if not sheet_url or not sheet_name:
        raise SystemExit("sheet URL and sub sheet name are required")

    result = run(
        sheet_url,
        sheet_name,
        output_title=args.output_sheet,
        limit=args.limit,
        skip_docs=args.skip_docs,
    )
    print(result)
    if result.get("failures"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
