#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "Proxy.list"
SNAPSHOT = ROOT / ".github" / "proxy-source-snapshot.json"
SOURCES = {
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Proxy/Proxy.list",
    "rabbit": "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules/Proxy.list",
    "loyalsoldier": "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/proxy.txt",
    "yuu": "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/category-proxy-tunnels.list",
}
MINIMUMS = {"bm7": 100, "rabbit": 6_000, "loyalsoldier": 20_000, "yuu": 10}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_TYPES = DOMAIN_TYPES | {
    "DOMAIN-KEYWORD", "DOMAIN-WILDCARD", "IP-CIDR", "IP-CIDR6", "IP-ASN",
    "USER-AGENT", "PROCESS-NAME",
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
                url, headers={"User-Agent": "cbzy-3p-Surge-Proxy-Updater/1.0"}
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


def normalize_domain(value: str) -> str | None:
    value = value.strip().lower().rstrip(".")
    if value.startswith("*."):
        value = value[2:]
    return value if DOMAIN_RE.fullmatch(value) else None


def normalize_rule(rule_type: str, value: str) -> tuple[str, str] | None:
    rule_type = rule_type.upper()
    value = value.strip()
    if rule_type not in RULE_TYPES:
        return None
    if rule_type in DOMAIN_TYPES:
        normalized = normalize_domain(value)
        return (rule_type, normalized) if normalized else None
    if rule_type == "DOMAIN-WILDCARD":
        normalized = value.lower().rstrip(".")
        return (rule_type, normalized) if normalized.startswith("*.") and normalize_domain(normalized) else None
    if rule_type in {"DOMAIN-KEYWORD", "USER-AGENT", "PROCESS-NAME"}:
        normalized = value.lower()
        return (rule_type, normalized) if normalized and not any(char.isspace() for char in normalized) else None
    if rule_type == "IP-ASN":
        return (rule_type, str(int(value))) if value.isdecimal() and int(value) > 0 else None
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None
    if (rule_type == "IP-CIDR") != (network.version == 4):
        return None
    return (rule_type, str(network))


def parse_surge(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        line = raw.split(" #", 1)[0].split(" //", 1)[0].strip()
        if not line or line.startswith(("#", "//", ";")):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            rule = normalize_rule(parts[0], parts[1])
            if rule:
                rules.add(rule)
    return rules


def parse_plain(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        token = raw.split("#", 1)[0].strip().split(maxsplit=1)[0] if raw.strip() else ""
        if not token or token.startswith(("!", ";")):
            continue
        rule_type = "DOMAIN-SUFFIX"
        if token.startswith("full:"):
            token, rule_type = token[5:], "DOMAIN"
        elif token.startswith("domain:"):
            token = token[7:]
        elif token.startswith(("regexp:", "keyword:", "include:", "geosite:")):
            continue
        rule = normalize_rule(rule_type, token)
        if rule:
            rules.add(rule)
    return rules


def merge(rules: set[tuple[str, str]], additions: set[tuple[str, str]]) -> set[tuple[str, str]]:
    suffixes = {value for kind, value in rules | additions if kind == "DOMAIN-SUFFIX"}
    merged = rules | additions
    return {
        rule for rule in merged
        if rule[0] != "DOMAIN" or not any(rule[1] == suffix or rule[1].endswith(f".{suffix}") for suffix in suffixes)
    }


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    return {key: int(value) for key, value in json.loads(SNAPSHOT.read_text())["counts"].items()}


def validate_snapshot(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old in previous.items():
        if name not in current or old < 20:
            continue
        new = current[name]
        if new * 100 < old * 65 or new > old * 5 // 2:
            raise RuntimeError(f"unexpected source count change for {name}: {old} -> {new}")


def render(rules: set[tuple[str, str]]) -> str:
    order = {"DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2, "DOMAIN-WILDCARD": 3, "USER-AGENT": 4, "PROCESS-NAME": 5, "IP-CIDR": 6, "IP-CIDR6": 7, "IP-ASN": 8}
    def key(rule: tuple[str, str]) -> tuple[int, str]:
        return (order[rule[0]], rule[1])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        "# NAME: Multi-source-Proxy",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# RULE COUNT: {len(rules)}",
        *[f"# SOURCE: {url}" for url in SOURCES.values()],
        "# NOTE: Sources are normalized, merged and deduplicated; DOMAIN-SUFFIX overrides covered DOMAIN entries.",
        "",
    ]
    body = []
    for rule_type, value in sorted(rules, key=key):
        suffix = ",no-resolve" if rule_type in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} else ""
        body.append(f"{rule_type},{value}{suffix}")
    return "\n".join(header + body) + "\n"


def main() -> None:
    fetched = {
        "bm7": parse_surge(fetch(SOURCES["bm7"])),
        "rabbit": parse_surge(fetch(SOURCES["rabbit"])),
        "loyalsoldier": parse_surge(fetch(SOURCES["loyalsoldier"])),
        "yuu": parse_surge(fetch(SOURCES["yuu"])),
    }
    counts = {name: len(rules) for name, rules in fetched.items()}
    for name, minimum in MINIMUMS.items():
        if counts[name] < minimum:
            raise RuntimeError(f"{name} source unexpectedly small: {counts[name]} < {minimum}")
    rules: set[tuple[str, str]] = set()
    for source in fetched.values():
        rules = merge(rules, source)
    counts["output"] = len(rules)
    validate_snapshot(load_snapshot(), counts)
    if TARGET.exists() and len(rules) * 100 < sum(1 for line in TARGET.read_text().splitlines() if line and not line.startswith("#")) * 65:
        raise RuntimeError("output rule count dropped too much")
    TARGET.write_text(render(rules), encoding="utf-8")
    SNAPSHOT.write_text(json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"updated {TARGET.name} with {len(rules)} rules")


if __name__ == "__main__":
    main()
