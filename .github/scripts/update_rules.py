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
OUT = ROOT / "Rules"
SNAPSHOT = ROOT / ".github" / "rule-source-snapshot.json"
BM7_BASE = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge"
V2FLY_BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data"
RABBIT_BASE = "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules"
LOYAL_BASE = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset"
META_BASE = "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite"

Rule = tuple[str, str]

# BM7 remains the baseline. Supplemental sources are used only for direct category matches.
TARGETS = {
    "GitHub": {"v2fly": "github", "rabbit": None, "loyal": None, "meta": None},
    "Kingsoft": {"v2fly": "kingsoft", "rabbit": None, "loyal": None, "meta": None},
    "AppleMusic": {"v2fly": "apple-music", "rabbit": None, "loyal": None, "meta": "apple-music"},
    "AppleTV": {"v2fly": "apple-tvplus", "rabbit": None, "loyal": None, "meta": "apple-tvplus"},
    "OpenAI": {"v2fly": "openai", "rabbit": None, "loyal": None, "meta": None},
    "GoogleVoice": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "Google": {"v2fly": "google", "rabbit": "Google.list", "loyal": "google.txt", "meta": None},
    "TikTok": {"v2fly": "tiktok", "rabbit": "TikTok.list", "loyal": None, "meta": None},
    "Instagram": {"v2fly": "instagram", "rabbit": "Instagram.list", "loyal": None, "meta": None},
    "Facebook": {"v2fly": "facebook", "rabbit": "Facebook.list", "loyal": None, "meta": None},
    "PayPal": {"v2fly": "paypal", "rabbit": None, "loyal": None, "meta": None},
    "OKX": {"v2fly": "okx", "rabbit": None, "loyal": None, "meta": None},
    "Binance": {"v2fly": "binance", "rabbit": None, "loyal": None, "meta": "binance"},
    "Crypto": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "Cryptocurrency": {"v2fly": "category-cryptocurrency", "rabbit": None, "loyal": None, "meta": "category-cryptocurrency"},
}

DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_TYPES = DOMAIN_TYPES | {
    "DOMAIN-KEYWORD", "DOMAIN-WILDCARD", "DOMAIN-SET",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP",
    "USER-AGENT", "URL-REGEX", "PROCESS-NAME",
    "DEST-PORT", "SRC-PORT", "IN-PORT", "SRC-IP", "DEVICE-NAME",
    "MAC-ADDRESS", "PROTOCOL", "HOSTNAME-TYPE", "SUBNET",
    "CELLULAR-RADIO", "CELLULAR-CARRIER", "SCRIPT",
    "RULE-SET", "AND", "OR", "NOT",
}
MIN_BM7_LINES = {
    "GitHub": 25, "Kingsoft": 200, "AppleMusic": 8, "AppleTV": 8,
    "OpenAI": 25, "GoogleVoice": 1, "Google": 600, "TikTok": 25,
    "Instagram": 3, "Facebook": 500, "PayPal": 200, "OKX": 3,
    "Binance": 8, "Crypto": 150, "Cryptocurrency": 35,
}
VERIFIED_SUPPLEMENTS = {
    "TikTok": {
        ("DOMAIN", "lf19-pkgcdn.pitaya-clientai.com"),
    },
}

MIN_SOURCE_RULES = {
    ("v2fly", "github"): 40,
    ("v2fly", "kingsoft"): 25,
    ("v2fly", "apple-music"): 10,
    ("v2fly", "apple-tvplus"): 5,
    ("v2fly", "openai"): 15,
    ("v2fly", "google"): 800,
    ("v2fly", "tiktok"): 20,
    ("v2fly", "instagram"): 50,
    ("v2fly", "facebook"): 300,
    ("v2fly", "paypal"): 180,
    ("v2fly", "okx"): 7,
    ("v2fly", "binance"): 30,
    ("v2fly", "category-cryptocurrency"): 180,
    ("rabbit", "Google.list"): 500,
    ("rabbit", "TikTok.list"): 20,
    ("rabbit", "Instagram.list"): 2,
    ("rabbit", "Facebook.list"): 400,
    ("loyal", "google.txt"): 80,
    ("meta", "apple-music"): 12,
    ("meta", "apple-tvplus"): 5,
    ("meta", "binance"): 30,
    ("meta", "category-cryptocurrency"): 180,
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
    re.IGNORECASE,
)


