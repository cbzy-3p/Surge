import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_rules.py")
SPEC = importlib.util.spec_from_file_location("update_rules", SCRIPT)
assert SPEC and SPEC.loader
UPDATE_RULES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE_RULES)


class SurgeRuleTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
