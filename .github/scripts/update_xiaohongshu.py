#!/usr/bin/env python3
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


OUTPUT = Path("XiaoHongShu.list")
V2FLY_BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/"
BLACKMATRIX_URL = (
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/"
    "rule/Surge/XiaoHongShu/XiaoHongShu.list"
)
APP_RULE_URL = (
    "https://raw.githubusercontent.com/wresource/hxmy-proxy/master/"
    "app/src/main/assets/rules/app-xiaohongshu.txt"
)
SOURCE_LABELS = (
    "v2fly/domain-list-community data/xiaohongshu (recursive includes)",
    "blackmatrix7/ios_rule_script XiaoHongShu.list",
    "wresource/hxmy-proxy app-xiaohongshu.txt",
    "Xiaohongshu first-party domains verified from ICP records",
)
PINNED_DOMAINS = {
    "cdnxhs.com",
    "cn-rednotecdn.com",
    "rednote.life",
    "rl.ink",
    "rnote.com",
    "rnotecdn.com",
    "xhsredcdn.com",
    "xiaohongshu.com",
    "xhscdn.com",
    "xhscdn.net",
    "xhslink.com",
    "xhsrcdn.com",
    "xingin.cn",
    "xingin.net",
}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def fetch_text(url: str, attempts: int = 3) -> str:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Rongwuyou-Surge-Rule-Updater/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                content = response.read().decode("utf-8")
            if not content.strip():
                raise RuntimeError(f"Empty response: {url}")
            return content
        except Exception as exc:  # urllib reports several transport error types
            error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Failed to fetch {url}: {error}")


def normalize_domain(value: str) -> str | None:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    if not DOMAIN_RE.fullmatch(domain):
        return None
    return domain


def parse_v2fly(entry: str, visited: set[str] | None = None) -> set[str]:
    visited = visited or set()
    if entry in visited:
        return set()
    visited.add(entry)

    domains: set[str] = set()
    content = fetch_text(f"{V2FLY_BASE}{entry}")
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        token = line.split()[0]
        if token.startswith("include:"):
            included = token.removeprefix("include:")
            if included:
                domains.update(parse_v2fly(included, visited))
            continue
        if token.startswith(("regexp:", "keyword:")):
            continue
        if token.startswith(("domain:", "full:")):
            token = token.split(":", 1)[1]
        domain = normalize_domain(token)
        if domain:
            domains.add(domain)
    return domains


def parse_surge_rules(content: str) -> set[str]:
    domains: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line.startswith(("#", ";")):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or parts[0] not in {"DOMAIN", "DOMAIN-SUFFIX"}:
            continue
        domain = normalize_domain(parts[1])
        if domain:
            domains.add(domain)
    return domains


def parse_plain_domains(content: str) -> set[str]:
    domains: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        domain = normalize_domain(line.split()[0])
        if domain:
            domains.add(domain)
    return domains


def current_domains() -> set[str]:
    if not OUTPUT.exists():
        return set()
    return parse_surge_rules(OUTPUT.read_text(encoding="utf-8"))


def render(domains: set[str]) -> str:
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        "# NAME: XiaoHongShu",
        "# AUTHOR: Rongwuyou",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        *[f"# SOURCE: {source}" for source in SOURCE_LABELS],
        "# NOTE: Domain-only merge to avoid shared-IP collateral damage.",
        f"# DOMAIN-SUFFIX: {len(domains)}",
        f"# TOTAL: {len(domains)}",
        "",
    ]
    rules = [f"DOMAIN-SUFFIX,{domain}" for domain in sorted(domains)]
    return "\n".join(header + rules) + "\n"


def main() -> None:
    domains = set(PINNED_DOMAINS)
    domains.update(parse_v2fly("xiaohongshu"))
    domains.update(parse_surge_rules(fetch_text(BLACKMATRIX_URL)))
    domains.update(parse_plain_domains(fetch_text(APP_RULE_URL)))

    missing = PINNED_DOMAINS - domains
    if missing:
        raise RuntimeError(f"Missing required domains: {sorted(missing)}")
    if not 10 <= len(domains) <= 200:
        raise RuntimeError(f"Unexpected domain count: {len(domains)}")

    if domains == current_domains():
        print(f"No changes. {len(domains)} domains remain valid.")
        return

    OUTPUT.write_text(render(domains), encoding="utf-8")
    print(f"Updated {OUTPUT} with {len(domains)} domains.")


if __name__ == "__main__":
    main()
