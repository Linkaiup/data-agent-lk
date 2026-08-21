"""Lazy, read-only adapters for supported analytical databases."""

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Tuple
from urllib.parse import unquote, urlparse

from sql_safety import apply_limit


@dataclass(frozen=True)
class SourceConfig:
    env_name: str
    package: str
    catalog_sql: str


SOURCES = {
    "postgres": SourceConfig("DATA_AGENT_POSTGRES_URL", "psycopg", "SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2, ordinal_position"),
    "mysql": SourceConfig("DATA_AGENT_MYSQL_URL", "pymysql", "SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE table_schema = DATABASE() ORDER BY 1, 2, ordinal_position"),
    "clickhouse": SourceConfig("DATA_AGENT_CLICKHOUSE_URL", "clickhouse_connect", "SELECT database, table, name FROM system.columns WHERE database NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema') ORDER BY 1, 2, position"),
}


class DatabaseAdapter:
    def __init__(self, source: str, connection: Any):
        self.source = source
        self.connection = connection

    @classmethod
    def for_source(
        cls,
        source: str,
        environ: Mapping[str, str],
        importer: Callable[[str], Any] = importlib.import_module,
    ) -> "DatabaseAdapter":
        if source not in SOURCES:
            raise ValueError("source must be one of: postgres, mysql, clickhouse.")
        config = SOURCES[source]
        url = environ.get(config.env_name)
        if not url:
            raise ValueError(f"Missing required environment variable: {config.env_name}.")
        try:
            driver = importer(config.package)
        except (ImportError, ModuleNotFoundError):
            driver = None
        if driver is None:
            raise RuntimeError(f"{source} support requires optional package `{config.package}`. Install it and retry.")
        try:
            connection = cls._connect(source, driver, url)
        except Exception as error:
            raise RuntimeError(f"Could not connect to {source}: {type(error).__name__}.") from None
        return cls(source, connection)

    @staticmethod
    def _connect(source: str, driver: Any, url: str) -> Any:
        if source == "postgres":
            return driver.connect(url)
        parsed = urlparse(url)
        if source == "mysql":
            return driver.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                database=parsed.path.lstrip("/"),
            )
        return driver.get_client(
            host=parsed.hostname,
            port=parsed.port or 8123,
            username=unquote(parsed.username or "default"),
            password=unquote(parsed.password or ""),
            database=parsed.path.lstrip("/") or "default",
            secure=parsed.scheme.endswith("s"),
        )

    def _cursor(self) -> Any:
        return self.connection.cursor()

    def _set_read_only(self, cursor: Any) -> None:
        if self.source == "postgres":
            cursor.execute("SET TRANSACTION READ ONLY")
        elif self.source == "mysql":
            cursor.execute("SET SESSION TRANSACTION READ ONLY")

    def query(self, sql: str, max_rows: int = 1000) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        statement = apply_limit(sql, max_rows)
        if self.source == "clickhouse":
            result = self.connection.query(statement)
            return list(result.column_names), [tuple(row) for row in result.result_rows]
        cursor = self._cursor()
        self._set_read_only(cursor)
        cursor.execute(statement)
        return [item[0] for item in cursor.description], list(cursor.fetchall())

    def catalog(self) -> Dict[str, List[str]]:
        config = SOURCES[self.source]
        columns, rows = self.query(config.catalog_sql, max_rows=100000)
        if len(columns) < 3:
            raise RuntimeError(f"Unexpected catalog response from {self.source}.")
        catalog: Dict[str, List[str]] = {}
        for schema, table, column in rows:
            catalog.setdefault(f"{schema}.{table}", []).append(str(column))
        return {"source": self.source, "tables": catalog}
