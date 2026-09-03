#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULE_DIR = ROOT / "Rule"
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
Network = ipaddress.IPv4Network | ipaddress.IPv6Network
RULE_TYPES = DOMAIN_TYPES | {
    "DOMAIN-KEYWORD", "DOMAIN-WILDCARD", "DOMAIN-SET",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP",
    "USER-AGENT", "URL-REGEX", "PROCESS-NAME", "DEST-PORT",
    "SRC-PORT", "IN-PORT", "SRC-IP", "DEVICE-NAME", "MAC-ADDRESS",
    "PROTOCOL", "HOSTNAME-TYPE", "SUBNET", "CELLULAR-RADIO",
    "CELLULAR-CARRIER", "SCRIPT", "RULE-SET", "AND", "OR", "NOT",
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
LOGICAL_DOMAIN_RE = re.compile(
    r"\((DOMAIN-SUFFIX|DOMAIN),\s*([^(),]+)\)", re.IGNORECASE
)


def normalize_domain(value: str, allow_tld: bool = False) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    if DOMAIN_RE.fullmatch(domain):
        return domain
    return domain if allow_tld and DOMAIN_LABEL_RE.fullmatch(domain) else None


def strip_comment(raw: str) -> str:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "//", ";")):
        return ""
    if " //" in line:
        line = line.split(" //", 1)[0].rstrip()
    if " #" in line:
        line = line.split(" #", 1)[0].rstrip()
    return line


