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
OUT = ROOT / "Rule"
SNAPSHOT = ROOT / ".github" / "rule-source-snapshot.json"
BM7_BASE = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge"
RABBIT_BASE = "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules"
LOYAL_BASE = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset"
CONNERS_BASE = "https://raw.githubusercontent.com/ConnersHua/RuleGo/master/Surge/Ruleset/Extra"
YUU_BASE = "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite"

Rule = tuple[str, str]

# BM7 defines fine-grained category boundaries. Fixed supplemental sources are
# merged only when they provide the same category.
TARGETS = {
    "GitHub": {"rabbit": None, "conners": None, "loyal": None, "yuu": "github"},
    "Kingsoft": {"rabbit": None, "conners": None, "loyal": None, "yuu": "kingsoft"},
    "AppleMusic": {"rabbit": None, "conners": "Apple/Music.list", "loyal": None, "yuu": "apple-music"},
    "AppleTV": {"rabbit": None, "conners": "Apple/TV.list", "loyal": None, "yuu": "apple-tvplus"},
    "OpenAI": {"rabbit": None, "conners": "GenAI/OpenAI.list", "loyal": None, "yuu": "openai"},
    "GoogleVoice": {"rabbit": None, "conners": "Google/GoogleVoice.list", "loyal": None, "yuu": None},
    "Google": {"rabbit": "Google.list", "conners": "Google/Google.list", "loyal": "google.txt", "yuu": "google"},
    "TikTok": {"rabbit": "TikTok.list", "conners": "Streaming/Video/TikTok.list", "loyal": None, "yuu": "tiktok"},
    "Instagram": {"rabbit": "Instagram.list", "conners": "Streaming/Music/Instagram.list", "loyal": None, "yuu": "instagram"},
    "Facebook": {"rabbit": "Facebook.list", "conners": None, "loyal": None, "yuu": "facebook"},
    "PayPal": {"rabbit": None, "conners": "PayPal.list", "loyal": None, "yuu": "paypal"},
    "OKX": {"rabbit": None, "conners": None, "loyal": None, "yuu": "okx"},
    "Binance": {"rabbit": None, "conners": None, "loyal": None, "yuu": "binance"},
    "Crypto": {"rabbit": None, "conners": "Crypto.list", "loyal": None, "yuu": None},
    "Cryptocurrency": {"rabbit": None, "conners": "Crypto.list", "loyal": None, "yuu": "category-cryptocurrency"},
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
    ("rabbit", "Google.list"): 500,
    ("rabbit", "TikTok.list"): 20,
    ("rabbit", "Instagram.list"): 2,
    ("rabbit", "Facebook.list"): 400,
    ("loyal", "google.txt"): 80,
    ("conners", "Apple/Music.list"): 5,
    ("conners", "Apple/TV.list"): 5,
    ("conners", "GenAI/OpenAI.list"): 5,
    ("conners", "Google/GoogleVoice.list"): 1,
    ("conners", "Google/Google.list"): 10,
    ("conners", "Streaming/Video/TikTok.list"): 5,
    ("conners", "Streaming/Music/Instagram.list"): 2,
    ("conners", "PayPal.list"): 5,
    ("conners", "Crypto.list"): 5,
    ("yuu", "github"): 40,
    ("yuu", "kingsoft"): 25,
    ("yuu", "apple-music"): 8,
    ("yuu", "apple-tvplus"): 5,
    ("yuu", "openai"): 15,
    ("yuu", "google"): 500,
    ("yuu", "tiktok"): 20,
    ("yuu", "instagram"): 50,
    ("yuu", "facebook"): 300,
    ("yuu", "paypal"): 180,
    ("yuu", "okx"): 7,
    ("yuu", "binance"): 30,
    ("yuu", "category-cryptocurrency"): 180,
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
                url, headers={"User-Agent": "cbzy-3p-Surge-Rules-Updater/2.0"}
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


def compact_rule_lines(lines: list[str]) -> list[str]:
    parsed: dict[int, tuple[str, str, tuple[str, ...]]] = {}
    suffixes: dict[tuple[str, ...], set[str]] = {}
    cidrs: dict[int, tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, tuple[str, ...]]] = {}
    networks: dict[
        tuple[str, ...], set[ipaddress.IPv4Network | ipaddress.IPv6Network]
    ] = {}
    for index, line in enumerate(lines):
        parts = rule_parts(line)
        if len(parts) < 2:
            continue
        options = tuple(part.lower() for part in parts[2:])
        if parts[0] in {"IP-CIDR", "IP-CIDR6"}:
            try:
                network = ipaddress.ip_network(parts[1], strict=False)
            except ValueError:
                continue
            cidrs[index] = network, options
            networks.setdefault(options, set()).add(network)
            continue
        if parts[0] not in DOMAIN_TYPES:
            continue
        domain = norm_domain(parts[1])
        if not domain:
            continue
        parsed[index] = parts[0], domain, options
        if parts[0] == "DOMAIN-SUFFIX":
            suffixes.setdefault(options, set()).add(domain)

    keep: list[str] = []
    for index, line in enumerate(lines):
        cidr = cidrs.get(index)
        if cidr:
            network, options = cidr
            if any(
                network.supernet(new_prefix=prefix) in networks[options]
                for prefix in range(network.prefixlen - 1, -1, -1)
            ):
                continue
            keep.append(line)
            continue
        rule = parsed.get(index)
        if not rule:
            keep.append(line)
            continue
        rule_type, domain, options = rule
        candidates = suffixes.get(options, set())
        covered = any(
            domain == suffix or domain.endswith(f".{suffix}")
            for suffix in candidates
            if rule_type == "DOMAIN" or suffix != domain
        )
        if not covered:
            keep.append(line)
    return keep


