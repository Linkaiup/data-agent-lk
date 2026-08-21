"""Validation helpers for JSON semantic-layer definitions."""

import json
from pathlib import Path
from typing import Any, Dict, List


def load_semantic(path: Path) -> Dict[str, Any]:
    try:
        semantic = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read semantic JSON: {error}") from None
    if not isinstance(semantic, dict) or not isinstance(semantic.get("source"), str):
        raise ValueError("semantic layer requires a string source.")
    if not isinstance(semantic.get("tables"), dict) or not semantic["tables"]:
        raise ValueError("semantic layer tables must not be empty.")
    for name, table in semantic["tables"].items():
        if not isinstance(table, dict):
            raise ValueError(f"table {name} must be an object.")
        for key, expected in (("grain", str), ("dimensions", dict), ("metrics", dict), ("joins", list)):
            if not isinstance(table.get(key), expected):
                raise ValueError(f"table {name} requires {key} as {expected.__name__}.")
    return semantic


def _catalog_table(name: str, tables: Dict[str, List[str]]) -> str:
    if name in tables:
        return name
    matches = [candidate for candidate in tables if candidate.split(".")[-1] == name]
    return matches[0] if len(matches) == 1 else ""


def validate_semantic(semantic: Dict[str, Any], catalog: Dict[str, Any]) -> List[str]:
    tables = catalog.get("tables", {})
    if not isinstance(tables, dict):
        return ["catalog tables must be an object"]
    errors: List[str] = []
    for name, definition in semantic.get("tables", {}).items():
        catalog_name = _catalog_table(name, tables)
        if not catalog_name:
            errors.append(f"unknown table: {name}")
            continue
        columns = set(tables[catalog_name])
        for _, column in definition.get("dimensions", {}).items():
            if column not in columns:
                errors.append(f"unknown column: {name}.{column}")
        for join in definition.get("joins", []):
            if not isinstance(join, dict) or not isinstance(join.get("table"), str):
                errors.append(f"invalid join in table: {name}")
                continue
            if not _catalog_table(join["table"], tables):
                errors.append(f"unknown table: {join['table']}")
    return errors
