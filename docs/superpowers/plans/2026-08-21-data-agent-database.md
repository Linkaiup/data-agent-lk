# Data Agent Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe read-only PostgreSQL, MySQL, and ClickHouse querying and JSON semantic-layer validation to Local Data Agent.

**Architecture:** Keep the current CLI as the entry point. Add isolated SQL-safety, database-adapter, and semantic-validation modules so the local-file flow remains unchanged. Database drivers load only on use; source-specific URLs come only from environment variables.

**Tech Stack:** Python 3.9 standard library; optional `psycopg`, `pymysql`, and `clickhouse-connect`; `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-21-data-agent-database-design.md`

## Global Constraints

- Read only `DATA_AGENT_POSTGRES_URL`, `DATA_AGENT_MYSQL_URL`, and `DATA_AGENT_CLICKHOUSE_URL` for credentials.
- Never write or echo database URLs, passwords, or tokens.
- Only one `SELECT` or `WITH` statement may execute.
- Default query result limit is 1,000 rows.
- Tests use fake connections only; no live database connection.

---

### Task 1: Extract SQL safety and bounded-query behavior

**Files:**
- Create: `data-agent/scripts/sql_safety.py`
- Modify: `data-agent/scripts/analyze_data.py`
- Test: `tests/test_sql_safety.py`

**Interfaces:**
- Produces: `validate_read_only(sql: str) -> str` and `apply_limit(sql: str, max_rows: int) -> str`.
- Consumes: Existing local-file CLI calls to `validate_read_only`.

- [ ] **Step 1: Write the failing tests**

```python
from sql_safety import apply_limit, validate_read_only

def test_allows_replace_function_in_select():
    assert validate_read_only("SELECT REPLACE(name, 'a', 'b') FROM data").startswith("SELECT")

def test_appends_limit_when_absent():
    assert apply_limit("SELECT * FROM orders", 1000).endswith("LIMIT 1000")

def test_rejects_multiple_or_mutating_statements():
    with self.assertRaisesRegex(ValueError, "read-only"):
        validate_read_only("SELECT 1; DELETE FROM orders")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -B -m unittest tests/test_sql_safety.py -v`

Expected: FAIL because `sql_safety` does not exist.

- [ ] **Step 3: Implement the minimal validator and limiter**

```python
def apply_limit(sql: str, max_rows: int) -> str:
    if re.search(r"\\bLIMIT\\s+\\d+", sql, re.I):
        return sql
    return f"{sql.rstrip()} LIMIT {max_rows}"
```

Allow `REPLACE()` as a scalar function while continuing to reject write/DDL keywords and semicolon-separated statements.

- [ ] **Step 4: Run focused and existing tests**

Run: `python3 -B -m unittest tests/test_sql_safety.py tests/test_analyze_data.py -v`

Expected: PASS.

### Task 2: Build lazy database adapters and catalog export

**Files:**
- Create: `data-agent/scripts/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `DatabaseAdapter.for_source(source: str, environ: Mapping[str, str])`, `.catalog() -> dict`, and `.query(sql: str) -> tuple[list[str], list[tuple]]`.
- Consumes: `validate_read_only` and `apply_limit` from `sql_safety.py`.

- [ ] **Step 1: Write failing adapter tests using fake driver modules**

```python
def test_missing_url_names_environment_variable():
    with self.assertRaisesRegex(ValueError, "DATA_AGENT_POSTGRES_URL"):
        DatabaseAdapter.for_source("postgres", {})

