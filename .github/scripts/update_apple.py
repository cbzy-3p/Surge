#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "Apple.list"
SNAPSHOT = ROOT / ".github" / "apple-source-snapshot.json"
SOURCES = {
    "skk": "https://ruleset.skk.moe/List/non_ip/apple_services.conf",
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Apple/Apple_All_No_Resolve.list",
    "yuu": "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/apple.list",
    "meta": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/apple.list",
}
MINIMUMS = {"skk": 20, "bm7": 1_500, "yuu": 1_500, "meta": 1_500}
RULE_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "USER-AGENT", "PROCESS-NAME",
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SKK_WATERMARK = "7h15.ru1353t.1s.m4d3.by.5ukk4w.skk.moe"


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "cbzy-3p-Surge-Apple-Updater/1.0"}
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


def normalize_domain(value: str, allow_tld: bool = False) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith(("+.", "*.")):
        domain = domain[2:]
    if DOMAIN_RE.fullmatch(domain):
        return domain
    return domain if allow_tld and DOMAIN_LABEL_RE.fullmatch(domain) else None


def strip_comment(raw: str) -> str:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "//", ";", "!")):
        return ""
    for marker in (" //", " #"):
        if marker in line:
            line = line.split(marker, 1)[0].strip()
    return line


def normalize_rule(rule_type: str, value: str) -> tuple[str, str] | None:
    rule_type = rule_type.upper()
    value = value.strip()
    if rule_type not in RULE_TYPES:
        return None
    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
        domain = normalize_domain(value, allow_tld=rule_type == "DOMAIN-SUFFIX")
        if not domain or domain == SKK_WATERMARK:
            return None
        return rule_type, domain
    if rule_type == "DOMAIN-WILDCARD":
        wildcard = value.lower().rstrip(".")
        return (rule_type, wildcard) if wildcard.startswith("*.") and normalize_domain(wildcard) else None
    if rule_type in {"DOMAIN-KEYWORD", "USER-AGENT", "PROCESS-NAME"}:
        return (rule_type, value) if value else None
    return rule_type, value.lower()


def parse_surge(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        line = strip_comment(raw)
        if not line:
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
        token = strip_comment(raw).split(maxsplit=1)[0] if strip_comment(raw) else ""
        if not token:
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


def covered_by_suffix(domain: str, suffixes: set[str]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)


def compact(rules: set[tuple[str, str]]) -> set[tuple[str, str]]:
    other = {rule for rule in rules if rule[0] not in {"DOMAIN", "DOMAIN-SUFFIX"}}
    suffixes: set[str] = set()
    candidates = sorted(
        (value for kind, value in rules if kind == "DOMAIN-SUFFIX"),
        key=lambda value: (value.count("."), value),
    )
    for domain in candidates:
        if not covered_by_suffix(domain, suffixes):
            suffixes.add(domain)
    exact = {
        value for kind, value in rules
        if kind == "DOMAIN" and not covered_by_suffix(value, suffixes)
    }
    return other | {("DOMAIN-SUFFIX", value) for value in suffixes} | {("DOMAIN", value) for value in exact}


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return {key: int(value) for key, value in data.get("counts", {}).items()}


def validate_snapshot(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old in previous.items():
        if name not in current or old < 20:
            continue
        new = current[name]
        if new * 100 < old * 65 or new > old * 5 // 2:
            raise RuntimeError(f"unexpected source count change for {name}: {old} -> {new}")


def render(rules: set[tuple[str, str]], updated: str | None = None) -> str:
    order = {
        "DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2,
        "DOMAIN-WILDCARD": 3, "USER-AGENT": 4, "PROCESS-NAME": 5,
        "IP-CIDR": 6, "IP-CIDR6": 7, "IP-ASN": 8,
    }
    body = []
    for rule_type, value in sorted(rules, key=lambda rule: (order[rule[0]], rule[1].lower())):
        suffix = ",no-resolve" if rule_type in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} else ""
        body.append(f"{rule_type},{value}{suffix}")
    updated = updated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        "# NAME: Multi-source-Apple",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        f"# RULE COUNT: {len(rules)}",
        *[f"# SOURCE: {url}" for url in SOURCES.values()],
        "# NOTE: Sources are normalized, merged and deduplicated; the SKK watermark domain is excluded.",
        "",
    ]
    return "\n".join(header + body) + "\n"


def main() -> None:
    fetched = {
        "skk": parse_surge(fetch(SOURCES["skk"])),
        "bm7": parse_surge(fetch(SOURCES["bm7"])),
        "yuu": parse_surge(fetch(SOURCES["yuu"])),
        "meta": parse_plain(fetch(SOURCES["meta"])),
    }
    counts = {name: len(rules) for name, rules in fetched.items()}
    for name, minimum in MINIMUMS.items():
        if counts[name] < minimum:
            raise RuntimeError(f"{name} source unexpectedly small: {counts[name]} < {minimum}")
    rules = compact(set().union(*fetched.values()))
    counts["output"] = len(rules)
    validate_snapshot(load_snapshot(), counts)
    previous_text = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if previous_text:
        previous = sum(1 for line in previous_text.splitlines() if line and not line.startswith("#"))
        if previous >= 20 and (len(rules) * 100 < previous * 65 or len(rules) > previous * 5 // 2):
            raise RuntimeError(f"unexpected output count change: {previous} -> {len(rules)}")
    previous_updated = re.search(r"^# UPDATED: (.+)$", previous_text, re.MULTILINE)
    unchanged_text = render(rules, previous_updated.group(1)) if previous_updated else ""
    if unchanged_text != previous_text:
        TARGET.write_text(render(rules), encoding="utf-8")
    SNAPSHOT.write_text(
        json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"updated {TARGET.name} with {len(rules)} rules")


if __name__ == "__main__":
    main()
