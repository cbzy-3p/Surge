#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE_DIR = ROOT / "Rule"
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_SUFFIXES = {".list", ".txt"}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def strip_comment(raw: str) -> str:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "//", ";")):
        return ""
    for marker in (" //", " #"):
        if marker in line:
            line = line.split(marker, 1)[0].strip()
    return line


def normalize_domain(value: str) -> str | None:
    domain = value.strip().lower().rstrip(".")
    while domain.startswith(("+.", "*.")):
        domain = domain[2:]
    if domain.startswith("."):
        domain = domain[1:]
    return domain if DOMAIN_RE.fullmatch(domain) else None


def normalize_rule(path: Path, raw: str) -> tuple[str, str, tuple[str, ...]] | None:
    line = strip_comment(raw)
    if not line:
        return None

    if path.name == "CN-Additional.list" and "," not in line:
        domain = normalize_domain(line)
        if not domain:
            return None
        return ("DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN", domain, ())

    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        return None
    rule_type = parts[0].upper()
    value = parts[1]
    options = tuple(part.lower() for part in parts[2:] if part)

    if rule_type in DOMAIN_TYPES:
        domain = normalize_domain(value)
        return (rule_type, domain, options) if domain else None
    if rule_type == "IP-CIDR":
        try:
            value = str(ipaddress.IPv4Network(value, strict=False))
        except ValueError:
            return None
    elif rule_type == "IP-CIDR6":
        try:
            value = str(ipaddress.IPv6Network(value, strict=False))
        except ValueError:
            return None
    elif rule_type == "IP-ASN":
        if not value.isdecimal():
            return None
        value = str(int(value))
    else:
        value = value.lower()
    return rule_type, value, options


def canonical(rule: tuple[str, str, tuple[str, ...]]) -> str:
    rule_type, value, options = rule
    return ",".join((rule_type, value, *options))


def covering_suffixes(domain: str) -> list[str]:
    labels = domain.split(".")
    return [".".join(labels[index:]) for index in range(len(labels))]


def audit(paths: list[Path]) -> dict[str, object]:
    rule_files: dict[Path, set[tuple[str, str, tuple[str, ...]]]] = {}
    exact_index: dict[str, set[Path]] = defaultdict(set)
    suffix_index: dict[tuple[str, tuple[str, ...]], set[Path]] = defaultdict(set)

    for path in paths:
        rules = {
            rule
            for raw in path.read_text(encoding="utf-8").replace("\r", "").splitlines()
            if (rule := normalize_rule(path, raw)) is not None
        }
        rule_files[path] = rules
        for rule in rules:
            exact_index[canonical(rule)].add(path)
            if rule[0] == "DOMAIN-SUFFIX":
                suffix_index[(rule[1], rule[2])].add(path)

    exact_pair_counts: Counter[tuple[str, str]] = Counter()
    exact_samples: dict[tuple[str, str], list[str]] = defaultdict(list)
    exact_shared_rules = 0
    for rule_text, files in exact_index.items():
        if len(files) < 2:
            continue
        exact_shared_rules += 1
        for left, right in combinations(sorted(path.name for path in files), 2):
            pair = (left, right)
            exact_pair_counts[pair] += 1
            if len(exact_samples[pair]) < 3:
                exact_samples[pair].append(rule_text)

    covered_pair_counts: Counter[tuple[str, str]] = Counter()
    covered_samples: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen_covered: set[tuple[str, str, str]] = set()
    for path, rules in rule_files.items():
        for rule_type, value, options in rules:
            if rule_type not in DOMAIN_TYPES:
                continue
            candidates = covering_suffixes(value)
            if rule_type == "DOMAIN-SUFFIX":
                candidates = candidates[1:]
            for suffix in candidates:
                covering_files = suffix_index.get((suffix, options), set())
                for covering_file in covering_files:
                    if covering_file == path:
                        continue
                    key = (path.name, canonical((rule_type, value, options)), covering_file.name)
                    if key in seen_covered:
                        continue
                    seen_covered.add(key)
                    pair = tuple(sorted((path.name, covering_file.name)))
                    covered_pair_counts[pair] += 1
                    if len(covered_samples[pair]) < 3:
                        covered_samples[pair].append(
                            f"{rule_type},{value} covered by DOMAIN-SUFFIX,{suffix}"
                        )
                if covering_files:
                    break

    return {
        "files": len(rule_files),
        "exact_shared_rules": exact_shared_rules,
        "exact_pair_counts": exact_pair_counts,
        "exact_samples": exact_samples,
        "covered_relations": len(seen_covered),
        "covered_pair_counts": covered_pair_counts,
        "covered_samples": covered_samples,
    }


def print_pairs(
    title: str,
    counts: Counter[tuple[str, str]],
    samples: dict[tuple[str, str], list[str]],
) -> None:
    print(title)
    if not counts:
        print("  none")
        return
    for pair, count in counts.most_common(15):
        sample = "; ".join(samples.get(pair, []))
        suffix = f" | sample: {sample}" if sample else ""
        print(f"  {pair[0]} <-> {pair[1]}: {count}{suffix}")


def main() -> None:
    paths = sorted(
        path
        for path in RULE_DIR.iterdir()
        if path.is_file() and path.suffix in RULE_SUFFIXES
    )
    if not paths:
        raise SystemExit("no top-level rule files found")
    result = audit(paths)
    print(
        "Cross-file audit (informational only): "
        f"{result['files']} top-level files, "
        f"{result['exact_shared_rules']} exact rules shared, "
        f"{result['covered_relations']} cross-file domain coverage relations"
    )
    print_pairs(
        "Top exact-overlap file pairs:",
        result["exact_pair_counts"],
        result["exact_samples"],
    )
    print_pairs(
        "Top semantic-domain-overlap file pairs:",
        result["covered_pair_counts"],
        result["covered_samples"],
    )


if __name__ == "__main__":
    main()
