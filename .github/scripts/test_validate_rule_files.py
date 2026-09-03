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

    def test_parent_domain_suffix_overlap_is_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "DOMAIN-SUFFIX,api.example.com\nDOMAIN-SUFFIX,example.com\n",
            )

    def test_exact_subdomain_covered_by_suffix_is_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "DOMAIN,api.example.com\nDOMAIN-SUFFIX,example.com\n",
            )

    def test_parent_cidr_overlap_is_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "IP-CIDR,192.0.2.0/24,no-resolve\n"
                "IP-CIDR,192.0.2.0/25,no-resolve\n",
            )

    def test_logical_or_overlap_is_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "OR,((DOMAIN,api.example.com),(DOMAIN-SUFFIX,example.com)),Proxy\n",
            )

    def test_different_options_are_not_treated_as_redundant(self):
        result = VALIDATOR.validate_text(
            Path("sample.list"),
            "DOMAIN,api.example.com,extended-matching\n"
            "DOMAIN-SUFFIX,example.com\n",
        )
        self.assertEqual(result["rules"], 2)

    def test_duplicate_rules_are_rejected(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(Path("sample.list"), "DOMAIN-SUFFIX,example.com\nDOMAIN-SUFFIX,example.com\n")

    def test_top_level_domain_suffix_is_valid(self):
        result = VALIDATOR.validate_text(Path("sample.list"), "DOMAIN-SUFFIX,cn\n")
        self.assertEqual(result["rules"], 1)

    def test_declared_rule_count_must_match(self):
        with self.assertRaises(RuntimeError):
            VALIDATOR.validate_text(
                Path("sample.list"),
                "# RULE COUNT: 2\nDOMAIN-SUFFIX,example.com\n",
            )


if __name__ == "__main__":
    unittest.main()
