"""Build student-facing feedback document matching the Nxtwave Edge 2.0 sample report."""

from __future__ import annotations

from config import (
    ASSESSMENT_META,
    CS_MCQ,
    Cutoffs,
    DISPLAY_SECTIONS,
    DSA_CODING,
    SQL_CODING,
    SQL_MCQ,
)
from processor import StudentData


def _fmt_score(score: float | None) -> str:
    if score is None:
        return "N/A"
    if abs(score - round(score)) < 1e-9:
        return str(int(round(score)))
    return f"{score:.2f}".rstrip("0").rstrip(".")


def _section_score(scores: dict, key: str) -> float | None:
    detail = scores.get("detail", {}).get(key, {})
    return detail.get("score")


def _display_rows(scores: dict, cutoffs: Cutoffs) -> list[dict]:
    rows = []
    for block in DISPLAY_SECTIONS:
        total = 0.0
        missing = False
        for src in block["source_sections"]:
            detail = scores.get("detail", {}).get(src, {})
            s = detail.get("score")
            qcount = detail.get("question_count", 0) or 0
            # Empty optional part (e.g. no SQL MCQ rows) counts as 0
            if s is None and qcount == 0 and src in (SQL_MCQ, CS_MCQ):
                s = 0.0
            if s is None:
                missing = True
            else:
                total += s
        score = None if missing else round(total, 2)
        if score is not None:
            cutoff = None
            if block["key"] == "dsa":
                cutoff = cutoffs.dsa
            elif block["key"] == "sql":
                cutoff = cutoffs.sql_combined
            elif block["key"] == "cs":
                cutoff = cutoffs.cs
            if cutoff is not None:
                status = "Cleared" if score >= cutoff else "Below the bar"
            else:
                status = "Cutoff pending"
        else:
            status = "Score unavailable"
        rows.append(
            {
                "label": block["label"],
                "score": score,
                "max_marks": block["max_marks"],
                "status": status,
            }
        )
    return rows


def _overall_status(overall: float | None, cutoffs: Cutoffs) -> str:
    if overall is None:
        return "Score incomplete — validation needed"
    if cutoffs.overall is None:
        return "Provisional review (overall cutoff not configured)"
    if overall >= cutoffs.overall:
        return "Qualified in this attempt"
    return "Not qualified in this attempt"


def build_feedback_document(
    student: StudentData,
    analysis: dict,
    cutoffs: Cutoffs,
) -> str:
    """Layout mirrors the Nxtwave Edge 2.0 sample Word feedback form."""
    scores = analysis.get("_scores") or {}
    overall = scores.get("overall_score")
    display = _display_rows(scores, cutoffs)
    status_line = _overall_status(overall, cutoffs)

    if analysis.get("result_line"):
        result_line = analysis["result_line"].strip()
        if not result_line.lower().startswith("result"):
            result_line = f"Result — {result_line}"
    else:
        result_line = f"Result — {status_line}"

    lines: list[str] = []
    lines.append(ASSESSMENT_META["title"])
    lines.append("")
    lines.append("Your Assessment Report")
    lines.append(ASSESSMENT_META["duration_label"])
    lines.append("")
    lines.append(f"Learner: {student.user_name}")
    lines.append(f"Assessment date: {student.assessment_date or 'Not available'}")
    lines.append("")
    lines.append(result_line)
    lines.append(f"You scored {_fmt_score(overall)} out of {scores.get('overall_max', 190)}.")
    lines.append("")
    lines.append("Your scores")
    lines.append("")
    lines.append("Section\tYour score\tOut of\tStatus")
    for i, row in enumerate(display, start=1):
        lines.append(
            f"{i}. {row['label']}\t{_fmt_score(row['score'])}\t{row['max_marks']}\t{row['status']}"
        )
    lines.append(
        f"Total\t{_fmt_score(overall)}\t{scores.get('overall_max', 190)}\t{status_line}"
    )
    lines.append("")
    lines.append("Status is Cleared or Below the bar for each section.")
    lines.append("")
    lines.append("Where you stood, topic by topic")
    lines.append("")
    lines.append(
        "Each topic below is marked Strong, Partial, Needs work or Not Attempted, "
        "based on the marks you scored in that part of the paper."
    )
    lines.append("")
    lines.append("Section\tTopic area\tYour level")
    for row in analysis.get("topic_rows") or []:
        lines.append(
            f"{row.get('section', '')}\t{row.get('topic_area', '')}\t{row.get('level', '')}"
        )
    lines.append("")
    lines.append("Highlights from this attempt")
    lines.append("")
    for bullet in analysis.get("what_went_well") or [
        "No clear topic strengths could be evidenced from available data."
    ]:
        lines.append(f"• {bullet}")
    lines.append("")
    lines.append("Where the score slipped")
    lines.append("")
    for bullet in analysis.get("where_you_lost_marks") or [
        "Key areas to improve could not be determined from available data."
    ]:
        lines.append(f"• {bullet}")
    lines.append("")
    lines.append("Focus plan for your next attempt")
    lines.append("")
    for bullet in analysis.get("what_to_work_on_next") or [
        "Focus on the weaker topic areas listed above."
    ]:
        lines.append(f"• {bullet}")
    lines.append("")
    lines.append("About this report: Scores are generated from your submitted answers and are final.")

    return "\n".join(lines)


