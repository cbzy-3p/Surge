#!/usr/bin/env python3
"""Build selected Surge rule sets from canonical V2Fly geosite data."""

from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Rule"
BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data"
TARGETS = {
    "Bybit": {"entry": "bybit", "minimum": 8, "required": "bybit.com"},
    "N26": {"entry": "n26", "minimum": 3, "required": "n26.com"},
}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
Rule = tuple[str, str]


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "cbzy-3p-surge-rule-updater"})
    error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8-sig")
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url}: {error}")


def normalize_domain(value: str) -> str:
    value = value.strip().rstrip(".").lower()
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"invalid internationalized domain: {value}") from exc
    if not DOMAIN_RE.fullmatch(value):
        raise ValueError(f"invalid domain: {value}")
    return value


def parse_entry(entry: str, loader=fetch, seen: set[str] | None = None) -> tuple[set[Rule], set[str]]:
    seen = set() if seen is None else seen
    if entry in seen:
        return set(), set()
    seen.add(entry)
    url = f"{BASE}/{entry}"
    rules: set[Rule] = set()
    sources = {url}
    for raw in loader(url).replace("\r", "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        token = line.split()[0]
        if token.startswith("include:"):
            child = token.removeprefix("include:")
            child_rules, child_sources = parse_entry(child, loader, seen)
            rules.update(child_rules)
            sources.update(child_sources)
            continue
        if token.startswith("regexp:"):
            raise ValueError(f"unsupported V2Fly regexp rule in {entry}: {token}")
        if token.startswith("full:"):
            rules.add(("DOMAIN", normalize_domain(token.removeprefix("full:"))))
        elif token.startswith("domain:"):
            rules.add(("DOMAIN-SUFFIX", normalize_domain(token.removeprefix("domain:"))))
        elif token.startswith("keyword:"):
            value = token.removeprefix("keyword:").lower()
            if not value:
                raise ValueError(f"empty keyword in {entry}")
            rules.add(("DOMAIN-KEYWORD", value))
        else:
            rules.add(("DOMAIN-SUFFIX", normalize_domain(token)))
    return compact(rules), sources


def compact(rules: set[Rule]) -> set[Rule]:
    suffixes: set[str] = set()
    for domain in sorted((v for k, v in rules if k == "DOMAIN-SUFFIX"), key=lambda v: (v.count("."), v)):
        labels = domain.split(".")
        if not any(".".join(labels[i:]) in suffixes for i in range(len(labels))):
            suffixes.add(domain)
    exact = {
        value for kind, value in rules
        if kind == "DOMAIN" and not any(value == suffix or value.endswith(f".{suffix}") for suffix in suffixes)
    }
    keywords = {value for kind, value in rules if kind == "DOMAIN-KEYWORD"}
    return {*(('DOMAIN', value) for value in exact), *(('DOMAIN-SUFFIX', value) for value in suffixes), *(('DOMAIN-KEYWORD', value) for value in keywords)}


def render(name: str, rules: set[Rule], sources: set[str]) -> str:
    order = {"DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2}
    lines = [f"{kind},{value}" for kind, value in sorted(rules, key=lambda r: (order[r[0]], r[1]))]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: V2Fly-{name}",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# RULE COUNT: {len(lines)}",
        *[f"# SOURCE: {source}" for source in sorted(sources)],
        "# NOTE: Generated from canonical V2Fly geosite data; unsupported regexp rules fail closed.",
        "",
    ]
    return "\n".join(header + lines) + "\n"


def stable(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("# UPDATED:"))


def count_rules(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() and not line.startswith("#"))


def main() -> None:
    for name, config in TARGETS.items():
        rules, sources = parse_entry(config["entry"])
        values = {value for _, value in rules}
        if len(rules) < config["minimum"] or config["required"] not in values:
            raise RuntimeError(f"unexpectedly small or incomplete {name} source: {len(rules)} rules")
        output = render(name, rules, sources)
        target = OUT / f"{name}.list"
        if target.exists():
            previous = count_rules(target.read_text(encoding="utf-8"))
            current = len(rules)
            if previous and (current * 2 < previous or current > previous * 3):
                raise RuntimeError(f"suspicious {name} rule count change: {previous} -> {current}")
            if stable(target.read_text(encoding="utf-8")) == stable(output):
                print(f"{name}: unchanged ({current} rules)")
                continue
        target.write_text(output, encoding="utf-8", newline="\n")
        print(f"{name}: updated ({len(rules)} rules)")


if __name__ == "__main__":
    main()
