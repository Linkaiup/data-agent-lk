import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "data-agent" / "scripts"))
from semantic import load_semantic, validate_semantic


class SemanticTests(unittest.TestCase):
    def test_reports_unknown_table_and_dimension_column(self):
        semantic = {
            "source": "postgres",
            "tables": {"orders": {"grain": "one row", "dimensions": {"country": "nation"}, "metrics": {}, "joins": []}},
        }
        errors = validate_semantic(semantic, {"tables": {"public.orders": ["id", "country"]}})
        self.assertIn("unknown column: orders.nation", errors)

    def test_load_requires_semantic_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "semantic.json"
            path.write_text(json.dumps({"source": "postgres", "tables": {}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tables must not be empty"):
                load_semantic(path)

    def test_accepts_public_table_alias_and_valid_dimensions(self):
        semantic = {
            "source": "postgres",
            "tables": {"orders": {"grain": "one row per order", "dimensions": {"country": "country"}, "metrics": {}, "joins": []}},
        }
        self.assertEqual(validate_semantic(semantic, {"tables": {"public.orders": ["id", "country"]}}), [])
