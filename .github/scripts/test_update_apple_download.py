import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_apple_download as updater
from validate_rule_files import validate_text


class AppleDownloadTests(unittest.TestCase):
    def test_downloads_and_control_plane_are_separated(self):
        for host in ("iosapps.itunes.apple.com", "osxapps.itunes.g.aaplimg.com",
                     "appldnld.apple.com", "updates.cdn-apple.com",
                     "apps.mzstatic.com", "swdownload.apple.com",
                     "appldnld-lb.apple.com.akadns.net", "oscdn.origin-apple.com.akadns.net"):
            self.assertTrue(updater.is_download(host), host)
        for host in ("apple.com", "cdn-apple.com", "itunes.apple.com", "apps.apple.com",
                     "buy.itunes.apple.com", "bag.itunes.apple.com", "idmsa.apple.com",
                     "gs.apple.com", "icloud.com", "ocsp.apple.com", "akadns.net",
                     "updates.cdn-apple.com.evil.org", "download.evil.com",
                     "mesu.apple.com", "gdmf.apple.com", "configuration.apple.com",
                     "swscan.apple.com", "swdist.apple.com", "swcatalog.apple.com",
                     "downloaddispatch.itunes.apple.com", "su.itunes.apple.com",
                     "adcdownload.apple.com", "download.developer.apple.com",
                     "devimages-cdn.apple.com", "mzstatic.com", "is1.mzstatic.com",
                     "sylvan.apple.com", "audiocontentdownload.apple.com",
                     "playground-cdn.apple.com", "ml.cdn-apple.com",
                     "publicassets.cdn-apple.com", "aod.itunes.apple.com",
                     "hls.itunes.apple.com", "mesu-cdn.apple.com.akadns.net",
                     "adcdownload.apple.com.akadns.net", "swscan-cdn.apple.com.akadns.net"):
            self.assertFalse(updater.is_download(host), host)

    def test_domainset_preserves_exact_and_suffix_semantics(self):
        text = "# comment\n.exact.example.com\nfull.example.com\n" + updater.apple.SKK_WATERMARK
        self.assertEqual(updater.parse_source("skk", text), {
            ("DOMAIN-SUFFIX", "exact.example.com"), ("DOMAIN", "full.example.com")})

    def test_malformed_or_empty_sources_fail(self):
        with self.assertRaises(RuntimeError):
            updater.parse_source("skk", "<html>error</html>")
        with self.assertRaises(RuntimeError):
            updater.parse_source("rabbit", "DOMAIN,bad domain")
        with self.assertRaises(RuntimeError):
            updater.build({name: "" for name in updater.SOURCES})

    def test_upstream_failure_leaves_both_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "AppleDownload.list"
            snapshot = Path(directory) / "snapshot.json"
            target.write_text(updater.render({("DOMAIN", "example.com")}, "test"))
            snapshot.write_text('{"counts": {}}')
            before = target.read_bytes(), snapshot.read_bytes()
            with patch.object(updater, "TARGET", target), patch.object(updater, "SNAPSHOT", snapshot):
                with patch.object(updater.apple, "fetch", side_effect=RuntimeError("offline")):
                    with self.assertRaises(RuntimeError):
                        updater.main()
            self.assertEqual(before, (target.read_bytes(), snapshot.read_bytes()))

    def test_build_does_not_import_broad_parent_or_account_hosts(self):
        text = "DOMAIN-SUFFIX,apple.com\nDOMAIN,buy.itunes.apple.com\nDOMAIN,iosapps.itunes.apple.com\n"
        with patch.object(updater, "SOURCES", {"rabbit": "fixture"}), patch.object(updater, "MINIMUMS", {"rabbit": 1}):
            rules, counts = updater.build({"rabbit": text})
        self.assertNotIn(("DOMAIN-SUFFIX", "apple.com"), rules)
        self.assertNotIn(("DOMAIN", "buy.itunes.apple.com"), rules)
        self.assertTrue(updater.apple.covered_by_suffix("iosapps.itunes.apple.com", {v for k, v in rules if k == "DOMAIN-SUFFIX"}))
        self.assertEqual(counts["rabbit/selected"], 1)
        self.assertEqual(validate_text(Path("AppleDownload.list"), updater.render(rules, "test"))["rules"], len(rules))


if __name__ == "__main__":
    unittest.main()
