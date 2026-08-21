#!/usr/bin/env python3
"""Read-only local tabular analysis helper used by the data-agent Skill."""

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from database import DatabaseAdapter
from semantic import load_semantic, validate_semantic
from sql_safety import apply_limit
from sql_safety import validate_read_only


def load_rows(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list) and all(isinstance(row, dict) for row in payload):
            return payload
        raise ValueError("JSON input must be an array of objects.")
    if suffix in {".xlsx", ".xls", ".parquet"}:
        raise ValueError(
            f"{suffix} requires an optional reader. Convert it to CSV/JSON for the zero-dependency MVP, "
            "or install pandas plus openpyxl (Excel) / pyarrow (Parquet)."
        )
    raise ValueError("Supported input formats are CSV and JSON (XLSX/Parquet need optional readers).")


def as_number(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            number = float(value.replace(",", ""))
            return int(number) if number.is_integer() else number
        except ValueError:
            return value
    return str(value)


def normalize_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{str(key): as_number(value) for key, value in row.items()} for row in rows]


def profile(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    names = sorted({key for row in rows for key in row})
    columns = {}
    for name in names:
        values = [row.get(name) for row in rows]
        present = [value for value in values if value not in (None, "")]
        numeric = [value for value in present if isinstance(value, (int, float)) and not isinstance(value, bool)]
        column = {
            "type": "number" if present and len(numeric) == len(present) else "string",
            "missing_count": len(values) - len(present),
            "distinct_count": len({str(value) for value in present}),
            "sample_values": [str(value) for value in present[:5]],
        }
        if numeric:
            column.update({"min": min(numeric), "max": max(numeric), "mean": round(sum(numeric) / len(numeric), 4)})
        columns[name] = column
    return {"row_count": len(rows), "column_count": len(names), "columns": columns}


def quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def create_database(rows: List[Dict[str, Any]]) -> sqlite3.Connection:
    if not rows:
        raise ValueError("Input contains no rows.")
    names = sorted({key for row in rows for key in row})
    connection = sqlite3.connect(":memory:")
    columns = ", ".join(f"{quoted(name)}" for name in names)
    connection.execute(f"CREATE TABLE data ({columns})")
    placeholders = ", ".join("?" for _ in names)
    connection.executemany(
        f"INSERT INTO data ({columns}) VALUES ({placeholders})",
        [[row.get(name) for name in names] for row in rows],
    )
    return connection


def write_query_csv(path: Path, cursor: sqlite3.Cursor) -> List[Tuple[Any, ...]]:
    names = [item[0] for item in cursor.description]
    result = cursor.fetchall()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        writer.writerows(result)
    return result


def write_rows_csv(path: Path, columns: List[str], rows: List[Tuple[Any, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def run_query(adapter: Any, sql: str, destination: Path, max_rows: int = 1000) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    bounded_sql = apply_limit(sql, max_rows)
    columns, rows = adapter.query(sql, max_rows=max_rows)
    (destination / "analysis.sql").write_text(bounded_sql + "\n", encoding="utf-8")
    write_rows_csv(destination / "result.csv", columns, rows)
    (destination / "report.md").write_text(
        "# Database analysis report\n\n"
        f"- Rows returned: {len(rows)}\n"
        "- Query: [`analysis.sql`](analysis.sql)\n"
        "- Query result: [`result.csv`](result.csv)\n",
        encoding="utf-8",
    )
    return destination


def write_bar_chart(path: Path, rows: List[Tuple[Any, ...]], x: str, y: str) -> None:
    values = [(str(row[0]), float(row[1] or 0)) for row in rows]
    width, height, left, bottom = 760, 420, 70, 60
    maximum = max((value for _, value in values), default=1) or 1
    bar_width = max(20, min(90, (width - left - 30) / max(1, len(values)) - 12))
    blocks = [f'<text x="{width / 2}" y="28" text-anchor="middle">{html.escape(y)} by {html.escape(x)}</text>']
    for index, (label, value) in enumerate(values):
        x_pos = left + index * ((width - left - 30) / max(1, len(values))) + 8
        bar_height = (height - bottom - 50) * value / maximum
        y_pos = height - bottom - bar_height
        blocks.extend([
            f'<rect x="{x_pos:.1f}" y="{y_pos:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="#2563eb"/>',
            f'<text x="{x_pos + bar_width / 2:.1f}" y="{height - bottom + 18}" text-anchor="middle">{html.escape(label)}</text>',
            f'<text x="{x_pos + bar_width / 2:.1f}" y="{y_pos - 6:.1f}" text-anchor="middle">{value:g}</text>',
        ])
    svg = "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font:13px -apple-system,BlinkMacSystemFont,sans-serif;fill:#172033} rect{rx:3}</style>',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - 20}" y2="{height - bottom}" stroke="#64748b"/>',
        *blocks,
        "</svg>",
    ])
    path.write_text(svg, encoding="utf-8")


def analyze(args: argparse.Namespace) -> None:
    source = Path(args.input).resolve()
    destination = Path(args.output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    rows = normalize_rows(load_rows(source))
    data_profile = profile(rows)
    (destination / "profile.json").write_text(json.dumps(data_profile, ensure_ascii=False, indent=2), encoding="utf-8")
    connection = create_database(rows)
    sql = args.sql
    if args.chart:
        if not args.x or not args.y:
            raise ValueError("--chart requires both --x and --y.")
        if args.x not in data_profile["columns"] or args.y not in data_profile["columns"]:
            raise ValueError("--x and --y must be existing column names.")
        sql = f"SELECT {quoted(args.x)}, SUM({quoted(args.y)}) AS total_{args.y} FROM data GROUP BY {quoted(args.x)} ORDER BY total_{args.y} DESC"
    sql = validate_read_only(sql or "SELECT * FROM data LIMIT 100")
    cursor = connection.execute(sql)
    result_rows = write_query_csv(destination / "result.csv", cursor)
    (destination / "analysis.sql").write_text(sql + "\n", encoding="utf-8")
    if args.chart:
        write_bar_chart(destination / "chart.svg", result_rows, args.x, args.y)
    report = [
        "# Data analysis report",
        "",
        f"- Source: `{source.name}`",
        f"- Rows: {data_profile['row_count']}",
        f"- Columns: {data_profile['column_count']}",
        "- Query: [`analysis.sql`](analysis.sql)",
        "- Query result: [`result.csv`](result.csv)",
    ]
    if args.chart:
        report.append("- Chart: [`chart.svg`](chart.svg)")
    report.extend(["", "## Data profile", "", "| Column | Type | Missing | Distinct |", "| --- | --- | ---: | ---: |"])
    report.extend(f"| {name} | {item['type']} | {item['missing_count']} | {item['distinct_count']} |" for name, item in data_profile["columns"].items())
    (destination / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Analysis written to {destination}")


def catalog(args: argparse.Namespace) -> None:
    destination = Path(args.output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    adapter = DatabaseAdapter.for_source(args.source, __import__("os").environ)
    data_catalog = adapter.catalog()
    (destination / "catalog.json").write_text(json.dumps(data_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Catalog written to {destination}")


def database_query(args: argparse.Namespace) -> None:
    adapter = DatabaseAdapter.for_source(args.source, __import__("os").environ)
    output = run_query(adapter, args.sql, Path(args.output_dir).resolve(), args.max_rows)
    print(f"Analysis written to {output}")


def semantic_check(args: argparse.Namespace) -> None:
    semantic = load_semantic(Path(args.semantic))
    try:
        catalog_data = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read catalog JSON: {error}") from None
    errors = validate_semantic(semantic, catalog_data)
    if errors:
        raise ValueError("\n".join(errors))
    print("Semantic layer is valid.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a safe, reproducible local data analysis.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("analyze")
    command.add_argument("input", help="CSV or JSON file to analyze")
    command.add_argument("--output-dir", required=True, help="Directory for reproducible outputs")
    command.add_argument("--sql", help="One read-only SQLite SELECT/WITH query against table data")
    command.add_argument("--chart", choices=["bar"], help="Create a chart from grouped x/y values")
    command.add_argument("--x", help="Grouping column for chart")
    command.add_argument("--y", help="Numeric value column for chart")
    catalog_command = subparsers.add_parser("catalog")
    catalog_command.add_argument("--source", required=True, choices=["postgres", "mysql", "clickhouse"])
    catalog_command.add_argument("--output-dir", required=True)
    query_command = subparsers.add_parser("query")
    query_command.add_argument("--source", required=True, choices=["postgres", "mysql", "clickhouse"])
    query_command.add_argument("--sql", required=True)
    query_command.add_argument("--output-dir", required=True)
    query_command.add_argument("--max-rows", type=int, default=1000)
    semantic_command = subparsers.add_parser("semantic-check")
    semantic_command.add_argument("semantic")
    semantic_command.add_argument("--catalog", required=True)
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            analyze(args)
        elif args.command == "catalog":
            catalog(args)
        elif args.command == "query":
            database_query(args)
        else:
            semantic_check(args)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
