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

    def test_normalize_removes_loon_metadata_and_renames_duplicate_scripts(self):
        source = """#!name=测试
#!loon_version=3.2.4
[Script]
净化 = type=http-response, pattern=one, script-path=https://kelee.one/Resource/JavaScript/a.js
净化 = type=http-response, pattern=two, script-path=https://kelee.one/Resource/JavaScript/a.js
[MITM]
hostname = %APPEND% api*.example.com
"""
        normalized = updater.normalize_module(source)
        self.assertNotIn("#!loon_version", normalized)
        self.assertIn("净化（2） = type=http-response", normalized)
        updater.validate_source(normalized, "test.sgmodule")

    def test_goofish_conversion_preserves_all_qx_actions(self):
        source = r"""hostname = a.example.com
host-suffix,ads.example.com,reject
^https:\/\/a\.example\.com\/splash url reject-200
^https:\/\/a\.example\.com\/feed url jsonjq-response-body 'del(.ads)'
^http:\/\/a\.example\.com\/amdc url script-response-body https://raw.githubusercontent.com/ddgksf2013/Scripts/refs/heads/master/amdc.js
"""
        converted = updater.convert_goofish(source)
        self.assertIn("DOMAIN-SUFFIX,ads.example.com,REJECT", converted)
        self.assertIn(" - reject-200", converted)
        self.assertIn("http-response-jq", converted)
        self.assertIn("type=http-response", converted)
        updater.validate_source(converted, "goofish.sgmodule")

    def test_external_script_allowlist_is_narrow(self):
        self.assertTrue(updater.external_script_allowed("https://kelee.one/Resource/JavaScript/App/a.js"))
        for url in ("http://kelee.one/Resource/JavaScript/a.js",
                    "https://evil.example/a.js",
                    "https://kelee.one/Resource/JavaScript/a.txt"):
            self.assertFalse(updater.external_script_allowed(url))


if __name__ == "__main__":
    unittest.main()
