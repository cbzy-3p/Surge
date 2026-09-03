import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "compact_rule_file", Path(__file__).with_name("compact_rule_file.py")
)
assert SPEC and SPEC.loader
COMPACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPACTOR)


class CompactRuleFileTests(unittest.TestCase):
    def test_covered_domains_and_cidrs_are_removed(self):
        output, removed = COMPACTOR.compact_text(
            "# Header\n"
            "DOMAIN,api.example.com\n"
            "DOMAIN-SUFFIX,api.example.com\n"
            "DOMAIN-SUFFIX,example.com\n"
            "IP-CIDR,192.0.2.0/24,no-resolve\n"
            "IP-CIDR,192.0.2.0/25,no-resolve\n"
        )
        self.assertEqual(
            output,
            "# Header\nDOMAIN-SUFFIX,example.com\nIP-CIDR,192.0.2.0/24,no-resolve\n",
        )
        self.assertEqual(removed, 3)

    def test_different_options_are_preserved(self):
        text = "DOMAIN,api.example.com,extended-matching\nDOMAIN-SUFFIX,example.com\n"
        output, removed = COMPACTOR.compact_text(text)
        self.assertEqual(output, text)
        self.assertEqual(removed, 0)

    def test_domain_set_suffixes_are_compacted(self):
        output, removed = COMPACTOR.compact_text(
            ".api.example.com\n.example.com\nexact.example.net\n",
            domain_set=True,
        )
        self.assertEqual(output, ".example.com\nexact.example.net\n")
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
