import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import update_modules as updater


class ModuleProtectionTests(unittest.TestCase):
    def test_release_redirect_with_proxy_host(self):
        import urllib.request
        request = urllib.request.Request("https://github.com/sub-store-org/Sub-Store/releases/download/v1/a.js")
        request.set_proxy("proxy.example:80", "http")
        redirected = updater.CheckedRedirect().redirect_request(request, None, 302, "Found", {}, "https://release-assets.githubusercontent.com/asset")
        self.assertIsNotNone(redirected)

    def test_repository_boundary(self):
        for url in ("https://raw.githubusercontent.com/other/Rewrite/main/a.js",
                    "http://raw.githubusercontent.com/Yu9191/Rewrite/main/a.js",
                    "https://raw.githubusercontent.com/Yu9191/Rewrite-evil/main/a.js"):
            with self.assertRaises(RuntimeError):
                updater.check_url(url)
        updater.check_url("https://raw.githubusercontent.com/Yu9191/Rewrite/main/a.js")

    def test_failed_update_preserves_live_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Module").mkdir()
            live = root / "Module/example.sgmodule"
            live.write_text("old version")
            def fail():
                (updater.ROOT / "Module/example.sgmodule").write_text("partial update")
                raise RuntimeError("upstream failed")
            with patch.object(updater, "ROOT", root), patch.object(updater.sys, "argv", ["updater"]), patch.object(updater, "update_staged", fail):
                with self.assertRaises(RuntimeError):
                    updater.main()
                self.assertEqual(updater.ROOT, root)
            self.assertEqual(live.read_text(), "old version")

    def test_abnormal_content(self):
        url = "https://raw.githubusercontent.com/Yu9191/Rewrite/main/a.js"
        for content in (b"<html>error page</html>", b"x" * 20):
            with self.assertRaises(RuntimeError):
                updater.validate_script(content, url, b"x" * 1000)


if __name__ == "__main__":
    unittest.main()
