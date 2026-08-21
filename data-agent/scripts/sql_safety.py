"""Conservative read-only SQL validation shared by local and remote adapters."""

import re


WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM|GRANT|REVOKE|TRUNCATE|MERGE|CALL)\b",
    re.IGNORECASE,
)


def validate_read_only(sql: str) -> str:
    statement = sql.strip()
    if not statement or ";" in statement or not re.match(r"^(SELECT|WITH)\b", statement, re.IGNORECASE):
        raise ValueError("Only a single read-only SELECT or WITH query is allowed.")
    if WRITE_KEYWORDS.search(statement):
        raise ValueError("Only a single read-only SELECT or WITH query is allowed.")
    return statement


def apply_limit(sql: str, max_rows: int = 1000) -> str:
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1.")
    statement = validate_read_only(sql)
    if re.search(r"\bLIMIT\s+\d+", statement, re.IGNORECASE):
        return statement
    return f"{statement} LIMIT {max_rows}"
