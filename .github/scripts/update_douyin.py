#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "douyin.txt"
SNAPSHOT = ROOT / ".github" / "douyin-source-snapshot.json"
BM7_URL = (
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/"
    "rule/Surge/DouYin/DouYin.list"
)
V2FLY_URL = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/douyin"
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_TYPES = DOMAIN_TYPES | {"DOMAIN-KEYWORD"}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
MIN_SOURCE_RULES = {"bm7": 10, "v2fly": 50}


def fetch_text(url: str, attempts: int = 3) -> str:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "cbzy-3p-Surge-Douyin-Updater/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                content = response.read().decode("utf-8")
            if not content.strip():
                raise RuntimeError(f"empty response: {url}")
            return content
        except Exception as exc:
            error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"failed to fetch {url}: {error}")


def normalize_domain(value: str) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    return domain if DOMAIN_RE.fullmatch(domain) else None


def merge_rule(rules: set[tuple[str, str]], rule: tuple[str, str]) -> None:
    rule_type, value = rule
    if rule_type == "DOMAIN-SUFFIX":
        rules.discard(("DOMAIN", value))
        rules.add(rule)
    elif rule_type != "DOMAIN" or ("DOMAIN-SUFFIX", value) not in rules:
        rules.add(rule)


def parse_surge_rules(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw_line in content.replace("\r", "").splitlines():
        line = raw_line.split("#", 1)[0].split("//", 1)[0].strip()
        if not line or line.startswith(";"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or parts[0] not in RULE_TYPES:
            continue
        if parts[0] == "DOMAIN-KEYWORD":
            value = parts[1].strip().lower()
            if not value or any(char.isspace() for char in value):
                value = None
        else:
            value = normalize_domain(parts[1])
        if value:
            merge_rule(rules, (parts[0], value))
    return rules


def parse_v2fly(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw_line in content.replace("\r", "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        token = line.split()[0]
        if token.startswith(("keyword:", "regexp:", "include:")):
            continue
        if token.startswith("full:"):
            token = token.split(":", 1)[1]
            rule_type = "DOMAIN"
        elif token.startswith("domain:"):
            token = token.split(":", 1)[1]
            rule_type = "DOMAIN-SUFFIX"
        else:
            rule_type = "DOMAIN-SUFFIX"
        value = normalize_domain(token)
        if value:
            merge_rule(rules, (rule_type, value))
    return rules


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return {key: int(value) for key, value in data.get("counts", {}).items()}


def validate_snapshot_change(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old_count in previous.items():
        if name not in current or old_count < 20:
            continue
        new_count = current[name]
        if new_count * 100 < old_count * 65:
            raise RuntimeError(f"source count dropped too much for {name}: {old_count} -> {new_count}")
        if new_count > old_count * 5 // 2:
            raise RuntimeError(f"source count grew too much for {name}: {old_count} -> {new_count}")


def render(rules: set[tuple[str, str]]) -> str:
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ordered = [f"{rule_type},{value}" for rule_type, value in sorted(rules)]
    header = [
        "# NAME: Multi-source-DouYin",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        f"# RULE COUNT: {len(rules)}",
        f"# SOURCE: {BM7_URL}",
        f"# SOURCE: {V2FLY_URL}",
        "# NOTE: Existing rules are preserved; upstream DOMAIN and DOMAIN-SUFFIX rules are merged and deduplicated.",
        "",
    ]
    return "\n".join(header + ordered) + "\n"


def main() -> None:
    current = parse_surge_rules(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else set()
    bm7 = parse_surge_rules(fetch_text(BM7_URL))
    v2fly = parse_v2fly(fetch_text(V2FLY_URL))
    if len(bm7) < MIN_SOURCE_RULES["bm7"]:
        raise RuntimeError(f"BM7 source count unexpectedly low: {len(bm7)}")
    if len(v2fly) < MIN_SOURCE_RULES["v2fly"]:
        raise RuntimeError(f"v2fly source count unexpectedly low: {len(v2fly)}")

    rules = set(current)
    for source in (bm7, v2fly):
        for rule in source:
            merge_rule(rules, rule)
    if len(rules) < 80 or len(rules) > 300:
        raise RuntimeError(f"unexpected output count: {len(rules)}")

    previous = current
    if len(previous) >= 20:
        if len(rules) * 100 < len(previous) * 65:
            raise RuntimeError(f"output count dropped too much: {len(previous)} -> {len(rules)}")
        if len(rules) > len(previous) * 5 // 2:
            raise RuntimeError(f"output count grew too much: {len(previous)} -> {len(rules)}")

    counts = {"bm7": len(bm7), "v2fly": len(v2fly), "output": len(rules)}
    validate_snapshot_change(load_snapshot(), counts)
    output = render(rules)
    if not TARGET.exists() or TARGET.read_text(encoding="utf-8").splitlines()[4:] != output.splitlines()[4:]:
        TARGET.write_text(output, encoding="utf-8")
        print(f"updated {TARGET} with {len(rules)} rules")
    else:
        print(f"unchanged {TARGET} with {len(rules)} rules")
    SNAPSHOT.write_text(json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
