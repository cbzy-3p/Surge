#!/usr/bin/env python3
"""Complete classified Alibaba family, including Alipay and observed XianYu hosts."""
from __future__ import annotations

import ipaddress
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import update_xianyu as xianyu
from update_douyin import fetch_text
from update_media_rules import compact, covering_suffix
from validate_rule_files import normalize_domain, strip_comment, validate_rule_line, validate_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "Alibaba.list"
XIAN_YU = ROOT / "Rule" / "XianYu.list"
SNAPSHOT = ROOT / ".github" / "alibaba-source-snapshot.json"
SOURCES = {
    "sukka": "https://ruleset.skk.moe/List/non_ip/domestic.conf",
    "sukka_scope": "https://raw.githubusercontent.com/SukkaW/Surge/master/Source/non_ip/domestic.ts",
    "sukka_ua": "https://raw.githubusercontent.com/SukkaW/Surge/master/Source/non_ip/domestic.conf",
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Alibaba/Alibaba_All.list",
    "bm7_extra": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/Alibaba/Alibaba.list",
    "bm7_alipay": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/AliPay/AliPay.list",
    "bm7_xianyu": xianyu.SOURCES["bm7"],
    "bm7_dingtalk": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/DingTalk/DingTalk.list",
    "rabbit": xianyu.SOURCES["rabbit"],
    "conners": "https://raw.githubusercontent.com/ConnersHua/RuleGo/master/Surge/Ruleset/Direct+.list",
    "loyal": xianyu.SOURCES["loyal"],
    "yuu": xianyu.SOURCES["yuu"],
    "yuu_cloud": "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/alibabacloud.list",
}
MINIMUMS = {"sukka": 500, "bm7": 1000, "bm7_extra": 50, "bm7_alipay": 10,
            "bm7_xianyu": 10, "bm7_dingtalk": 8, "rabbit": 3500,
            "loyal": 10000, "yuu": 100, "yuu_cloud": 5}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
RULE_TYPES = DOMAIN_TYPES | {"IP-CIDR", "IP-CIDR6", "IP-ASN", "USER-AGENT", "PROCESS-NAME"}
BRAND_TLDS = {"alibaba", "taobao", "tmall", "alipay"}
DEDICATED = ("bm7", "bm7_extra", "bm7_alipay", "bm7_xianyu", "bm7_dingtalk", "yuu", "yuu_cloud")
OUTPUT_LIMITS = (1000, 4000)


def parse_surge(name: str, text: str, general: bool = False) -> set[tuple[str, str]]:
    rules = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if general and parts[0] not in RULE_TYPES:
            continue  # Unselected domestic keyword/wildcard entries are not Alibaba evidence.
        if parts[0] not in RULE_TYPES:
            raise RuntimeError(f"unsupported rule in {name}: {line}")
        canonical, kind, value = validate_rule_line(Path(name), number, line)
        options = canonical.split(",")[2:]
        if options and (kind not in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} or options != ["no-resolve"]):
            raise RuntimeError(f"unexpected options in {name}: {line}")
        if kind == "DOMAIN-SUFFIX" and "." not in value and value not in BRAND_TLDS:
            if general:
                continue
            raise RuntimeError(f"unreviewed top-level domain in {name}: {value}")
        rules.add((kind, value))
    return rules


def parse_loyal(text: str) -> set[tuple[str, str]]:
    rules = set()
    for raw in text.splitlines():
        line = strip_comment(raw)
        if not line:
            continue
        kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
        host = normalize_domain(line.lstrip("."), allow_tld=kind == "DOMAIN-SUFFIX")
        if not host:
            raise RuntimeError(f"invalid Loyalsoldier domain: {line}")
        rules.add((kind, host))
    return rules


def sections(text: str, headings: set[str]) -> str:
    active = False
    lines = []
    for raw in text.splitlines():
        if raw.strip().startswith("# >"):
            active = raw.strip().lstrip("# >").strip() in headings
        elif raw.strip().startswith("# ---"):
            active = False
        elif active:
            lines.append(raw)
    return "\n".join(lines)


