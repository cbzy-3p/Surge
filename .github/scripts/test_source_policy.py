#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
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
