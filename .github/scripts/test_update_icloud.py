import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("icloud", Path(__file__).with_name("update_icloud.py"))
assert SPEC and SPEC.loader
ICLOUD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ICLOUD)


class ICloudRuleTests(unittest.TestCase):
    def test_missing_target_is_rebuilt_and_fetch_failure_preserves_files(self):
        rules = {("DOMAIN", f"x{i}.icloud.com") for i in range(30)}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rules.list"
            snapshot = Path(directory) / "snapshot.json"
            from contextlib import ExitStack
            with ExitStack() as stack:
                for name, value in [("TARGET", target), ("SNAPSHOT", snapshot),
                                    ("MINIMUMS", {}), ("fetch", lambda url: ""),
                                    ("parse_surge", lambda *a, **kw: rules)]:
                    stack.enter_context(patch.object(ICLOUD, name, value))
                parser = "parse_private_relay" if hasattr(ICLOUD, "parse_private_relay") else "parse_plain"
                stack.enter_context(patch.object(ICLOUD, parser, return_value=rules))
                stack.enter_context(patch("builtins.print"))
                ICLOUD.main()
                self.assertTrue(target.exists())
                before = (target.read_bytes(), snapshot.read_bytes())
                with patch.object(ICLOUD, "fetch", side_effect=RuntimeError("unavailable")):
                    with self.assertRaises(RuntimeError):
                        ICLOUD.main()
                self.assertEqual(before, (target.read_bytes(), snapshot.read_bytes()))

    def test_apple_wide_sources_are_filtered_to_icloud(self):
        text = (
            "DOMAIN-SUFFIX,icloud.com\n"
            "DOMAIN-SUFFIX,apple-cloudkit.com\n"
            "DOMAIN-SUFFIX,me.com\n"
            "DOMAIN-SUFFIX,apple.com\n"
            "DOMAIN-SUFFIX,cdn-apple.com\n"
        )
        self.assertEqual(
            ICLOUD.parse_surge(text),
            {
                ("DOMAIN-SUFFIX", "icloud.com"),
                ("DOMAIN-SUFFIX", "apple-cloudkit.com"),
                ("DOMAIN-SUFFIX", "me.com"),
            },
        )

    def test_dedicated_source_keeps_its_curated_icloud_dependencies(self):
        text = "DOMAIN-SUFFIX,cdn-apple.com\nDOMAIN-SUFFIX,icloud.com\n"
        self.assertEqual(
            ICLOUD.parse_surge(text, dedicated=True),
            {("DOMAIN-SUFFIX", "cdn-apple.com"), ("DOMAIN-SUFFIX", "icloud.com")},
        )

    def test_parent_suffix_removes_redundant_rules(self):
        rules = {
            ("DOMAIN", "quota.icloud.com"),
            ("DOMAIN-SUFFIX", "icloud.com"),
            ("DOMAIN-SUFFIX", "api.icloud.com"),
            ("DOMAIN-KEYWORD", "icloud.com.akadns.net"),
        }
        self.assertEqual(
            ICLOUD.compact(rules),
            {("DOMAIN-SUFFIX", "icloud.com"), ("DOMAIN-KEYWORD", "icloud.com.akadns.net")},
        )

    def test_private_relay_parser_keeps_only_icloud_endpoints(self):
        text = (
            "mask.icloud.com\n"
            "mask.apple-dns.net\n"
            "canary.mask.apple-dns.net\n"
            "example.com\n"
        )
        self.assertEqual(
            ICLOUD.parse_private_relay(text),
            {
                ("DOMAIN", "mask.icloud.com"),
                ("DOMAIN", "mask.apple-dns.net"),
                ("DOMAIN", "canary.mask.apple-dns.net"),
            },
        )

    def test_render_declares_rule_count_and_fixed_sources(self):
        rendered = ICLOUD.render({("DOMAIN-SUFFIX", "icloud.com")}, "2026-01-02 03:04:05 UTC")
        self.assertIn("# RULE COUNT: 1\n", rendered)
        self.assertIn("SukkaW/Surge", rendered)
        self.assertIn("blackmatrix7/ios_rule_script", rendered)


if __name__ == "__main__":
    unittest.main()
