import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_non_cn as m


class NonCNTests(unittest.TestCase):
    def test_suffix_compaction_preserves_exact_domain_semantics(self):
        with patch.object(m, 'MINIMUM', 1):
            output, counts = m.build('DOMAIN,api.example.com\nDOMAIN-SUFFIX,example.com\nDOMAIN,exact.other.com\n')
        self.assertNotIn('DOMAIN,api.example.com\n', output)
        self.assertIn('DOMAIN,exact.other.com\n', output)
        self.assertEqual(counts, {'source': 3, 'output': 2})

    def test_unexpected_type_options_and_malformed_line_fail(self):
        for source in ['IP-CIDR,1.1.1.0/24', 'DOMAIN,example.com,no-resolve', '<html>']:
            with self.subTest(source=source), patch.object(m, 'MINIMUM', 1):
                with self.assertRaises(RuntimeError):
                    m.build(source)

    def test_size_guard_preserves_existing_files_without_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'NonCN.list'
            snapshot = Path(directory) / 'snapshot.json'
            old = ''.join(f'DOMAIN,x{i}.example.com\n' for i in range(30))
            target.write_text(old)
            with patch.object(m, 'TARGET', target), patch.object(m, 'SNAPSHOT', snapshot), \
                 patch.object(m, 'MINIMUM', 1), patch.object(m, 'fetch', return_value='DOMAIN,only.example.com\n'):
                with self.assertRaises(RuntimeError):
                    m.main()
            self.assertEqual(target.read_text(), old)
            self.assertFalse(snapshot.exists())

    def test_missing_output_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'NonCN.list'
            snapshot = Path(directory) / 'snapshot.json'
            with patch.object(m, 'TARGET', target), patch.object(m, 'SNAPSHOT', snapshot), \
                 patch.object(m, 'MINIMUM', 1), patch.object(m, 'fetch', return_value='DOMAIN,example.com\n'):
                m.main()
            self.assertIn('DOMAIN,example.com', target.read_text())
            self.assertTrue(snapshot.exists())


if __name__ == '__main__':
    unittest.main()
