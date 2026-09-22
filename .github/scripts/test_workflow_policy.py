"""Regression checks for updater entry points, without third-party dependencies.

These check repository invariants; use actionlint for full workflow syntax.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ENTRY_POINTS = (
    "sync-telegram-rules", "update-apple-intelligence", "update-cn-additional",
    "update-douyin", "update-wechat", "update-xiaohongshu", "update-twitter",
)


def read_workflow(name):
    return (WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8")


class WorkflowPolicyTests(unittest.TestCase):
    def test_manual_entries_delegate_without_separate_commits(self):
        for name in ENTRY_POINTS:
            with self.subTest(workflow=name):
                text = read_workflow(name)
                update = text.split("\n  update:\n", 1)[1]
                self.assertIn("uses: ./.github/workflows/update-rules.yml", update)
                self.assertNotIn("steps:", update)
                self.assertNotIn("git push", text)
                self.assertNotIn("git-auto-commit-action", text)
                self.assertNotIn("schedule:", text)
                self.assertNotIn("surge-generated-content", text)
                self.assertIn("contents: write", text)

    def test_reusable_pipeline_keeps_write_event_guard(self):
        text = read_workflow("update-rules")
        self.assertIn("\n  workflow_call:\n", text)
        update = text.split("\n  update:\n", 1)[1]
        self.assertIn("if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'", update)
        self.assertNotIn("workflow_call'", update)
        self.assertIn("contents: write", update)

    def test_generated_content_writers_share_lock_and_refresh_branch(self):
        rules = read_workflow("update-rules")
        modules = read_workflow("update-modules")
        self.assertNotIn("\nconcurrency:", rules)
        update = rules.split("\n  update:\n", 1)[1]
        group = re.search(r"group: (.+)", update).group(1)
        self.assertIn("group: " + group.replace("${{ github.ref }}", "refs/heads/main"), modules)
        self.assertIn("ref: ${{ github.ref }}", update)
        self.assertIn("ref: main", modules)
        self.assertIn("cancel-in-progress: false", update)
        self.assertIn("cancel-in-progress: false", modules)
        self.assertIn("queue: max", update)
        self.assertIn("queue: max", modules)

    def test_full_validation_precedes_joint_snapshot_commit(self):
        update = read_workflow("update-rules").split("\n  update:\n", 1)[1]
        self.assertLess(update.index("test_workflow_policy.py"), update.index("python .github/scripts/update_rules.py"))
        self.assertLess(update.index('test "$count" -ge 2'), update.index("Validate all generated rules"))
        self.assertLess(update.index("python .github/scripts/validate_rule_files.py"), update.index("git add Rule .github/*-snapshot.json"))
        self.assertLess(update.index("git diff --check"), update.index("git commit"))

    def test_existing_pr_checks_are_retained(self):
        for name in ("update-douyin", "update-xiaohongshu"):
            with self.subTest(workflow=name):
                text = read_workflow(name)
                self.assertIn("\n  pull_request:\n", text)
                self.assertIn("if: github.event_name == 'pull_request'", text)
                self.assertIn("git diff --exit-code", text)
                self.assertIn("if: github.event_name == 'workflow_dispatch'", text)

    def test_schedules_are_unchanged(self):
        for name, cron in (("update-rules", "17 16 * * *"), ("update-modules", "29 16 * * *"), ("audit-rules", "35 16 * * *")):
            with self.subTest(workflow=name):
                self.assertIn(f'cron: "{cron}"', read_workflow(name))


if __name__ == "__main__":
    unittest.main()
