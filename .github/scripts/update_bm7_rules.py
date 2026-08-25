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

# BM7 is authoritative. v2fly is only merged where the category mapping is direct.
TARGETS = {
    "GitHub": "github",
    "Kingsoft": "kingsoft",
    "AppleMusic": "apple-music",
    "AppleTV": None,
    "OpenAI": None,
    "GoogleVoice": None,
    "Google": "google",
    "TikTok": None,
    "Instagram": "instagram",
    "Facebook": "facebook",
    "PayPal": None,
    "OKX": None,
    "Binance": "binance",
    "Crypto": None,
    "Cryptocurrency": None,
}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


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


def render(name: str, lines: list[str], additions: set[str], source_category: str | None) -> str:
    all_lines = list(lines)
    existing = {p[1].lower().rstrip(".") for line in lines for p in [[x.strip() for x in line.split(",")]] if len(p) >= 2 and p[0] in DOMAIN_TYPES}
    for d in sorted(additions - existing):
        all_lines.append(f"DOMAIN-SUFFIX,{d}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# NAME: BM7-{name}",
        "# AUTHOR: Rongwuyou",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {now}",
        f"# SOURCE: {BM7_BASE}/{name}/{name}.list",
    ]
    if source_category:
        header.append(f"# MERGED SOURCE: {V2FLY_BASE}/{source_category}")
    header += ["# NOTE: BM7 rules are retained; only directly corresponding domain suffixes are merged and deduplicated.", ""]
    return "\n".join(header + all_lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, category in TARGETS.items():
        bm7 = fetch(f"{BM7_BASE}/{name}/{name}.list")
        lines, _ = parse_bm7(bm7)
        additions = parse_v2fly(category) if category else set()
        if not lines:
            raise RuntimeError(f"empty BM7 rules: {name}")
        (OUT / f"{name}.list").write_text(render(name, lines, additions, category), encoding="utf-8")
        print(f"{name}: BM7={len(lines)} merged={len(additions)}")


if __name__ == "__main__":
    main()
