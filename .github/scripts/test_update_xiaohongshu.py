import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_xiaohongshu.py")
SPEC = importlib.util.spec_from_file_location("update_xiaohongshu", SCRIPT)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class XiaoHongShuRuleTests(unittest.TestCase):
    def test_surge_domain_semantics_are_preserved(self):
        rules = UPDATE.parse_surge_rules(
            "DOMAIN,api.xiaohongshu.com\nDOMAIN-SUFFIX,api.xiaohongshu.com\n"
        )
        self.assertEqual(rules, {("DOMAIN-SUFFIX", "api.xiaohongshu.com")})

    def test_non_domain_rules_are_not_merged(self):
        rules = UPDATE.parse_surge_rules(
            "IP-CIDR,43.159.95.0/24,no-resolve\nDOMAIN-KEYWORD,xiaohongshu\nIP-ASN,151281\n"
        )
        self.assertEqual(rules, {("IP-ASN", "151281")})

    def test_invalid_asn_is_rejected(self):
        self.assertIsNone(UPDATE.normalize_asn("0"))
        self.assertIsNone(UPDATE.normalize_asn("not-an-asn"))
        self.assertEqual(UPDATE.normalize_asn("151282"), "151282")

    def test_v2fly_full_domain_stays_exact(self):
        original = UPDATE.fetch_text
        try:
            UPDATE.fetch_text = lambda _: "full:api.xiaohongshu.com\n"
            rules = UPDATE.parse_v2fly("test")
        finally:
            UPDATE.fetch_text = original
        self.assertEqual(rules, {("DOMAIN", "api.xiaohongshu.com")})

    def test_source_history_rejects_large_changes(self):
        with self.assertRaises(RuntimeError):
            UPDATE.validate_snapshot_change({"bgpeer": 100}, {"bgpeer": 64})
        UPDATE.validate_snapshot_change({"bgpeer": 100}, {"bgpeer": 80})


if __name__ == "__main__":
    unittest.main()