def test_driver_error_never_echoes_url():
    env = {"DATA_AGENT_POSTGRES_URL": "postgresql://user:secret@host/db"}
    with self.assertRaisesRegex(RuntimeError, "psycopg") as raised:
        DatabaseAdapter.for_source("postgres", env, importer=lambda _: None)
    self.assertNotIn("secret", str(raised.exception))
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -B -m unittest tests/test_database.py -v`

Expected: FAIL because `database` does not exist.

- [ ] **Step 3: Implement source metadata and lazy connectors**

Define a source registry with driver name, URL environment variable, catalog query, and read-only setup. PostgreSQL and MySQL use cursor metadata; ClickHouse uses its query result column names. Ensure the source name, not a connection string, appears in errors.

- [ ] **Step 4: Verify fake-driver behavior**

Run: `python3 -B -m unittest tests/test_database.py -v`

Expected: PASS without any installed database driver.

### Task 3: Add semantic-layer validation

**Files:**
- Create: `data-agent/scripts/semantic.py`
- Create: `data-agent/assets/semantic-example.json`
- Test: `tests/test_semantic.py`

**Interfaces:**
- Produces: `load_semantic(path: Path) -> dict` and `validate_semantic(semantic: dict, catalog: dict) -> list[str]`.
- Consumes: Catalog JSON of the form `{"tables": {"schema.table": ["column"]}}`.

- [ ] **Step 1: Write failing tests**

```python
def test_reports_unknown_table_and_dimension_column(tmp_path):
    semantic = {"source": "postgres", "tables": {"orders": {"grain": "one row", "dimensions": {"country": "nation"}, "metrics": {}}}}
    errors = validate_semantic(semantic, {"tables": {"public.orders": ["id", "country"]}})
    self.assertIn("unknown table: orders", errors)
    self.assertIn("unknown column: orders.nation", errors)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -B -m unittest tests/test_semantic.py -v`

Expected: FAIL because `semantic` does not exist.

- [ ] **Step 3: Implement JSON schema checks and catalog matching**

Require `source`, `tables`, `grain`, `metrics`, `dimensions`, and `joins`. Match both exact and `public.`-prefixed table names. Validate only direct dimension-column mappings and join endpoints; retain metric SQL expressions as reviewed text.

- [ ] **Step 4: Verify semantic tests**

Run: `python3 -B -m unittest tests/test_semantic.py -v`

Expected: PASS.

### Task 4: Integrate commands and update Skill documentation

**Files:**
- Modify: `data-agent/scripts/analyze_data.py`
- Modify: `data-agent/SKILL.md`
- Modify: `data-agent/agents/openai.yaml`
- Test: `tests/test_database_cli.py`

**Interfaces:**
- Consumes: `DatabaseAdapter`, `load_semantic`, and `validate_semantic`.
- Produces: CLI `catalog`, `query`, and `semantic-check` commands plus per-run audit files.

- [ ] **Step 1: Write a failing CLI integration test with a patched adapter**

```python
def test_query_writes_sql_result_and_report(tmp_path):
    adapter = FakeAdapter(columns=["region", "revenue"], rows=[("East", 120)])
    output = run_query(adapter, "SELECT region, revenue FROM orders", tmp_path, max_rows=100)
    self.assertEqual((output / "result.csv").read_text(), "region,revenue\\nEast,120\\n")
    self.assertIn("LIMIT 100", (output / "analysis.sql").read_text())
```

- [ ] **Step 2: Run test and verify failure**

Run: `python3 -B -m unittest tests/test_database_cli.py -v`

Expected: FAIL because database command functions do not exist.

- [ ] **Step 3: Add CLI commands and audit output**

Add parsers for the three interfaces from the spec. `catalog` writes `catalog.json`; `query` writes SQL, CSV, and report; `semantic-check` exits nonzero with a line-per-error response. Update the Skill with environment-variable examples, no-secret rule, catalog-first workflow, and semantic JSON reference.

- [ ] **Step 4: Run complete verification**

Run: `python3 -B -m unittest discover -s tests -v && python3 /Users/bingerlin/.codex/skills/.system/skill-creator/scripts/quick_validate.py data-agent`

Expected: all tests PASS and `Skill is valid!`.

- [ ] **Step 5: Copy validated Skill to its installed location**

Run: `cp -R data-agent/. /Users/bingerlin/.codex/skills/local-data-agent/`

Expected: the installed Skill contains the new modules and documentation.
