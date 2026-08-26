import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_douyin.py")
SPEC = importlib.util.spec_from_file_location("update_douyin", SCRIPT)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class DouyinRuleTests(unittest.TestCase):
    def test_v2fly_domains_are_suffix_rules(self):
        self.assertEqual(
            UPDATE.parse_v2fly("full:api.douyin.com\ndomain:example.com\nkeyword:ignore\n"),
            {("DOMAIN-SUFFIX", "api.douyin.com"), ("DOMAIN-SUFFIX", "example.com")},
        )

    def test_suffix_replaces_exact_duplicate(self):
        rules = UPDATE.parse_surge_rules("DOMAIN,api.douyin.com\nDOMAIN-SUFFIX,douyin.com\n")
        UPDATE.merge_rule(rules, ("DOMAIN-SUFFIX", "api.douyin.com"))
        self.assertNotIn(("DOMAIN", "api.douyin.com"), rules)

    def test_unsupported_ip_rules_are_ignored(self):
        self.assertEqual(UPDATE.parse_surge_rules("IP-CIDR,1.1.1.1/32,no-resolve\n"), set())

    def test_existing_keyword_rules_are_preserved(self):
        self.assertEqual(
            UPDATE.parse_surge_rules("DOMAIN-KEYWORD,douyin\n"),
            {("DOMAIN-KEYWORD", "douyin")},
        )


if __name__ == "__main__":
    unittest.main()
