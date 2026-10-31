#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "iCloud.list"
SNAPSHOT = ROOT / ".github" / "icloud-source-snapshot.json"
SOURCES = {
    "skk_apple": "https://raw.githubusercontent.com/SukkaW/Surge/master/Source/non_ip/apple_services.conf",
    "skk_private_relay": "https://raw.githubusercontent.com/SukkaW/Surge/master/Source/domainset/icloud_private_relay.conf",
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/iCloud/iCloud.list",
    "rabbit": "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules/Apple.list",
    "conners": "https://raw.githubusercontent.com/ConnersHua/RuleGo/master/Surge/Ruleset/Extra/Apple/Apple.list",
    "loyal": "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/apple.txt",
    "yuu": "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/apple.list",
}
MINIMUMS = {
    "skk_apple": 2, "skk_private_relay": 5, "bm7": 40,
    "rabbit": 1, "conners": 1, "loyal": 0, "yuu": 1,
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "cbzy-3p-Surge-iCloud-Updater/1.0"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8")
            if not content.strip():
                raise RuntimeError("empty response")
            return content
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def is_icloud_value(value: str) -> bool:
    value = value.lower()
    return "icloud" in value or "apple-cloudkit.com" in value or value == "me.com" or value.endswith(".me.com")


def parse_surge(content: str, dedicated: bool = False) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith(("#", "//", ";")):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        rule_type, value = parts[0].upper(), parts[1].lower().rstrip(".")
        if rule_type not in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
            continue
        if rule_type == "DOMAIN-KEYWORD":
            valid = bool(value) and not any(char.isspace() for char in value)
        else:
            valid = bool(DOMAIN_RE.fullmatch(value))
        if valid and (dedicated or is_icloud_value(value)):
            rules.add((rule_type, value))
    return rules


def parse_private_relay(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        value = raw.strip().lstrip("\ufeff").split(maxsplit=1)[0] if raw.strip() else ""
        value = value.rstrip(".").lower()
        if value and not value.startswith("#") and (
            is_icloud_value(value) or value in {"mask.apple-dns.net", "canary.mask.apple-dns.net"}
        ):
            if DOMAIN_RE.fullmatch(value):
                rules.add(("DOMAIN", value))
    return rules


def covered_by_suffix(domain: str, suffixes: set[str]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)


def compact(rules: set[tuple[str, str]]) -> set[tuple[str, str]]:
    suffixes: set[str] = set()
    for domain in sorted(
        (value for kind, value in rules if kind == "DOMAIN-SUFFIX"),
        key=lambda value: (value.count("."), value),
    ):
        if not covered_by_suffix(domain, suffixes):
            suffixes.add(domain)
    exact = {
        value for kind, value in rules
        if kind == "DOMAIN" and not covered_by_suffix(value, suffixes)
    }
    keywords = {rule for rule in rules if rule[0] == "DOMAIN-KEYWORD"}
    return keywords | {("DOMAIN-SUFFIX", value) for value in suffixes} | {("DOMAIN", value) for value in exact}


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return {key: int(value) for key, value in data.get("counts", {}).items()}


def validate_snapshot(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old in previous.items():
        if name not in current or old < 10:
            continue
        new = current[name]
        if new * 100 < old * 65 or new > old * 5 // 2:
            raise RuntimeError(f"unexpected source count change for {name}: {old} -> {new}")


def render(rules: set[tuple[str, str]], updated: str | None = None) -> str:
    order = {"DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2}
    body = [
        f"{rule_type},{value}"
        for rule_type, value in sorted(rules, key=lambda rule: (order[rule[0]], rule[1]))
    ]
    updated = updated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        "# NAME: Multi-source-iCloud",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        f"# RULE COUNT: {len(rules)}",
        *[f"# SOURCE: {url}" for url in SOURCES.values()],
        "# NOTE: iCloud-specific entries are selected from Apple-wide source lists; general Apple domains are excluded.",
        "# NOTE: SukkaW Private Relay endpoints are included; broader suffix matches are compacted.",
        "",
    ]
    return "\n".join(header + body) + "\n"


def main() -> None:
    fetched = {
        "skk_apple": parse_surge(fetch(SOURCES["skk_apple"])),
        "skk_private_relay": parse_private_relay(fetch(SOURCES["skk_private_relay"])),
        "bm7": parse_surge(fetch(SOURCES["bm7"]), dedicated=True),
        "rabbit": parse_surge(fetch(SOURCES["rabbit"])),
        "conners": parse_surge(fetch(SOURCES["conners"])),
        "loyal": parse_surge(fetch(SOURCES["loyal"])),
        "yuu": parse_surge(fetch(SOURCES["yuu"])),
    }
    counts = {name: len(rules) for name, rules in fetched.items()}
    for name, minimum in MINIMUMS.items():
        if counts[name] < minimum:
            raise RuntimeError(f"{name} source unexpectedly small: {counts[name]} < {minimum}")
    contributing = sum(count > 0 for count in counts.values())
    if contributing < 5:
        raise RuntimeError(f"too few iCloud sources contributed rules: {contributing}")
    rules = compact(set().union(*fetched.values()))
    if len(rules) < 20:
        raise RuntimeError(f"iCloud output unexpectedly small: {len(rules)}")
    counts["output"] = len(rules)
    validate_snapshot(load_snapshot(), counts)
    previous_text = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if previous_text:
        previous = sum(1 for line in previous_text.splitlines() if line and not line.startswith("#"))
        if previous >= 20 and (len(rules) * 100 < previous * 65 or len(rules) > previous * 5 // 2):
            raise RuntimeError(f"unexpected output count change: {previous} -> {len(rules)}")
    previous_updated = re.search(r"^# UPDATED: (.+)$", previous_text, re.MULTILINE)
    unchanged_text = render(rules, previous_updated.group(1)) if previous_updated else ""
    if not TARGET.exists() or unchanged_text != previous_text:
        TARGET.write_text(render(rules), encoding="utf-8")
    SNAPSHOT.write_text(
        json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"updated {TARGET.name} with {len(rules)} rules")


if __name__ == "__main__":
    main()
