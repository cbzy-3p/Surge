#!/usr/bin/env python3
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Rules" / "BM7"
BM7_BASE = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge"
V2FLY_BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data"

# BM7 is authoritative. Other sources are merged only when the category mapping is direct.
TARGETS = {
    "GitHub": {"v2fly": "github", "rabbit": None, "loyal": None, "meta": None},
    "Kingsoft": {"v2fly": "kingsoft", "rabbit": None, "loyal": None, "meta": None},
    "AppleMusic": {"v2fly": "apple-music", "rabbit": None, "loyal": None, "meta": "apple-music"},
    "AppleTV": {"v2fly": None, "rabbit": None, "loyal": None, "meta": "apple-tvplus"},
    "OpenAI": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "GoogleVoice": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "Google": {"v2fly": "google", "rabbit": "Google.list", "loyal": "google.txt", "meta": None},
    "TikTok": {"v2fly": None, "rabbit": "TikTok.list", "loyal": None, "meta": None},
    "Instagram": {"v2fly": "instagram", "rabbit": "Instagram.list", "loyal": None, "meta": None},
    "Facebook": {"v2fly": "facebook", "rabbit": "Facebook.list", "loyal": None, "meta": None},
    "PayPal": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "OKX": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "Binance": {"v2fly": "binance", "rabbit": None, "loyal": None, "meta": "binance"},
    "Crypto": {"v2fly": None, "rabbit": None, "loyal": None, "meta": None},
    "Cryptocurrency": {"v2fly": None, "rabbit": None, "loyal": None, "meta": "category-cryptocurrency"},
}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RABBIT_BASE = "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules"
LOYAL_BASE = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset"
META_BASE = "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite"


def fetch(url: str, attempts: int = 3) -> str:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Rongwuyou-Surge-BM7-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {url}")
                text = r.read().decode("utf-8")
            if not text.strip():
                raise RuntimeError(f"empty response: {url}")
            return text
        except Exception as e:
            last = e
            if i + 1 < attempts:
                time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def norm_domain(value: str) -> str | None:
    d = value.strip().lower().rstrip(".")
    if d.startswith("*."):
        d = d[2:]
    return d if DOMAIN_RE.fullmatch(d) else None


def parse_bm7(text: str) -> tuple[list[str], set[str]]:
    lines: list[str] = []
    domains: set[str] = set()
    seen: set[str] = set()
    for raw in text.replace("\r", "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            lines.append(line)
            seen.add(line)
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0] in DOMAIN_TYPES:
            d = norm_domain(parts[1])
            if d:
                domains.add(d)
    return lines, domains


def parse_source_domains(content: str, plain: bool = False) -> set[str]:
    domains: set[str] = set()
    for raw in content.replace("\r", "").splitlines():
        line = raw.split("#", 1)[0].split("//", 1)[0].strip()
        if not line or line.startswith((";", "!")):
            continue
        if plain:
            token = line.split()[0]
            if token.startswith(("+.", "*.")):
                token = token[2:]
            if token.startswith(("geosite:", "regexp:", "keyword:")):
                continue
            d = norm_domain(token)
            if d:
                domains.add(d)
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0] in DOMAIN_TYPES:
            d = norm_domain(parts[1])
            if d:
                domains.add(d)
    return domains


def parse_v2fly(entry: str, visited: set[str] | None = None) -> set[str]:
    visited = visited or set()
    if entry in visited:
        return set()
    visited.add(entry)
    domains: set[str] = set()
    for raw in fetch(f"{V2FLY_BASE}/{entry}").replace("\r", "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        token = line.split()[0]
        if token.startswith("include:"):
            domains.update(parse_v2fly(token[8:], visited))
            continue
        if ":" in token and token.split(":", 1)[0] in {"domain", "full"}:
            token = token.split(":", 1)[1]
        d = norm_domain(token)
        if d:
            domains.add(d)
    return domains


def render(name: str, lines: list[str], additions: set[str], sources: list[str]) -> str:
    all_lines = list(lines)
    existing = {
        p[1].lower().rstrip(".")
        for line in lines
        for p in [[x.strip() for x in line.split(",")]]
        if len(p) >= 2 and p[0] in DOMAIN_TYPES
    }
    for d in sorted(additions - existing):
        all_lines.append(f"DOMAIN-SUFFIX,{d}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: BM7-{name}",
        "# AUTHOR: Rongwuyou",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# SOURCE: {BM7_BASE}/{name}/{name}.list",
        *[f"# MERGED SOURCE: {source}" for source in sources],
        "# NOTE: BM7 is authoritative; mapped sources add domain-only rules after exact deduplication.",
        "",
    ]
    return "\n".join(header + all_lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, mapping in TARGETS.items():
        bm7_url = f"{BM7_BASE}/{name}/{name}.list"
        bm7 = fetch(bm7_url)
        lines, _ = parse_bm7(bm7)
        additions: set[str] = set()
        sources: list[str] = []

        if mapping["v2fly"]:
            entry = mapping["v2fly"]
            additions.update(parse_v2fly(entry))
            sources.append(f"{V2FLY_BASE}/{entry}")
        if mapping["rabbit"]:
            entry = mapping["rabbit"]
            additions.update(parse_source_domains(fetch(f"{RABBIT_BASE}/{entry}")))
            sources.append(f"{RABBIT_BASE}/{entry}")
        if mapping["loyal"]:
            entry = mapping["loyal"]
            additions.update(parse_source_domains(fetch(f"{LOYAL_BASE}/{entry}")))
            sources.append(f"{LOYAL_BASE}/{entry}")
        if mapping["meta"]:
            entry = mapping["meta"]
            additions.update(parse_source_domains(fetch(f"{META_BASE}/{entry}.list"), plain=True))
            sources.append(f"{META_BASE}/{entry}.list")

        if not lines:
            raise RuntimeError(f"empty BM7 rules: {name}")
        output = render(name, lines, additions, sources)
        target = OUT / f"{name}.list"
        if target.exists() and target.read_text(encoding="utf-8") == output:
            print(f"{name}: unchanged")
        else:
            target.write_text(output, encoding="utf-8")
            print(f"{name}: BM7={len(lines)} additions={len(additions)} output={len(output.splitlines())}")


if __name__ == "__main__":
    main()
