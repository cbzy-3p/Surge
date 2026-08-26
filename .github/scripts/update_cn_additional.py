from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://static-file-global.353355.xyz/rules/cn-additional-list.txt"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "Rule" / "CN-Additional.list"
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")


def fetch_source() -> str:
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "cbzy-3p-Surge-Rules/2.0"},
    )
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig")


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

    return domains, invalid


def main() -> None:
    domains, invalid = convert(fetch_source())
    if len(domains) < 40000:
        raise RuntimeError(f"Unexpected rule count: {len(domains)}")

    # Surge DOMAIN-SET: a leading dot matches the domain itself and all subdomains.
    OUTPUT_PATH.write_text(
        "\n".join(f".{domain}" for domain in domains) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {len(domains)} domains to {OUTPUT_PATH}")
    if invalid:
        print(f"Skipped {len(invalid)} invalid lines")
        for line in invalid[:20]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