def select_sukka(scope: str, native: set[tuple[str, str]]) -> set[tuple[str, str]]:
    # Read only the first ALIBABA block in DOMESTICS, never Tencent or DOH_BOOTSTRAP.
    match = re.search(r"export const DOMESTICS\b.*?\bALIBABA:\s*\{.*?domains:\s*\[(.*?)\]\s*\}", scope, re.S)
    if not match:
        raise RuntimeError("Sukka Alibaba classification block missing")
    selectors = set()
    for raw in match.group(1).splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        token = re.fullmatch(r"'([+$]?[a-z0-9.-]+)'\s*,?", line)
        if not token:
            raise RuntimeError(f"Sukka classification syntax changed: {line}")
        value = token.group(1)
        kind = "DOMAIN" if value.startswith("$") else "DOMAIN-SUFFIX"
        host = normalize_domain(value.lstrip("+$"))
        if not host:
            raise RuntimeError(f"invalid Sukka classification: {value}")
        selectors.add((kind, host))
    if len(selectors) < 60:
        raise RuntimeError("Sukka Alibaba classification unexpectedly small")
    selected = {rule for rule in native if rule[0] in DOMAIN_TYPES and xianyu.covered(rule[1], selectors)}
    for kind, host in selectors:
        if not xianyu.covered(host, native):
            raise RuntimeError(f"Sukka native output lost classified host: {host}")
        # The compiled domestic feed can compact an Alibaba-hosted exact endpoint
        # beneath an unrelated customer's parent suffix. Keep the classified
        # endpoint, never import that customer's entire parent service.
        if not xianyu.covered(host, selected):
            selected.add((kind, host))
    return selected


def select_domains(rules: set[tuple[str, str]], classified: set[tuple[str, str]]) -> set[tuple[str, str]]:
    suffixes = {value for kind, value in classified if kind == "DOMAIN-SUFFIX"}
    return {rule for rule in rules if rule[0] in DOMAIN_TYPES and
            (rule in classified or covering_suffix(rule[1], suffixes) is not None)}


def covers_rule(rule: tuple[str, str], output: set[tuple[str, str]]) -> bool:
    kind, value = rule
    if rule in output:
        return True
    if kind in DOMAIN_TYPES:
        suffixes = {host for rule_type, host in output if rule_type == "DOMAIN-SUFFIX"}
        return covering_suffix(value, suffixes) is not None
    if kind in {"IP-CIDR", "IP-CIDR6"}:
        network = ipaddress.ip_network(value)
        return any(network.subnet_of(ipaddress.ip_network(host))
                   for rule_type, host in output if rule_type == kind)
    return False


def build(sources: dict[str, set[tuple[str, str]]], previous: set[tuple[str, str]],
          standalone: set[tuple[str, str]]) -> tuple[set[tuple[str, str]], dict[str, int]]:
    for name, minimum in MINIMUMS.items():
        if len(sources[name]) < minimum:
            raise RuntimeError(f"{name} source unexpectedly small: {len(sources[name])} < {minimum}")
    for name, host in (("bm7", "taobao.com"), ("bm7_alipay", "alipay.com"),
                       ("bm7_xianyu", "xianyu.mobi"), ("yuu", "goofish.com")):
        if ("DOMAIN-SUFFIX", host) not in sources[name]:
            raise RuntimeError(f"missing dedicated core in {name}: {host}")
    classified = set().union(*(sources[name] for name in (*DEDICATED, "sukka_selected", "sukka_ua", "conners")))
    # Existing independent XianYu rules include user-confirmed app endpoints.
    live_xianyu = xianyu.build({"bm7": sources["bm7_xianyu"],
        **{name: sources[name] for name in ("rabbit", "loyal", "yuu")}}, standalone)
    supplements = {name: select_domains(sources[name], classified) for name in ("sukka", "rabbit", "loyal")}
    merged = classified | live_xianyu | previous | set().union(*supplements.values())
    rules = compact(merged)
    if not OUTPUT_LIMITS[0] <= len(rules) <= OUTPUT_LIMITS[1]:
        raise RuntimeError(f"unexpected Alibaba output size: {len(rules)}")
    for rule in merged:
        if not covers_rule(rule, rules):
            raise RuntimeError(f"compaction reduced coverage: {rule}")
    counts = {name: len(sources[name]) for name in (*DEDICATED, "sukka_selected", "sukka_ua", "conners")}
    counts.update({name: len(ruleset) for name, ruleset in supplements.items()})
    counts.update({"xianyu_preserved": len(standalone), "output": len(rules)})
    return rules, counts


