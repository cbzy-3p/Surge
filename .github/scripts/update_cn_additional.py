from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://static-file-global.353355.xyz/rules/cn-additional-list.txt"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "Rule" / "CN-Additional.list"
SNAPSHOT_PATH = ROOT / ".github" / "cn-additional-source-snapshot.json"
SNAPSHOT_VERSION = 1
MINIMUM_OUTPUT = 40_000
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")


def fetch_source(attempts: int = 3) -> str:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(
                SOURCE_URL,
                headers={"User-Agent": "cbzy-3p-Surge-Rules/2.1"},
            )
            with urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                content = response.read().decode("utf-8-sig")
            if not content.strip():
                raise RuntimeError("empty response")
            return content
        except Exception as exc:
            error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"failed to fetch {SOURCE_URL}: {error}")


def normalize_domain(raw_line: str) -> str | None:
    line = raw_line.strip()
    if not line or line.startswith(("#", ";", "//")):
        return None

    upper = line.upper()
    if upper.startswith("DOMAIN-SUFFIX,") or upper.startswith("DOMAIN,"):
        line = line.split(",", 1)[1].strip()

    domain = line.lstrip(".").rstrip(".").lower()
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return None

    if len(domain) > 253 or not DOMAIN_RE.fullmatch(domain):
        return None

    labels = domain.split(".")
    if any(len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        return None

    return domain


def convert(text: str) -> tuple[list[str], list[str]]:
    domains: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        domain = normalize_domain(raw_line)
        if domain is None:
            if stripped and not stripped.startswith(("#", ";", "//")):
                invalid.append(stripped)
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)

    return compact_domains(domains), invalid


def count_valid_unique_domains(text: str) -> int:
    domains = {
        domain
        for raw_line in text.splitlines()
        if (domain := normalize_domain(raw_line)) is not None
    }
    return len(domains)


def compact_domains(domains: list[str]) -> list[str]:
    available = set(domains)
    compacted: list[str] = []
    for domain in domains:
        labels = domain.split(".")
        if any(".".join(labels[index:]) in available for index in range(1, len(labels))):
            continue
        compacted.append(domain)
    return compacted


def load_snapshot() -> dict[str, int]:
    if not SNAPSHOT_PATH.exists():
        return {}
    try:
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"invalid source snapshot: {SNAPSHOT_PATH}: {exc}") from exc
    if data.get("version") != SNAPSHOT_VERSION:
        return {}
    return {key: int(value) for key, value in data.get("counts", {}).items()}


def validate_snapshot(previous: dict[str, int], current: dict[str, int]) -> None:
    for name, old in previous.items():
        if name not in current or old < 20:
            continue
        new = current[name]
        if new * 100 < old * 65:
            raise RuntimeError(f"{name} count dropped too much: {old} -> {new}")
        if new > old * 5 // 2:
            raise RuntimeError(f"{name} count grew too much: {old} -> {new}")


def render_snapshot(counts: dict[str, int]) -> str:
    return json.dumps(
        {"version": SNAPSHOT_VERSION, "counts": counts},
        indent=2,
        sort_keys=True,
    ) + "\n"


def render_output(domains: list[str]) -> str:
    return "\n".join(f".{domain}" for domain in domains) + "\n"


def main() -> None:
    source = fetch_source()
    domains, invalid = convert(source)
    if len(domains) < MINIMUM_OUTPUT:
        raise RuntimeError(f"Unexpected rule count: {len(domains)}")

    counts = {
        "source_valid_unique": count_valid_unique_domains(source),
        "output": len(domains),
    }
    validate_snapshot(load_snapshot(), counts)

    output = render_output(domains)
    previous = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if output == previous:
        print(f"CN-Additional.list unchanged with {len(domains)} domains")
    else:
        OUTPUT_PATH.write_text(output, encoding="utf-8", newline="\n")
        print(f"updated CN-Additional.list with {len(domains)} domains")

    SNAPSHOT_PATH.write_text(render_snapshot(counts), encoding="utf-8", newline="\n")

    if invalid:
        print(f"Skipped {len(invalid)} invalid lines")
        for line in invalid[:20]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
