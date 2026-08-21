---
name: data-agent
description: Use when analyzing local CSV, JSON, Excel, or Parquet datasets; answering questions with tabular data; profiling data quality; producing reproducible SQL-based findings, charts, or Markdown reports.
---

# Data Agent Skill

Use this skill to answer data questions from local files with traceable outputs. Treat every conclusion as evidence-backed: preserve the source, query, result, and assumptions.

## Scope

- Native, dependency-free inputs: CSV and a JSON array of objects.
- Excel and Parquet are supported when their optional readers are installed; otherwise ask for CSV/JSON conversion or install `pandas` with `openpyxl` / `pyarrow`.
- The built-in query table is named `data`.
- Never modify source data. Queries must be one `SELECT` or `WITH` statement only.

## Workflow

1. Clarify the decision or question. If ambiguity materially changes a metric, ask before querying.
2. Profile first; inspect row count, types, missingness, distinct values, and possible grain. Flag limitations.
3. Form a small analysis plan: metric definition, filter, grouping, comparison, and expected chart.
4. Run the helper into a dedicated output folder. Review `profile.json`, `analysis.sql`, and `result.csv` before stating findings.
5. Explain results with the exact data range and caveats. Link the generated report/chart and never invent values not in `result.csv`.

## Commands

Profile and create a reproducible default sample:

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv --output-dir analysis/run-001
```

Run an explicit read-only query:

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv \
  --output-dir analysis/revenue-by-region \
  --sql 'SELECT region, SUM(revenue) AS revenue FROM data GROUP BY region ORDER BY revenue DESC'
```

Generate a bar chart. This uses `SUM(y)` grouped by `x` and writes `chart.svg`:

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/data.csv \
  --output-dir analysis/revenue-by-region \
  --chart bar --x region --y revenue
```

## Deliverable contract

Every run writes these auditable artifacts:

- `profile.json`: dataset dimensions and column-level data-quality profile.
- `analysis.sql`: the exact read-only query used.
- `result.csv`: evidence behind conclusions.
- `report.md`: source, data profile, and artifact links.
- `chart.svg`: when a chart is requested.

Do not overwrite a prior analysis folder unless the user requests it. Use a descriptive, task-specific path such as `analysis/churn-q2-2026`.

## Database sources and semantic layer

Set exactly one source URL in the environment; never put credentials in prompts, files, SQL, or reports:

```bash
export DATA_AGENT_POSTGRES_URL='postgresql://…'
export DATA_AGENT_MYSQL_URL='mysql://…'
export DATA_AGENT_CLICKHOUSE_URL='clickhouse://…'
```

Drivers are optional: install `psycopg`, `pymysql`, or `clickhouse-connect` only for the matching source. Start each database task by exporting catalog metadata, then validate the semantic layer before querying:

```bash
python3 data-agent/scripts/analyze_data.py catalog --source postgres --output-dir analysis/catalog
python3 data-agent/scripts/analyze_data.py semantic-check semantic/orders.json --catalog analysis/catalog/catalog.json
python3 data-agent/scripts/analyze_data.py query --source postgres --output-dir analysis/revenue --sql 'SELECT country, SUM(amount) FROM orders GROUP BY country'
```

Use [assets/semantic-example.json](assets/semantic-example.json) as the JSON template. A semantic table defines its grain, direct dimension-to-column mappings, reviewed metric expressions, and joins. Database queries are capped at 1,000 rows by default and remain single-statement read-only queries.
