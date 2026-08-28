import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_rule_files.py")
SPEC = importlib.util.spec_from_file_location("validate_rule_files", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RuleFileValidationTests(unittest.TestCase):
    def test_cn_domain_set_entries_are_validated(self):
        result = VALIDATOR.validate_text(Path("CN-Additional.list"), ".example.com\n")
        self.assertEqual(result["rules"], 1)

    def test_domain_suffix_overlap_is_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "DOMAIN,example.com\nDOMAIN-SUFFIX,example.com\n",
            )

    def test_duplicate_rules_are_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(Path("sample.list"), "DOMAIN-SUFFIX,example.com\nDOMAIN-SUFFIX,example.com\n")

    def test_top_level_domain_suffix_is_valid(self):
        result = VALIDATOR.validate_text(Path("sample.list"), "DOMAIN-SUFFIX,cn\n")
        self.assertEqual(result["rules"], 1)


if __name__ == "__main__":
    unittest.main()
