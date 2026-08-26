#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULE_DIR = ROOT / "Rule"
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
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


def normalize_domain(value: str) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    return domain if DOMAIN_RE.fullmatch(domain) else None


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
        normalized_value = normalize_domain(value) or ""
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


def validate_text(path: Path, text: str) -> dict[str, int]:
    exact_lines: set[str] = set()
    domains: set[str] = set()
    suffixes: set[str] = set()
    rule_count = 0
    for number, raw in enumerate(text.replace("\r", "").splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if path.name == "CN-Additional.list" and "," not in line:
            domain = normalize_domain(line.lstrip("."))
            if not domain:
                raise RuntimeError(f"{path}:{number}: invalid DOMAIN-SET entry: {line}")
            canonical = f"DOMAIN-SET,{domain}"
            if canonical in exact_lines:
                raise RuntimeError(f"{path}:{number}: duplicate rule: {line}")
            exact_lines.add(canonical)
            rule_count += 1
            continue

        canonical, rule_type, value = validate_rule_line(path, number, line)
        if canonical in exact_lines:
            raise RuntimeError(f"{path}:{number}: duplicate rule: {line}")
        exact_lines.add(canonical)
        rule_count += 1
        if rule_type == "DOMAIN":
            domains.add(value)
        elif rule_type == "DOMAIN-SUFFIX":
            suffixes.add(value)

    conflicts = domains & suffixes
    if conflicts:
        sample = ", ".join(sorted(conflicts)[:5])
        raise RuntimeError(f"{path}: DOMAIN and DOMAIN-SUFFIX overlap: {sample}")
    if rule_count == 0:
        raise RuntimeError(f"{path}: no rules found")
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
