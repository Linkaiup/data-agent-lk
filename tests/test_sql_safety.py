import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "data-agent" / "scripts"))
from sql_safety import apply_limit, validate_read_only


class SqlSafetyTests(unittest.TestCase):
    def test_allows_replace_function_in_select(self):
        self.assertTrue(validate_read_only("SELECT REPLACE(name, 'a', 'b') FROM data").startswith("SELECT"))

    def test_appends_limit_when_absent(self):
        self.assertTrue(apply_limit("SELECT * FROM orders", 1000).endswith("LIMIT 1000"))

    def test_preserves_explicit_limit(self):
        self.assertEqual(apply_limit("SELECT * FROM orders LIMIT 10", 1000), "SELECT * FROM orders LIMIT 10")

    def test_rejects_multiple_or_mutating_statements(self):
        with self.assertRaisesRegex(ValueError, "read-only"):
            validate_read_only("SELECT 1; DELETE FROM orders")
