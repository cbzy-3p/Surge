import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "cn_additional", Path(__file__).with_name("update_cn_additional.py")
)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class CNAdditionalTests(unittest.TestCase):
    def test_invalid_source_preserves_output_and_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "CN-Additional.list"
            snapshot = Path(directory) / "snapshot.json"
            target.write_text(".example.com\n")
            snapshot.write_text("old snapshot")
            with patch.object(UPDATE, "OUTPUT_PATH", target), patch.object(UPDATE, "SNAPSHOT_PATH", snapshot), \
                 patch.object(UPDATE, "MINIMUM_OUTPUT", 1), \
                 patch.object(UPDATE, "fetch_source", return_value="example.com\n<html>\n"):
                with self.assertRaises(RuntimeError):
                    UPDATE.main()
            self.assertEqual(target.read_text(), ".example.com\n")
            self.assertEqual(snapshot.read_text(), "old snapshot")

    def test_missing_snapshot_does_not_disable_output_drop_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "CN-Additional.list"
            snapshot = Path(directory) / "snapshot.json"
            old = "".join(f".x{i}.example.com\n" for i in range(30))
            target.write_text(old)
            with patch.object(UPDATE, "OUTPUT_PATH", target), patch.object(UPDATE, "SNAPSHOT_PATH", snapshot), \
                 patch.object(UPDATE, "MINIMUM_OUTPUT", 1), \
                 patch.object(UPDATE, "fetch_source", return_value="other.example\n"):
                with self.assertRaises(RuntimeError):
                    UPDATE.main()
            self.assertEqual(target.read_text(), old)
            self.assertFalse(snapshot.exists())

    def test_parent_suffix_removes_child_domain(self):
        domains, invalid = UPDATE.convert("api.example.com\nexample.com\nother.example\n")
        self.assertEqual(domains, ["example.com", "other.example"])
        self.assertEqual(invalid, [])

    def test_invalid_lines_are_reported(self):
        domains, invalid = UPDATE.convert("example.com\nnot a domain\n")
        self.assertEqual(domains, ["example.com"])
        self.assertEqual(invalid, ["not a domain"])

    def test_valid_source_count_is_normalized_and_deduplicated(self):
        count = UPDATE.count_valid_unique_domains(
            "example.com\nEXAMPLE.com\n.foo.com\nDOMAIN-SUFFIX,bar.com\n"
        )
        self.assertEqual(count, 3)

    def test_snapshot_rejects_suspicious_changes(self):
        with self.assertRaises(RuntimeError):
            UPDATE.validate_snapshot({"output": 100}, {"output": 64})
        with self.assertRaises(RuntimeError):
            UPDATE.validate_snapshot({"output": 100}, {"output": 251})
        UPDATE.validate_snapshot({"output": 100}, {"output": 80})

    def test_domain_set_output_uses_leading_dot(self):
        self.assertEqual(
            UPDATE.render_output(["example.com", "other.example"]),
            ".example.com\n.other.example\n",
        )


if __name__ == "__main__":
    unittest.main()
