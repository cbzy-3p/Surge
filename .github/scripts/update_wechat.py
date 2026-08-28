#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "WeChat.list"
SOURCE_URLS = [
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/WeChat/WeChat.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/Wechat.list",
    "https://raw.githubusercontent.com/ConnersHua/RuleGo/master/Surge/Ruleset/Extra/WeChat.list",
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


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cbzy-3p-Surge-Updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


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
    value = parts[1].strip()
    if not rule_type or not value:
        return None
    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
        return f"{rule_type},{value.lower().rstrip('.')}"
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
    return ",".join([rule_type, value] + [part for part in parts[2:] if part])


def collect_rule_lines(text: str) -> list[str]:
    return [rule for raw_line in text.splitlines() if (rule := normalize_rule(raw_line))]


def dedupe_rules(rules: set[str]) -> set[str]:
    suffixes = {
        rule.split(",", 1)[1]
        for rule in rules
        if rule.startswith("DOMAIN-SUFFIX,")
    }
    return {
        rule
        for rule in rules
        if not (
            rule.startswith("DOMAIN,")
            and rule.split(",", 1)[1] in suffixes
        )
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
        "# > WeChat\n"
        f"# UpdateTime: {now}\n"
        f"# RuleCount: {len(rules)}\n"
        "# AutoUpdate: daily at 00:17 Beijing time; current rules preserved; upstream rules merged and semantically deduplicated\n"
        "# Sources: blackmatrix7 WeChat, ACL4SSR Wechat, ConnersHua RuleGo WeChat\n"
        "\n"
        f"{body}\n"
    )


def main() -> int:
    if not TARGET.exists():
        raise SystemExit("WeChat.list not found")

    current_text = TARGET.read_text(encoding="utf-8")
    current_lines = collect_rule_lines(current_text)
    rules = dedupe_rules(set(current_lines))

    fetched_count = 0
    for url in SOURCE_URLS:
        try:
            text = fetch_text(url)
        except Exception as exc:
            print(f"skip source: {url} ({exc})", file=sys.stderr)
            continue
        fetched_count += 1
        rules |= set(collect_rule_lines(text))
        rules = dedupe_rules(rules)

    if fetched_count == 0:
        raise SystemExit("all upstream WeChat sources failed")
    if len(rules) < 500:
        raise SystemExit(f"unexpectedly small WeChat rule set: {len(rules)}")

    if sorted(rules, key=sort_key) == sorted(current_lines, key=sort_key):
        print(f"No rule changes. Checked {len(rules)} rules from {fetched_count} sources.")
        return 0

    TARGET.write_text(render(rules), encoding="utf-8", newline="\n")
    print(f"Updated WeChat.list with {len(rules)} rules from {fetched_count} upstream sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
