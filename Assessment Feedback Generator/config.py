"""Assessment structure, section mapping, and configurable cutoffs."""

from __future__ import annotations

import os
from dataclasses import dataclass

# --- Section keys used internally ---
DSA_CODING = "DSA_Coding"
SQL_CODING = "SQL_Coding"
CS_MCQ = "CS_Fundamentals_MCQ"
SQL_MCQ = "SQL_MCQ"

SECTION_ORDER = [DSA_CODING, SQL_CODING, CS_MCQ, SQL_MCQ]

SECTION_META = {
    DSA_CODING: {
        "label": "DSA Coding",
        "max_marks": 120,
        "expected_questions": 4,
        "duration": "1 hour 30 minutes",
    },
    SQL_CODING: {
        "label": "SQL Coding",
        "max_marks": 15,
        "expected_questions": 1,
        "duration": "15 minutes",
    },
    CS_MCQ: {
        "label": "Core CS Fundamentals MCQs",
        "max_marks": 40,
        "expected_questions": 40,
        "duration": "30 minutes",
    },
    SQL_MCQ: {
        "label": "SQL MCQs",
        "max_marks": 15,
        "expected_questions": 15,
        "duration": "15 minutes",
    },
}

TOTAL_MAX_MARKS = 190
ASSESSMENT_META = {
    "title": "NXTWAVE EDGE 2.0 ASSESSMENT FEEDBACK",
    "duration_label": "150 minutes • 3 sections • 190 marks",
}

# Display grouping for student-facing score table (matches sample form):
# SQL Coding + SQL MCQs → "SQL" out of 30
DISPLAY_SECTIONS = [
    {
        "key": "dsa",
        "label": "DSA Coding",
        "source_sections": [DSA_CODING],
        "max_marks": 120,
    },
    {
        "key": "sql",
        "label": "SQL",
        "source_sections": [SQL_CODING, SQL_MCQ],
        "max_marks": 30,
    },
    {
        "key": "cs",
        "label": "CS Fundamentals",
        "source_sections": [CS_MCQ],
        "max_marks": 40,
    },
]

# Sheet question_type → coding sections
QUESTION_TYPE_MAP = {
    "dsa_coding": DSA_CODING,
    "sql_coding": SQL_CODING,
    "mcq": "MCQ",  # further split by content
}


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass
class Cutoffs:
    """Optional section cutoffs. None = do not label Cleared / Below the bar."""

    dsa: float | None = None
    sql_combined: float | None = None  # out of 30 (coding + MCQ)
    cs: float | None = None
    overall: float | None = None  # out of 190

    @classmethod
    def from_env(cls) -> "Cutoffs":
        return cls(
            dsa=_env_float("CUTOFF_DSA"),
            sql_combined=_env_float("CUTOFF_SQL"),
            cs=_env_float("CUTOFF_CS"),
            overall=_env_float("CUTOFF_OVERALL"),
        )

    def any_configured(self) -> bool:
        return any(v is not None for v in (self.dsa, self.sql_combined, self.cs, self.overall))


# Keywords used to classify MCQ rows into SQL MCQs vs Core CS Fundamentals.
# Keep conceptual DBMS/OS/OOP/Networks in CS; use query-oriented cues for SQL MCQs.
SQL_MCQ_KEYWORDS = (
    "sql",
    "select ",
    "select*",
    "inner join",
    "left join",
    "right join",
    "full join",
    "cross join",
    "group by",
    "order by",
    "having ",
    "where clause",
    "aggregate function",
    "subquery",
    "nested query",
    "common table expression",
    "cte",
    "window function",
    "over (",
    "rank()",
    "dense_rank",
    "insert into",
    "update ",
    "delete from",
    "which query",
    "write a query",
    "sql query",
)
