#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
import ast
from urllib.parse import urlparse
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
FIXED_HOST_MARKERS = (
    "ruleset.skk.moe/",
    "blackmatrix7/",
    "Rabbit-Spec/",
    "ConnersHua/",
    "Loyalsoldier/",
    "Yuu518/",
)


def load(name: str):
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SourcePolicyTest(unittest.TestCase):
    def test_all_rule_updaters_have_no_unrecorded_external_sources(self):
        # Existing supplements remain until their unique coverage is compared.
        # This records exceptions, not a claim that all six preferred sources lack them.
        exceptions = {
            "update_cn_additional.py": {"static-file-global.353355.xyz"},
            "update_douyin.py": {"v2fly/domain-list-community"},
            "update_xiaohongshu.py": {"v2fly/domain-list-community", "wresource/hxmy-proxy", "bgpeer/rules", "dl123100/clash-geosite"},
            "update_v2fly_rules.py": {"v2fly/domain-list-community"},
        }
        preferred = {"blackmatrix7", "Rabbit-Spec", "ConnersHua", "Loyalsoldier", "Yuu518"}
        for path in SCRIPT_DIR.glob("update_*.py"):
            if path.name == "update_modules.py":
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value.startswith("https://"):
                    continue
                url = urlparse(node.value)
                parts = url.path.strip("/").split("/")
                if url.hostname == "ruleset.skk.moe":
                    continue
                if url.hostname in {"github.com", "raw.githubusercontent.com"}:
                    if parts[0] in preferred or parts[0] == "cbzy-3p":
                        continue
                    key = "/".join(parts[:2])
                else:
                    key = url.hostname
                self.assertIn(key, exceptions.get(path.name, set()), (path.name, node.value))

    def test_core_source_maps_use_only_fixed_sources(self):
        apple = load("update_apple")
        proxy = load("update_proxy")
        media = load("update_media_rules")
        urls = list(apple.SOURCES.values()) + list(proxy.SOURCES.values())
        urls += [item[1] for config in media.CONFIGS.values() for item in config]
        invalid = [url for url in urls if not any(marker in url for marker in FIXED_HOST_MARKERS)]
        self.assertEqual(invalid, [])

    def test_category_updater_has_only_fixed_active_mappings(self):
        rules = load("update_rules")
        self.assertTrue(all(set(mapping) == {"rabbit", "conners", "loyal", "yuu"} for mapping in rules.TARGETS.values()))

    def test_legacy_general_sources_are_not_active(self):
        active_files = (
            "update_apple.py",
            "update_apple_intelligence.py",
            "update_media_rules.py",
            "update_proxy.py",
            "update_twitter.py",
            "update_wechat.py",
        )
        active_text = "\n".join((SCRIPT_DIR / name).read_text(encoding="utf-8") for name in active_files)
        self.assertNotIn("ACL4SSR/", active_text)
        self.assertNotIn("MetaCubeX/", active_text)


if __name__ == "__main__":
    unittest.main()
