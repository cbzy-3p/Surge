"""Apply reviewed category exclusions to the affected Rabbit-Spec inputs."""

from pathlib import Path


EXCLUSIONS = Path(__file__).with_name("data") / "rabbit-spec-apple-globalmedia-exclusions.list"


def filter_reviewed_rules(rules: set[tuple[str, str]], category: str | None = None) -> set[tuple[str, str]]:
    excluded = set()
    paths = [EXCLUSIONS]
    if category == "Apple":
        paths.append(EXCLUSIONS.with_name("rabbit-spec-apple-exclusions.list"))
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                rule_type, value = line.split(",", 1)
                excluded.add((rule_type, value))
    return rules - excluded