def domain_rules_from_lines(lines: list[str]) -> set[Rule]:
    rules: set[Rule] = set()
    for line in lines:
        parts = rule_parts(line)
        if len(parts) >= 2 and parts[0] in DOMAIN_TYPES:
            domain = norm_domain(parts[1])
            if domain:
                rules.add((parts[0], domain))
    return rules


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
    all_lines = compact_rule_lines(all_lines)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: Multi-source-{name}",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# RULE COUNT: {len(all_lines)}",
        f"# SOURCE: {BM7_BASE}/{name}/{name}.list",
        *[f"# MERGED SOURCE: {source}" for source in sources],
        *[f"# VERIFIED SUPPLEMENT: {rule_type},{value} from iOS App Privacy Report" for rule_type, value in sorted(verified_supplements)],
        "# NOTE: BM7 coverage is preserved; supplemental DOMAIN and DOMAIN-SUFFIX semantics are retained and compacted.",
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
        lines, _ = parse_bm7(fetch(bm7_url))
        validate_bm7(name, lines)
        source_counts[f"bm7/{name}"] = len(lines)
        lines = compact_rule_lines(lines)
        base_rules = domain_rules_from_lines(lines)
        source_rules: set[Rule] = set()
        sources: list[str] = []

        if mapping["rabbit"]:
            entry = mapping["rabbit"]
            rules = parse_source_rules(fetch(f"{RABBIT_BASE}/{entry}"))
            validate_source("rabbit", entry, rules)
            source_counts[f"rabbit/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{RABBIT_BASE}/{entry}")
        if mapping["conners"]:
            entry = mapping["conners"]
            rules = parse_source_rules(fetch(f"{CONNERS_BASE}/{entry}"))
            validate_source("conners", entry, rules)
            source_counts[f"conners/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{CONNERS_BASE}/{entry}")
        if mapping["loyal"]:
            entry = mapping["loyal"]
            rules = parse_source_rules(fetch(f"{LOYAL_BASE}/{entry}"))
            validate_source("loyal", entry, rules)
            source_counts[f"loyal/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{LOYAL_BASE}/{entry}")
        if mapping["yuu"]:
            entry = mapping["yuu"]
            rules = parse_source_rules(fetch(f"{YUU_BASE}/{entry}.list"))
            validate_source("yuu", entry, rules)
            source_counts[f"yuu/{entry}"] = len(rules)
            for rule in rules:
                merge_rule(source_rules, rule)
            sources.append(f"{YUU_BASE}/{entry}.list")

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
