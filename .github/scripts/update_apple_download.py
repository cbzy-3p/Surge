#!/usr/bin/env python3
"""Build a download subset, never importing the complete Apple CDN/service set."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import update_apple as apple
from validate_rule_files import validate_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule/AppleDownload.list"
SNAPSHOT = ROOT / ".github/apple-download-source-snapshot.json"
SOURCES = {key: value for key, value in apple.SOURCES.items() if key != "bm7_icloud"}
SOURCES["skk"] = "https://ruleset.skk.moe/List/domainset/apple_cdn.conf"
MINIMUMS = {key: value for key, value in apple.MINIMUMS.items() if key != "bm7_icloud"}

# Reviewed download namespaces. Storefront/account/payment/DRM stay in Apple.list.
# Apple official software-update and carrier-update hosts are supplemented below;
# gs/gg/xp and signing/authentication remain with the existing Apple policy.
DOWNLOAD_ROOTS = set("""
appldnld.apple.com secure-appldnld.apple.com
updates.cdn-apple.com updates-http.cdn-apple.com
oscdn.apple.com osrecovery.apple.com swcdn.apple.com swdist.apple.com
swdownload.apple.com swscan.apple.com swcatalog.apple.com
mesu.apple.com gdmf.apple.com gdmf-ados.apple.com configuration.apple.com
ig.apple.com skl.apple.com
adcdownload.apple.com download.developer.apple.com devimages-cdn.apple.com
audiocontentdownload.apple.com playground-assets-cdn.apple.com
playground-cdn.apple.com sylvan.apple.com
iosapps.itunes.apple.com osxapps.itunes.apple.com
downloaddispatch.itunes.apple.com su.itunes.apple.com
iosapps.itunes.g.aaplimg.com osxapps.itunes.g.aaplimg.com
appldnld.g.aaplimg.com swcdn.g.aaplimg.com
appldnld.apple.com.edgesuite.net
mzstatic.com
publicassets.cdn-apple.com ml.cdn-apple.com
aod.itunes.apple.com aod-ssl.itunes.apple.com
audio.itunes.apple.com audio-ssl.itunes.apple.com
mvod.itunes.apple.com streamingaudio.itunes.apple.com
hls.itunes.apple.com hls-amt.itunes.apple.com hls-svod.itunes.apple.com
""".split())
# Only aliases present in a fixed upstream are added; no broad akadns/Akamai rule.
ALIAS_RE = re.compile(
    r"^(?:appldnld(?:-lb)?|secure-appldnld|adcdownload2?|mesu(?:-cdn|-china)?|"
    r"swcdn|swdist|swdownload|swscan(?:-cdn)?|swcatalog(?:-cdn)?|"
    r"oscdn|osrecovery|configuration|updates(?:-http)?)\."
    r"(?:apple\.com|origin-apple\.com|cdn-apple\.com)\.akadns\.net$"
)


def is_download(domain: str) -> bool:
    return apple.covered_by_suffix(domain, DOWNLOAD_ROOTS) or bool(ALIAS_RE.fullmatch(domain))


def parse_source(name: str, text: str) -> set[tuple[str, str]]:
    if name != "skk":
        # Fail closed on malformed lines, rather than silently dropping coverage.
        for number, raw in enumerate(text.splitlines(), 1):
            line = apple.strip_comment(raw)
            if line:
                from validate_rule_files import validate_rule_line
                validate_rule_line(Path(name), number, line)
        return apple.parse_surge(text)
    rules = set()
    for raw in text.splitlines():
        line = apple.strip_comment(raw)
        if not line or line == apple.SKK_WATERMARK:
            continue
        kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
        domain = apple.normalize_domain(line.lstrip("."))
        if domain is None:
            raise RuntimeError(f"invalid SKK domain: {line}")
        rules.add((kind, domain))
    return rules


def build(texts: dict[str, str]) -> tuple[set[tuple[str, str]], dict[str, int]]:
    rules = {("DOMAIN-SUFFIX", domain) for domain in DOWNLOAD_ROOTS}
    counts = {}
    for name in SOURCES:
        parsed = parse_source(name, texts[name])
        if len(parsed) < MINIMUMS[name]:
            raise RuntimeError(f"{name} source unexpectedly small: {len(parsed)}")
        selected = {(kind, value) for kind, value in parsed
                    if kind in {"DOMAIN", "DOMAIN-SUFFIX"} and is_download(value)}
        counts[name] = len(parsed)
        counts[name + "/selected"] = len(selected)
        rules.update(selected)
    rules = apple.compact(rules)
    counts["output"] = len(rules)
    return rules, counts


def render(rules: set[tuple[str, str]], updated: str) -> str:
    return "\n".join([
        "# NAME: Multi-source-AppleDownload",
        "# AUTHOR: cbzy-3p",
        "# FORMAT: Surge Rule Set",
        f"# UPDATED: {updated}",
        f"# RULE COUNT: {len(rules)}",
        *[f"# SOURCE: {url}" for url in SOURCES.values()],
        "# NOTE: Reviewed download subset; see AppleDownload-Sources.md for scope and shared media hosts.",
        "", *[f"{kind},{domain}" for kind, domain in sorted(rules)], "",
    ])


def main() -> None:
    previous = TARGET.read_text() if TARGET.exists() else ""
    if previous:
        validate_text(TARGET, previous)
    with ThreadPoolExecutor(max_workers=6) as pool:
        texts = dict(zip(SOURCES, pool.map(apple.fetch, SOURCES.values())))
    rules, counts = build(texts)
    old_counts = json.loads(SNAPSHOT.read_text())["counts"] if SNAPSHOT.exists() else {}
    apple.validate_snapshot(old_counts, counts)
    # Also guard the committed output if its snapshot was lost.
    if previous:
        apple.validate_snapshot({"output": validate_text(TARGET, previous)["rules"]}, counts)
    stamp = re.search(r"^# UPDATED: (.+)$", previous, re.M)
    updated = stamp.group(1) if stamp else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = render(rules, updated)
    if content != previous:
        content = render(rules, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    validate_text(TARGET, content)
    TARGET.write_text(content, encoding="utf-8")
    SNAPSHOT.write_text(json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n")
    print(f"updated {TARGET.name} with {len(rules)} rules")


if __name__ == "__main__":
    main()
