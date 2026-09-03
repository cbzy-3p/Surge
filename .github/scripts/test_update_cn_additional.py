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


if __name__ == "__main__":
    unittest.main()
