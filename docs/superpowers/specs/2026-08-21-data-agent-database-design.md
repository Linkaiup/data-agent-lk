# Data Agent Database and Semantic Layer Design

## Goal

Extend the local Data Agent with safe, read-only PostgreSQL, MySQL, and ClickHouse querying plus version-controlled semantic definitions.

## Constraints

- Credentials are supplied only through environment variables; no URL, password, or token may be persisted or logged.
- Database SQL is a single read-only `SELECT` or `WITH` statement.
- The helper must set a read-only transaction where supported and apply a default row limit.
- Missing optional drivers must produce an actionable installation message.
- Tests must use fake connections and never connect to a real database.

## Architecture

`database.py` exposes one small adapter interface: connect from a named environment variable, list catalog metadata, and execute a query. PostgreSQL, MySQL, and ClickHouse implementations load drivers lazily. `sql_safety.py` validates statements before an adapter receives them.

`semantic.py` loads JSON semantic-layer files, validates their required shape, and checks referenced tables and columns against an exported catalog. It does not evaluate user-provided expressions.

The existing CLI gains `catalog`, `query`, and `semantic-check` commands. `query` writes `analysis.sql`, `result.csv`, and `report.md`, preserving the current audit contract.

## Interfaces

- `catalog --source postgres|mysql|clickhouse --output-dir DIR`
- `query --source postgres|mysql|clickhouse --sql SQL --output-dir DIR [--max-rows N]`
- `semantic-check PATH --catalog PATH`

Connection variables are fixed: `DATA_AGENT_POSTGRES_URL`, `DATA_AGENT_MYSQL_URL`, and `DATA_AGENT_CLICKHOUSE_URL`.

## Error Handling

Failures name only the source, driver package, missing environment-variable name, or query-validation error. They must not include the connection string. Catalog and report files contain schemas, tables, columns, SQL, and query output only.

## Verification

Unit tests cover connection environment-variable resolution, driver-missing guidance, SQL rejection, row limiting, catalog normalization, semantic JSON validation, and unknown table/column detection. The existing local-file tests must stay green.
