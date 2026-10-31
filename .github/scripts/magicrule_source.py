"""Resolve reviewed MagicRule categories without hard-coding versioned artifacts."""
import hashlib
import json
from urllib.parse import urlparse

INDEX_URL = "https://magicrule.pages.dev/data/index/Surge.json"


def checked_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"magicrule.pages.dev", "rule-26r.pages.dev"}:
        raise RuntimeError("unexpected MagicRule source host")
    if parsed.username or parsed.password or not parsed.path.startswith("/data/"):
        raise RuntimeError("unexpected MagicRule source URL")
    return url


def fetch_category(name, fetch):
    index = json.loads(fetch(INDEX_URL))
    matches = [r for r in index["rules"] if r["name"] == name]
    if index.get("client") != "Surge" or len(matches) != 1:
        raise RuntimeError(f"missing or ambiguous MagicRule category: {name}")
    manifest_url = checked_url(matches[0]["manifest"])
    manifest = json.loads(fetch(manifest_url))
    if manifest.get("client") != "Surge" or manifest.get("rule") != name:
        raise RuntimeError("MagicRule manifest classification mismatch")
    artifacts = [a for a in manifest["artifacts"] if a.get("role") == "full" and not a.get("binary") and not a.get("empty")]
    if len(artifacts) != 1:
        raise RuntimeError("missing or ambiguous MagicRule full artifact")
    artifact = artifacts[0]
    content = fetch(checked_url(artifact["url"]))
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != artifact["dedupe"]["bytes_sha256"]:
        raise RuntimeError(f"MagicRule checksum mismatch: {name}; retain committed rules")
    lines = [s for s in content.splitlines() if s.strip() and not s.lstrip().startswith(("#", "//", ";"))]
    if not lines or len(lines) != manifest["total_line_count"]:
        raise RuntimeError(f"MagicRule rule count mismatch: {name}")
    return content, manifest_url
