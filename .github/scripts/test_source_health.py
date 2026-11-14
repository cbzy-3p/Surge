import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import source_health as health


class SourceHealthTests(unittest.TestCase):
    def events(self, root):
        return [json.loads(p.read_text()) for p in (root / "events").glob("*.json")]

    def test_disabled_recording_preserves_result_without_files(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as directory:
            @health.record_source
            def fetch(url):
                return "DOMAIN,example.com\n"
            self.assertEqual(fetch("https://example.com/rules"), "DOMAIN,example.com\n")
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(fetch.__name__, "fetch")

    def test_parallel_successes_and_failed_fallback_keep_all_events(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RULE_AUDIT_DIR": directory}):
            @health.record_source
            def fetch(url):
                if "failed" in url:
                    raise HTTPError(url, 503, "temporary error", {}, None)
                return "DOMAIN-SUFFIX,example.com\n"
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(fetch, ["https://example.com/rules"] * 20))
            with self.assertRaises(HTTPError):
                fetch("https://example.com/failed?token=private")
            events = self.events(Path(directory))
            self.assertEqual(len(events), 21)
            self.assertEqual(sum(e["status"] == "failed" for e in events), 1)
            self.assertNotIn("private", json.dumps(events))
            self.assertNotIn("token", json.dumps(events))
            for event in events:
                if event["status"] == "success":
                    self.assertEqual((Path(directory) / event["content_file"]).read_text(), "DOMAIN-SUFFIX,example.com\n")

    def test_invalid_responses_fail_and_json_metadata_passes(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RULE_AUDIT_DIR": directory}):
            @health.record_source(url="https://example.com/source")
            def fetch(text):
                return text
            for response in ("", "  \n", "<!doctype html><html>error</html>"):
                with self.assertRaises(ValueError):
                    fetch(response)
            self.assertEqual(fetch('{"rules": []}'), '{"rules": []}')
            self.assertEqual(fetch('{"description": "<html> is a string"}'),
                             '{"description": "<html> is a string"}')
            events = self.events(Path(directory))
            self.assertEqual(sum(e["status"] == "failed" for e in events), 3)

    def test_matching_bodies_ignore_order_and_comments(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RULE_AUDIT_DIR": directory, "GITHUB_STEP_SUMMARY": str(Path(directory) / "summary.md")}):
            health.write_event("https://example.com/a", "success", "# a\nDOMAIN,a.example\nDOMAIN,b.example\n")
            health.write_event("https://example.com/b", "success", "# b\nDOMAIN,b.example\nDOMAIN,a.example\n")
            health.record_validation_failure("https://example.com/c", "no usable rules")
            with contextlib.redirect_stdout(io.StringIO()):
                report = health.finalize(Path(directory))
            self.assertEqual(report["identical_body_url_groups"], [["https://example.com/a", "https://example.com/b"]])
            self.assertEqual(report["failed_or_invalid_calls"], 1)
            self.assertIn("do not establish independent maintenance", (Path(directory) / "summary.md").read_text())

    def test_empty_run_is_reported_as_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            report = health.finalize(Path(directory))
            self.assertEqual(report["fetch_calls"], 0)
            self.assertIn("No upstream calls", (Path(directory) / "source-health.md").read_text())


if __name__ == "__main__":
    unittest.main()
