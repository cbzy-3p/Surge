"""Report reject-list overlaps and stop new shared suspicious category additions."""
from __future__ import annotations

import json
import os
from pathlib import Path

from check_rule_changes import POLICY, ROOT, load_policy, read_revision, read_worktree, resolve_commit
from check_supplemental_sources import parse_domain_set
from update_rules import fetch

REJECT_SOURCE = "https://ruleset.skk.moe/List/domainset/reject.conf"


def overlap(rules: set[str], blocked: set[str]) -> set[str]:
    exact = {r.split(",", 1)[1] for r in blocked if r.startswith("DOMAIN,")}
    suffixes = {r.split(",", 1)[1] for r in blocked if r.startswith("DOMAIN-SUFFIX,")}
    matches = set()
    for rule in rules:
        parts = rule.split(",")
        if parts[0] not in {"DOMAIN", "DOMAIN-SUFFIX"}:
            continue
        host = parts[1]
        labels = host.split(".")
        if host in exact or any(".".join(labels[i:]) in suffixes for i in range(len(labels))):
            matches.add(rule)
    return matches


def review(current: dict, baseline: dict, blocked: set[str], pairs: list,
           review_files: list | None = None) -> tuple[dict, list]:
    report = {}
    errors = []
    for name, rules in sorted(current.items()):
        matches = overlap(rules, blocked)
        newly_added = matches - baseline.get(name, set())
        report[name] = {"overlap_count": len(matches), "new_overlap_count": len(newly_added),
                        "overlaps": sorted(matches), "new_overlaps": sorted(newly_added)}
    for name in review_files or []:
        if name not in current or name not in baseline:
            errors.append(f"missing monitored category {name}")
        elif report[name]["new_overlap_count"]:
            errors.append(f"{name}: {report[name]['new_overlap_count']} new reject-overlap rules require category review")
    for left, right in pairs:
        if left not in current or right not in current or left not in baseline or right not in baseline:
            errors.append(f"missing classification pair {left} / {right}")
            continue
        new_shared = (current[left] & current[right]) - (baseline[left] & baseline[right])
        suspicious = overlap(new_shared, blocked)
        if suspicious:
            errors.append(f"{left} / {right}: {len(suspicious)} new shared reject-overlap rules; review required: " + "; ".join(sorted(suspicious)[:5]))
    return report, errors


def main() -> int:
    directory = Path(os.environ["RULE_AUDIT_DIR"])
    policy = load_policy(POLICY)
    baseline, errors = read_revision(ROOT, resolve_commit(ROOT, policy["baseline_commit"]))
    current, current_errors = read_worktree(ROOT)
    if errors or current_errors:
        raise RuntimeError("; ".join(errors + current_errors))
    blocked = parse_domain_set(fetch(REJECT_SOURCE))
    if len(blocked) < 100_000:
        raise RuntimeError("reject comparison source unexpectedly small")
    report, errors = review(current, baseline, blocked, policy["disjoint_pairs"],
                            policy.get("reject_review_files", []))
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"source": REJECT_SOURCE, "note": "An overlap is review evidence, not proof of an incorrect service classification.",
               "files": report, "errors": errors}
    (directory / "classification-overlaps.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["## Classification overlap review", "", payload["note"], ""]
    for name, row in report.items():
        if row["overlap_count"]:
            lines.append(f"- {name}: {row['overlap_count']} overlaps, {row['new_overlap_count']} newly added rules since baseline.")
    lines.extend(f"ERROR: {error}" for error in errors)
    text = "\n".join(lines) + "\n"
    (directory / "classification-overlaps.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
