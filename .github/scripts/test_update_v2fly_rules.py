#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("update_v2fly_rules.py")
SPEC = importlib.util.spec_from_file_location("update_v2fly_rules", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UpdateV2FlyRulesTest(unittest.TestCase):
    def test_parse_yuu_surge_rules(self):
        data = "# comment\nDOMAIN,api.example.com\nDOMAIN-SUFFIX,example.com\nIP-CIDR,1.1.1.0/24\n"
        rules, sources = MODULE.parse_yuu("test", lambda _: data)
        self.assertEqual(rules, {("DOMAIN-SUFFIX", "example.com")})
        self.assertEqual(sources, {f"{MODULE.YUU_BASE}/test.list"})

    def test_parse_supported_rules_and_attributes(self):
        data = "example.com\nfull:api.example.net @cn\ndomain:cdn.example.org\nkeyword:wallet\n"
        rules, _ = MODULE.parse_entry("test", lambda _: data)
        self.assertEqual(
            rules,
            {
                ("DOMAIN-SUFFIX", "example.com"),
                ("DOMAIN", "api.example.net"),
                ("DOMAIN-SUFFIX", "cdn.example.org"),
                ("DOMAIN-KEYWORD", "wallet"),
            },
        )

    def test_include_is_resolved_once(self):
        data = {
            f"{MODULE.BASE}/root": "include:child\nroot.example\ninclude:child\n",
            f"{MODULE.BASE}/child": "child.example\n",
        }
        rules, sources = MODULE.parse_entry("root", data.__getitem__)
        self.assertEqual(rules, {("DOMAIN-SUFFIX", "root.example"), ("DOMAIN-SUFFIX", "child.example")})
        self.assertEqual(len(sources), 2)

    def test_parent_suffix_removes_children_and_exact_domains(self):
        rules = MODULE.compact(
            {
                ("DOMAIN-SUFFIX", "example.com"),
                ("DOMAIN-SUFFIX", "api.example.com"),
                ("DOMAIN", "login.example.com"),
                ("DOMAIN", "other.example.net"),
            }
        )
        self.assertEqual(rules, {("DOMAIN-SUFFIX", "example.com"), ("DOMAIN", "other.example.net")})

    def test_regexp_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported V2Fly regexp"):
            MODULE.parse_entry("test", lambda _: "regexp:^example\\.com$\n")

    def test_render_has_count_and_source(self):
        output = MODULE.render("Example", {("DOMAIN-SUFFIX", "example.com")}, {f"{MODULE.BASE}/example"})
        self.assertIn("# RULE COUNT: 1\n", output)
        self.assertIn(f"# SOURCE: {MODULE.BASE}/example\n", output)
        self.assertTrue(output.endswith("DOMAIN-SUFFIX,example.com\n"))


if __name__ == "__main__":
    unittest.main()