def fetch(url: str, attempts: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Rongwuyou-Surge-Rules-Updater/2.0"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                content = response.read().decode("utf-8")
            if not content.strip():
                raise RuntimeError(f"empty response: {url}")
            return content
        except Exception as error:
            last = error
            if attempt + 1 < attempts:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def norm_domain(value: str) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    return domain if DOMAIN_RE.fullmatch(domain) else None


def strip_surge_comment(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith(("#", "//", ";")):
        return ""
    quote: str | None = None
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if quote is not None or (index and not raw[index - 1].isspace()):
            continue
        if raw.startswith("//", index) or char in {"#", ";"}:
            return raw[:index].strip()
    return line


def rule_parts(line: str) -> list[str]:
    return [part.strip().strip('"\'') for part in line.split(",")]


def merge_rule(rules: set[Rule], rule: Rule) -> None:
    rule_type, domain = rule
    if rule_type == "DOMAIN-SUFFIX":
        rules.discard(("DOMAIN", domain))
        rules.add(rule)
    elif ("DOMAIN-SUFFIX", domain) not in rules:
        rules.add(rule)


def parse_bm7(text: str) -> tuple[list[str], set[Rule]]:
    lines: list[str] = []
    domain_rules: set[Rule] = set()
    seen: set[str] = set()
    for raw in text.replace("\r", "").splitlines():
        line = strip_surge_comment(raw)
        if not line:
            continue
        if line not in seen:
            lines.append(line)
            seen.add(line)
        parts = rule_parts(line)
        if len(parts) >= 2 and parts[0] in DOMAIN_TYPES:
            domain = norm_domain(parts[1])
            if domain:
                domain_rules.add((parts[0], domain))
    return lines, domain_rules


def validate_rule(name: str, index: int, line: str) -> None:
    parts = rule_parts(line)
    if not parts or parts[0] not in RULE_TYPES:
        raise RuntimeError(f"unsupported Surge rule in {name} line {index}: {line}")
    if len(parts) < 2 or not parts[1]:
        raise RuntimeError(f"missing rule value in {name} line {index}: {line}")
    rule_type, value = parts[0], parts[1]
    if rule_type in DOMAIN_TYPES and not HOSTNAME_RE.fullmatch(value):
        raise RuntimeError(f"invalid domain rule in {name} line {index}: {line}")
    if re.search(r"(?:^|,)\s*pre-matching\s*(?:,|$)", line, re.IGNORECASE):
        raise RuntimeError(f"pre-matching is not allowed in a Surge rule set: {name} line {index}")
    if rule_type == "IP-CIDR":
        ipaddress.IPv4Network(value, strict=False)
    elif rule_type == "IP-CIDR6":
        ipaddress.IPv6Network(value, strict=False)
    elif rule_type == "IP-ASN" and not value.isdigit():
        raise RuntimeError(f"invalid ASN rule in {name} line {index}: {line}")


def validate_bm7(name: str, lines: list[str]) -> None:
    minimum = MIN_BM7_LINES[name]
    if len(lines) < minimum:
        raise RuntimeError(f"BM7 rule count unexpectedly low for {name}: {len(lines)} < {minimum}")
    for index, line in enumerate(lines, 1):
        validate_rule(name, index, line)


def parse_source_rules(content: str, plain: bool = False) -> set[Rule]:
    rules: set[Rule] = set()
    for raw in content.replace("\r", "").splitlines():
        line = raw.split("#", 1)[0].split("//", 1)[0].strip()
        if not line or line.startswith((";", "!")):
            continue
        if plain:
            token = line.split()[0]
            rule_type = "DOMAIN"
            if token.startswith(("+.", "*.")):
                token = token[2:]
                rule_type = "DOMAIN-SUFFIX"
            elif token.startswith("full:"):
                token = token[5:]
            elif token.startswith("domain:"):
                token = token[7:]
                rule_type = "DOMAIN-SUFFIX"
            elif token.startswith(("geosite:", "regexp:", "keyword:")):
                continue
            domain = norm_domain(token)
            if domain:
                merge_rule(rules, (rule_type, domain))
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2 and parts[0] in DOMAIN_TYPES:
            domain = norm_domain(parts[1])
            if domain:
                merge_rule(rules, (parts[0], domain))
    return rules


def parse_v2fly(entry: str, visited: set[str] | None = None) -> set[Rule]:
    visited = visited or set()
    if entry in visited:
        return set()
    visited.add(entry)
    rules: set[Rule] = set()
    for raw in fetch(f"{V2FLY_BASE}/{entry}").replace("\r", "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        token = fields[0]
        if token.startswith("include:"):
            if len(fields) > 1:
                raise RuntimeError(f"selective v2fly include is not supported: {entry}: {line}")
            for rule in parse_v2fly(token[8:], visited):
                merge_rule(rules, rule)
            continue
        rule_type = "DOMAIN-SUFFIX"
        if token.startswith("full:"):
            token = token[5:]
            rule_type = "DOMAIN"
        elif token.startswith("domain:"):
            token = token[7:]
        elif token.startswith(("keyword:", "regexp:")):
            continue
        domain = norm_domain(token)
        if domain:
            merge_rule(rules, (rule_type, domain))
    return rules


def validate_source(kind: str, entry: str, rules: set[Rule]) -> None:
    minimum = MIN_SOURCE_RULES[(kind, entry)]
    if len(rules) < minimum:
        raise RuntimeError(
            f"source rule count unexpectedly low for {kind}/{entry}: {len(rules)} < {minimum}"
        )


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    try:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return {key: int(value) for key, value in data.get("counts", {}).items()}
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError(f"invalid source snapshot: {SNAPSHOT}: {error}") from error


def validate_snapshot_change(previous: dict[str, int], current: dict[str, int]) -> None:
    for key, old_count in previous.items():
        if key not in current or old_count < 20:
            continue
        new_count = current[key]
        if new_count * 100 < old_count * 65:
            raise RuntimeError(f"source rule count dropped too much for {key}: {old_count} -> {new_count}")
        if new_count > old_count * 5 // 2:
            raise RuntimeError(f"source rule count grew too much for {key}: {old_count} -> {new_count}")


def render_snapshot(counts: dict[str, int]) -> str:
    return json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n"


def covered_by_suffix(domain: str, suffixes: set[str]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)


def select_additions(base_rules: set[Rule], source_rules: set[Rule]) -> list[Rule]:
    exact = {domain for rule_type, domain in base_rules if rule_type == "DOMAIN"}
    suffixes = {domain for rule_type, domain in base_rules if rule_type == "DOMAIN-SUFFIX"}
    selected: list[Rule] = []

    suffix_candidates = sorted(
        (domain for rule_type, domain in source_rules if rule_type == "DOMAIN-SUFFIX"),
        key=lambda domain: (domain.count("."), domain),
    )
    for domain in suffix_candidates:
        if covered_by_suffix(domain, suffixes):
            continue
        selected.append(("DOMAIN-SUFFIX", domain))
        suffixes.add(domain)

    exact_candidates = sorted(
        domain for rule_type, domain in source_rules if rule_type == "DOMAIN"
    )
    for domain in exact_candidates:
        if domain in exact or covered_by_suffix(domain, suffixes):
            continue
        selected.append(("DOMAIN", domain))
        exact.add(domain)

    return sorted(selected)


def render(
    name: str,
    lines: list[str],
    additions: list[Rule],
    sources: list[str],
    verified_supplements: set[Rule],
) -> str:
    all_lines = list(lines)
    all_lines.extend(f"{rule_type},{domain}" for rule_type, domain in additions)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: Multi-source-{name}",
        "# AUTHOR: Rongwuyou",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# RULE COUNT: {len(all_lines)}",
        f"# SOURCE: {BM7_BASE}/{name}/{name}.list",
        *[f"# MERGED SOURCE: {source}" for source in sources],
        *[f"# VERIFIED SUPPLEMENT: {rule_type},{value} from iOS App Privacy Report" for rule_type, value in sorted(verified_supplements)],
        "# NOTE: BM7 is preserved; supplemental DOMAIN and DOMAIN-SUFFIX semantics are retained and deduplicated.",
        "",
    ]
    return "\n".join(header + all_lines) + "\n"


def stable(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("# UPDATED:")
    )


def count_rules(text: str) -> int:
    return sum(
        1 for line in text.replace("\r", "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def validate_change(name: str, target: Path, output: str) -> None:
    if not target.exists():
        return
    previous = count_rules(target.read_text(encoding="utf-8"))
    current = count_rules(output)
    if previous >= 20:
        if current * 100 < previous * 65:
            raise RuntimeError(f"output rule count dropped too much for {name}: {previous} -> {current}")
        if current > previous * 5 // 2:
            raise RuntimeError(f"output rule count grew too much for {name}: {previous} -> {current}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    source_counts: dict[str, int] = {}
    for name, mapping in TARGETS.items():
        bm7_url = f"{BM7_BASE}/{name}/{name}.list"
        lines, base_rules = parse_bm7(fetch(bm7_url))
        validate_bm7(name, lines)
        source_counts[f"bm7/{name}"] = len(lines)
        source_rules: set[Rule] = set()
        sources: list[str] = []

        if mapping["v2fly"]:
            entry = mapping["v2fly"]
            rules = parse_v2fly(entry)
            validate_source("v2fly", entry, rules)
            source_counts[f"v2fly/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{V2FLY_BASE}/{entry}")
        if mapping["rabbit"]:
            entry = mapping["rabbit"]
            rules = parse_source_rules(fetch(f"{RABBIT_BASE}/{entry}"))
            validate_source("rabbit", entry, rules)
            source_counts[f"rabbit/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{RABBIT_BASE}/{entry}")
        if mapping["loyal"]:
            entry = mapping["loyal"]
            rules = parse_source_rules(fetch(f"{LOYAL_BASE}/{entry}"))
            validate_source("loyal", entry, rules)
            source_counts[f"loyal/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{LOYAL_BASE}/{entry}")
        if mapping["meta"]:
            entry = mapping["meta"]
            rules = parse_source_rules(fetch(f"{META_BASE}/{entry}.list"), plain=True)
            validate_source("meta", entry, rules)
            source_counts[f"meta/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{META_BASE}/{entry}.list")

        verified_supplements = VERIFIED_SUPPLEMENTS.get(name, set())
        for rule in verified_supplements:
            merge_rule(source_rules, rule)
        additions = select_additions(base_rules, source_rules)
        output = render(name, lines, additions, sources, verified_supplements)
        for index, line in enumerate(
            (line for line in output.splitlines() if line and not line.startswith("#")), 1
        ):
            validate_rule(name, index, line)

        target = OUT / f"{name}.list"
        validate_change(name, target, output)
        outputs[name] = output

    validate_snapshot_change(load_snapshot(), source_counts)
    for name, output in outputs.items():
        target = OUT / f"{name}.list"
        if target.exists() and stable(target.read_text(encoding="utf-8")) == stable(output):
            print(f"{name}: unchanged")
        else:
            target.write_text(output, encoding="utf-8")
            print(
                f"{name}: BM7={len(lines)} sources={len(source_rules)} "
                f"added={len(additions)} output={count_rules(output)}"
            )
    SNAPSHOT.write_text(render_snapshot(source_counts), encoding="utf-8")


if __name__ == "__main__":
    main()
