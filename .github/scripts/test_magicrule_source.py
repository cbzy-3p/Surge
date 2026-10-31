import hashlib
import json
import unittest
from magicrule_source import fetch_category, checked_url, INDEX_URL


class MagicRuleTests(unittest.TestCase):
    def fixture(self):
        body = 'DOMAIN-SUFFIX,example.com\n'
        manifest_url = 'https://magicrule.pages.dev/data/rules/Surge/example/manifest.json'
        artifact_url = 'https://magicrule.pages.dev/data/_shared/artifacts/example.list'
        index = {'client': 'Surge', 'rules': [{'name': 'Example', 'manifest': manifest_url}]}
        manifest = {'client': 'Surge', 'rule': 'Example', 'total_line_count': 1,
                    'artifacts': [{'role': 'full', 'url': artifact_url,
                                   'dedupe': {'bytes_sha256': hashlib.sha256(body.encode()).hexdigest()}}]}
        return index, manifest, body, manifest_url, artifact_url

    def run_fixture(self, mutation=lambda i, m: None, body_override=None):
        i, m, body, mu, au = self.fixture()
        mutation(i, m)
        data = {INDEX_URL: json.dumps(i), mu: json.dumps(m), au: body if body_override is None else body_override}
        return fetch_category('Example', data.__getitem__)

    def test_resolves_manifest_and_full_artifact(self):
        self.assertEqual(self.run_fixture()[0], 'DOMAIN-SUFFIX,example.com\n')

    def test_checksum_rejects_modified_body(self):
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            self.run_fixture(body_override='DOMAIN-SUFFIX,wrong.com\n')

    def test_wrong_category_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_fixture(lambda i, m: m.update(rule='Wrong'))

    def test_wrong_count_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'count'):
            self.run_fixture(lambda i, m: m.update(total_line_count=2))

    def test_missing_category_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_fixture(lambda i, m: i.update(rules=[]))

    def test_duplicate_artifacts_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_fixture(lambda i, m: m['artifacts'].append(m['artifacts'][0]))

    def test_unexpected_hosts_rejected(self):
        for url in ['http://magicrule.pages.dev/data/a', 'https://example.com/data/a', 'https://user@magicrule.pages.dev/data/a']:
            with self.assertRaises(RuntimeError):
                checked_url(url)


if __name__ == '__main__':
    unittest.main()
