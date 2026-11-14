"""Compare narrow/single-source outputs with related feeds without broadening them."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import update_v2fly_rules as v2fly
from update_rules import fetch
from validate_rule_files import normalize_domain, strip_comment, validate_rule_line
from check_rule_changes import canonical_rules

ROOT = Path(__file__).resolve().parents[2]
LOYAL_PROXY = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/proxy.txt"


def parse_domain_set(text: str) -> set[str]:
    rules = set()
    for raw in text.splitlines():
        line = strip_comment(raw)
        if not line:
            continue
        kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
        domain = normalize_domain(line.lstrip("."), allow_tld=kind == "DOMAIN-SUFFIX")
        # Comparison feeds may contain DNS labels with underscores. Preserve
        # these as evidence without relaxing published rule validation.
        candidate = line.removeprefix(".").lower().rstrip(".")
        if not domain and "_" in candidate and len(candidate) <= 253 and re.fullmatch(
            r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?)+", candidate
        ):
            domain = candidate
        if not domain:
            raise ValueError("invalid related domain-set entry")
        rules.add(f"{kind},{domain}")
    if not rules:
        raise ValueError("empty related domain set")
    return rules


def parse_related_rules(text: str) -> set[str]:
    rules = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        _, kind, value = validate_rule_line(Path("related-source.list"), number, line)
        rules.add(f"{kind},{value}")
    if not rules:
        raise ValueError("empty related rules")
    return rules


def compare(current: set[str], other: set[str]) -> dict:
    def uncovered(left, right):
        suffixes = {r.split(",")[1] for r in right if r.startswith("DOMAIN-SUFFIX,")}
        missing = set()
        for rule in left - right:
            kind, value = rule.split(",", 1)
            if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
                labels = value.split(".")
                if any(".".join(labels[i:]) in suffixes for i in range(len(labels))):
                    continue
            missing.add(rule)
        return sorted(missing)
    return {"current_rules": len(current), "comparison_rules": len(other),
            "only_current": uncovered(current, other), "only_comparison": uncovered(other, current)}


def read(name: str) -> set[str]:
    path = ROOT / "Rule" / f"{name}.list"
    return canonical_rules(path, path.read_text(encoding="utf-8"))


def main() -> None:
    directory = Path(os.environ["RULE_AUDIT_DIR"])
    results = {}
    for name in ("NonCN", "Bybit", "N26"):
        try:
            if name == "NonCN":
                other = parse_related_rules(fetch(LOYAL_PROXY))
            else:
                parsed, _urls = v2fly.parse_entry(v2fly.TARGETS[name]["entry"])
                other = {f"{kind},{value}" for kind, value in parsed}
            results[name] = {"status": "compared_related_data", **compare(read(name), other)}
        except Exception as error:
            results[name] = {"status": "comparison_unavailable", "error_type": type(error).__name__}
            print(f"::warning::{name} optional related-source comparison unavailable ({type(error).__name__})")
    results["CN-Additional"] = {
        "status": "compared_different_scope",
        "note": "China is a multi-source comparison. Its narrower scope does not replace CN-Additional.",
        **compare(read("CN-Additional"), read("China")),
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "supplemental-comparisons.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["## Supplemental source comparisons", "",
             "Related-source and different-scope comparisons provide evidence for review. They do not modify published rules.", ""]
    for name, result in results.items():
        detail = result["status"]
        if "only_current" in result:
            detail += f"; current-only {len(result['only_current'])}, comparison-only {len(result['only_comparison'])}"
        lines.append(f"- {name}: {detail}")
    text = "\n".join(lines) + "\n"
    (directory / "supplemental-comparisons.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)


if __name__ == "__main__":
    main()
