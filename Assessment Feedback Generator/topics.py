"""Map questions to detailed topic areas (Nxtwave TopTalent exam taxonomy)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# (display_section, topic_area, keywords) — first match wins; order matters (specific → broad)
TOPIC_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    # OS
    ("CS Fundamentals", "Memory Management", ("memory management", "paging", "segmentation", "page replacement", "virtual memory", "tlb")),
    ("CS Fundamentals", "Deadlocks", ("deadlock", "banker's algorithm", "circular wait")),
    ("CS Fundamentals", "CPU Scheduling", ("cpu scheduling", "round robin", "fcfs", "sjf", "priority scheduling", "multilevel queue")),
    ("CS Fundamentals", "File Systems", ("file system", "inode", "directory structure")),
    ("CS Fundamentals", "Process Synchronization", ("synchronization", "semaphore", "mutex", "critical section", "monitor ")),
    ("CS Fundamentals", "Processes and Threads", ("process", "thread", "pcb", "context switch", "multiprocessing")),
    ("CS Fundamentals", "Inter-Process Communication", ("ipc", "inter-process", "interprocess", "shared memory", "message passing", "pipe")),
    ("CS Fundamentals", "Distributed Systems", ("distributed system", "distributed computing")),
    ("CS Fundamentals", "System Calls", ("system call", "syscall")),
    ("CS Fundamentals", "Operating Systems", ("operating system", "os ", "kernel")),
    # OOPS
    ("CS Fundamentals", "Polymorphism", ("polymorphism", "runtime polymorphism", "vptr", "vtable", "virtual function")),
    ("CS Fundamentals", "Encapsulation", ("encapsulation", "data hiding")),
    ("CS Fundamentals", "Inheritance", ("inheritance", "extends", "base class", "derived class")),
    ("CS Fundamentals", "Abstraction", ("abstraction", "abstract class", "abstract method")),
    ("CS Fundamentals", "Object Composition", ("composition", "aggregation", "has-a")),
    ("CS Fundamentals", "Operator Overloading", ("operator overloading",)),
    ("CS Fundamentals", "SOLID Design Principles", ("solid", "single responsibility", "open/closed", "liskov", "dependency inversion")),
    ("CS Fundamentals", "Exception Handling", ("exception", "try-catch", "throw")),
    ("CS Fundamentals", "Interfaces and Contracts", ("interface", "implements")),
    ("CS Fundamentals", "General OOP Concepts", ("oop", "object oriented", "class and object", "constructor", "destructor")),
    # Computer Networks
    ("CS Fundamentals", "Network Layer", ("network layer", "ip address", "ipv4", "ipv6", "routing table")),
    ("CS Fundamentals", "Transport Layer", ("transport layer", "tcp", "udp", "port number")),
    ("CS Fundamentals", "Application Layer", ("application layer", "http", "ftp", "dns", "smtp")),
    ("CS Fundamentals", "Data Link Layer", ("data link", "mac address", "framing", "crc")),
    ("CS Fundamentals", "Routing Protocols", ("routing protocol", "ospf", "bgp", "rip ")),
    ("CS Fundamentals", "Physical Layer", ("physical layer", "modulation", "multiplexing")),
    ("CS Fundamentals", "Quality of Service (QoS)", ("qos", "quality of service")),
    ("CS Fundamentals", "Network Security", ("network security", "firewall", "encryption", "ssl", "tls")),
    ("CS Fundamentals", "Network Topologies", ("topology", "star topology", "mesh topology", "bus topology")),
    ("CS Fundamentals", "Presentation Layer", ("presentation layer",)),
    ("CS Fundamentals", "Computer Networks", ("computer network", "osi", "osi model")),
    # DBMS theory → CS Fundamentals (avoid broad select/join — those are SQL MCQ practice)
    ("CS Fundamentals", "Transactions", ("transaction", "acid", "commit", "rollback", "isolation level")),
    ("CS Fundamentals", "Normalization", ("normalization", "1nf", "2nf", "3nf", "bcnf", "normal form")),
    ("CS Fundamentals", "Keys", ("primary key", "foreign key", "candidate key", "super key")),
    ("CS Fundamentals", "Recovery", ("recovery", "log-based", "checkpoint")),
    ("CS Fundamentals", "Indexing", ("index", "b+ tree", "b-tree", "indexing")),
    ("CS Fundamentals", "Constraints", ("constraint", "referential integrity", "check constraint")),
    ("CS Fundamentals", "Relational Algebra", ("relational algebra", "projection", "selection", "cartesian")),
    ("CS Fundamentals", "ER Modeling", ("er model", "entity relationship", "entity-relationship", "cardinality")),
    ("CS Fundamentals", "Stored Procedures", ("stored procedure", "trigger", "function in sql")),
    ("CS Fundamentals", "Database Management Systems", ("dbms", "database")),
    # DSA MCQ-style topics (when present in MCQ content)
    ("CS Fundamentals", "Heaps", ("heap", "priority queue", "min-heap", "max-heap")),
    ("CS Fundamentals", "Bit Manipulation", ("bit manipulation", "bitwise", "xor", "bitmask")),
    ("CS Fundamentals", "Arrays and Strings", ("array", "string", "substring", "palindrome")),
    ("CS Fundamentals", "Linked Lists", ("linked list", "singly linked", "doubly linked")),
    ("CS Fundamentals", "Graphs", ("graph", "bfs", "dfs", "adjacency", "shortest path", "dijkstra")),
    ("CS Fundamentals", "Binary Search", ("binary search", "lower bound", "upper bound")),
    ("CS Fundamentals", "Complexity Analysis", ("time complexity", "space complexity", "big-o", "o(n)")),
    ("CS Fundamentals", "Recursion and Backtracking", ("recursion", "backtracking", "recursive")),
    ("CS Fundamentals", "Trees", ("binary tree", "bst", "avl", "tree traversal", "inorder")),
    ("CS Fundamentals", "Hashing", ("hash", "hashmap", "hashtable", "collision")),
    # DSA Coding pools / coding topics
    ("DSA Coding", "Greedy Algorithms", ("greedy",)),
    ("DSA Coding", "Graph Traversal", ("graph", "bfs", "dfs", "traversal")),
    ("DSA Coding", "Dynamic Programming", ("dynamic programming", "dp ", "memoization", "tabulation")),
    ("DSA Coding", "Arrays, Strings and Hashing", ("array", "string", "hash")),
    ("DSA Coding", "Searching and Sorting", ("sort", "search", "binary search")),
    ("DSA Coding", "Recursion and Backtracking", ("recursion", "backtrack")),
    ("DSA Coding", "Trees and Heaps", ("tree", "heap")),
    ("DSA Coding", "Edge Cases and Complexity", ("edge case", "complexity", "constraint")),
    ("DSA Coding", "Problem Solving Approach", ("approach", "algorithm")),
    # SQL Coding / SQL MCQ section (query practice)
    ("SQL", "Basic SQL Queries", ("select", "from ", "basic query")),
    ("SQL", "Filtering and Sorting Data", ("where ", "order by", "filter", "sort")),
    ("SQL", "Joins across tables", ("join", "inner join", "left join")),
    ("SQL", "Grouping and Aggregation", ("group by", "aggregate", "count(", "sum(", "avg(")),
    ("SQL", "Subqueries and CTEs", ("subquery", "cte", "with ")),
    ("SQL", "Window Functions and Ranking", ("window", "over (", "rank(", "dense_rank")),
    ("SQL", "SQL Syntax and Commands", ("sql", "syntax")),
    ("SQL", "Data Manipulation Language", ("insert", "update", "delete", "dml")),
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def infer_topic(question_content: str, section_hint: str | None = None) -> tuple[str, str]:
    """
    Return (display_section, topic_area).
    section_hint: DSA Coding | SQL | CS Fundamentals (optional preferred bucket).
    """
    text = _norm(question_content)
    for section, topic, keys in TOPIC_RULES:
        if section_hint and section != section_hint:
            # Allow CS rules when hint is CS; SQL rules for SQL; DSA for DSA
            if not (
                (section_hint == "CS Fundamentals" and section == "CS Fundamentals")
                or (section_hint == "SQL" and section == "SQL")
                or (section_hint == "DSA Coding" and section == "DSA Coding")
            ):
                continue
        if any(k in text for k in keys):
            return section, topic

    # Fallbacks without hint filter
    for section, topic, keys in TOPIC_RULES:
        if any(k in text for k in keys):
            return section, topic

    if section_hint == "DSA Coding":
        return "DSA Coding", "Problem Solving Approach"
    if section_hint == "SQL":
        return "SQL", "Basic SQL Queries"
    return "CS Fundamentals", "Core CS Concepts"


def section_hint_for_internal(section_key: str) -> str:
    from config import CS_MCQ, DSA_CODING, SQL_CODING, SQL_MCQ

    if section_key == DSA_CODING:
        return "DSA Coding"
    if section_key in (SQL_CODING, SQL_MCQ):
        return "SQL"
    if section_key == CS_MCQ:
        return "CS Fundamentals"
    return "CS Fundamentals"


@dataclass
class TopicStat:
    section: str
    topic_area: str
    correct: int = 0
    incorrect: int = 0
    unanswered: int = 0
    coding_attempted: int = 0
    coding_total: int = 0

    @property
    def level(self) -> str:
        # Coding topics
        if self.coding_total:
            if self.coding_attempted == 0:
                return "Not Attempted"
            ratio = self.coding_attempted / self.coding_total
            if ratio >= 0.75:
                return "Strong"
            if ratio >= 0.4:
                return "Partial"
            return "Needs work"
        total = self.correct + self.incorrect + self.unanswered
        if total == 0:
            return "Not Attempted"
        if self.correct + self.incorrect == 0:
            return "Not Attempted"
        rate = self.correct / max(self.correct + self.incorrect, 1)
        if self.unanswered and self.correct + self.incorrect == 0:
            return "Not Attempted"
        if rate >= 0.75 and self.incorrect <= 1:
            return "Strong"
        if rate >= 0.45:
            return "Partial"
        return "Needs work"


def build_topic_stats(student) -> list[dict]:
    """Deterministic topic rows from question content + evaluation / code presence."""
    from config import CS_MCQ, DSA_CODING, SQL_CODING, SQL_MCQ

    buckets: dict[tuple[str, str], TopicStat] = {}

    def get_stat(section: str, topic: str) -> TopicStat:
        key = (section, topic)
        if key not in buckets:
            buckets[key] = TopicStat(section=section, topic_area=topic)
        return buckets[key]

    for section_key, sec in student.sections.items():
        hint = section_hint_for_internal(section_key)
        for q in sec.questions:
            section, topic = infer_topic(q.question_content, hint)
            # Keep coding questions under DSA/SQL coding display sections
            if section_key == DSA_CODING:
                section = "DSA Coding"
            elif section_key == SQL_CODING:
                section = "SQL"
            elif section_key == SQL_MCQ:
                section = "SQL"
            elif section_key == CS_MCQ:
                section = "CS Fundamentals"

            st = get_stat(section, topic)
            if section_key in (DSA_CODING, SQL_CODING):
                st.coding_total += 1
                if (q.code_content or "").strip() and (q.code_content or "").strip().lower() not in (
                    "none",
                    "null",
                ):
                    st.coding_attempted += 1
            else:
                result = (q.evaluation_result or "").strip().upper()
                options = (q.response_options or "").strip()
                if result in ("CORRECT", "TRUE", "RIGHT"):
                    st.correct += 1
                elif result in ("INCORRECT", "FALSE", "WRONG"):
                    st.incorrect += 1
                elif not options or options.lower() in ("none", "[]", "null"):
                    st.unanswered += 1
                else:
                    st.unanswered += 1

    rows = [
        {"section": s.section, "topic_area": s.topic_area, "level": s.level}
        for s in buckets.values()
    ]
    order = {"DSA Coding": 0, "SQL": 1, "CS Fundamentals": 2}
    rows.sort(key=lambda r: (order.get(r["section"], 9), r["topic_area"]))
    return rows


def mcq_correct_count(questions) -> int:
    n = 0
    for q in questions:
        if (q.evaluation_result or "").strip().upper() in ("CORRECT", "TRUE", "RIGHT"):
            n += 1
    return n
