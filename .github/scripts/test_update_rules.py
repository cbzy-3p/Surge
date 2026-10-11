import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_rules.py")
SPEC = importlib.util.spec_from_file_location("update_rules", SCRIPT)
assert SPEC and SPEC.loader
UPDATE_RULES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE_RULES)


class SurgeRuleTests(unittest.TestCase):
    def test_update_log_reports_each_files_own_source_counts(self):
        mapping = {"rabbit": None, "conners": None, "loyal": None, "yuu": None}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(UPDATE_RULES, "OUT", root), \
                 patch.object(UPDATE_RULES, "SNAPSHOT", root / "snapshot.json"), \
                 patch.object(UPDATE_RULES, "TARGETS", {"First": mapping, "Second": mapping}), \
                 patch.object(UPDATE_RULES, "fetch", side_effect=[
                     "DOMAIN-SUFFIX,one.example\n",
                     "DOMAIN-SUFFIX,two.example\nDOMAIN-SUFFIX,three.example\n",
                 ]), \
                 patch.object(UPDATE_RULES, "validate_bm7"), \
                 patch("builtins.print") as output:
                UPDATE_RULES.main()
                output.assert_any_call("First: BM7=1 sources=0 added=0 output=1")
                output.assert_any_call("Second: BM7=2 sources=0 added=0 output=2")

    def test_official_comment_forms_are_removed(self):
        text = """
        # first
        // second
        ; third
        DOMAIN-SUFFIX,example.com // inline
        URL-REGEX,^https://example.com/path
        """
        lines, _ = UPDATE_RULES.parse_bm7(text)
        self.assertEqual(
            lines,
            ["DOMAIN-SUFFIX,example.com", "URL-REGEX,^https://example.com/path"],
        )

    def test_current_surge_rule_types_are_accepted(self):
        valid = [
            "DOMAIN-SUFFIX,local",
            "DOMAIN-WILDCARD,*.example.com",
            "SRC-IP,192.168.1.0/24",
            "SRC-PORT,443",
            "HOSTNAME-TYPE,DOMAIN",
            "CELLULAR-RADIO,5G",
        ]
        for index, line in enumerate(valid, 1):
            UPDATE_RULES.validate_rule("Test", index, line)

    def test_forbidden_rule_set_entries_are_rejected(self):
        with self.assertRaises(RuntimeError):
            UPDATE_RULES.validate_rule("Test", 1, "FINAL")
        with self.assertRaises(RuntimeError):
            UPDATE_RULES.validate_rule(
                "Test", 2, "DOMAIN-SUFFIX,example.com,pre-matching"
            )

    def test_v2fly_full_domain_stays_exact(self):
        rules = UPDATE_RULES.parse_source_rules(
            "full:api.example.com\ndomain:example.org\n+.example.net\n", plain=True
        )
        self.assertEqual(
            rules,
            {
                ("DOMAIN", "api.example.com"),
                ("DOMAIN-SUFFIX", "example.org"),
                ("DOMAIN-SUFFIX", "example.net"),
            },
        )

    def test_source_history_rejects_large_changes(self):
        with self.assertRaises(RuntimeError):
            UPDATE_RULES.validate_snapshot_change({"source": 100}, {"source": 64})
        with self.assertRaises(RuntimeError):
            UPDATE_RULES.validate_snapshot_change({"source": 100}, {"source": 251})
        UPDATE_RULES.validate_snapshot_change({"source": 100}, {"source": 80})

    def test_base_rules_are_compacted_without_losing_non_domain_rules(self):
        lines = [
            "DOMAIN,api.example.com",
            "DOMAIN-SUFFIX,api.example.com",
            "DOMAIN-SUFFIX,example.com",
            "IP-CIDR,192.0.2.0/24,no-resolve",
        ]
        self.assertEqual(
            UPDATE_RULES.compact_rule_lines(lines),
            [
                "DOMAIN-SUFFIX,example.com",
                "IP-CIDR,192.0.2.0/24,no-resolve",
            ],
        )

    def test_supplemental_parent_suffix_compacts_base_children(self):
        output = UPDATE_RULES.render(
            "Example",
            [
                "DOMAIN-SUFFIX,api.example.com",
                "DOMAIN-SUFFIX,static.example.com",
            ],
            [("DOMAIN-SUFFIX", "example.com")],
            ["https://example.com/rules.list"],
            set(),
        )
        self.assertIn("DOMAIN-SUFFIX,example.com\n", output)
        self.assertNotIn("DOMAIN-SUFFIX,api.example.com\n", output)
        self.assertNotIn("DOMAIN-SUFFIX,static.example.com\n", output)
        self.assertIn("# RULE COUNT: 1\n", output)

    def test_domain_rules_with_different_options_are_preserved(self):
        lines = [
            "DOMAIN,api.example.com,extended-matching",
            "DOMAIN-SUFFIX,example.com",
        ]
        self.assertEqual(UPDATE_RULES.compact_rule_lines(lines), lines)

    def test_covered_cidr_is_removed(self):
        lines = [
            "IP-CIDR,192.0.2.0/24,no-resolve",
            "IP-CIDR,192.0.2.0/25,no-resolve",
        ]
        self.assertEqual(
            UPDATE_RULES.compact_rule_lines(lines),
            ["IP-CIDR,192.0.2.0/24,no-resolve"],
        )


if __name__ == "__main__":
    unittest.main()
