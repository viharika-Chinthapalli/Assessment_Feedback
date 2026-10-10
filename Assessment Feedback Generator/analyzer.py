"""Evidence-based coding + MCQ analysis per student (LLM-assisted, data-grounded)."""

from __future__ import annotations

import json

from config import CS_MCQ, DSA_CODING, SECTION_META, SECTION_ORDER, SQL_CODING, SQL_MCQ
from llm_client import chat_json
from processor import StudentData, compute_scores
from topics import build_topic_stats


def _mcq_stats(student: StudentData, section: str) -> dict:
    sec = student.sections.get(section)
    if not sec:
        return {"correct": 0, "incorrect": 0, "unanswered": 0, "unavailable": 0, "incorrect_samples": []}
    correct = incorrect = unanswered = unavailable = 0
    incorrect_samples = []
    for q in sec.questions:
        result = (q.evaluation_result or "").strip().upper()
        options = (q.response_options or "").strip()
        if result in ("CORRECT", "TRUE", "RIGHT"):
            correct += 1
            status = "CORRECT"
        elif result in ("INCORRECT", "FALSE", "WRONG"):
            incorrect += 1
            status = "INCORRECT"
            if len(incorrect_samples) < 12:
                incorrect_samples.append(
                    {
                        "question_snippet": (q.question_content or "")[:180],
                        "selected": options[:80],
                        "result": status,
                    }
                )
        elif not options or options.lower() in ("none", "[]", "null"):
            unanswered += 1
        else:
            unavailable += 1
    return {
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "unavailable": unavailable,
        "incorrect_samples": incorrect_samples,
    }


def _coding_payload(student: StudentData, section: str) -> list[dict]:
    sec = student.sections.get(section)
    if not sec:
        return []
    out = []
    for q in sec.questions:
        out.append(
            {
                "question_id": q.question_id,
                "question_content": (q.question_content or "")[:1200],
                "code_language": q.code_language or "unknown",
                "code_content": (q.code_content or "")[:2500],
                "submission_datetime": q.submission_datetime,
                "has_code": bool((q.code_content or "").strip()),
            }
        )
    return out


def build_analysis_context(student: StudentData) -> dict:
    scores = compute_scores(student)
    topic_rows = build_topic_stats(student)
    return {
        "student": {"user_id": student.user_id, "user_name": student.user_name, "date": student.assessment_date},
        "scores": scores,
        "topic_rows_computed": topic_rows,
        "dsa_coding": _coding_payload(student, DSA_CODING),
        "sql_coding": _coding_payload(student, SQL_CODING),
        "cs_mcq": _mcq_stats(student, CS_MCQ),
        "sql_mcq": _mcq_stats(student, SQL_MCQ),
        "data_flags": student.flags
        + [f"{SECTION_META[k]['label']}: {f}" for k in SECTION_ORDER for f in (student.sections.get(k).flags if student.sections.get(k) else [])],
    }


SYSTEM_PROMPT = """You write polished Nxtwave Edge 2.0 assessment coaching feedback.

Rules (critical):
- Use ONLY the provided scores, topic_rows_computed levels, coding attempt signals, and MCQ correct/incorrect counts.
- Never invent scores, cutoffs, or question text. Never quote problems, options, IDs, or code.
- Tone: calm, professional, encouraging, specific — like a senior coach, not a rubric dump.

NARRATIVE STYLE (match this depth; write original wording, do not copy stock phrases):
Each bullet should be 1–3 full sentences. Mention real scores as "X out of Y" when available.
Name concrete topics from topic_rows_computed (e.g. Polymorphism, Normalization, Graph Traversal, CPU Scheduling).

what_went_well — 3 to 5 bullets covering:
- Sections that held up, with score (e.g. SQL / CS Fundamentals) and which topics carried them (Strong/Partial).
- Coding basics if submissions show working attempts on opening problems.
- Any clear bright spots in OOPS, DBMS, OS, Networks, SQL, or DSA topics.

where_you_lost_marks — 3 to 5 bullets covering:
- The main shortfall section with score (especially DSA Coding if low).
- Pattern of unattempted vs attempted coding topics.
- Uneven fundamentals (e.g. strong OOPS/DBMS, weak Computer Networks / Memory Management) and how that pulls the section down.

what_to_work_on_next — 4 to 6 actionable bullets covering:
- Specific topic drills (Graphs: BFS/DFS then shortest path; DP: recursion → memo → table; Networks: layers, TCP vs UDP, URL journey).
- Study method that is practical and timed.
- Testing habit before submit (empty / single / max constraint cases) when coding was weak.
- Prioritise Needs work / Not Attempted topics from topic_rows_computed.

Return JSON:
{
  "result_line": "Result — <short status grounded in data; no invented pass/fail unless provisional_status given>",
  "what_went_well": ["long professional bullet", "..."],
  "where_you_lost_marks": ["long professional bullet", "..."],
  "what_to_work_on_next": ["long actionable bullet", "..."],
  "final_summary": "2-3 encouraging sentences naming the top priority topics",
  "data_limitations": ["only if needed"]
}
"""


def analyze_student(student: StudentData, provisional_status: str | None = None) -> dict:
    ctx = build_analysis_context(student)
    # Compact score view for the model (display-style)
    scores = ctx["scores"]
    detail = scores.get("detail") or {}
    dsa = detail.get(DSA_CODING) or {}
    sql_c = detail.get(SQL_CODING) or {}
    sql_m = detail.get(SQL_MCQ) or {}
    cs = detail.get(CS_MCQ) or {}
    sql_combined = None
    if sql_c.get("score") is not None and sql_m.get("score") is not None:
        sql_combined = round(float(sql_c["score"]) + float(sql_m["score"]), 2)
    elif sql_c.get("score") is not None:
        sql_combined = float(sql_c["score"])
    elif sql_m.get("score") is not None:
        sql_combined = float(sql_m["score"])

    user = {
        "provisional_status": provisional_status,
        "score_snapshot": {
            "overall": scores.get("overall_score"),
            "overall_max": 190,
            "dsa_coding": {"score": dsa.get("score"), "max": 120},
            "sql_combined": {"score": sql_combined, "max": 30},
            "cs_fundamentals": {"score": cs.get("score"), "max": 40},
        },
        "topic_rows_computed": ctx["topic_rows_computed"],
        "coding_signals": {
            "dsa": [
                {
                    "language": x.get("code_language"),
                    "has_code": x.get("has_code"),
                    "topic_hint_from_content_only_for_you": True,
                }
                for x in ctx["dsa_coding"]
            ],
            "sql": [{"has_code": x.get("has_code"), "language": x.get("code_language")} for x in ctx["sql_coding"]],
        },
        "mcq_counts": {
            "cs": {k: ctx["cs_mcq"][k] for k in ("correct", "incorrect", "unanswered")},
            "sql": {k: ctx["sql_mcq"][k] for k in ("correct", "incorrect", "unanswered")},
        },
        "instructions": (
            "Write detailed coaching bullets like a finished student report. "
            "Use score_snapshot numbers and topic_rows_computed topic names/levels. "
            "Original professional wording only — do not paste generic templates."
        ),
    }
    result = chat_json(SYSTEM_PROMPT, json.dumps(user, ensure_ascii=False))
    # Always use deterministic detailed topics in the student document
    result["topic_rows"] = ctx["topic_rows_computed"]
    result["_scores"] = ctx["scores"]
    result["_mcq"] = {"cs": ctx["cs_mcq"], "sql": ctx["sql_mcq"]}
    result["_flags"] = ctx["data_flags"]
    return result
