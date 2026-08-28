#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "Twitter.list"

SURGE_SOURCES = [
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Twitter/Twitter.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/Twitter.list",
    "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/twitter.list",
]
V2FLY_SOURCE = (
    "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/twitter"
)

TYPE_ORDER = {
    "DOMAIN": 0,
    "DOMAIN-SUFFIX": 1,
    "DOMAIN-KEYWORD": 2,
    "IP-CIDR": 3,
    "IP-CIDR6": 4,
    "IP-ASN": 5,
}


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "cbzy-3p-Surge-Updater"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_comment(line: str) -> str:
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "//", ";")):
        return ""
    for mark in (" //", " #"):
        if mark in line:
            line = line.split(mark, 1)[0].strip()
    return line


def normalize_rule(line: str) -> str | None:
    line = strip_comment(line)
    if not line:
        return None

    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        return None

    rule_type = parts[0].upper()
    value = parts[1].lower().rstrip(".")
    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
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
        return f"IP-ASN,{value},no-resolve"
    return None


def collect_surge_rules(text: str) -> set[str]:
    return {
        rule
        for line in text.splitlines()
        if (rule := normalize_rule(line)) is not None
    }


def collect_v2fly_rules(text: str) -> set[str]:
    rules: set[str] = set()
    for raw_line in text.splitlines():
        line = strip_comment(raw_line)
        if not line:
            continue
        value = line.split()[0].lower().rstrip(".")
        if value.startswith(("include:", "regexp:")):
            continue
        if value.startswith("full:"):
            value = value.removeprefix("full:")
            rule_type = "DOMAIN"
        elif value.startswith("domain:"):
            value = value.removeprefix("domain:")
            rule_type = "DOMAIN-SUFFIX"
        else:
            rule_type = "DOMAIN-SUFFIX"
        if value:
            rules.add(f"{rule_type},{value}")
    return rules


def sort_key(rule: str):
    parts = rule.split(",")
    rule_type = parts[0]
    value = parts[1]
    order = TYPE_ORDER.get(rule_type, 99)
    if rule_type in {"IP-CIDR", "IP-CIDR6"}:
        network = ipaddress.ip_network(value, strict=False)
        return (order, network.version, int(network.network_address), network.prefixlen)
    if rule_type == "IP-ASN":
        return (order, int(value))
    return (order, value)


def current_rules() -> list[str]:
    if not TARGET.exists():
        return []
    return sorted(collect_surge_rules(TARGET.read_text(encoding="utf-8")), key=sort_key)


def validate(rules: set[str]) -> None:
    required = {
        "DOMAIN-SUFFIX,twitter.com",
        "DOMAIN-SUFFIX,x.com",
        "DOMAIN-SUFFIX,twimg.com",
    }
    missing = required - rules
    if missing:
        raise SystemExit(f"required Twitter/X rules missing: {sorted(missing)}")
    if len(rules) < 20:
        raise SystemExit(f"unexpectedly small rule set: {len(rules)}")


def render(rules: set[str]) -> str:
    china_tz = timezone(timedelta(hours=8))
    now = datetime.now(china_tz).strftime("%Y-%m-%d %H:%M:%S")
    body = "\n".join(sorted(rules, key=sort_key))
    return (
        "# > Twitter / X\n"
        f"# UpdateTime: {now}\n"
        f"# RuleCount: {len(rules)}\n"
        "# Sources:\n"
        "# - blackmatrix7/ios_rule_script rule/Surge/Twitter/Twitter.list\n"
        "# - ACL4SSR/ACL4SSR Clash/Ruleset/Twitter.list\n"
        "# - v2fly/domain-list-community data/twitter\n"
        "# - Yuu518/Yuu-rules surge/geosite/twitter.list\n"
        "# AutoUpdate: daily at 00:17 Beijing time; rebuilt, normalized and deduplicated\n"
        "\n"
        f"{body}\n"
    )


def main() -> int:
    rules: set[str] = set()
    for url in SURGE_SOURCES:
        rules |= collect_surge_rules(fetch_text(url))
    rules |= collect_v2fly_rules(fetch_text(V2FLY_SOURCE))
    validate(rules)

    if sorted(rules, key=sort_key) == current_rules():
        print(f"No rule changes. Checked {len(rules)} rules from 4 sources.")
        return 0

    TARGET.write_text(render(rules), encoding="utf-8", newline="\n")
    print(f"Updated Twitter.list with {len(rules)} rules from 4 sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
