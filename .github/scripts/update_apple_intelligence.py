#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "AppleIntelligence.list"

SOURCE_URLS = [
    "https://raw.githubusercontent.com/xpdigital/Apple-Rule/refs/heads/main/Apple-AI.list",
    "https://ruleset.skk.moe/List/non_ip/apple_intelligence.conf",
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Siri/Siri.list",
]

TYPE_ORDER = {
    "DOMAIN": 0,
    "DOMAIN-SUFFIX": 1,
    "DOMAIN-KEYWORD": 2,
    "DOMAIN-SET": 3,
    "IP-CIDR": 4,
    "IP-CIDR6": 5,
    "IP-ASN": 6,
    "GEOIP": 7,
    "USER-AGENT": 8,
    "URL-REGEX": 9,
    "PROCESS-NAME": 10,
}

RULE_PATTERN = re.compile(
    r"\b(DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN-SET|DOMAIN|IP-CIDR6|IP-CIDR|IP-ASN|GEOIP|USER-AGENT|URL-REGEX|PROCESS-NAME),([^#;\s]+)",
    re.IGNORECASE,
)
DOMAIN_VALUE_PATTERN = re.compile(r"^(?:\*\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*$")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Rongwuyou-Surge-Updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_rule(line: str) -> str | None:
    line = line.strip().lstrip("\ufeff")
    if not line:
        return None

    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        return None

    rule_type = parts[0].upper()
    value = parts[1].strip()
    if not rule_type or not value:
        return None

    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
        value = value.lower().rstrip(".")
        if not DOMAIN_VALUE_PATTERN.match(value):
            return None
        return f"{rule_type},{value}"

    if rule_type == "DOMAIN-KEYWORD":
        value = value.lower().rstrip(".")
        if not value or any(ch.isspace() for ch in value):
            return None
        return f"{rule_type},{value}"

    if rule_type in {"IP-CIDR", "IP-CIDR6"}:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            return None
        if rule_type == "IP-CIDR" and network.version != 4:
            return None
        if rule_type == "IP-CIDR6" and network.version != 6:
            return None
        return f"{rule_type},{network},no-resolve"

    if rule_type == "IP-ASN":
        return f"{rule_type},{value},no-resolve"

    cleaned_parts = [rule_type, value] + [p for p in parts[2:] if p]
    return ",".join(cleaned_parts)


def collect_rules(text: str) -> set[str]:
    rules: set[str] = set()
    for match in RULE_PATTERN.finditer(text):
        rule = normalize_rule(f"{match.group(1)},{match.group(2)}")
        if rule:
            rules.add(rule)
    return dedupe_rules(rules)


def dedupe_rules(rules: set[str]) -> set[str]:
    suffix_values = {rule.split(",", 1)[1] for rule in rules if rule.startswith("DOMAIN-SUFFIX,")}
    return {
        rule
        for rule in rules
        if not (rule.startswith("DOMAIN,") and rule.split(",", 1)[1] in suffix_values)
    }


def sort_key(rule: str):
    parts = rule.split(",")
    rule_type = parts[0]
    value = parts[1] if len(parts) > 1 else ""
    order = TYPE_ORDER.get(rule_type, 99)
    if rule_type in {"IP-CIDR", "IP-CIDR6"}:
        try:
            net = ipaddress.ip_network(value, strict=False)
            return (order, net.version, int(net.network_address), net.prefixlen, rule)
        except ValueError:
            return (order, value.lower(), rule)
    if rule_type == "IP-ASN":
        try:
            return (order, int(value), rule)
        except ValueError:
            return (order, value.lower(), rule)
    return (order, value.lower(), rule)


def render(rules: set[str]) -> str:
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    body = "\n".join(sorted(rules, key=sort_key))
    return (
        "# > Apple Intelligence\n"
        f"# UpdateTime: {now}\n"
        f"# RuleCount: {len(rules)}\n"
        "# AutoUpdate: daily at 00:17 Beijing time; upstream rules merged and deduplicated\n"
        "# Sources: xpdigital Apple-AI, SukkaW apple_intelligence, blackmatrix7 Siri\n"
        "\n"
        f"{body}\n"
    )


def existing_rules(text: str) -> set[str]:
    return collect_rules(text)


def main() -> int:
    current_text = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    rules = existing_rules(current_text)

    fetched_count = 0
    for url in SOURCE_URLS:
        try:
            text = fetch_text(url)
        except Exception as exc:
            print(f"skip source: {url} ({exc})", file=sys.stderr)
            continue
        fetched_count += 1
        rules |= collect_rules(text)
        rules = dedupe_rules(rules)

    if fetched_count == 0:
        raise SystemExit("all upstream Apple Intelligence sources failed")
    if len(rules) < 8:
        raise SystemExit(f"unexpectedly small Apple Intelligence rule set: {len(rules)}")

    if sorted(rules, key=sort_key) == sorted(existing_rules(current_text), key=sort_key):
        print("No rule changes.")
        return 0

    TARGET.write_text(render(rules), encoding="utf-8", newline="\n")
    print(f"Updated AppleIntelligence.list with {len(rules)} rules from {fetched_count} upstream sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
