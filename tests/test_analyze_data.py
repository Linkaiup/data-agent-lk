"""Acceptance tests for the local data-agent helper."""

import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "data-agent" / "scripts" / "analyze_data.py"


def write_sales_csv(path: Path) -> None:
    path.write_text(
        "month,region,revenue,orders\n"
        "2026-01,East,120,12\n"
        "2026-02,East,180,18\n"
        "2026-01,West,90,9\n"
        "2026-02,West,150,15\n",
        encoding="utf-8",
    )


def run_agent(data_file: Path, output_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "analyze", str(data_file), "--output-dir", str(output_dir), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class AnalyzeDataTests(unittest.TestCase):
    def test_analyze_writes_reproducible_profile_report_and_svg_chart(self) -> None:
        tmp_path = Path(self._tmp_dir)
        source = tmp_path / "sales.csv"
        output = tmp_path / "analysis"
        write_sales_csv(source)

        result = run_agent(source, output, "--chart", "bar", "--x", "region", "--y", "revenue")

        self.assertEqual(result.returncode, 0, result.stderr)
        profile = json.loads((output / "profile.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["row_count"], 4)
        self.assertEqual(profile["columns"]["revenue"]["type"], "number")
        self.assertTrue((output / "report.md").read_text(encoding="utf-8").startswith("# Data analysis report"))
        self.assertIn('SUM("revenue")', (output / "analysis.sql").read_text(encoding="utf-8"))
        self.assertIn("<svg", (output / "chart.svg").read_text(encoding="utf-8"))


    def test_query_rejects_mutating_sql_and_preserves_data(self) -> None:
        tmp_path = Path(self._tmp_dir)
        source = tmp_path / "sales.csv"
        output = tmp_path / "analysis"
        write_sales_csv(source)

        result = run_agent(source, output, "--sql", "DELETE FROM data")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Only a single read-only SELECT or WITH query is allowed", result.stderr)
        with source.open(encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 4)

    def setUp(self) -> None:
        import tempfile

        self._temp_dir = tempfile.TemporaryDirectory()
        self._tmp_dir = self._temp_dir.name

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
