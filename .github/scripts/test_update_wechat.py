import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "wechat", Path(__file__).with_name("update_wechat.py")
)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class WeChatRuleTests(unittest.TestCase):
    def test_parent_suffix_removes_child_domains(self):
        rules = {
            "DOMAIN,api.example.com",
            "DOMAIN-SUFFIX,api.example.com",
            "DOMAIN-SUFFIX,example.com",
        }
        self.assertEqual(UPDATE.dedupe_rules(rules), {"DOMAIN-SUFFIX,example.com"})

    def test_cidrs_are_collapsed(self):
        rules = {
            "IP-CIDR,192.0.2.0/25,no-resolve",
            "IP-CIDR,192.0.2.128/25,no-resolve",
        }
        self.assertEqual(
            UPDATE.dedupe_rules(rules),
            {"IP-CIDR,192.0.2.0/24,no-resolve"},
        )


if __name__ == "__main__":
    unittest.main()
