"""Compare narrow/single-source outputs with related feeds without broadening them."""
from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path

import update_v2fly_rules as v2fly
from update_media_rules import CONNERS, SKK, parse_surge
from update_proxy import SOURCES as PROXY_SOURCES, parse_surge as parse_proxy
from update_rules import fetch
from validate_rule_files import normalize_domain, strip_comment, validate_rule_line
from check_rule_changes import canonical_rules

ROOT = Path(__file__).resolve().parents[2]
LOYAL_PROXY = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/proxy.txt"

REVIEW_INPUTS = {
    "Proxy": ("https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules/Proxy.list", 6000, parse_proxy),
    "ChinaMedia": (f"{CONNERS}/Streaming/CN.list", 10, parse_surge),
    "GlobalMedia": (f"{CONNERS}/Streaming/!CN.list", 100, parse_surge),
    "China": (f"{SKK}/non_ip/domestic.conf", 500, parse_surge),
    "CN-Additional / Loyalsoldier": (
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/direct.txt", 10000, parse_surge
    ),
    "ChinaCIDR": (
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/cncidr.txt", 1000, parse_surge
    ),
}


def parse_domain_set(text: str) -> set[str]:
    rules = set()
    for raw in text.splitlines():
        line = strip_comment(raw)
        if not line:
            continue
        kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
        domain = normalize_domain(line.lstrip("."), allow_tld=kind == "DOMAIN-SUFFIX")
        # Comparison feeds may contain DNS labels with underscores. Preserve
        # these as evidence without relaxing published rule validation.
        candidate = line.removeprefix(".").lower().rstrip(".")
        if not domain and "_" in candidate and len(candidate) <= 253 and re.fullmatch(
            r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?)+", candidate
        ):
            domain = candidate
        if not domain:
            raise ValueError("invalid related domain-set entry")
        rules.add(f"{kind},{domain}")
    if not rules:
        raise ValueError("empty related domain set")
    return rules


def parse_related_rules(text: str) -> set[str]:
    rules = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        _, kind, value = validate_rule_line(Path("related-source.list"), number, line)
        rules.add(f"{kind},{value}")
    if not rules:
        raise ValueError("empty related rules")
    return rules


def compare(current: set[str], other: set[str]) -> dict:
    def uncovered(left, right):
        suffixes = {r.split(",")[1] for r in right if r.startswith("DOMAIN-SUFFIX,")}
        missing = set()
        for rule in left - right:
            kind, value = rule.split(",", 1)
            if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
                labels = value.split(".")
                if any(".".join(labels[i:]) in suffixes for i in range(len(labels))):
                    continue
            missing.add(rule)
        return sorted(missing)
    return {"current_rules": len(current), "comparison_rules": len(other),
            "only_current": uncovered(current, other), "only_comparison": uncovered(other, current)}


def read(name: str) -> set[str]:
    path = ROOT / "Rule" / f"{name}.list"
    return canonical_rules(path, path.read_text(encoding="utf-8"))


def summarize_comparison(current: set[str], candidate: set[str]) -> dict:
    diff = compare(current, candidate)
    return {**diff,
            "only_current_count": len(diff["only_current"]),
            "only_comparison_count": len(diff["only_comparison"]),
            "only_current": diff["only_current"][:25],
            "only_comparison": diff["only_comparison"][:25]}


def cidr_comparison(current: set[str], candidate: set[str]) -> dict:
    def collapse(rows):
        networks = [ipaddress.ip_network(rule.split(",")[1]) for rule in rows]
        return {net for version in (4, 6)
                for net in ipaddress.collapse_addresses(n for n in networks if n.version == version)}

    current_networks = collapse(current)
    candidate_networks = collapse(candidate)
    missing = sorted(str(net) for net in candidate_networks
                     if net not in current_networks and not any(
                         net.supernet(new_prefix=prefix) in current_networks for prefix in range(net.prefixlen)))
    return {"current_rules": len(current_networks), "comparison_rules": len(candidate_networks),
            "only_comparison_count": len(missing), "only_comparison": missing[:25]}


def review_upstream(name: str, url: str, minimum: int, parse) -> dict:
    parsed = parse(fetch(url))
    if len(parsed) < minimum:
        raise ValueError(f"unexpected source size: {len(parsed)} < {minimum}")
    candidate = {f"{kind},{value}" for kind, value in parsed}
    target = name.split(" / ")[0]
    current = {",".join(rule.split(",")[:2]) for rule in read(target)}
    if name == "ChinaCIDR":
        current = {rule for rule in current if rule.startswith(("IP-CIDR,", "IP-CIDR6,"))}
        report = cidr_comparison(current, candidate)
    else:
        report = summarize_comparison(current, candidate)
    if name == "Proxy":
        pinned = parse(fetch(PROXY_SOURCES["rabbit"]))
        report["pinned_revision"] = PROXY_SOURCES["rabbit"]
        report["raw_added_since_pin"] = len(parsed - pinned)
        report["raw_removed_since_pin"] = len(pinned - parsed)
    return {"status": "review_only", "url": url, **report}


def main() -> None:
    directory = Path(os.environ["RULE_AUDIT_DIR"])
    results = {}
    for name, (url, minimum, parse) in REVIEW_INPUTS.items():
        try:
            results[name] = review_upstream(name, url, minimum, parse)
        except Exception as error:
            results[name] = {"status": "comparison_unavailable", "url": url, "error_type": type(error).__name__}
            print(f"::warning::{name} optional comparison unavailable ({type(error).__name__})")
    for name in ("NonCN", "Bybit", "N26"):
        try:
            if name == "NonCN":
                other = parse_related_rules(fetch(LOYAL_PROXY))
            else:
                parsed, _urls = v2fly.parse_entry(v2fly.TARGETS[name]["entry"])
                other = {f"{kind},{value}" for kind, value in parsed}
            results[name] = {"status": "compared_related_data", **compare(read(name), other)}
        except Exception as error:
            results[name] = {"status": "comparison_unavailable", "error_type": type(error).__name__}
            print(f"::warning::{name} optional related-source comparison unavailable ({type(error).__name__})")
    results["CN-Additional"] = {
        "status": "compared_different_scope",
        "note": "China is a multi-source comparison. Its narrower scope does not replace CN-Additional.",
        **compare(read("CN-Additional"), read("China")),
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "supplemental-comparisons.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["## Supplemental source comparisons", "",
             "Related-source and different-scope comparisons provide evidence for review. They do not modify published rules.", ""]
    for name, result in results.items():
        detail = result["status"]
        if "only_current" in result:
            detail += f"; current-only {result.get('only_current_count', len(result['only_current']))}"
        if "only_comparison" in result:
            detail += f"; comparison-only {result.get('only_comparison_count', len(result['only_comparison']))}"
        if "raw_added_since_pin" in result:
            detail += f"; moving feed vs pin +{result['raw_added_since_pin']}/-{result['raw_removed_since_pin']}"
        lines.append(f"- {name}: {detail}")
    text = "\n".join(lines) + "\n"
    (directory / "supplemental-comparisons.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)


if __name__ == "__main__":
    main()
