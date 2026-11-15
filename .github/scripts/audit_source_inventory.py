"""Describe configured sources and their limits without inferring independence."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import update_alibaba as alibaba
import update_apple as apple
import update_apple_download as download
import update_apple_intelligence as intelligence
import update_cn_additional as cn
import update_douyin as douyin
import update_icloud as icloud
import update_media_rules as media
import update_non_cn as non_cn
import update_proxy as proxy
import update_rules as rules
import update_twitter as twitter
import update_v2fly_rules as v2fly
import update_wechat as wechat
import update_xianyu as xianyu
import update_xiaohongshu as red
from validate_rule_files import normalize_domain, strip_comment, validate_rule_line
from check_rule_changes import canonical_rules

ROOT = Path(__file__).resolve().parents[2]
MANUAL = {"AppStore", "Novel", "One", "SafeW", "soulapp", "web3"}


def configured_sources() -> dict:
    catalog = {}
    for name, mapping in rules.TARGETS.items():
        primary = f"{rules.BM7_BASE}/{name}/{name}.list"
        if name in rules.MAGICRULE_TARGETS:
            text = (ROOT / "Rule" / f"{name}.list").read_text(encoding="utf-8")
            primary = re.search(r"^# SOURCE: (https://\S+)", text, re.MULTILINE).group(1)
        urls = [primary]
        for key, base in (("rabbit", rules.RABBIT_BASE), ("conners", rules.CONNERS_BASE),
                          ("loyal", rules.LOYAL_BASE), ("yuu", rules.YUU_BASE)):
            if mapping[key]:
                suffix = ".list" if key == "yuu" else ""
                urls.append(f"{base}/{mapping[key]}{suffix}")
        catalog[name] = {"mode": "merged", "urls": urls}
    for name, sources in media.CONFIGS.items():
        catalog[name] = {"mode": "merged", "urls": [row[1] for row in sources]}
    for name, sources in (("Apple", apple.SOURCES), ("AppleDownload", download.SOURCES),
                          ("iCloud", icloud.SOURCES), ("Alibaba", alibaba.SOURCES),
                          ("XianYu", xianyu.SOURCES), ("Proxy", proxy.SOURCES)):
        catalog[name] = {"mode": "merged_with_scope_checks", "urls": list(sources.values())}
    for name, urls in (("AppleIntelligence", intelligence.SOURCE_URLS),
                       ("WeChat", wechat.SOURCE_URLS), ("Twitter", twitter.SURGE_SOURCES),
                       ("douyin", [douyin.BM7_URL, douyin.YUU_URL]),
                       ("XiaoHongShu", [red.BLACKMATRIX_URL, red.YUU_URL, red.APP_RULE_URL,
                                        red.BGPEER_URL, red.DL123_URL])):
        catalog[name] = {"mode": "merged_with_retained_evidence", "urls": list(urls)}
    catalog["CN-Additional"] = {"mode": "single_source", "urls": [cn.SOURCE_URL],
                                "limitation": "No verified second source with identical scope and DOMAIN-SET semantics."}
    catalog["NonCN"] = {"mode": "single_source", "urls": [non_cn.SOURCE],
                        "limitation": "Loyalsoldier is a related-data cross-check, not independent confirmation."}
    for name, config in v2fly.TARGETS.items():
        catalog[name] = {"mode": "primary_with_related_fallback",
                         "urls": [f"{v2fly.YUU_BASE}/{config['entry']}.list"],
                         "fallback_urls": [f"{v2fly.BASE}/{config['entry']}"],
                         "limitation": "Yuu and V2Fly were content-identical at review; independence is not established."}
    for name in MANUAL:
        catalog[name] = {"mode": "manual_or_device_evidence", "urls": [],
                         "limitation": "No verified automatic multi-source updater for this specific scope."}
    workflow = (ROOT / ".github/workflows/update-rules.yml").read_text(encoding="utf-8")
    telegram = workflow.split("      - name: Sync Telegram rules\n", 1)[1].split("      - name:", 1)[0]
    urls = list(dict.fromkeys(re.findall(r'"(https://[^"\s]+)"', telegram)))
    catalog["Telegram/Telegram_All"] = {"mode": "merged", "urls": urls}
    paths = set()
    for name, entry in catalog.items():
        entry["path"] = f"Rule/{name}.list"
        paths.add(entry["path"])
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / "Rule").rglob("*.list")}
    telegram_copies = {p for p in actual if p.startswith("Rule/Telegram/") and p not in paths}
    if actual - telegram_copies != paths:
        raise RuntimeError(f"source inventory mismatch: {sorted((actual - telegram_copies) ^ paths)}")
    return dict(sorted(catalog.items()))


def source_kind(url: str) -> str:
    if re.search(r"/[0-9a-f]{40}/", url):
        return "pinned_revision"
    if "Rabbit-Spec/" in url:
        return "aggregator_or_relay; several categories relay MagicRule"
    if "magicrule.pages.dev/" in url or "rule-26r.pages.dev/" in url:
        return "aggregator; manifest providers need category review"
    if "Loyalsoldier/" in url or "v2fly/" in url:
        return "related_V2Fly_data; some lists have additional providers"
    if "Yuu518/" in url:
        return "generated_data; independence_unverified"
    return "configured_provider; independence_unverified"


def build_report(directory: Path) -> dict:
    events = [json.loads(p.read_text(encoding="utf-8")) for p in (directory / "events").glob("*.json")]
    latest = {}
    for event in sorted(events, key=lambda e: e["fetched_at"]):
        latest[event["url"]] = event
    catalog = configured_sources()
    for entry in catalog.values():
        entry["sources"] = []
        for url in entry["urls"] + entry.get("fallback_urls", []):
            event = latest.get(url, {})
            entry["sources"].append({"url": url, "kind": source_kind(url),
                                      "status": event.get("status", "not_observed_this_run"),
                                      "fetched_at": event.get("fetched_at"),
                                      "sha256": event.get("sha256"),
                                      "content_file": event.get("content_file")})
    return {"version": 1, "categories": catalog,
            "note": "Configured URLs and retrieval evidence do not establish independent corroboration or per-rule classification."}


def observed_rules(text: str) -> set[str]:
    observed = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if "," in line:
            try:
                _canonical, kind, value = validate_rule_line(Path("source.list"), number, line)
                observed.add(f"{kind},{value}")
            except RuntimeError:
                continue
        else:
            kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
            domain = normalize_domain(line.lstrip("."), allow_tld=kind == "DOMAIN-SUFFIX")
            if domain:
                observed.add(f"{kind},{domain}")
    return observed


def write_rule_evidence(directory: Path, report: dict) -> None:
    result = {}
    cache = {}
    for name, entry in report["categories"].items():
        occurrences = {}
        for source in entry["sources"]:
            content_file = source["content_file"]
            if source["status"] != "success" or not content_file:
                continue
            if content_file not in cache:
                cache[content_file] = observed_rules((directory / content_file).read_text(encoding="utf-8"))
            occurrences[source["url"]] = cache[content_file]
        path = ROOT / entry["path"]
        rules = canonical_rules(path, path.read_text(encoding="utf-8"))
        rows = {}
        for rule in sorted(rules):
            key = ",".join(rule.split(",")[:2])
            rows[rule] = [url for url, observed in occurrences.items() if key in observed]
        result[name] = rows
    payload = {"method": "Exact type/value occurrence in configured downloaded inputs, ignoring options. Empty matches may reflect compaction, scoping, metadata indirection, manual evidence or missing downloads. This is not a category verdict.",
               "categories": result}
    (directory / "rule-source-occurrences.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=os.environ.get("RULE_AUDIT_DIR"))
    args = parser.parse_args()
    if args.directory is None:
        parser.error("set RULE_AUDIT_DIR or provide --directory")
    report = build_report(args.directory)
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / "source-inventory.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_rule_evidence(args.directory, report)
    lines = ["## Rule source inventory", "", report["note"], ""]
    for name, entry in report["categories"].items():
        lines.append(f"- {name}: {entry['mode']}; {len(entry['urls'])} configured URLs.")
        if entry.get("limitation"):
            lines.append(f"  {entry['limitation']}")
        for source in entry["sources"]:
            if source["kind"] == "pinned_revision":
                lines.append(f"  Pinned input: {source['url']}")
    text = "\n".join(lines) + "\n"
    (args.directory / "source-inventory.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
            summary.write(text)
    print(text)


if __name__ == "__main__":
    main()
