"""Coverage, isolation, and preservation checks for the XianYu updater."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_xianyu as updater


class XianYuTests(unittest.TestCase):
    def sources(self):
        dedicated = {("DOMAIN-SUFFIX", "xianyu.mobi")}
        dedicated |= {("DOMAIN-SUFFIX", f"share{i}.example.com") for i in range(9)}
        parents = {("DOMAIN-SUFFIX", "goofish.com")}
        parents |= {("DOMAIN-SUFFIX", host) for host in updater.DEPENDENCY_HOSTS}
        parents |= {("DOMAIN-SUFFIX", "aliyuncs.com"), ("DOMAIN-SUFFIX", "qq.com")}
        return {"bm7": dedicated, "rabbit": set(parents), "loyal": set(parents), "yuu": set(parents)}

    def build(self, sources=None, previous=None):
        with patch.object(updater, "MIN_SOURCE_RULES", {name: 1 for name in updater.SOURCES}):
            return updater.build(sources or self.sources(), previous or set())

    def test_core_coverage_and_shared_endpoint_isolation(self):
        rules = self.build()
        for host in ("acs.m.goofish.com", "passport.goofish.com", "h5api.m.goofish.com",
                     "stream-upload.goofish.com", "wss-goofish.dingtalk.com",
                     "down.im.dingtalk.cn", "xianyu-video.alicdn.com", "amdc.m.taobao.com"):
            self.assertTrue(updater.covered(host, rules), host)
        for host in ("unrelated.aliyuncs.com", "qq.com", "unrelated.dingtalk.com",
                     "unrelated.alicdn.com", "unrelated.taobao.com", "evilgoofish.com"):
            self.assertFalse(updater.covered(host, rules), host)

    def test_device_evidence_survives_absence_from_broad_parent_sources(self):
        sources = self.sources()
        for name in ("rabbit", "loyal", "yuu"):
            self.assertFalse(updater.covered("ali.wosms.cn", sources[name]))
        rules = self.build(sources)
        for host in ("ali.wosms.cn", "tls-goofish.dingtalk.com", "vpp-license-proxy.aliyuncs.com",
                     "cloud-config-service.rtc.aliyuncs.com", "ntp.ynuf.aliapp.org",
                     "dinamicx.alibabausercontent.com", "gw.alipayobjects.com"):
            self.assertIn(("DOMAIN", host), rules)
        for host in ("other.wosms.cn", "other.alibabausercontent.com",
                     "other.alipayobjects.com", "other.rtc.aliyuncs.com",
                     "dynamicx.alibabausercontent.com", "dynamic.alibabausercontent.com"):
            self.assertFalse(updater.covered(host, rules), host)

    def test_domain_set_tlds_and_exact_hosts_keep_semantics(self):
        self.assertEqual(updater.parse_source("loyal", ".alibaba\n.goofish.com\nlogin.example.com\n"),
                         {("DOMAIN-SUFFIX", "alibaba"), ("DOMAIN-SUFFIX", "goofish.com"),
                          ("DOMAIN", "login.example.com")})

    def test_rabbit_domain_set_and_legacy_rules_keep_matching_semantics(self):
        text = "# Rabbit-Spec China\n.cn\n.goofish.com\nlogin.example.com\nDOMAIN,legacy.example.com\n"
        self.assertEqual(updater.parse_source("rabbit", text), {
            ("DOMAIN-SUFFIX", "cn"),
            ("DOMAIN-SUFFIX", "goofish.com"),
            ("DOMAIN", "login.example.com"),
            ("DOMAIN", "legacy.example.com"),
        })

    def test_undersized_source_retries_and_accepts_only_valid_content(self):
        url = updater.SOURCES["rabbit"]
        with patch.object(updater, "MIN_SOURCE_RULES", {"rabbit": 1}), \
             patch.object(updater, "fetch_text", side_effect=["# temporary empty response\n",
                                                                 "DOMAIN,goofish.com\n"]) as fetch, \
             patch.object(updater.time, "sleep") as sleep:
            name, text = updater.fetch_valid_source(("rabbit", url))
        self.assertEqual((name, text), ("rabbit", "DOMAIN,goofish.com\n"))
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_undersized_source_fails_after_retries_without_lowering_threshold(self):
        url = updater.SOURCES["rabbit"]
        with patch.object(updater, "MIN_SOURCE_RULES", {"rabbit": 2}), \
             patch.object(updater, "fetch_text", return_value="DOMAIN,one.example.com\n") as fetch, \
             patch.object(updater.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts: 1 < 2"):
                updater.fetch_valid_source(("rabbit", url))
        self.assertEqual(fetch.call_count, 3)

    def test_truncated_baseline_fails(self):
        sources = self.sources()
        sources["bm7"] = {("DOMAIN-SUFFIX", "unrelated.example.com")}
        with self.assertRaisesRegex(RuntimeError, "classification"):
            self.build(sources)

    def test_missing_corroboration_fails(self):
        sources = self.sources()
        for name in ("rabbit", "loyal"):
            sources[name].remove(("DOMAIN-SUFFIX", "wss-goofish.dingtalk.com"))
        with self.assertRaisesRegex(RuntimeError, "corroboration"):
            self.build(sources)

    def test_source_additions_and_existing_verified_rules_are_preserved(self):
        sources = self.sources()
        sources["bm7"].add(("DOMAIN-SUFFIX", "newshare.example.com"))
        previous = {("DOMAIN", "retained.goofish.com")}
        rules = self.build(sources, previous)
        self.assertTrue(updater.covered("newshare.example.com", rules))
        self.assertTrue(updater.covered("retained.goofish.com", rules))

    def test_shared_parent_injection_is_rejected(self):
        sources = self.sources()
        sources["bm7"].add(("DOMAIN-SUFFIX", "aliyuncs.com"))
        with self.assertRaisesRegex(RuntimeError, "broad"):
            self.build(sources)

    def test_failed_fetch_leaves_last_valid_files_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "XianYu.list"
            snapshot = Path(directory) / "snapshot.json"
            target.write_text("last valid rules\n")
            snapshot.write_text('{"version": 1}\n')
            with patch.object(updater, "TARGET", target), patch.object(updater, "SNAPSHOT", snapshot), \
                 patch.object(updater, "fetch_text", side_effect=RuntimeError("source unavailable")), \
                 patch.object(updater.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    updater.main()
            self.assertEqual(target.read_text(), "last valid rules\n")
            self.assertEqual(snapshot.read_text(), '{"version": 1}\n')

    def test_unchanged_rules_do_not_rewrite_timestamp(self):
        sources = self.sources()
        texts = {updater.SOURCES[name]: "\n".join(
            ("." + host if kind == "DOMAIN-SUFFIX" else host) if name == "loyal"
            else f"{kind},{host}" for kind, host in rules)
            for name, rules in sources.items()}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "XianYu.list"
            snapshot = Path(directory) / "snapshot.json"
            output = updater.render(self.build())
            lines = output.splitlines()
            lines[3] = "# UPDATED: 2000-01-01 00:00:00 UTC"
            original = "\n".join(lines) + "\n"
            target.write_text(original)
            with patch.object(updater, "TARGET", target), patch.object(updater, "SNAPSHOT", snapshot), \
                 patch.object(updater, "MIN_SOURCE_RULES", {name: 1 for name in updater.SOURCES}), \
                 patch.object(updater, "fetch_text", side_effect=texts.__getitem__):
                updater.main()
                snapshot_before = snapshot.read_bytes()
                updater.main()
                self.assertEqual(snapshot.read_bytes(), snapshot_before)
            self.assertEqual(target.read_text(), original)


if __name__ == "__main__":
    unittest.main()
