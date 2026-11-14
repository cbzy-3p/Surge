import unittest
from audit_classification import overlap, review


class ClassificationTests(unittest.TestCase):
    def test_blocked_parent_matches_subdomain_but_not_lookalike(self):
        rules = {"DOMAIN,api.example.com", "DOMAIN,notexample.com", "DOMAIN,sub.exact.com"}
        self.assertEqual(overlap(rules, {"DOMAIN-SUFFIX,example.com", "DOMAIN,exact.com"}),
                         {"DOMAIN,api.example.com"})

    def test_one_new_shared_blocked_rule_stops_publication(self):
        baseline = {"A": {"DOMAIN,a.example"}, "B": {"DOMAIN,b.example"}}
        bad = {"DOMAIN,tracking.example"}
        current = {name: rules | bad for name, rules in baseline.items()}
        report, errors = review(current, baseline, bad, [("A", "B")])
        self.assertEqual(len(errors), 1)
        self.assertEqual(report["A"]["new_overlap_count"], 1)
        self.assertEqual(review(current, current, bad, [("A", "B")])[1], [])

    def test_overlap_in_one_category_is_reported_without_deleting_it(self):
        baseline = {"A": {"DOMAIN,a.example"}}
        current = {"A": baseline["A"] | {"DOMAIN,telemetry.example"}}
        saved = set(current["A"])
        report, errors = review(current, baseline, {"DOMAIN,telemetry.example"}, [])
        self.assertEqual(errors, [])
        self.assertEqual(current["A"], saved)
        self.assertEqual(report["A"]["new_overlap_count"], 1)
        _report, errors = review(current, baseline, {"DOMAIN,telemetry.example"}, [], ["A"])
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
