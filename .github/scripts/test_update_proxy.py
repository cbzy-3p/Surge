import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("proxy", Path(__file__).with_name("update_proxy.py"))
assert SPEC and SPEC.loader
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)


class ProxyRuleTests(unittest.TestCase):
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
                    stack.enter_context(patch.object(PROXY, name, value))
                parser = "parse_private_relay" if hasattr(PROXY, "parse_private_relay") else "parse_plain"
                stack.enter_context(patch.object(PROXY, parser, return_value=rules))
                stack.enter_context(patch("builtins.print"))
                PROXY.main()
                self.assertTrue(target.exists())
                before = (target.read_bytes(), snapshot.read_bytes())
                with patch.object(PROXY, "fetch", side_effect=RuntimeError("unavailable")):
                    with self.assertRaises(RuntimeError):
                        PROXY.main()
                self.assertEqual(before, (target.read_bytes(), snapshot.read_bytes()))

    def test_suffix_removes_covered_exact_domain(self):
        result = PROXY.merge({("DOMAIN", "api.example.com")}, {("DOMAIN-SUFFIX", "example.com")})
        self.assertEqual(result, {("DOMAIN-SUFFIX", "example.com")})

    def test_plain_domain_uses_suffix_semantics(self):
        self.assertEqual(PROXY.parse_plain("example.com\n"), {("DOMAIN-SUFFIX", "example.com")})

    def test_ip_rules_are_normalized(self):
        self.assertEqual(PROXY.parse_surge("IP-CIDR,1.1.1.1/24\n"), {("IP-CIDR", "1.1.1.0/24")})

    def test_parent_suffix_removes_child_suffix(self):
        self.assertEqual(
            PROXY.compact({
                ("DOMAIN-SUFFIX", "api.example.com"),
                ("DOMAIN-SUFFIX", "example.com"),
            }),
            {("DOMAIN-SUFFIX", "example.com")},
        )

    def test_cidrs_are_collapsed_without_losing_coverage(self):
        self.assertEqual(
            PROXY.compact({
                ("IP-CIDR", "192.0.2.0/25"),
                ("IP-CIDR", "192.0.2.128/25"),
            }),
            {("IP-CIDR", "192.0.2.0/24")},
        )

    def test_render_can_preserve_update_time(self):
        rendered = PROXY.render(
            {("DOMAIN-SUFFIX", "example.com")},
            "2026-01-02 03:04:05 UTC",
        )
        self.assertIn("# UPDATED: 2026-01-02 03:04:05 UTC\n", rendered)


if __name__ == "__main__":
    unittest.main()
