"""Apply reviewed category exclusions to the affected Rabbit-Spec inputs."""

from pathlib import Path


EXCLUSIONS = Path(__file__).with_name("data") / "rabbit-spec-apple-globalmedia-exclusions.list"


def filter_reviewed_rules(rules: set[tuple[str, str]]) -> set[tuple[str, str]]:
    excluded = set()
    for line in EXCLUSIONS.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            rule_type, value = line.split(",", 1)
            excluded.add((rule_type, value))
    return rules - excluded
