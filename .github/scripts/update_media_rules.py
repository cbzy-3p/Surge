#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULE_DIR = ROOT / "Rule"
SNAPSHOT = ROOT / ".github" / "media-source-snapshot.json"
SNAPSHOT_VERSION = 1

RABBIT = "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules"
BM7 = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge"
SKK = "https://ruleset.skk.moe/List"
CONNERS = "https://raw.githubusercontent.com/ConnersHua/RuleGo/master/Surge/Ruleset/Extra"
YUU = "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge"

CONFIGS = {
    "AIGC": [
        ("skk-non-ip", f"{SKK}/non_ip/ai.conf", "surge", 20),
        ("skk-ip", f"{SKK}/ip/ai.conf", "surge", 5),
        ("rabbit", f"{RABBIT}/AIGC.list", "surge", 100),
        ("conners", f"{CONNERS}/AI.list", "surge", 20),
        ("yuu", f"{YUU}/geosite/category-ai-!cn.list", "surge", 50),
    ],
    "YouTube": [
        ("rabbit", f"{RABBIT}/YouTube.list", "surge", 150),
        ("bm7", f"{BM7}/YouTube/YouTube.list", "surge", 150),
        ("conners", f"{CONNERS}/Streaming/Video/YouTube.list", "surge", 20),
        ("yuu", f"{YUU}/geosite/youtube.list", "surge", 150),
    ],
    "Netflix": [
        ("rabbit", f"{RABBIT}/Netflix.list", "surge", 1_000),
        ("bm7", f"{BM7}/Netflix/Netflix.list", "surge", 1_000),
        ("conners", f"{CONNERS}/Streaming/Video/Netflix.list", "surge", 10),
        ("yuu-domain", f"{YUU}/geosite/netflix.list", "surge", 20),
        ("yuu-ip", f"{YUU}/geoip/netflix.list", "surge", 100),
    ],
    "ChinaMedia": [
        ("rabbit", f"{RABBIT}/ChinaMedia.list", "surge", 400),
        ("bm7", f"{BM7}/ChinaMedia/ChinaMedia.list", "surge", 400),
        ("yuu", f"{YUU}/geosite/category-media-cn.list", "surge", 350),
    ],
    "GlobalMedia": [
        ("skk-non-ip", f"{SKK}/non_ip/stream.conf", "surge", 100),
        ("skk-ip", f"{SKK}/ip/stream.conf", "surge", 15),
        ("rabbit", f"{RABBIT}/GlobalMedia.list", "surge", 2_000),
        ("bm7", f"{BM7}/GlobalMedia/GlobalMedia_All_No_Resolve.list", "surge", 2_000),
        ("yuu", f"{YUU}/geosite/category-media.list", "surge", 1_400),
    ],
    "China": [
        ("rabbit", f"{RABBIT}/China.list", "surge", 3_500),
        ("bm7", f"{BM7}/China/China_Domain.list", "domain", 3_500),
        ("yuu", f"{YUU}/geosite/geolocation-cn.list", "surge", 5_000),
    ],
    "ChinaCIDR": [
        ("skk-ipv4", f"{SKK}/ip/china_ip.conf", "surge", 1_000),
        ("skk-ipv6", f"{SKK}/ip/china_ip_ipv6.conf", "surge", 100),
        ("rabbit", f"{RABBIT}/ChinaCIDR.list", "surge", 9_000),
        ("bm7", f"{BM7}/ChinaIPs/ChinaIPs.list", "surge", 20_000),
        ("yuu", f"{YUU}/geoip/cn.list", "surge", 8_500),
    ],
}

RULE_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "USER-AGENT", "PROCESS-NAME",
    "URL-REGEX",
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
BLOCKED_EXACT_DOMAINS = {"7h15.ru1353t.1s.m4d3.by.5ukk4w.skk.moe"}


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "cbzy-3p-Surge-Media-Updater/1.0"}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                content = response.read().decode("utf-8")
            if not content.strip():
                raise RuntimeError("empty response")
            return content
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def strip_comment(raw: str) -> str:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "//", ";", "!")):
        return ""
    for marker in (" //", " #"):
        if marker in line:
            line = line.split(marker, 1)[0].strip()
    return line


def normalize_domain(value: str, allow_tld: bool = False) -> str | None:
    domain = value.strip().lower().rstrip(".")
    while domain.startswith(("+.", "*.", ".")):
        domain = domain[2:] if domain.startswith(("+.", "*.")) else domain[1:]
    if DOMAIN_RE.fullmatch(domain):
        return domain
    return domain if allow_tld and DOMAIN_LABEL_RE.fullmatch(domain) else None


def normalize_rule(rule_type: str, value: str) -> tuple[str, str] | None:
    rule_type = rule_type.upper()
    value = value.strip()
    if rule_type not in RULE_TYPES:
        return None
    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
        domain = normalize_domain(value, allow_tld=rule_type == "DOMAIN-SUFFIX")
        return (rule_type, domain) if domain and domain not in BLOCKED_EXACT_DOMAINS else None
    if rule_type == "DOMAIN-WILDCARD":
        wildcard = value.lower().rstrip(".")
        return (rule_type, wildcard) if wildcard.startswith("*.") and normalize_domain(wildcard) else None
    if rule_type == "DOMAIN-KEYWORD":
        return (rule_type, value) if value and not any(char.isspace() for char in value) else None
    if rule_type in {"USER-AGENT", "PROCESS-NAME", "URL-REGEX"}:
        return (rule_type, value) if value else None
    if rule_type == "IP-ASN":
        return (rule_type, str(int(value))) if value.isdecimal() and int(value) > 0 else None
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None
    if (rule_type == "IP-CIDR") != (network.version == 4):
        return None
    return rule_type, str(network)


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


