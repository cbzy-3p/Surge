#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Rule" / "XiaoHongShu.list"
SNAPSHOT = ROOT / ".github" / "xiaohongshu-source-snapshot.json"
V2FLY_BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/"
BLACKMATRIX_URL = (
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/"
    "rule/Surge/XiaoHongShu/XiaoHongShu.list"
)
APP_RULE_URL = (
    "https://raw.githubusercontent.com/wresource/hxmy-proxy/master/"
    "app/src/main/assets/rules/app-xiaohongshu.txt"
)
BGPEER_URL = (
    "https://raw.githubusercontent.com/bgpeer/rules/main/"
    "geo/geosite/xiaohongshu.list"
)
DL123_URL = (
    "https://raw.githubusercontent.com/dl123100/clash-geosite/master/"
    "rule-files/XHS.list"
)

Rule = tuple[str, str]
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_TYPES = DOMAIN_TYPES | {"IP-ASN"}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)

# These domains are registered to Xiaohongshu's operating company in public ICP records.
VERIFIED_FIRST_PARTY_DOMAINS = {
    "aboutmgzn.com",
    "batman.plus",
    "cn-rednotecdn.com",
    "hongyunlogistics.com",
    "iselect.red",
    "redelight.net",
    "rednote.life",
    "redselect.cn",
    "rl.ink",
    "rnote.com",
    "rnotecdn.com",
    "xhs.cn",
    "xhsredcdn.com",
    "xingin.cn",
    "yuukoo.info",
}
# APNIC registers both ASNs to Xingyin Information Technology (Shanghai) Co., Ltd.
VERIFIED_FIRST_PARTY_ASNS = {"151281", "151282"}
MIN_SOURCE_RULES = {
    "v2fly": 10,
    "blackmatrix7": 4,
    "wresource": 20,
    "bgpeer": 40,
    "dl123100": 40,
}
SOURCE_LABELS = (
    "v2fly/domain-list-community data/xiaohongshu (recursive includes)",
    "blackmatrix7/ios_rule_script XiaoHongShu.list",
    "wresource/hxmy-proxy app-xiaohongshu.txt",
    "bgpeer/rules geosite/xiaohongshu.list",
    "dl123100/clash-geosite XHS.list",
    "Xiaohongshu first-party domains verified from public ICP records",
)


def fetch_text(url: str, attempts: int = 3) -> str:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "cbzy-3p-Surge-XiaoHongShu-Updater/2.0"},
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


def normalize_asn(value: str) -> str | None:
    asn = value.strip()
    if not asn.isdecimal():
        return None
    number = int(asn)
    return str(number) if 1 <= number <= 4_294_967_295 else None


def merge_rule(rules: set[Rule], rule: Rule) -> None:
    rule_type, domain = rule
    if rule_type == "DOMAIN-SUFFIX":
        rules.discard(("DOMAIN", domain))
        rules.add(rule)
    elif rule_type != "DOMAIN" or ("DOMAIN-SUFFIX", domain) not in rules:
        rules.add(rule)


def compact_rules(rules: set[Rule]) -> set[Rule]:
    suffixes: set[str] = set()
    for domain in sorted(
        (value for rule_type, value in rules if rule_type == "DOMAIN-SUFFIX"),
        key=lambda value: (value.count("."), value),
    ):
        labels = domain.split(".")
        if not any(".".join(labels[index:]) in suffixes for index in range(len(labels))):
            suffixes.add(domain)
    result = {rule for rule in rules if rule[0] not in DOMAIN_TYPES}
    result.update(("DOMAIN-SUFFIX", domain) for domain in suffixes)
    result.update(
        ("DOMAIN", domain) for rule_type, domain in rules
        if rule_type == "DOMAIN"
        and not any(
            ".".join(domain.split(".")[index:]) in suffixes
            for index in range(len(domain.split(".")))
        )
    )
    return result