def render(rules: set[tuple[str, str]]) -> str:
    header = ["# NAME: Alibaba (Taobao, Alipay, XianYu and Alibaba family)", "# AUTHOR: cbzy-3p",
              "# FORMAT: Surge Rule Set",
              "# UPDATED: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")]
    header.extend(f"# SOURCE: {name}: {url}" for name, url in SOURCES.items())
    header += ["# EVIDENCE: Rule/Alibaba-Sources.md; includes existing XianYu device evidence",
               "# NOTE: Full Alibaba classification includes shared cloud/CDN networks and overseas ranges.",
               "# NOTE: Customer sites hosted on these networks may also match; first match wins."]
    for kind in sorted(RULE_TYPES):
        count = sum(rule_type == kind for rule_type, _ in rules)
        if count:
            header.append(f"# {kind}: {count}")
    header += [f"# RULE COUNT: {len(rules)}", ""]
    body = [f"{kind},{host}" + (",no-resolve" if kind in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} else "")
            for kind, host in sorted(rules)]
    return "\n".join(header + body) + "\n"


def main() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        texts = dict(zip(SOURCES, pool.map(fetch_text, SOURCES.values())))
    sources = {name: parse_surge(name, text, general=name in {"sukka", "rabbit"})
               for name, text in texts.items() if name not in {"loyal", "sukka_scope", "sukka_ua", "conners"}}
    sources["loyal"] = parse_loyal(texts["loyal"])
    sources["sukka_selected"] = select_sukka(texts["sukka_scope"], sources["sukka"])
    sources["sukka_ua"] = parse_surge("sukka_ua", sections(texts["sukka_ua"], {"Alibaba"}))
    sources["conners"] = parse_surge("conners", sections(texts["conners"], {"Alibaba", "Umeng"}))
    if len(sources["sukka_ua"]) < 2 or len(sources["conners"]) < 2:
        raise RuntimeError("Alibaba sections missing from Sukka/Conners")
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    standalone_text = XIAN_YU.read_text(encoding="utf-8")
    validate_text(XIAN_YU, standalone_text)
    rules, counts = build(sources, parse_surge("previous", current), parse_surge("xianyu", standalone_text))
    old = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    for name, old_count in old.get("counts", {}).items():
        if old_count >= 20 and not old_count * .65 <= counts[name] <= old_count * 2.5:
            raise RuntimeError(f"selected source count changed too much: {name}")
    output = render(rules)
    validate_text(TARGET, output)
    snapshot = json.dumps({"version": 1, "counts": counts}, indent=2, sort_keys=True) + "\n"
    if current.splitlines()[:3] + current.splitlines()[4:] != output.splitlines()[:3] + output.splitlines()[4:]:
        TARGET.write_text(output, encoding="utf-8")
    if not SNAPSHOT.exists() or SNAPSHOT.read_text() != snapshot:
        SNAPSHOT.write_text(snapshot, encoding="utf-8")
    print(f"Alibaba: {len(rules)} rules; six preferred sources checked; all merged coverage preserved")


if __name__ == "__main__":
    main()
