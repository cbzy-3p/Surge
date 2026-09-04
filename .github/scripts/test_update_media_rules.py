import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("media", Path(__file__).with_name("update_media_rules.py"))
assert SPEC and SPEC.loader
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)


class MediaRuleTests(unittest.TestCase):
    def test_user_agent_with_space_is_preserved(self):
        self.assertEqual(
            MEDIA.normalize_rule("USER-AGENT", "Prime Video*"),
            ("USER-AGENT", "Prime Video*"),
        )

    def test_plain_domain_variants_are_suffixes(self):
        rules = MEDIA.parse_domains(".example.com\n+.example.net\ndomain:example.org\n")
        self.assertEqual(rules, {
            ("DOMAIN-SUFFIX", "example.com"),
            ("DOMAIN-SUFFIX", "example.net"),
            ("DOMAIN-SUFFIX", "example.org"),
        })

    def test_full_domain_stays_exact(self):
        self.assertEqual(
            MEDIA.parse_domains("full:api.example.com\n"),
            {("DOMAIN", "api.example.com")},
        )

    def test_parent_suffix_removes_covered_domain_rules(self):
        rules = {
            ("DOMAIN", "api.example.com"),
            ("DOMAIN-SUFFIX", "api.example.com"),
            ("DOMAIN-SUFFIX", "example.com"),
        }
        self.assertEqual(MEDIA.compact(rules), {("DOMAIN-SUFFIX", "example.com")})

    def test_cidrs_are_collapsed_without_losing_coverage(self):
        rules = {
            ("IP-CIDR", "192.0.2.0/25"),
            ("IP-CIDR", "192.0.2.128/25"),
            ("IP-CIDR6", "2001:db8::/32"),
        }
        self.assertEqual(MEDIA.compact(rules), {
            ("IP-CIDR", "192.0.2.0/24"),
            ("IP-CIDR6", "2001:db8::/32"),
        })

    def test_render_can_preserve_update_time(self):
        rendered = MEDIA.render(
            "YouTube",
            {("DOMAIN-SUFFIX", "youtube.com")},
            ["https://example.com/youtube.list"],
            "2026-01-02 03:04:05 UTC",
        )
        self.assertIn("# UPDATED: 2026-01-02 03:04:05 UTC\n", rendered)

    def test_write_creates_a_missing_target(self):
        original = MEDIA.RULE_DIR
        with tempfile.TemporaryDirectory() as directory:
            MEDIA.RULE_DIR = Path(directory)
            try:
                MEDIA.write_if_changed(
                    "YouTube",
                    {("DOMAIN-SUFFIX", "youtube.com")},
                    ["https://example.com/youtube.list"],
                )
                self.assertTrue((Path(directory) / "YouTube.list").exists())
            finally:
                MEDIA.RULE_DIR = original

    def test_case_variants_have_a_stable_order(self):
        rendered = MEDIA.render(
            "ChinaMedia",
            {("USER-AGENT", "iQiyi*"), ("USER-AGENT", "iQiYi*")},
            ["https://example.com/media.list"],
            "2026-01-02 03:04:05 UTC",
        )
        self.assertLess(rendered.index("USER-AGENT,iQiYi*"), rendered.index("USER-AGENT,iQiyi*"))

    def test_skk_watermark_is_excluded(self):
        watermark = next(iter(MEDIA.BLOCKED_EXACT_DOMAINS))
        self.assertEqual(MEDIA.parse_surge(f"DOMAIN,{watermark}\n"), set())


if __name__ == "__main__":
    unittest.main()
