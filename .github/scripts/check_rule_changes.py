"""Check generated rules against the last commit and a fixed reviewed baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from validate_rule_files import normalize_domain, strip_comment, validate_rule_line, validate_text


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".github" / "rule-review-policy.json"
RULE_SUFFIXES = {".list", ".txt"}
SHARED_ADDITION_LIMIT = 10


def canonical_rules(path: Path, text: str) -> set[str]:
    validate_text(path, text)
    rules = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if path.name == "CN-Additional.list" and "," not in line:
            kind = "DOMAIN-SUFFIX" if line.startswith(".") else "DOMAIN"
            rules.add(f"{kind},{normalize_domain(line.lstrip('.'))}")
        else:
            canonical, _kind, _value = validate_rule_line(path, number, line)
            rules.add(canonical)
    return rules


def rules_hash(rules: set[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(rules)) + "\n").encode("utf-8")).hexdigest()


def rule_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"invalid policy rule path: {value}")
    if path.parts and path.parts[0] != "Rule":
        path = PurePosixPath("Rule") / path
    if len(path.parts) < 2 or path.suffix not in RULE_SUFFIXES:
        raise ValueError(f"invalid policy rule path: {value}")
    return path.as_posix()


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("version") != 1:
        raise ValueError("unsupported rule review policy version")
    if not re.fullmatch(r"[0-9a-f]{40}", policy.get("baseline_commit", "")):
        raise ValueError("baseline_commit must pin a full commit SHA")
    pairs = []
    for pair in policy.get("disjoint_pairs", []):
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("each disjoint_pairs entry must contain two rule paths")
        left, right = (rule_path(value) for value in pair)
        if left == right:
            raise ValueError("disjoint_pairs must name different files")
        pairs.append(tuple(sorted((left, right))))
    def validate_hashes(field):
        hashes = {}
        for path, digest in policy.get(field, {}).items():
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"invalid reviewed rule SHA256: {path}")
            hashes[rule_path(path)] = digest
        return hashes
    review_files = sorted({rule_path(value) for value in policy.get("reject_review_files", [])})
    return {**policy, "disjoint_pairs": sorted(set(pairs)),
            "reviewed_current_hashes": validate_hashes("reviewed_current_hashes"),
            "reviewed_new_hashes": validate_hashes("reviewed_new_hashes"),
            "reject_review_files": review_files}


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout


def resolve_commit(root: Path, ref: str) -> str:
    return git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").strip()


def read_revision(root: Path, commit: str) -> tuple[dict[str, set[str]], list[str]]:
    names = git(root, "ls-tree", "-r", "--name-only", "-z", commit, "--", "Rule").split("\0")
    snapshot = {}
    errors = []
    for name in sorted(name for name in names if Path(name).suffix in RULE_SUFFIXES):
        try:
            snapshot[name] = canonical_rules(Path(name), git(root, "show", f"{commit}:{name}"))
        except (RuntimeError, ValueError) as error:
            errors.append(f"invalid {commit[:12]}:{name}: {error}")
    if not snapshot:
        errors.append(f"no valid rule files at commit {commit}")
    return snapshot, errors


def read_worktree(root: Path) -> tuple[dict[str, set[str]], list[str]]:
    snapshot = {}
    errors = []
    for path in sorted((root / "Rule").rglob("*")):
        if not path.is_file() or path.suffix not in RULE_SUFFIXES:
            continue
        name = path.relative_to(root).as_posix()
        try:
            snapshot[name] = canonical_rules(path, path.read_text(encoding="utf-8"))
        except (RuntimeError, ValueError, OSError) as error:
            errors.append(f"invalid working rule file {name}: {error}")
    if not snapshot:
        errors.append("no valid rule files in working tree")
    return snapshot, errors


def sample(rules: set[str]) -> str:
    return "; ".join(sorted(rules)[:5])


def compare_rules(
    baseline: dict[str, set[str]], previous: dict[str, set[str]],
    current: dict[str, set[str]], policy: dict,
) -> tuple[list[str], list[str]]:
    lines = []
    errors = []
    hashes = policy.get("reviewed_current_hashes", {})
    new_hashes = policy.get("reviewed_new_hashes", {})
    for path in sorted(set(baseline) | set(previous) | set(current) | set(new_hashes)):
        if path not in baseline:
            if path in current and new_hashes.get(path) == rules_hash(current[path]):
                lines.append(f"{path}: exact reviewed hash for new rule file")
                continue
            errors.append(f"{path}: missing from reviewed baseline")
            continue
        if path not in previous:
            errors.append(f"{path}: missing from previous revision")
            continue
        if path not in current:
            errors.append(f"{path}: missing from working tree")
            continue
        reviewed = hashes.get(path) == rules_hash(current[path])
        for label, old, floor, ratio in (
            ("baseline", baseline[path], 20, 0.20),
            ("previous", previous[path], 10, 0.10),
        ):
            added, removed = current[path] - old, old - current[path]
            limit = max(floor, math.ceil(len(old) * ratio))
            status = "exact reviewed hash" if reviewed else f"limit {limit} per direction"
            lines.append(f"{path} vs {label}: {len(old)} -> {len(current[path])}, +{len(added)} -{len(removed)} ({status})")
            if added:
                lines.append(f"  added sample: {sample(added)}")
            if removed:
                lines.append(f"  removed sample: {sample(removed)}")
            if not reviewed and (len(added) > limit or len(removed) > limit):
                errors.append(f"{path}: {label} change exceeds {limit}, +{len(added)} -{len(removed)}")

    for left, right in policy.get("disjoint_pairs", []):
        if left not in baseline or right not in baseline or left not in current or right not in current:
            errors.append(f"cannot audit configured pair {left} / {right}: missing rule file")
            continue
        shared_added = (current[left] & current[right]) - (baseline[left] & baseline[right])
        lines.append(f"{left} / {right}: {len(shared_added)} new shared rules since baseline")
        if shared_added:
            lines.append(f"  shared sample: {sample(shared_added)}")
        if len(shared_added) >= SHARED_ADDITION_LIMIT:
            errors.append(f"{left} / {right}: {len(shared_added)} new shared rules requires category review")
    return lines, errors


def write_report(lines: list[str], errors: list[str]) -> None:
    heading = "Rule change review FAILED" if errors else "Rule change review passed"
    report = "\n".join([heading, *lines, *[f"ERROR: {error}" for error in errors]])
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        # Indentation keeps upstream text from becoming Markdown directives.
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join("    " + line for line in report.splitlines()) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--baseline-ref", help="override only for an explicit historical replay")
    parser.add_argument("--previous-ref", default="HEAD")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        baseline_commit = resolve_commit(ROOT, args.baseline_ref or policy["baseline_commit"])
        previous_commit = resolve_commit(ROOT, args.previous_ref)
        baseline, errors = read_revision(ROOT, baseline_commit)
        previous, previous_errors = read_revision(ROOT, previous_commit)
        current, current_errors = read_worktree(ROOT)
        lines, change_errors = compare_rules(baseline, previous, current, policy)
        errors += previous_errors + current_errors + change_errors
        lines.insert(0, f"Fixed baseline {baseline_commit}; previous {previous_commit}")
    except (RuntimeError, ValueError, OSError, TypeError) as error:
        lines, errors = [], [str(error)]
    write_report(lines, errors)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
