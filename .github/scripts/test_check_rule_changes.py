import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_rule_changes as CHECK


def rules(count: int, prefix: str = "host") -> set[str]:
    return {f"DOMAIN-SUFFIX,{prefix}{number}.example" for number in range(count)}


class RuleChangeTests(unittest.TestCase):
    def test_small_change_is_reported_without_failure(self):
        baseline = {"Rule/Test.list": rules(100)}
        current = {"Rule/Test.list": rules(103)}
        lines, errors = CHECK.compare_rules(baseline, baseline, current, {})
        self.assertEqual(errors, [])
        self.assertIn("+3 -0", lines[0])

    def test_same_count_replacement_checks_both_directions(self):
        baseline = {"Rule/Test.list": rules(100)}
        current = {"Rule/Test.list": rules(100, "replacement")}
        _lines, errors = CHECK.compare_rules(baseline, baseline, current, {})
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("+100 -100" in error for error in errors))

    def test_small_daily_growth_cannot_move_fixed_baseline(self):
        baseline = {"Rule/Test.list": rules(100)}
        previous = {"Rule/Test.list": rules(120)}
        current = {"Rule/Test.list": rules(121)}
        _lines, errors = CHECK.compare_rules(baseline, previous, current, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("baseline change exceeds 20", errors[0])

    def test_equal_threshold_is_allowed_and_next_rule_is_blocked(self):
        baseline = {"Rule/Test.list": rules(100)}
        current = {"Rule/Test.list": rules(110)}
        self.assertEqual(CHECK.compare_rules(baseline, baseline, current, {})[1], [])
        current["Rule/Test.list"] = rules(111)
        self.assertIn("previous change exceeds 10", CHECK.compare_rules(baseline, baseline, current, {})[1][0])

    def test_missing_or_added_files_cannot_pass_by_matching_hash(self):
        baseline = {"Rule/Test.list": rules(10)}
        current = {"Rule/New.list": rules(10)}
        policy = {"reviewed_current_hashes": {"Rule/New.list": CHECK.rules_hash(rules(10))}}
        _lines, errors = CHECK.compare_rules(baseline, baseline, current, policy)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("missing from reviewed baseline" in error for error in errors))
        self.assertTrue(any("missing from working tree" in error for error in errors))

    def test_explicit_new_file_requires_exact_content_and_presence(self):
        baseline = {"Rule/Test.list": rules(10)}
        new = "Rule/New.list"
        policy = {"reviewed_new_hashes": {new: CHECK.rules_hash(rules(2))}}
        self.assertEqual(CHECK.compare_rules(baseline, baseline, {**baseline, new: rules(2)}, policy)[1], [])
        self.assertTrue(CHECK.compare_rules(baseline, baseline, {**baseline, new: rules(3)}, policy)[1])
        self.assertTrue(CHECK.compare_rules(baseline, baseline, baseline, policy)[1])

    def test_only_exact_reviewed_hash_bypasses_change_threshold(self):
        baseline = {"Rule/Test.list": rules(100)}
        current = {"Rule/Test.list": rules(40)}
        policy = {"reviewed_current_hashes": {"Rule/Test.list": CHECK.rules_hash(current["Rule/Test.list"])}}
        self.assertEqual(CHECK.compare_rules(baseline, baseline, current, policy)[1], [])
        current["Rule/Test.list"] = rules(41)
        self.assertEqual(len(CHECK.compare_rules(baseline, baseline, current, policy)[1]), 2)

    def test_shared_growth_uses_fixed_baseline_and_does_not_count_existing_overlap(self):
        shared_before = rules(20, "existing")
        baseline = {
            "Rule/Apple.list": rules(200, "apple") | shared_before,
            "Rule/GlobalMedia.list": rules(200, "media") | shared_before,
        }
        policy = {"disjoint_pairs": [("Rule/Apple.list", "Rule/GlobalMedia.list")]}
        previous = {path: data | rules(9, "new") for path, data in baseline.items()}
        current = {path: data | rules(10, "new") for path, data in baseline.items()}
        policy["reviewed_current_hashes"] = {path: CHECK.rules_hash(data) for path, data in current.items()}
        _lines, errors = CHECK.compare_rules(baseline, previous, current, policy)
        self.assertEqual(len(errors), 1)
        self.assertIn("10 new shared rules", errors[0])
        self.assertEqual(CHECK.compare_rules(baseline, previous, previous, policy)[1], [])

    def test_invalid_empty_and_duplicate_data_fail_validation(self):
        for text in ("", "# only comments\n", "DOMAIN,invalid name\n", "DOMAIN,example.com\nDOMAIN,example.com\n"):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                CHECK.canonical_rules(Path("Test.list"), text)

    def test_domain_set_preserves_exact_and_suffix_semantics(self):
        path = Path("CN-Additional.list")
        self.assertEqual(CHECK.canonical_rules(path, "example.com\n"), {"DOMAIN,example.com"})
        self.assertEqual(CHECK.canonical_rules(path, ".example.com\n"), {"DOMAIN-SUFFIX,example.com"})

    def test_comments_order_case_and_cidr_spelling_do_not_create_drift(self):
        path = Path("Test.list")
        first = CHECK.canonical_rules(path, "# Updated today\nDOMAIN,Example.COM.\nIP-CIDR,192.0.2.3/24,no-resolve\n")
        second = CHECK.canonical_rules(path, "IP-CIDR,192.0.2.0/24,no-resolve\nDOMAIN,example.com\n")
        self.assertEqual(first, second)
        self.assertEqual(CHECK.rules_hash(first), CHECK.rules_hash(second))

    def test_output_has_stable_order_and_at_most_five_samples(self):
        baseline = {"Rule/Z.list": rules(100), "Rule/A.list": rules(100)}
        current = {path: rules(101) for path in reversed(baseline)}
        left = CHECK.compare_rules(baseline, baseline, current, {})
        right = CHECK.compare_rules(dict(reversed(list(baseline.items()))), baseline, current, {})
        self.assertEqual(left, right)
        self.assertEqual(len(CHECK.sample(rules(20)).split("; ")), 5)

    def test_policy_requires_pinned_commit_and_normalizes_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            policy = {"version": 1, "baseline_commit": "a" * 40, "disjoint_pairs": [["Apple.list", "Rule/GlobalMedia.list"]]}
            path.write_text(json.dumps(policy))
            self.assertEqual(CHECK.load_policy(path)["disjoint_pairs"], [("Rule/Apple.list", "Rule/GlobalMedia.list")])
            policy["baseline_commit"] = "main"
            path.write_text(json.dumps(policy))
            with self.assertRaises(ValueError):
                CHECK.load_policy(path)
            for value in ("../outside.list", "/tmp/file.list", "Rule/not-a-rule.json"):
                with self.assertRaises(ValueError):
                    CHECK.rule_path(value)

    def test_report_writes_all_errors_to_stdout_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            stdout = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), contextlib.redirect_stdout(stdout):
                CHECK.write_report(["Rule/Test.list +5 -3"], ["failure one", "failure two"])
            for content in (stdout.getvalue(), summary.read_text()):
                self.assertIn("Rule change review FAILED", content)
                self.assertIn("failure one", content)
                self.assertIn("failure two", content)


class GitIntegrationTests(unittest.TestCase):
    def test_revision_current_nested_rules_and_missing_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            nested = root / "Rule" / "Telegram"
            nested.mkdir(parents=True)
            target = nested / "All.list"
            target.write_text("DOMAIN-SUFFIX,telegram.org\n")
            subprocess.run(["git", "-C", str(root), "add", "Rule"], check=True)
            subprocess.run([
                "git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "-qm", "baseline",
            ], check=True)
            commit = CHECK.resolve_commit(root, "HEAD")
            baseline, errors = CHECK.read_revision(root, commit)
            self.assertEqual(errors, [])
            self.assertEqual(set(baseline), {"Rule/Telegram/All.list"})
            target.write_text("")
            current, errors = CHECK.read_worktree(root)
            self.assertEqual(current, {})
            self.assertTrue(any("no rules found" in error for error in errors))
            with self.assertRaises(RuntimeError):
                CHECK.resolve_commit(root, "f" * 40)
            target.unlink()
            current, errors = CHECK.read_worktree(root)
            self.assertTrue(errors)
            self.assertIn("missing from working tree", CHECK.compare_rules(baseline, baseline, current, {})[1][0])


if __name__ == "__main__":
    unittest.main()
