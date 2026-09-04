import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "audit_cross_file_rules", Path(__file__).with_name("audit_cross_file_rules.py")
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class CrossFileAuditTests(unittest.TestCase):
    def test_exact_and_semantic_overlap_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "First.list"
            second = root / "Second.list"
            third = root / "Third.list"
            first.write_text(
                "DOMAIN-SUFFIX,example.com\nDOMAIN,foo.test\n",
                encoding="utf-8",
            )
            second.write_text(
                "DOMAIN-SUFFIX,example.com\nDOMAIN,api.example.com\n",
                encoding="utf-8",
            )
            third.write_text(
                "DOMAIN-SUFFIX,sub.example.com\n",
                encoding="utf-8",
            )

            result = AUDIT.audit([first, second, third])

            self.assertEqual(result["exact_shared_rules"], 1)
            self.assertGreaterEqual(result["covered_relations"], 2)
            self.assertEqual(
                result["exact_pair_counts"][("First.list", "Second.list")],
                1,
            )

    def test_cn_additional_domain_set_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cn = root / "CN-Additional.list"
            other = root / "Other.list"
            cn.write_text(".example.com\n", encoding="utf-8")
            other.write_text("DOMAIN-SUFFIX,example.com\n", encoding="utf-8")

            result = AUDIT.audit([cn, other])

            self.assertEqual(result["exact_shared_rules"], 1)


if __name__ == "__main__":
    unittest.main()
