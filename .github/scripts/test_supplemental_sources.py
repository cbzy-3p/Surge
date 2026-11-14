import unittest

from check_supplemental_sources import compare, parse_domain_set, parse_related_rules
from audit_source_inventory import configured_sources, source_kind


class SupplementalSourceTests(unittest.TestCase):
    def test_exact_domain_does_not_cover_suffix(self):
        result = compare({"DOMAIN-SUFFIX,example.com"}, {"DOMAIN,example.com"})
        self.assertEqual(result["only_current"], ["DOMAIN-SUFFIX,example.com"])
        self.assertEqual(result["only_comparison"], [])

    def test_domain_set_parser_preserves_scope(self):
        self.assertEqual(parse_domain_set(".example.com\napi.test.com\n"),
                         {"DOMAIN-SUFFIX,example.com", "DOMAIN,api.test.com"})
        with self.assertRaises(ValueError):
            parse_domain_set("<html>error</html>")

    def test_comparison_preserves_underscore_dns_labels(self):
        self.assertEqual(parse_domain_set(".piano_log.kingsoft.jp"),
                         {"DOMAIN-SUFFIX,piano_log.kingsoft.jp"})
        with self.assertRaises(ValueError):
            parse_domain_set(".bad_/label.example.com")

    def test_related_rules_allow_redundant_upstream_entries(self):
        self.assertEqual(parse_related_rules("DOMAIN,a.example.com\nDOMAIN-SUFFIX,example.com\n"),
                         {"DOMAIN,a.example.com", "DOMAIN-SUFFIX,example.com"})

    def test_every_output_has_a_known_maintenance_mode(self):
        catalog = configured_sources()
        self.assertEqual(catalog["One"]["mode"], "manual_or_device_evidence")
        self.assertEqual(catalog["CN-Additional"]["mode"], "single_source")
        self.assertEqual(catalog["N26"]["mode"], "primary_with_related_fallback")
        self.assertEqual(len(catalog["AppleIntelligence"]["urls"]), 4)
        self.assertEqual(len(catalog["Telegram/Telegram_All"]["urls"]), 7)
        self.assertTrue(any(source_kind(url) == "pinned_revision" for url in catalog["Proxy"]["urls"]))


if __name__ == "__main__":
    unittest.main()
