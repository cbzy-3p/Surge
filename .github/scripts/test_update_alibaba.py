"""Full-family coverage, safe selection and fail-before-write regressions."""
import tempfile
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import update_alibaba as updater


class AlibabaTests(unittest.TestCase):
    def sources(self):
        parents = {("DOMAIN-SUFFIX", host) for host in updater.xianyu.DEPENDENCY_HOSTS | {"goofish.com"}}
        baseline = {("DOMAIN-SUFFIX", "taobao.com"), ("DOMAIN-SUFFIX", "alicdn.com"),
                    ("DOMAIN-SUFFIX", "aliyuncs.com"), ("DOMAIN-SUFFIX", "mmstat.com"),
                    ("IP-CIDR", "192.0.2.0/25"), ("IP-CIDR", "192.0.2.128/25"),
                    ("IP-CIDR6", "2001:db8::/32"), ("PROCESS-NAME", "com.taobao.taobao")}
        return {
            "bm7": baseline,
            "bm7_extra": {("DOMAIN-SUFFIX", "taobao"), ("DOMAIN-SUFFIX", "tmall"), ("DOMAIN-SUFFIX", "alibaba")},
            "bm7_alipay": {("DOMAIN-SUFFIX", "alipay.com"), ("DOMAIN-SUFFIX", "alipay")},
            "bm7_xianyu": {("DOMAIN-SUFFIX", "xianyu.mobi")},
            "bm7_dingtalk": {("DOMAIN-SUFFIX", "dingtalk.com")},
            "yuu": parents | {("DOMAIN-SUFFIX", "new-family.example.com")},
            "yuu_cloud": {("DOMAIN-SUFFIX", "alibabacloud.com")},
            "sukka": {("DOMAIN-SUFFIX", "taobao.com"), ("DOMAIN-SUFFIX", "qq.com")},
            "sukka_selected": {("DOMAIN-SUFFIX", "taobao.com")},
            "sukka_ua": {("USER-AGENT", "%E6%89%8B%E6%9C%BA%E6%B7%98%E5%AE%9D*")},
            "conners": {("DOMAIN", "log.mmstat.com")},
            "rabbit": parents | {("DOMAIN-SUFFIX", "qq.com")},
            "loyal": parents | {("DOMAIN-SUFFIX", "cn")},
        }

    def limits(self):
        stack = ExitStack()
        stack.enter_context(patch.object(updater, "MINIMUMS", {name: 1 for name in updater.MINIMUMS}))
        stack.enter_context(patch.object(updater, "OUTPUT_LIMITS", (1, 4000)))
        stack.enter_context(patch.object(updater.xianyu, "MIN_SOURCE_RULES", {name: 1 for name in updater.xianyu.MIN_SOURCE_RULES}))
        return stack

    def build(self, sources=None, previous=None, standalone=None):
        with self.limits():
            return updater.build(sources or self.sources(), previous or set(), standalone or set())[0]

    def test_full_family_and_original_rule_types_survive_compaction(self):
        sources = self.sources()
        rules = self.build(sources)
        for name in updater.DEDICATED:
            for rule in sources[name]:
                self.assertTrue(updater.covers_rule(rule, rules), (name, rule))
        for host in ("login.taobao.com", "mobilegw.alipay.com", "video.goofish.com",
                     "unlisted.aliyuncs.com", "imgextra.alicdn.com", "chat.dingtalk.com"):
            self.assertTrue(updater.xianyu.covered(host, rules), host)
        self.assertIn(("IP-CIDR", "192.0.2.0/24"), rules)
        self.assertIn(("IP-CIDR6", "2001:db8::/32"), rules)
        self.assertIn(("PROCESS-NAME", "com.taobao.taobao"), rules)
        text = updater.render(rules)
        self.assertIn("IP-CIDR,192.0.2.0/24,no-resolve", text)
        updater.validate_text(Path("Alibaba.list"), text)

    def test_observed_hosts_and_previous_coverage_are_preserved(self):
        previous = {("DOMAIN", "retained.example.org")}
        standalone = {("DOMAIN", "new-device.example.net")}
        rules = self.build(previous=previous, standalone=standalone)
        for host in updater.xianyu.OBSERVED_HOSTS | {"retained.example.org", "new-device.example.net"}:
            self.assertTrue(updater.xianyu.covered(host, rules), host)

    def test_generic_parent_lists_do_not_import_unrelated_domains_or_tlds(self):
        rules = self.build()
        for host in ("qq.com", "unrelated.cn", "eviltaobao.com"):
            self.assertFalse(updater.xianyu.covered(host, rules), host)

    def test_brand_tlds_and_no_resolve_parse_without_loss(self):
        self.assertEqual(updater.parse_surge("test", "DOMAIN-SUFFIX,alipay\nIP-CIDR,192.0.2.1/24,no-resolve\n"),
                         {("DOMAIN-SUFFIX", "alipay"), ("IP-CIDR", "192.0.2.0/24")})
        self.assertEqual(updater.parse_loyal(".alibaba\n.exact.example.com\nlogin.example.com\n"),
                         {("DOMAIN-SUFFIX", "alibaba"), ("DOMAIN-SUFFIX", "exact.example.com"), ("DOMAIN", "login.example.com")})

    def test_unknown_rules_options_tlds_and_invalid_ips_fail(self):
        for line in ("FINAL,DIRECT", "DOMAIN-SUFFIX,cn", "IP-CIDR,bad", "DOMAIN,taobao.com,DIRECT",
                     "DOMAIN,taobao.com,pre-matching", "IP-CIDR6,192.0.2.0/24"):
            with self.subTest(line=line), self.assertRaises(RuntimeError):
                updater.parse_surge("dedicated", line)

    def test_sukka_customer_endpoint_does_not_import_customer_parent(self):
        hosts = [f"owned{i}.example.com" for i in range(60)]
        scope = "export const DOMESTICS = { ALIBABA: { domains: [\n" + "\n".join(f"'{h}'," for h in hosts) + "\n'$media.customer.example',\n] }, TENCENT: { domains: ['qq.com'] } };"
        native = {("DOMAIN-SUFFIX", h) for h in hosts} | {("DOMAIN-SUFFIX", "customer.example"), ("DOMAIN-SUFFIX", "qq.com")}
        selected = updater.select_sukka(scope, native)
        self.assertIn(("DOMAIN", "media.customer.example"), selected)
        self.assertNotIn(("DOMAIN-SUFFIX", "customer.example"), selected)
        self.assertNotIn(("DOMAIN-SUFFIX", "qq.com"), selected)
        with self.assertRaisesRegex(RuntimeError, "lost classified host"):
            updater.select_sukka(scope, native - {("DOMAIN-SUFFIX", hosts[0])})

    def test_sections_stop_at_next_service(self):
        text = "# > Alibaba\nDOMAIN,log.mmstat.com\n# > Tencent\nDOMAIN,qq.com\n# > Umeng\nDOMAIN,msg.umeng.com\n# ------\nDOMAIN,unrelated.com\n"
        selected = updater.parse_surge("conners", updater.sections(text, {"Alibaba", "Umeng"}))
        self.assertEqual(selected, {("DOMAIN", "log.mmstat.com"), ("DOMAIN", "msg.umeng.com")})

    def test_no_suffix_promotion_from_exact_classification(self):
        classified = {("DOMAIN", "api.shared.example")}
        candidates = {("DOMAIN-SUFFIX", "api.shared.example"), ("DOMAIN", "api.shared.example"),
                      ("DOMAIN-SUFFIX", "shared.example")}
        self.assertEqual(updater.select_domains(candidates, classified), classified)

    def test_truncation_and_missing_core_fail(self):
        sources = self.sources()
        sources["bm7"] = set()
        with self.assertRaisesRegex(RuntimeError, "unexpectedly small"):
            self.build(sources)
        sources = self.sources()
        sources["bm7_alipay"] = {("DOMAIN-SUFFIX", "other.example.com")}
        with self.assertRaisesRegex(RuntimeError, "missing dedicated core"):
            self.build(sources)

    def test_failed_fetch_leaves_previous_target_and_snapshot_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Alibaba.list"
            snapshot = Path(directory) / "snapshot.json"
            target.write_text("last valid rules\n")
            snapshot.write_text('{"version": 1}\n')
            with patch.object(updater, "TARGET", target), patch.object(updater, "SNAPSHOT", snapshot), \
                 patch.object(updater, "fetch_text", side_effect=RuntimeError("source unavailable")):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    updater.main()
            self.assertEqual(target.read_text(), "last valid rules\n")
            self.assertEqual(snapshot.read_text(), '{"version": 1}\n')

    def test_unchanged_output_retains_timestamp_and_snapshot_drift_fails_before_write(self):
        sources = self.sources()
        owned = {("DOMAIN-SUFFIX", f"owned{i}.example.com") for i in range(60)}
        sources["sukka"] |= owned
        texts = {updater.SOURCES[name]: "\n".join(f"{kind},{host}" for kind, host in rules)
                 for name, rules in sources.items() if name in updater.SOURCES}
        texts[updater.SOURCES["loyal"]] = "\n".join("." + host if kind == "DOMAIN-SUFFIX" else host
                                                   for kind, host in sources["loyal"])
        texts[updater.SOURCES["sukka_scope"]] = "export const DOMESTICS = { ALIBABA: { domains: [\n" + "\n".join(f"'{host}'," for _, host in owned) + "\n] } };"
        texts[updater.SOURCES["sukka_ua"]] = "# >> Alibaba\nUSER-AGENT,Taobao*\nUSER-AGENT,Youku*\n# >> Vivo\nDOMAIN-SUFFIX,vivo.com\n"
        texts[updater.SOURCES["conners"]] = "# > Alibaba\nDOMAIN,log.mmstat.com\nDOMAIN,sycm.mmstat.com\n# > Tencent\nDOMAIN,qq.com\n"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Alibaba.list"
            snapshot = Path(directory) / "snapshot.json"
            standalone = Path(directory) / "XianYu.list"
            standalone.write_text("DOMAIN-SUFFIX,xianyu.mobi\n")
            with self.limits(), patch.object(updater, "TARGET", target), patch.object(updater, "SNAPSHOT", snapshot), \
                 patch.object(updater, "XIAN_YU", standalone), patch.object(updater, "fetch_text", side_effect=texts.__getitem__):
                updater.main()
                lines = target.read_text().splitlines()
                lines[3] = "# UPDATED: 2000-01-01 00:00:00 UTC"
                target.write_text("\n".join(lines) + "\n")
                before = target.read_bytes(), snapshot.read_bytes()
                updater.main()
                self.assertEqual((target.read_bytes(), snapshot.read_bytes()), before)
                data = json.loads(snapshot.read_text())
                data["counts"]["bm7"] = 100
                snapshot.write_text(json.dumps(data))
                before = target.read_bytes(), snapshot.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "count changed too much"):
                    updater.main()
                self.assertEqual((target.read_bytes(), snapshot.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
