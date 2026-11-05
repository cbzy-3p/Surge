#!/usr/bin/env python3
"""XianYu rules: dedicated baseline plus reviewed, narrowly scoped dependencies."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from update_douyin import compact_rules, fetch_text, parse_surge_rules
from validate_rule_files import normalize_domain, validate_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "Rule" / "XianYu.list"
SNAPSHOT = ROOT / ".github" / "xianyu-source-snapshot.json"
SOURCES = {
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/XianYu/XianYu.list",
    "rabbit": "https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules/China.list",
    "loyal": "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt",
    "yuu": "https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/alibaba.list",
}

# Reviewed against first-party site code and SDK disclosures. See XianYu-Sources.md.
# Shared service endpoints stay exact: do not import Alibaba/China wholesale.
DEPENDENCY_HOSTS = {
    "2.taobao.com", "acs.m.taobao.com", "amdc.m.taobao.com",
    "h5.m.taobao.com", "h5api.m.taobao.com", "login.m.taobao.com", "login.taobao.com",
    "market.m.taobao.com", "msgacs.m.taobao.com", "passport.taobao.com",
    "trade-acs.m.taobao.com", "a.tbcdn.cn", "wwc.taobaocdn.com",
    "assets.alicdn.com", "cbu01.alicdn.com", "fli.alicdn.com",
    "g.alicdn.com", "gw.alicdn.com", "heic.alicdn.com",
    "ilce.alicdn.com", "img.alicdn.com", "o.alicdn.com",
    "ossimg.alicdn.com", "terms.alicdn.com", "wwc.alicdn.com",
    "xianyu-video.alicdn.com", "i01.lw.aliimg.com",
    "down-cdn.dingtalk.com", "down.dingtalk.com", "down.im.dingtalk.cn",
    "impaas-static.dingtalk.com", "static.dingtalk.com",
    "wss-cntaobao.dingtalk.com", "wss-goofish.dingtalk.com",
    "wss.im.dingtalk.cn", "mobilegw.alipay.com", "render.alipay.com",
    "gm.mmstat.com", "log.mmstat.com", "s-gm.mmstat.com",
}
# App Privacy Report recorded on the user's iPhone on 2026-10-07 at 19:56.
# These exact hosts have direct device evidence and need no broad upstream membership.
# Keep the observed spelling "dinamicx", not "dynamic" or "dynamicx".
OBSERVED_HOSTS = {
    "tls-goofish.dingtalk.com", "umc.danuoyi.alicdn.com",
    "vpp-license-proxy.aliyuncs.com",
    "alivc-aio.cn-hangzhou.dualstack.log.aliyuncs.com",
    "cloud-config-service.rtc.aliyuncs.com", "ali.wosms.cn",
    "slsrole.alicdn.com", "videocloud.cn-hangzhou.dualstack.log.aliyuncs.com",
    "vod-newplayer.cn-hangzhou.log.aliyuncs.com", "vod.cn-shanghai.aliyuncs.com",
    "livephoto.cloudvideocdn.taobao.com", "dinamicx.alibabausercontent.com",
    "gw.alipayobjects.com", "ntp.ynuf.aliapp.org", "tbexpand.alicdn.com",
    "abtest.alibaba.com", "cloud.video.taobao.com", "mgwapi-tb.alipay.com",
    "orange-dc.m.taobao.com", "video-sdk-cert-cdn.aliyuncs.com",
    "zconfig.alibabausercontent.com",
}
MIN_SOURCE_RULES = {"bm7": 10, "rabbit": 3500, "loyal": 10000, "yuu": 100}
SOURCE_FETCH_ATTEMPTS = 3
FORBIDDEN_SUFFIXES = {
    "taobao.com", "alicdn.com", "dingtalk.com", "dingtalk.cn",
    "aliyuncs.com", "aliyun.com", "alibaba.com", "alipay.com",
    "qq.com", "amap.com", "zijieapi.com",
}


def parse_source(name: str, text: str) -> set[tuple[str, str]]:
    if name != "loyal":
        return parse_surge_rules(text)
    rules = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
            host = normalize_domain(line.lstrip("."), allow_tld=kind == "DOMAIN-SUFFIX")
            if not host:
                raise RuntimeError(f"invalid Loyalsoldier domain: {line}")
            rules.add((kind, host))
    return rules


def fetch_valid_source(source: tuple[str, str]) -> tuple[str, str]:
    name, url = source
    minimum = MIN_SOURCE_RULES[name]
    last_count = 0
    last_error: Exception | None = None
    for attempt in range(1, SOURCE_FETCH_ATTEMPTS + 1):
        try:
            text = fetch_text(url)
        except Exception as exc:
            last_error = exc
        else:
            last_error = None
            last_count = len(parse_source(name, text))
            if last_count >= minimum:
                return name, text
        if attempt < SOURCE_FETCH_ATTEMPTS:
            time.sleep(attempt * 2)
    if last_error is not None:
        raise RuntimeError(
            f"{name} source fetch failed after {SOURCE_FETCH_ATTEMPTS} attempts: {last_error}"
        ) from last_error
    raise RuntimeError(
        f"{name} source unexpectedly small after {SOURCE_FETCH_ATTEMPTS} attempts: "
        f"{last_count} < {minimum}"
    )


def covered(host: str, rules: set[tuple[str, str]]) -> bool:
    return any((kind == "DOMAIN" and host == value) or
               (kind == "DOMAIN-SUFFIX" and (host == value or host.endswith("." + value)))
               for kind, value in rules)


def build(sources: dict[str, set[tuple[str, str]]], previous: set[tuple[str, str]]) -> set[tuple[str, str]]:
    for name, minimum in MIN_SOURCE_RULES.items():
        if len(sources[name]) < minimum:
            raise RuntimeError(f"{name} source unexpectedly small: {len(sources[name])} < {minimum}")
    baseline = sources["bm7"]
    if not covered("xianyu.mobi", baseline) or len(baseline) > 128:
        raise RuntimeError("BM7 XianYu classification changed unexpectedly")
    # Cross-check the core and shared endpoints; broad corroborating rules are never emitted.
    for host in DEPENDENCY_HOSTS | {"goofish.com"}:
        votes = sum(covered(host, sources[name]) for name in ("rabbit", "loyal", "yuu"))
        if votes < 2:
            raise RuntimeError(f"dependency lost cross-source corroboration: {host} ({votes}/3)")
    rules = compact_rules(previous | baseline | {("DOMAIN-SUFFIX", "goofish.com")} |
                          {("DOMAIN", host) for host in DEPENDENCY_HOSTS | OBSERVED_HOSTS})
    if any(kind not in {"DOMAIN", "DOMAIN-SUFFIX"} for kind, _ in rules):
        raise RuntimeError("unexpected non-domain rule in XianYu")
    if any("." not in value for _, value in rules):
        raise RuntimeError("refusing top-level domain in XianYu")
    if any(kind == "DOMAIN-SUFFIX" and value in FORBIDDEN_SUFFIXES for kind, value in rules):
        raise RuntimeError("refusing broad shared-service suffix in XianYu")
    if not 30 <= len(rules) <= 200:
        raise RuntimeError(f"unexpected XianYu output size: {len(rules)}")
    return rules


def render(rules: set[tuple[str, str]]) -> str:
    header = ["# NAME: XianYu", "# AUTHOR: cbzy-3p", "# FORMAT: Surge Rule Set",
              "# UPDATED: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")]
    header.extend(f"# SOURCE: {name}: {url}" for name, url in SOURCES.items())
    header += ["# SOURCE: User iPhone App Privacy Report; screen recording 2026-10-07 19:56 (UTC+8)",
               "# EVIDENCE: Rule/XianYu-Sources.md; first-party assets, SDK disclosure, and observed app hosts",
               "# NOTE: Shared dependency hosts also match other apps using the same hosts.",
               "# NOTE: No whole Alibaba cloud/CDN networks, third-party SDK umbrellas, or unverified IPs."]
    for kind in ("DOMAIN", "DOMAIN-SUFFIX"):
        header.append(f"# {kind}: {sum(item[0] == kind for item in rules)}")
    header += [f"# TOTAL: {len(rules)}", ""]
    return "\n".join(header + [f"{kind},{host}" for kind, host in sorted(rules)]) + "\n"


def main() -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        texts = dict(pool.map(fetch_valid_source, SOURCES.items()))
    sources = {name: parse_source(name, text) for name, text in texts.items()}
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    previous = parse_surge_rules(current)
    rules = build(sources, previous)
    old = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    old_count = old.get("counts", {}).get("bm7", 0)
    if old_count and not old_count * .65 <= len(sources["bm7"]) <= old_count * 2.5:
        raise RuntimeError("BM7 XianYu source count changed too much")
    output = render(rules)
    validate_text(TARGET, output)
    # Broad parent list churn is irrelevant: record only the selected classification/coverage.
    snapshot = json.dumps({"version": 1, "counts": {"bm7": len(sources["bm7"]),
        "reviewed_dependencies": len(DEPENDENCY_HOSTS), "observed_app_hosts": len(OBSERVED_HOSTS),
        "output": len(rules)}}, indent=2, sort_keys=True) + "\n"
    if current.splitlines()[:3] + current.splitlines()[4:] != output.splitlines()[:3] + output.splitlines()[4:]:
        TARGET.write_text(output, encoding="utf-8")
    if not SNAPSHOT.exists() or SNAPSHOT.read_text() != snapshot:
        SNAPSHOT.write_text(snapshot, encoding="utf-8")
    print(f"XianYu: {len(rules)} rules; four sources checked; shared endpoints scoped exactly")


if __name__ == "__main__":
    main()
