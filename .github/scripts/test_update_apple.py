import importlib.util
import unittest
import tempfile
import json
from unittest.mock import patch
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("apple", Path(__file__).with_name("update_apple.py"))
assert SPEC and SPEC.loader
APPLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLE)


class AppleRuleTests(unittest.TestCase):
    def test_specialist_icloud_source_preserves_missing_general_domain(self):
        def fetch(url):
            return ("DOMAIN-SUFFIX,icloud.cn\n" if url == APPLE.SOURCES["bm7_icloud"]
                    else "DOMAIN-SUFFIX,apple.com\n")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Apple.list"
            snapshot = Path(directory) / "snapshot.json"
            with patch.object(APPLE, "TARGET", target), \
                 patch.object(APPLE, "SNAPSHOT", snapshot), \
                 patch.object(APPLE, "MINIMUMS", {name: 1 for name in APPLE.SOURCES}), \
                 patch.object(APPLE, "fetch", side_effect=fetch), patch("builtins.print"):
                APPLE.main()
            self.assertIn("DOMAIN-SUFFIX,icloud.cn\n", target.read_text())
            self.assertEqual(json.loads(snapshot.read_text())["counts"]["bm7_icloud"], 1)

    def test_icloud_source_failure_leaves_previous_files_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Apple.list"
            snapshot = Path(directory) / "snapshot.json"
            target.write_text("old rules")
            snapshot.write_text("old snapshot")
            def fetch(url):
                if url == APPLE.SOURCES["bm7_icloud"]:
                    raise RuntimeError("source unavailable")
                return "DOMAIN-SUFFIX,apple.com\n"
            with patch.object(APPLE, "TARGET", target), \
                 patch.object(APPLE, "SNAPSHOT", snapshot), \
                 patch.object(APPLE, "fetch", side_effect=fetch):
                with self.assertRaises(RuntimeError):
                    APPLE.main()
            self.assertEqual(target.read_text(), "old rules")
            self.assertEqual(snapshot.read_text(), "old snapshot")

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
