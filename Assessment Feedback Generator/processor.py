"""Group submissions by student/section, extract section scores once, validate data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from config import (
    CS_MCQ,
    DSA_CODING,
    QUESTION_TYPE_MAP,
    SECTION_META,
    SECTION_ORDER,
    SQL_CODING,
    SQL_MCQ,
)
from mcq_classify import EXPECTED_CS_MCQ, EXPECTED_SQL_MCQ, split_mcqs
from topics import mcq_correct_count


def _section_score_from_questions(questions: list[QuestionRecord]) -> tuple[float | None, list[str]]:
    """
    Section total for questions assigned to this section:
    1) Prefer unique user_exam_attempt_score on those rows (already the section total).
    2) Else majority sheet score if nearly unique.
    3) Else correct-count (1 mark each).
    """
    flags: list[str] = []
    if not questions:
        return 0.0, ["No questions in this section"]

    sheet_vals = [
        round(q.sheet_section_score, 4)
        for q in questions
        if q.sheet_section_score is not None
    ]
    unique = sorted(set(sheet_vals))
    derived = float(mcq_correct_count(questions))

    if len(unique) == 1:
        flags.append(
            f"Section score from sheet={unique[0]} "
            f"(rows={len(questions)}, correct-count={int(derived)})"
        )
        return float(unique[0]), flags

    if len(unique) > 1:
        # Majority vote on sheet score within the bucket
        from collections import Counter

        counts = Counter(sheet_vals)
        majority_score, majority_n = counts.most_common(1)[0]
        if majority_n >= max(1, int(0.7 * len(sheet_vals))):
            flags.append(
                f"Section score from majority sheet value={majority_score} "
                f"({majority_n}/{len(sheet_vals)} rows); also saw {unique}"
            )
            return float(majority_score), flags
        flags.append(
            f"Inconsistent sheet scores {unique}; using correct-count {int(derived)}/{len(questions)}"
        )
        return derived, flags

    flags.append(f"Score from correct count {int(derived)}/{len(questions)} (1 mark each)")
    return derived, flags


@dataclass
class QuestionRecord:
    question_id: str
    question_content: str
    question_type_raw: str
    section: str
    evaluation_result: str
    response_options: str
    submission_datetime: str
    code_content: str
    code_language: str
    sheet_section_score: float | None = None  # user_exam_attempt_score from that row


@dataclass
class SectionData:
    section: str
    score: float | None
    score_inconsistent: bool
    questions: list[QuestionRecord] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class StudentData:
    user_id: str
    user_name: str
    sections: dict[str, SectionData] = field(default_factory=dict)
    assessment_date: str | None = None
    flags: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _is_mcq_type(question_type: str) -> bool:
    key = _norm(question_type).replace(" ", "_").replace("-", "_")
    return key == "mcq" or "mcq" in key


def map_coding_section(question_type: str) -> str | None:
    key = _norm(question_type).replace(" ", "_").replace("-", "_")
    mapped = QUESTION_TYPE_MAP.get(key)
    if mapped in (DSA_CODING, SQL_CODING):
        return mapped
    if "dsa" in key and "cod" in key:
        return DSA_CODING
    if "sql" in key and "cod" in key:
        return SQL_CODING
    return None


def _parse_score(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw or raw.lower() in ("none", "null", "n/a", "-"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _pick_assessment_date(datetimes: list[str]) -> str | None:
    parsed: list[datetime] = []
    for raw in datetimes:
        raw = (raw or "").strip()
        if not raw or raw.lower() == "none":
            continue
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                parsed.append(
                    datetime.strptime(raw[:19], fmt)
                    if len(raw) >= 10
                    else datetime.strptime(raw, fmt)
                )
                break
            except ValueError:
                continue
    if not parsed:
        return None
    return max(parsed).strftime("%d %B %Y")


def _get(row: dict[str, str], *names: str) -> str:
    lower_map = {_norm(k): v for k, v in row.items()}
    for name in names:
        if _norm(name) in lower_map:
            return lower_map[_norm(name)]
    return ""


def _dedupe_questions(questions: list[QuestionRecord]) -> tuple[list[QuestionRecord], list[str]]:
    by_qid: dict[str, QuestionRecord] = {}
    flags: list[str] = []
    for q in questions:
        key = q.question_id or str(id(q))
        if key not in by_qid:
            by_qid[key] = q
            continue
        prev = by_qid[key]
        if (q.code_content or q.response_options) and not (
            prev.code_content or prev.response_options
        ):
            by_qid[key] = q
        flags.append(f"Duplicate question_id {q.question_id}")
    return list(by_qid.values()), flags


def _unique_sheet_score(values: list[float]) -> tuple[float | None, bool]:
    unique = sorted(set(round(s, 4) for s in values))
    if not unique:
        return None, False
    if len(unique) > 1:
        return unique[0], True
    return unique[0], False


def group_students(rows: list[dict[str, str]]) -> list[StudentData]:
    by_user: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        uid = _get(row, "user_id")
        if not uid:
            continue
        by_user[uid].append(row)

    students: list[StudentData] = []
    for user_id, user_rows in by_user.items():
        name = _get(user_rows[0], "user_name") or "Unknown"
        student = StudentData(user_id=user_id, user_name=name)

        coding_score_values: dict[str, list[float]] = defaultdict(list)
        pending_mcqs: list[QuestionRecord] = []
        all_dts: list[str] = []

        for row in user_rows:
            q_type = _get(row, "question_type")
            content = _get(row, "question_content")
            score = _parse_score(_get(row, "user_exam_attempt_score"))
            rec = QuestionRecord(
                question_id=_get(row, "question_id"),
                question_content=content,
                question_type_raw=q_type,
                section="",  # filled below
                evaluation_result=_get(row, "candidate_evaluation_result"),
                response_options=_get(row, "candidate_response_options"),
                submission_datetime=_get(row, "submission_datetime"),
                code_content=_get(row, "code_content"),
                code_language=_get(row, "code_language"),
                sheet_section_score=score,
            )
            all_dts.append(rec.submission_datetime)

            if _is_mcq_type(q_type):
                pending_mcqs.append(rec)
                continue

            section = map_coding_section(q_type)
            if section is None:
                student.flags.append(
                    f"Unmapped question_type '{q_type}' for question_id={rec.question_id}"
                )
                continue

            rec.section = section
            if score is not None:
                coding_score_values[section].append(score)
            if section not in student.sections:
                student.sections[section] = SectionData(
                    section=section, score=None, score_inconsistent=False
                )
            student.sections[section].questions.append(rec)

        # --- Classify each MCQ by content (SQL vs CS), not top-N ---
        pending_mcqs, mcq_dup_flags = _dedupe_questions(pending_mcqs)
        student.flags.extend(mcq_dup_flags)

        sql_mcqs, cs_mcqs, split_method = split_mcqs(pending_mcqs)
        student.flags.append(
            f"MCQ split ({split_method}): SQL MCQs={len(sql_mcqs)} "
            f"(expected ~{EXPECTED_SQL_MCQ}), CS Fundamentals={len(cs_mcqs)} "
            f"(expected ~{EXPECTED_CS_MCQ})"
        )

        for q in sql_mcqs:
            q.section = SQL_MCQ
        for q in cs_mcqs:
            q.section = CS_MCQ

        sql_score, sql_flags = _section_score_from_questions(sql_mcqs)
        cs_score, cs_flags = _section_score_from_questions(cs_mcqs)

        sql_score = min(sql_score or 0.0, float(SECTION_META[SQL_MCQ]["max_marks"]))
        cs_score = min(cs_score or 0.0, float(SECTION_META[CS_MCQ]["max_marks"]))

        student.sections[SQL_MCQ] = SectionData(
            section=SQL_MCQ,
            score=sql_score,
            score_inconsistent=False,
            questions=sql_mcqs,
            flags=sql_flags,
        )
        student.sections[CS_MCQ] = SectionData(
            section=CS_MCQ,
            score=cs_score,
            score_inconsistent=False,
            questions=cs_mcqs,
            flags=cs_flags,
        )

        # --- Coding sections: use user_exam_attempt_score once ---
        for section_key in (DSA_CODING, SQL_CODING):
            meta = SECTION_META[section_key]
            sec = student.sections.get(section_key)
            if sec is None:
                student.sections[section_key] = SectionData(
                    section=section_key,
                    score=None,
                    score_inconsistent=False,
                    flags=[f"No records found for {meta['label']}"],
                )
                continue

            qs, dup_flags = _dedupe_questions(sec.questions)
            sec.questions = qs
            sec.flags.extend(dup_flags)

            sheet_score, inconsistent = _unique_sheet_score(
                coding_score_values.get(section_key, [])
            )
            sec.score = sheet_score
            sec.score_inconsistent = inconsistent
            if sheet_score is None:
                sec.flags.append("Section score missing (user_exam_attempt_score empty)")
            elif inconsistent:
                sec.flags.append(
                    f"Inconsistent section scores across rows — using {sheet_score}"
                )

            if len(sec.questions) != meta["expected_questions"]:
                sec.flags.append(
                    f"Expected {meta['expected_questions']} questions, found {len(sec.questions)}"
                )

        for key, expected in ((SQL_MCQ, EXPECTED_SQL_MCQ), (CS_MCQ, EXPECTED_CS_MCQ)):
            sec = student.sections[key]
            n = len(sec.questions)
            if n and abs(n - expected) > 3:
                sec.flags.append(f"Expected about {expected} questions, classified {n}")

        student.assessment_date = _pick_assessment_date(all_dts)
        students.append(student)

    students.sort(key=lambda s: (s.user_name.lower(), s.user_id))
    return students


def compute_scores(student: StudentData) -> dict:
    """Build score summary without double-counting section scores."""
    detail = {}
    overall = 0.0
    missing = False
    for key in SECTION_ORDER:
        meta = SECTION_META[key]
        sec = student.sections.get(key)
        qcount = len(sec.questions) if sec else 0
        score = sec.score if sec else None
        if score is None and qcount == 0 and key in (CS_MCQ, SQL_MCQ):
            score = 0.0
        if score is None:
            missing = True
            pct = None
        else:
            overall += score
            pct = round((score / meta["max_marks"]) * 100, 2) if meta["max_marks"] else None
        detail[key] = {
            "label": meta["label"],
            "score": score,
            "max_marks": meta["max_marks"],
            "percentage": pct,
            "question_count": qcount,
            "expected_questions": meta["expected_questions"],
            "flags": list(sec.flags) if sec else [],
            "score_inconsistent": bool(sec and sec.score_inconsistent),
        }

    return {
        "detail": detail,
        "overall_score": None if missing else round(overall, 2),
        "overall_max": 190,
        "overall_percentage": None if missing else round((overall / 190) * 100, 2),
        "incomplete_scores": missing,
    }