def validate_rule_line(path: Path, number: int, line: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        raise RuntimeError(f"{path}:{number}: missing comma or rule value: {line}")
    rule_type = parts[0].upper()
    value = parts[1].strip()
    if rule_type not in RULE_TYPES or not value:
        raise RuntimeError(f"{path}:{number}: unsupported or empty rule: {line}")
    if any(part.strip().lower() == "pre-matching" for part in parts[2:]):
        raise RuntimeError(f"{path}:{number}: pre-matching is not allowed: {line}")

    normalized_value = value
    if rule_type in DOMAIN_TYPES:
        normalized_value = normalize_domain(
            value, allow_tld=rule_type == "DOMAIN-SUFFIX"
        ) or ""
        if not normalized_value:
            raise RuntimeError(f"{path}:{number}: invalid domain: {line}")
    elif rule_type == "DOMAIN-KEYWORD":
        normalized_value = value.lower()
        if any(char.isspace() for char in normalized_value):
            raise RuntimeError(f"{path}:{number}: invalid keyword: {line}")
    elif rule_type == "IP-CIDR":
        try:
            normalized_value = str(ipaddress.IPv4Network(value, strict=False))
        except ValueError as error:
            raise RuntimeError(f"{path}:{number}: invalid IPv4 CIDR: {line}") from error
    elif rule_type == "IP-CIDR6":
        try:
            normalized_value = str(ipaddress.IPv6Network(value, strict=False))
        except ValueError as error:
            raise RuntimeError(f"{path}:{number}: invalid IPv6 CIDR: {line}") from error
    elif rule_type == "IP-ASN":
        if not value.isdecimal() or not 1 <= int(value) <= 4_294_967_295:
            raise RuntimeError(f"{path}:{number}: invalid ASN: {line}")
        normalized_value = str(int(value))

    normalized = ",".join([rule_type, normalized_value] + [part.strip().lower() for part in parts[2:]])
    return normalized, rule_type, normalized_value


def covering_suffix(domain: str, suffixes: set[str], include_self: bool = True) -> str | None:
    labels = domain.split(".")
    start = 0 if include_self else 1
    for index in range(start, len(labels)):
        candidate = ".".join(labels[index:])
        if candidate in suffixes:
            return candidate
    return None


def validate_logical_or(path: Path, number: int, line: str) -> None:
    if not line.upper().startswith("OR,"):
        return
    rules = [
        (rule_type.upper(), normalize_domain(value) or "")
        for rule_type, value in LOGICAL_DOMAIN_RE.findall(line)
    ]
    rules = [(rule_type, value) for rule_type, value in rules if value]
    suffixes = {value for rule_type, value in rules if rule_type == "DOMAIN-SUFFIX"}
    for rule_type, value in rules:
        parent = covering_suffix(value, suffixes, include_self=rule_type == "DOMAIN")
        if parent and not (rule_type == "DOMAIN-SUFFIX" and parent == value):
            raise RuntimeError(
                f"{path}:{number}: logical OR contains covered domain: "
                f"{rule_type},{value} covered by DOMAIN-SUFFIX,{parent}"
            )


def validate_text(path: Path, text: str) -> dict[str, int]:
    exact_lines: set[str] = set()
    domain_rules: list[tuple[str, str, tuple[str, ...]]] = []
    cidr_rules: list[tuple[Network, tuple[str, ...]]] = []
    rule_count = 0
    for number, raw in enumerate(text.replace("\r", "").splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if path.name == "CN-Additional.list" and "," not in line:
            domain = normalize_domain(line.lstrip("."))
            if not domain:
                raise RuntimeError(f"{path}:{number}: invalid DOMAIN-SET entry: {line}")
            rule_type = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
            canonical = f"{rule_type},{domain}"
            if canonical in exact_lines:
                raise RuntimeError(f"{path}:{number}: duplicate rule: {line}")
            exact_lines.add(canonical)
            domain_rules.append((rule_type, domain, ()))
            rule_count += 1
            continue

        validate_logical_or(path, number, line)
        canonical, rule_type, value = validate_rule_line(path, number, line)
        if canonical in exact_lines:
            raise RuntimeError(f"{path}:{number}: duplicate rule: {line}")
        exact_lines.add(canonical)
        rule_count += 1
        options = tuple(canonical.split(",")[2:])
        if rule_type in DOMAIN_TYPES:
            domain_rules.append((rule_type, value, options))
        elif rule_type in {"IP-CIDR", "IP-CIDR6"}:
            cidr_rules.append((ipaddress.ip_network(value), options))

    suffixes_by_options: dict[tuple[str, ...], set[str]] = {}
    for rule_type, value, options in domain_rules:
        if rule_type == "DOMAIN-SUFFIX":
            suffixes_by_options.setdefault(options, set()).add(value)
    for rule_type, value, options in domain_rules:
        suffixes = suffixes_by_options.get(options, set())
        parent = covering_suffix(value, suffixes, include_self=rule_type == "DOMAIN")
        if parent and not (rule_type == "DOMAIN-SUFFIX" and parent == value):
            raise RuntimeError(
                f"{path}: covered domain rule: {rule_type},{value} "
                f"covered by DOMAIN-SUFFIX,{parent}"
            )

    networks_by_options: dict[tuple[str, ...], set[Network]] = {}
    for network, options in cidr_rules:
        networks_by_options.setdefault(options, set()).add(network)
    for network, options in cidr_rules:
        networks = networks_by_options[options]
        for prefix in range(network.prefixlen - 1, -1, -1):
            parent = network.supernet(new_prefix=prefix)
            if parent in networks:
                raise RuntimeError(
                    f"{path}: covered CIDR rule: {network} covered by {parent}"
                )
    if rule_count == 0:
        raise RuntimeError(f"{path}: no rules found")
    declared = re.search(r"^#\s*(?:RULE COUNT|RuleCount):\s*(\d+)\s*$", text, re.MULTILINE)
    if declared and int(declared.group(1)) != rule_count:
        raise RuntimeError(
            f"{path}: declared rule count {declared.group(1)} does not match {rule_count}"
        )
    return {"rules": rule_count}


def main() -> None:
    files = sorted(path for path in RULE_DIR.rglob("*") if path.suffix in {".list", ".txt"})
    if not files:
        raise SystemExit("Rule directory contains no rule files")
    total = 0
    for path in files:
        stats = validate_text(path, path.read_text(encoding="utf-8"))
        total += stats["rules"]
        print(f"validated {path.relative_to(ROOT)}: {stats['rules']} rules")
    print(f"validated {len(files)} files and {total} rules")


if __name__ == "__main__":
    main()
