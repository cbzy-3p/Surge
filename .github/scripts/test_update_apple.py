import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("apple", Path(__file__).with_name("update_apple.py"))
assert SPEC and SPEC.loader
APPLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLE)


class AppleRuleTests(unittest.TestCase):
    def test_skk_watermark_is_excluded(self):
        text = f"DOMAIN,{APPLE.SKK_WATERMARK}\nDOMAIN-SUFFIX,apple.com\n"
        self.assertEqual(APPLE.parse_surge(text), {("DOMAIN-SUFFIX", "apple.com")})

    def test_parent_suffix_removes_redundant_rules(self):
        rules = {
            ("DOMAIN", "api.apple.com"),
            ("DOMAIN-SUFFIX", "apple.com"),
            ("DOMAIN-SUFFIX", "api.apple.com"),
        }
        self.assertEqual(APPLE.compact(rules), {("DOMAIN-SUFFIX", "apple.com")})

    def test_plain_plus_prefix_becomes_suffix(self):
        self.assertEqual(APPLE.parse_plain("+.apple.com\n"), {("DOMAIN-SUFFIX", "apple.com")})

    def test_render_can_preserve_update_time(self):
        rendered = APPLE.render({("DOMAIN-SUFFIX", "apple.com")}, "2026-01-02 03:04:05 UTC")
        self.assertIn("# UPDATED: 2026-01-02 03:04:05 UTC\n", rendered)


if __name__ == "__main__":
    unittest.main()
