import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "cn_additional", Path(__file__).with_name("update_cn_additional.py")
)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class CNAdditionalTests(unittest.TestCase):
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