def parse_v2fly(entry: str, visited: set[str] | None = None) -> set[Rule]:
    visited = visited or set()
    if entry in visited:
        return set()
    visited.add(entry)

    rules: set[Rule] = set()
    for raw_line in fetch_text(f"{V2FLY_BASE}{entry}").replace("\r", "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        token = fields[0]
        if token.startswith("include:"):
            if len(fields) > 1:
                raise RuntimeError(f"selective v2fly include is unsupported: {entry}: {line}")
            for rule in parse_v2fly(token.removeprefix("include:"), visited):
                merge_rule(rules, rule)
            continue
        rule_type = "DOMAIN-SUFFIX"
        if token.startswith("full:"):
            token = token.removeprefix("full:")
            rule_type = "DOMAIN"
        elif token.startswith("domain:"):
            token = token.removeprefix("domain:")
        elif token.startswith(("regexp:", "keyword:")):
            continue
        domain = normalize_domain(token)
        if domain:
            merge_rule(rules, (rule_type, domain))
    return rules


def parse_surge_rules(content: str) -> set[Rule]:
    rules: set[Rule] = set()
    for raw_line in content.replace("\r", "").splitlines():
        line = raw_line.split("#", 1)[0].split("//", 1)[0].strip()
        if not line or line.startswith(";"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or parts[0] not in RULE_TYPES:
            continue
        rule_type = parts[0]
        value = normalize_domain(parts[1]) if rule_type in DOMAIN_TYPES else normalize_asn(parts[1])
        if value:
            merge_rule(rules, (rule_type, value))
    return rules


def parse_plain_domains(content: str) -> set[Rule]:
    rules: set[Rule] = set()
    for raw_line in content.replace("\r", "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        domain = normalize_domain(line.split()[0])
        if domain:
            merge_rule(rules, ("DOMAIN-SUFFIX", domain))
    return rules


def validate_source(name: str, rules: set[Rule]) -> None:
    minimum = MIN_SOURCE_RULES[name]
    if len(rules) < minimum:
        raise RuntimeError(f"source count unexpectedly low for {name}: {len(rules)} < {minimum}")


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    try:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return {key: int(value) for key, value in data.get("counts", {}).items()}
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError(f"invalid source snapshot: {error}") from error


def validate_snapshot_change(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old_count in previous.items():
        if name not in current or old_count < 20:
            continue
        new_count = current[name]
        if new_count * 100 < old_count * 65:
            raise RuntimeError(f"source count dropped too much for {name}: {old_count} -> {new_count}")
        if new_count > old_count * 5 // 2:
            raise RuntimeError(f"source count grew too much for {name}: {old_count} -> {new_count}")


def render_snapshot(counts: dict[str, int]) -> str:
    return json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n"


def current_rules() -> set[Rule]:
    if not OUTPUT.exists():
        return set()
    return parse_surge_rules(OUTPUT.read_text(encoding="utf-8"))


def validate_rules(rules: set[Rule]) -> None:
    if not 30 <= len(rules) <= 150:
        raise RuntimeError(f"unexpected output count: {len(rules)}")
    for rule_type, value in rules:
        valid = normalize_domain(value) if rule_type in DOMAIN_TYPES else normalize_asn(value)
        if rule_type not in RULE_TYPES or not valid:
            raise RuntimeError(f"invalid Surge rule: {rule_type},{value}")


def validate_output_change(previous: set[Rule], current: set[Rule]) -> None:
    if len(previous) < 20:
        return
    if len(current) * 100 < len(previous) * 65:
        raise RuntimeError(f"output count dropped too much: {len(previous)} -> {len(current)}")
    if len(current) > len(previous) * 5 // 2:
        raise RuntimeError(f"output count grew too much: {len(previous)} -> {len(current)}")


def render(rules: set[Rule]) -> str:
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    by_type = {rule_type: sum(1 for item in rules if item[0] == rule_type) for rule_type in RULE_TYPES}
    header = [
        "# NAME: XiaoHongShu",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        *[f"# SOURCE: {source}" for source in SOURCE_LABELS],
        "# NOTE: Domain rules require cross-source corroboration or public ICP ownership verification. IP-ASN rules require direct registry ownership verification.",
        f"# DOMAIN: {by_type['DOMAIN']}",
        f"# DOMAIN-SUFFIX: {by_type['DOMAIN-SUFFIX']}",
        f"# IP-ASN: {by_type['IP-ASN']}",
        f"# TOTAL: {len(rules)}",
        "",
    ]
    return "\n".join(header + [f"{rule_type},{domain}" for rule_type, domain in sorted(rules)]) + "\n"


def main() -> None:
    v2fly = parse_v2fly("xiaohongshu")
    blackmatrix7 = parse_surge_rules(fetch_text(BLACKMATRIX_URL))
    wresource = parse_plain_domains(fetch_text(APP_RULE_URL))
    bgpeer = parse_surge_rules(fetch_text(BGPEER_URL))
    dl123100 = parse_surge_rules(fetch_text(DL123_URL))
    sources = {
        "v2fly": v2fly,
        "blackmatrix7": blackmatrix7,
        "wresource": wresource,
        "bgpeer": bgpeer,
        "dl123100": dl123100,
    }
    for name, rules in sources.items():
        validate_source(name, rules)

    rules: set[Rule] = set()
    for source_rules in (v2fly, blackmatrix7, wresource):
        for rule in source_rules:
            merge_rule(rules, rule)
    for domain in VERIFIED_FIRST_PARTY_DOMAINS:
        merge_rule(rules, ("DOMAIN-SUFFIX", domain))
    for asn in VERIFIED_FIRST_PARTY_ASNS:
        merge_rule(rules, ("IP-ASN", asn))
    bgpeer_domains = {value for rule_type, value in bgpeer if rule_type in DOMAIN_TYPES}
    dl123100_domains = {value for rule_type, value in dl123100 if rule_type in DOMAIN_TYPES}
    for domain in bgpeer_domains & dl123100_domains:
        merge_rule(rules, ("DOMAIN-SUFFIX", domain))

    rules = compact_rules(rules)
    validate_rules(rules)
    previous = current_rules()
    validate_output_change(previous, rules)
    counts = {name: len(source_rules) for name, source_rules in sources.items()}
    counts["corroborated"] = len(bgpeer_domains & dl123100_domains)
    counts["output"] = len(rules)
    validate_snapshot_change(load_snapshot(), counts)

    output = render(rules)
    snapshot = render_snapshot(counts)
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8").splitlines()[4:] != output.splitlines()[4:]:
        OUTPUT.write_text(output, encoding="utf-8")
        print(f"updated {OUTPUT.name} with {len(rules)} Surge domain rules")
    else:
        print(f"unchanged {OUTPUT.name} with {len(rules)} Surge domain rules")
    SNAPSHOT.write_text(snapshot, encoding="utf-8")


if __name__ == "__main__":
    main()
