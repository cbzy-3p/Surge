#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import sys
from pathlib import Path


DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
CIDR_TYPES = {"IP-CIDR", "IP-CIDR6"}
Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def compact_text(text: str, domain_set: bool = False) -> tuple[str, int]:
    lines = text.replace("\r", "").splitlines()
    parsed: dict[int, tuple[str, str, tuple[str, ...]]] = {}
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith(("#", "//", ";")):
            continue
        if domain_set and "," not in line:
            rule_type = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
            parsed[index] = rule_type, line.lstrip(".").lower().rstrip("."), ()
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or parts[0].upper() not in DOMAIN_TYPES | CIDR_TYPES:
            continue
        rule_type = parts[0].upper()
        value = parts[1].lower().rstrip(".")
        if rule_type in CIDR_TYPES:
            try:
                value = str(ipaddress.ip_network(value, strict=False))
            except ValueError:
                continue
        parsed[index] = rule_type, value, tuple(part.lower() for part in parts[2:])

    remove: set[int] = set()
    suffixes: dict[tuple[str, ...], set[str]] = {}
    for rule_type, value, options in parsed.values():
        if rule_type == "DOMAIN-SUFFIX":
            suffixes.setdefault(options, set()).add(value)
    for index, (rule_type, value, options) in parsed.items():
        if rule_type not in DOMAIN_TYPES:
            continue
        labels = value.split(".")
        start = 0 if rule_type == "DOMAIN" else 1
        for label_index in range(start, len(labels)):
            suffix = ".".join(labels[label_index:])
            if suffix in suffixes.get(options, set()):
                remove.add(index)
                break

    networks: dict[tuple[str, tuple[str, ...]], set[Network]] = {}
    for rule_type, value, options in parsed.values():
        if rule_type in CIDR_TYPES:
            networks.setdefault((rule_type, options), set()).add(ipaddress.ip_network(value))
    for index, (rule_type, value, options) in parsed.items():
        if rule_type not in CIDR_TYPES:
            continue
        network = ipaddress.ip_network(value)
        available = networks[(rule_type, options)]
        for prefix in range(network.prefixlen - 1, -1, -1):
            if network.supernet(new_prefix=prefix) in available:
                remove.add(index)
                break

    output = "\n".join(line for index, line in enumerate(lines) if index not in remove) + "\n"
    return output, len(remove)


def main(paths: list[str]) -> int:
    if not paths:
        raise SystemExit("usage: compact_rule_file.py <rule-file> [...]")
    for raw_path in paths:
        path = Path(raw_path)
        text = path.read_text(encoding="utf-8")
        output, removed = compact_text(text, domain_set=path.name == "CN-Additional.list")
        if output != text:
            path.write_text(output, encoding="utf-8", newline="\n")
        print(f"compacted {path}: removed {removed} covered rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
