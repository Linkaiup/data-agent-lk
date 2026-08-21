import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "data-agent" / "scripts"))
from database import DatabaseAdapter


class FakeCursor:
    description = [("region",), ("revenue",)]

    def __init__(self):
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def fetchall(self):
        return [("East", 120)]


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()

    def cursor(self):
        return self.cursor_value


class FakePsycopg:
    @staticmethod
    def connect(url):
        return FakeConnection()


class DatabaseAdapterTests(unittest.TestCase):
    def test_missing_url_names_environment_variable(self):
        with self.assertRaisesRegex(ValueError, "DATA_AGENT_POSTGRES_URL"):
            DatabaseAdapter.for_source("postgres", {})

    def test_driver_error_never_echoes_url(self):
        env = {"DATA_AGENT_POSTGRES_URL": "postgresql://user:secret@host/db"}
        with self.assertRaisesRegex(RuntimeError, "psycopg") as raised:
            DatabaseAdapter.for_source("postgres", env, importer=lambda _: None)
        self.assertNotIn("secret", str(raised.exception))

    def test_postgres_query_sets_read_only_and_limits_results(self):
        env = {"DATA_AGENT_POSTGRES_URL": "postgresql://user:secret@host/db"}
        adapter = DatabaseAdapter.for_source("postgres", env, importer=lambda _: FakePsycopg)
        columns, rows = adapter.query("SELECT region, revenue FROM orders", max_rows=25)
        self.assertEqual(columns, ["region", "revenue"])
        self.assertEqual(rows, [("East", 120)])
        self.assertIn("SET TRANSACTION READ ONLY", adapter.connection.cursor_value.executed)
        self.assertTrue(adapter.connection.cursor_value.executed[-1].endswith("LIMIT 25"))
