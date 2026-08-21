import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "data-agent" / "scripts"))
from analyze_data import run_query


class FakeAdapter:
    def query(self, sql, max_rows=1000):
        self.sql = sql
        self.max_rows = max_rows
        return ["region", "revenue"], [("East", 120)]


class DatabaseCliTests(unittest.TestCase):
    def test_query_writes_sql_result_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = run_query(FakeAdapter(), "SELECT region, revenue FROM orders", Path(directory), max_rows=100)
            self.assertEqual((output / "result.csv").read_text(encoding="utf-8"), "region,revenue\nEast,120\n")
            self.assertIn("LIMIT 100", (output / "analysis.sql").read_text(encoding="utf-8"))
            self.assertIn("Database analysis report", (output / "report.md").read_text(encoding="utf-8"))
