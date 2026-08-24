---
name: data-agent
description: Use when analyzing local CSV, JSON, Excel, or Parquet datasets; answering questions with tabular data; profiling data quality; producing reproducible SQL-based findings, charts, or Markdown reports.
---

# Data Agent Skill

Use this skill for auditable analysis of local tabular data or approved database sources. Treat scripts as evidence-gathering tools, not as a substitute for judgment: every conclusion must be traceable to the source, a stated metric definition, executed SQL, and returned rows.

## Delivery standard

- Do not invent values, filters, business definitions, or findings. State what is unavailable or ambiguous.
- Never modify source data. Database credentials belong only in environment variables; never repeat them in prompts, code, reports, or logs.
- A result is not ready to present until its `analysis.sql` and `result.csv` have been reviewed.
- Distinguish observed facts from interpretation and recommendations. State material data-quality limitations.

## Directory navigation

| Path | Purpose | Read or run when |
| --- | --- | --- |
| `scripts/analyze_data.py` | CLI entry point for local analysis, database catalog/query, semantic validation, reports, and SVG bar charts. | Every executable workflow. |
| `scripts/sql_safety.py` | Validates one read-only `SELECT`/`WITH` statement and applies database row limits. | SQL is generated, reviewed, or rejected. |
| `scripts/database.py` | Lazy adapters for PostgreSQL, MySQL, and ClickHouse. | The user provides a database source. |
| `scripts/semantic.py` | Loads and validates JSON semantic definitions against a catalog. | A semantic layer is present or requested. |
| `assets/sample-sales.csv` | Safe example data for testing the local workflow. | Demonstration or smoke test. |
| `assets/semantic-example.json` | Template for a version-controlled semantic layer. | Creating a semantic definition. |
| `agents/openai.yaml` | Codex-facing display name and default prompt metadata. | UI metadata only; do not treat as analysis instructions. |

## Choose the workflow

| Situation | Required path |
| --- | --- |
| CSV or JSON array of objects | Local-file workflow. |
| Excel or Parquet | The current helper does not read these formats directly. Ask for CSV/JSON conversion or perform a separate, auditable conversion before using this Skill. |
| PostgreSQL, MySQL, or ClickHouse | Database workflow: catalog → semantic validation when available → query. |
| A known, narrow question on trusted data | Profile or catalog first, then run the smallest read-only query that answers it. |
| Ambiguous metric, grain, period, or audience | Stop after profiling/cataloging and ask the smallest question that resolves the ambiguity. |

## Quality gates

1. **Understand before aggregating.** For local data, inspect row count, types, missingness, cardinality, and likely grain. For databases, export a fresh catalog.
2. **Declare the calculation.** State metric, time range, filters, grouping, denominator, and comparison before drawing conclusions. Use a semantic layer where one exists.
3. **Validate before execution.** SQL must be one read-only `SELECT` or `WITH` statement. Never bypass the query validator.
4. **Review evidence before reporting.** Inspect `analysis.sql` and `result.csv`. Do not claim a number that is absent from the result.
5. **Preserve the audit trail.** Use a new, descriptive output directory unless the user explicitly authorizes overwriting a prior run.

## Local-file workflow

Native inputs are CSV and a JSON array of objects. The in-memory SQL table is named `data`.

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv \
  --output-dir analysis/run-001
```

Run an explicit query only after profiling:

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv \
  --output-dir analysis/revenue-by-region \
  --sql 'SELECT region, SUM(revenue) AS revenue FROM data GROUP BY region ORDER BY revenue DESC'
```

For a bar chart, use a categorical `x` column and numeric `y` column. The command calculates `SUM(y)` grouped by `x` and writes `chart.svg`.

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv \
  --output-dir analysis/revenue-by-region \
  --chart bar --x region --y revenue
```

## Database workflow

Set only the source required for the task. Do not print these values.

```bash
export DATA_AGENT_POSTGRES_URL='postgresql://…'
export DATA_AGENT_MYSQL_URL='mysql://…'
export DATA_AGENT_CLICKHOUSE_URL='clickhouse://…'
```

Install the matching optional driver only when required: `psycopg`, `pymysql`, or `clickhouse-connect`. If unavailable, report the package name and stop; do not substitute a different source.

```bash
# 1. Discover available schemas, tables, and columns.
python3 data-agent/scripts/analyze_data.py catalog \
  --source postgres --output-dir analysis/catalog

# 2. Validate a saved business definition when one is available.
python3 data-agent/scripts/analyze_data.py semantic-check semantic/orders.json \
  --catalog analysis/catalog/catalog.json

# 3. Execute one bounded read-only query.
python3 data-agent/scripts/analyze_data.py query \
  --source postgres --output-dir analysis/revenue \
  --sql 'SELECT country, SUM(amount) AS revenue FROM orders GROUP BY country'
```

Database queries default to 1,000 rows. Use `--max-rows` only when a larger evidence set is necessary and explain why.

## Semantic layer

Use `assets/semantic-example.json` as the starting structure. Each table must declare:

- `grain`: what one row represents.
- `dimensions`: approved business dimension → physical column mappings.
- `metrics`: reviewed SQL metric expressions.
- `joins`: allowed table relationships.

The validator checks tables and direct dimension columns against the catalog. It does not prove that metric SQL expressions are business-correct; review those expressions before relying on them.

## Audit outputs

Every local analysis writes these artifacts; database query runs write `analysis.sql`, `result.csv`, and `report.md`.

- `profile.json`: dataset dimensions and column-level quality profile.
- `analysis.sql`: exact executed or bounded SQL.
- `result.csv`: rows supporting the conclusion.
- `report.md`: source, audit links, and summary metadata.
- `chart.svg`: only when a bar chart is requested.

Use the artifact links in the final response. If profile, catalog, SQL execution, or validation failed, report that status rather than presenting a partial result as complete.