def parse_domains(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        line = strip_comment(raw)
        if not line:
            continue
        token = line.split(maxsplit=1)[0]
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


def parse_cidrs(content: str) -> set[tuple[str, str]]:
    rules: set[tuple[str, str]] = set()
    for raw in content.replace("\r", "").splitlines():
        token = strip_comment(raw).split(maxsplit=1)[0] if strip_comment(raw) else ""
        if not token:
            continue
        try:
            network = ipaddress.ip_network(token, strict=False)
        except ValueError:
            continue
        rules.add(("IP-CIDR" if network.version == 4 else "IP-CIDR6", str(network)))
    return rules


PARSERS = {"surge": parse_surge, "domain": parse_domains, "cidr": parse_cidrs}


def covering_suffix(domain: str, suffixes: set[str]) -> str | None:
    """Return the nearest covering suffix without scanning the whole set."""
    labels = domain.split(".")
    for index in range(len(labels)):
        candidate = ".".join(labels[index:])
        if candidate in suffixes:
            return candidate
    return None


def compact(rules: set[tuple[str, str]]) -> set[tuple[str, str]]:
    suffixes: set[str] = set()
    for domain in sorted(
        (value for kind, value in rules if kind == "DOMAIN-SUFFIX"),
        key=lambda value: (value.count("."), value),
    ):
        if covering_suffix(domain, suffixes) is None:
            suffixes.add(domain)
    exact = {
        value for kind, value in rules
        if kind == "DOMAIN" and covering_suffix(value, suffixes) is None
    }
    result = {
        rule for rule in rules
        if rule[0] not in {"DOMAIN", "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6"}
    }
    result.update(("DOMAIN-SUFFIX", value) for value in suffixes)
    result.update(("DOMAIN", value) for value in exact)
    for version, rule_type in ((4, "IP-CIDR"), (6, "IP-CIDR6")):
        networks = [
            ipaddress.ip_network(value)
            for kind, value in rules
            if kind == rule_type and ipaddress.ip_network(value).version == version
        ]
        result.update((rule_type, str(network)) for network in ipaddress.collapse_addresses(networks))
    return result


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT.exists():
        return {}
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if data.get("version") != SNAPSHOT_VERSION:
        return {}
    return {key: int(value) for key, value in data.get("counts", {}).items()}


def validate_snapshot(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old in previous.items():
        if name not in current or old < 20:
            continue
        new = current[name]
        if new * 100 < old * 65 or new > old * 5 // 2:
            raise RuntimeError(f"unexpected rule count change for {name}: {old} -> {new}")


def render(name: str, rules: set[tuple[str, str]], sources: list[str], updated: str | None = None) -> str:
    order = {
        "DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2,
        "DOMAIN-WILDCARD": 3, "USER-AGENT": 4, "PROCESS-NAME": 5,
        "URL-REGEX": 6, "IP-CIDR": 7, "IP-CIDR6": 8, "IP-ASN": 9,
    }
    updated = updated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: Multi-source-{name}",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        f"# RULE COUNT: {len(rules)}",
        *[f"# SOURCE: {url}" for url in sources],
        "# NOTE: Sources are normalized, merged, deduplicated and compacted without reducing coverage.",
        "",
    ]
    body = []
    for rule_type, value in sorted(rules, key=lambda rule: (order[rule[0]], rule[1].lower(), rule[1])):
        option = ",no-resolve" if rule_type in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} else ""
        body.append(f"{rule_type},{value}{option}")
    return "\n".join(header + body) + "\n"


def write_if_changed(name: str, rules: set[tuple[str, str]], sources: list[str]) -> None:
    target = RULE_DIR / f"{name}.list"
    previous_text = target.read_text(encoding="utf-8") if target.exists() else ""
    previous_updated = re.search(r"^# UPDATED: (.+)$", previous_text, re.MULTILINE)
    unchanged = render(name, rules, sources, previous_updated.group(1)) if previous_updated else ""
    if not target.exists() or unchanged != previous_text:
        target.write_text(render(name, rules, sources), encoding="utf-8")


def main() -> None:
    snapshot: dict[str, int] = {}
    outputs: dict[str, tuple[set[tuple[str, str]], list[str]]] = {}
    fetched: dict[tuple[str, str], set[tuple[str, str]]] = {}
    jobs = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for name, sources in CONFIGS.items():
            for source_name, url, parser_name, _minimum in sources:
                future = executor.submit(lambda source_url=url, parser=parser_name: PARSERS[parser](fetch(source_url)))
                jobs[future] = (name, source_name)
        for future in as_completed(jobs):
            fetched[jobs[future]] = future.result()
    for name, sources in CONFIGS.items():
        combined: set[tuple[str, str]] = set()
        urls: list[str] = []
        for source_name, url, parser_name, minimum in sources:
            rules = fetched[(name, source_name)]
            if len(rules) < minimum:
                raise RuntimeError(f"{name}/{source_name} source unexpectedly small: {len(rules)} < {minimum}")
            snapshot[f"{name}/{source_name}"] = len(rules)
            combined.update(rules)
            urls.append(url)
        output = compact(combined)
        snapshot[f"{name}/output"] = len(output)
        outputs[name] = output, urls
    validate_snapshot(load_snapshot(), snapshot)
    for name, (rules, urls) in outputs.items():
        write_if_changed(name, rules, urls)
        print(f"updated {name}.list with {len(rules)} rules")
    SNAPSHOT.write_text(
        json.dumps({"version": SNAPSHOT_VERSION, "counts": snapshot}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
