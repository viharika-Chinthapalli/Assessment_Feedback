"""
Split unlabeled MCQs into SQL MCQs vs CS Fundamentals.

Primary signal: user_exam_attempt_score on the sheet already encodes the section
(e.g. 40 rows sharing score 26 = CS; 15 rows sharing score 9 = SQL).

Fallback: content keywords when sheet scores do not partition cleanly.
"""

from __future__ import annotations

import re
from collections import defaultdict

EXPECTED_SQL_MCQ = 15
EXPECTED_CS_MCQ = 40

_CS_FORCE = (
    "operating system", "deadlock", "semaphore", "mutex", "paging", "virtual memory",
    "cpu scheduling", "round robin", "context switch", "system call", "inode",
    "process synchronization", "thread", "pcb", "banker",
    "polymorphism", "encapsulation", "inheritance", "abstraction", "virtual function",
    "vptr", "vtable", "solid", "overloading", "abstract class", "oop", "object oriented",
    "constructor", "destructor", "interface",
    "osi", "tcp", "udp", "http", "dns", "smtp", "routing", "mac address", "ipv4", "ipv6",
    "network layer", "transport layer", "application layer", "data link", "firewall",
    "topology", "computer network",
    "normalization", "normal form", "transitive dependency", "1nf", "2nf", "3nf", "bcnf",
    "acid", "transaction", "isolation",
    "primary key", "foreign key", "candidate key", "er model", "entity relationship",
    "relational algebra", "b+ tree", "b-tree", "indexing", "dbms", "referential integrity",
    "stored procedure", "concurrency control", "two-phase",
    "time complexity", "space complexity", "big-o", "binary search", "linked list",
    "hashmap", "hashtable", "avl", "recursion", "backtracking", "bit manipulation",
)

_SQL_BELONGS = (
    "select ", "select*", " from ", " where ", " group by", " order by", " having ",
    "inner join", "left join", "right join", "full join", "cross join", "outer join",
    "subquery", "nested query", "common table expression", " cte", "with ",
    "window function", " over(", "rank()", "dense_rank", "row_number",
    "insert into", "update ", "delete from", "which query", "write a query",
    "sql query", "output of the following query", "result of the query",
    "following query", "query returns", "query will", "execute the query",
    "aggregate", "count(", "sum(", "avg(", "max(", "min(",
    "distinct", "union ", "intersect", "except ",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def is_sql_mcq_by_content(question_content: str) -> bool:
    text = _norm(question_content)
    if not text:
        return False
    if any(k in text for k in _CS_FORCE):
        return False
    if any(k in text for k in _SQL_BELONGS):
        return True
    if "select" in text and "from" in text:
        return True
    return False


def _near(n: int, target: int, tol: int = 3) -> bool:
    return abs(n - target) <= tol


def split_mcqs(mcq_records: list) -> tuple[list, list, str]:
    """
    Returns (sql_mcqs, cs_mcqs, method).

    Prefer grouping by sheet user_exam_attempt_score:
      - group with ~15 rows → SQL MCQs, section score = that sheet value
      - group with ~40 rows → CS Fundamentals, section score = that sheet value
    Fallback to content classification.
    """
    if not mcq_records:
        return [], [], "empty"

    by_score: dict[float | None, list] = defaultdict(list)
    for q in mcq_records:
        key = None if q.sheet_section_score is None else round(float(q.sheet_section_score), 4)
        by_score[key].append(q)

    scored_groups = [(score, qs) for score, qs in by_score.items() if score is not None]
    scored_groups.sort(key=lambda x: len(x[1]), reverse=True)

    # Case: exactly two distinct section scores with ~15 and ~40 rows
    if len(scored_groups) == 2:
        (s1, g1), (s2, g2) = scored_groups[0], scored_groups[1]
        # Match by count first
        if _near(len(g1), EXPECTED_CS_MCQ) and _near(len(g2), EXPECTED_SQL_MCQ):
            return g2, g1, f"sheet_score_groups cs={s1}({len(g1)}) sql={s2}({len(g2)})"
        if _near(len(g1), EXPECTED_SQL_MCQ) and _near(len(g2), EXPECTED_CS_MCQ):
            return g1, g2, f"sheet_score_groups sql={s1}({len(g1)}) cs={s2}({len(g2)})"
        # Match by score magnitude (SQL max 15, CS max 40)
        if s1 <= EXPECTED_SQL_MCQ + 0.01 and s2 <= EXPECTED_CS_MCQ + 0.01 and s1 < s2:
            return g1, g2, f"sheet_score_magnitude sql={s1}({len(g1)}) cs={s2}({len(g2)})"
        if s2 <= EXPECTED_SQL_MCQ + 0.01 and s1 <= EXPECTED_CS_MCQ + 0.01 and s2 < s1:
            return g2, g1, f"sheet_score_magnitude sql={s2}({len(g2)}) cs={s1}({len(g1)})"

    # Case: more than two score groups — pick best SQL-sized and CS-sized groups
    sql_cand = [(s, g) for s, g in scored_groups if _near(len(g), EXPECTED_SQL_MCQ) or s <= EXPECTED_SQL_MCQ + 0.01]
    cs_cand = [(s, g) for s, g in scored_groups if _near(len(g), EXPECTED_CS_MCQ) or (EXPECTED_SQL_MCQ < s <= EXPECTED_CS_MCQ + 0.01)]
    if sql_cand and cs_cand:
        sql_s, sql_g = min(sql_cand, key=lambda x: abs(len(x[1]) - EXPECTED_SQL_MCQ))
        cs_s, cs_g = min(cs_cand, key=lambda x: abs(len(x[1]) - EXPECTED_CS_MCQ))
        if sql_g is not cs_g:
            used = {id(q) for q in sql_g} | {id(q) for q in cs_g}
            leftovers = [q for q in mcq_records if id(q) not in used]
            # Put leftovers into CS by default
            return sql_g, cs_g + leftovers, f"sheet_score_multi sql={sql_s} cs={cs_s}"

    # Fallback: content membership
    sql, cs = [], []
    for q in mcq_records:
        if is_sql_mcq_by_content(q.question_content):
            sql.append(q)
        else:
            cs.append(q)
    return sql, cs, "content_fallback"