def build_output_row(
    student: StudentData,
    analysis: dict,
    cutoffs: Cutoffs,
    feedback_text: str,
) -> dict[str, str]:
    scores = analysis.get("_scores") or {}
    display = _display_rows(scores, cutoffs)
    dsa, sql, cs = display[0], display[1], display[2]
    detail = scores.get("detail", {})

    return {
        "user_id": student.user_id,
        "user_name": student.user_name,
        "assessment_date": student.assessment_date or "",
        "overall_score": _fmt_score(scores.get("overall_score")),
        "overall_max": "190",
        "overall_percentage": _fmt_score(scores.get("overall_percentage")),
        "result_status": _overall_status(scores.get("overall_score"), cutoffs),
        "dsa_score": _fmt_score(dsa["score"]),
        "dsa_max": str(dsa["max_marks"]),
        "dsa_status": dsa["status"],
        "sql_combined_score": _fmt_score(sql["score"]),
        "sql_combined_max": str(sql["max_marks"]),
        "sql_combined_status": sql["status"],
        "cs_score": _fmt_score(cs["score"]),
        "cs_max": str(cs["max_marks"]),
        "cs_status": cs["status"],
        "dsa_coding_score": _fmt_score(detail.get(DSA_CODING, {}).get("score")),
        "sql_coding_score": _fmt_score(detail.get(SQL_CODING, {}).get("score")),
        "cs_mcq_score": _fmt_score(detail.get(CS_MCQ, {}).get("score")),
        "sql_mcq_score": _fmt_score(detail.get(SQL_MCQ, {}).get("score")),
        "what_went_well": " | ".join(analysis.get("what_went_well") or []),
        "where_you_lost_marks": " | ".join(analysis.get("where_you_lost_marks") or []),
        "what_to_work_on_next": " | ".join(analysis.get("what_to_work_on_next") or []),
        "final_summary": analysis.get("final_summary") or "",
        "data_flags": " | ".join(analysis.get("_flags") or []),
        "google_doc_url": "",
        "feedback_document": feedback_text,
    }


OUTPUT_HEADERS = [
    "user_id",
    "user_name",
    "assessment_date",
    "overall_score",
    "overall_max",
    "overall_percentage",
    "result_status",
    "dsa_score",
    "dsa_max",
    "dsa_status",
    "sql_combined_score",
    "sql_combined_max",
    "sql_combined_status",
    "cs_score",
    "cs_max",
    "cs_status",
    "dsa_coding_score",
    "sql_coding_score",
    "cs_mcq_score",
    "sql_mcq_score",
    "what_went_well",
    "where_you_lost_marks",
    "what_to_work_on_next",
    "final_summary",
    "data_flags",
    "google_doc_url",
    "feedback_document",
]
