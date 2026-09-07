#!/usr/bin/env python3
"""Sync fixed upstream Surge modules and rebuild local aggregate modules."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "cbzy-3p-Surge-Module-Updater/1.0"
SOURCES = {
    "Module/18+/one.sgmodule": "https://one-api.zzxu.de/one/one.sgmodule",
    "Module/18+/porntube.sgmodule": "https://raw.githubusercontent.com/Yu9191/Rewrite/refs/heads/main/porntube/modules/porntube.sgmodule",
    "Module/18+/huangdou.sgmodule": "https://raw.githubusercontent.com/Yu9191/Rewrite/main/huangdouduanju/modules/huangdou.sgmodule",
    "Module/18+/lzlukvca.sgmodule": "https://raw.githubusercontent.com/7452323/QuantumultX/refs/heads/main/script/pornography/lzlukvca.sgmodule",
    "Module/Tools/boxjs.sgmodule": "https://github.com/chavyleung/scripts/raw/master/box/rewrite/boxjs.rewrite.surge.sgmodule",
    "Module/Tools/script-hub.sgmodule": "https://raw.githubusercontent.com/Script-Hub-Org/Script-Hub/main/modules/script-hub.beta.surge.sgmodule",
    "Module/Tools/sub-store.sgmodule": "https://raw.githubusercontent.com/sub-store-org/Sub-Store/master/config/Surge-Beta.sgmodule",
    "Module/Telegram/TgRedirect.sgmodule": "https://raw.githubusercontent.com/Yu9191/Rewrite/refs/heads/main/TgRedirect.sgmodule",
}


HOSTNAME_RE = re.compile(r"^(?:\*\.)?[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
SCRIPT_HOSTS = {"github.com", "raw.githubusercontent.com"}
MAX_SCRIPT_BYTES = 5 * 1024 * 1024
MAX_CHANGED_SCRIPTS = 10


def validate_source(text: str, url: str) -> None:
    if len(text.encode("utf-8")) < 100 or not re.search(r"(?m)^#!name\s*=", text):
        raise RuntimeError(f"missing module metadata: {url}")
    if "[MITM]" not in text:
        raise RuntimeError(f"MITM section missing: {url}")
    for line in text.splitlines():
        if line.startswith("hostname ="):
            if line.count("%APPEND%") + line.count("%INSERT%") > 1:
                raise RuntimeError(f"duplicate MITM insertion marker: {url}")
            values = items(line.split("=", 1)[1])
            if not values or any(not HOSTNAME_RE.fullmatch(value) for value in values):
                raise RuntimeError(f"invalid MITM hostname list: {url}")
        if "script-path=" in line:
            script_url = re.search(r"script-path=(https?[^,\s]+)", line)
            if not script_url or not script_url.group(1).startswith("https://"):
                raise RuntimeError(f"invalid remote script URL: {url}")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    validate_source(text, url)
    return text


def section(text: str, name: str) -> str:
    found = re.search(rf"(?ms)^\[{re.escape(name)}\]\n(.*?)(?=^\[|\Z)", text)
    return found.group(1).strip() if found else ""


def metadata(text: str, key: str) -> str:
    found = re.search(rf"(?m)^#!{re.escape(key)}\s*=\s*(.*)$", text)
    return found.group(1).strip() if found else ""


def items(value: str) -> list[str]:
    return [item.strip() for item in value.replace("%APPEND%", "").replace("%INSERT%", "").split(",") if item.strip()]


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def aggregate_18() -> str:
    paths = [ROOT / "Module/18+" / f"{x}.sgmodule" for x in ("one", "porntube", "huangdou")]
    texts = [path.read_text(encoding="utf-8") for path in paths]
    rewrites = "\n".join(filter(None, (section(text, "URL Rewrite") for text in texts)))
    scripts = "\n".join(filter(None, (section(text, "Script") for text in texts)))
    hosts = unique([host for text in texts for host in items(section(text, "MITM").split("=", 1)[-1])])
    # porntube already provides the shared 日志级别 argument used by 黄豆短剧.
    args = [metadata(texts[1], "arguments")] if metadata(texts[1], "arguments") else []
    desc = [metadata(texts[1], "arguments-desc")] if metadata(texts[1], "arguments-desc") else []
    lines = [
        "#!name=18+ 推荐合集", "#!desc=18+ 模块精选合集：One、porntube、黄豆短剧",
        "#!author=cbzy-3p（整合；原作者见 README.md）", "#!homepage=https://github.com/cbzy-3p/Surge", "#!category=18+",
    ]
    if args: lines.append("#!arguments=" + ",".join(args))
    if desc: lines.append("#!arguments-desc=" + "\\n".join(desc))
    return "\n".join(lines) + f"\n\n[URL Rewrite]\n{rewrites}\n\n[Script]\n{scripts}\n\n[MITM]\nhostname = %APPEND% {', '.join(hosts)}\n"


def aggregate_tools() -> str:
    paths = [ROOT / "Module/Tools" / f"{x}.sgmodule" for x in ("boxjs", "script-hub", "sub-store")]
    texts = [path.read_text(encoding="utf-8") for path in paths]
    force_hosts = unique([host for text in texts for host in items(next((line.split("=", 1)[1] for line in section(text, "General").splitlines() if line.startswith("force-http-engine-hosts")), ""))])
    scripts = "\n".join(filter(None, (section(text, "Script") for text in texts)))
    hosts = unique([host for text in texts for host in items(section(text, "MITM").split("=", 1)[-1])])
    args = [metadata(text, "arguments") for text in texts if metadata(text, "arguments")]
    desc = [metadata(text, "arguments-desc") for text in texts if metadata(text, "arguments-desc")]
    return "\n".join([
        "#!name=工具推荐合集", "#!desc=BoxJs、Script Hub、Sub-Store（β）", "#!author=cbzy-3p（整合；原作者见 README.md）", "#!homepage=https://github.com/cbzy-3p/Surge", "#!category=工具",
        "#!arguments=" + ",".join(args), "#!arguments-desc=" + "\\n".join(desc), "",
        "[General]", "force-http-engine-hosts = %APPEND% " + ", ".join(force_hosts), "", "[Script]", scripts, "", "[MITM]", "hostname = %APPEND% " + ", ".join(hosts), "",
    ])


def write(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if old == content: return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def validate_script(content: bytes, url: str, previous: bytes = b"") -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in SCRIPT_HOSTS:
        raise RuntimeError(f"unapproved script host: {url}")
    if len(content) < 16 or len(content) > MAX_SCRIPT_BYTES:
        raise RuntimeError(f"unexpected script size: {url}")
    lowered = content.lstrip().lower()
    if b"\x00" in content or lowered.startswith((b"<!doctype html", b"<html")):
        raise RuntimeError(f"invalid remote script content: {url}")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"script is not UTF-8 text: {url}") from exc
    if previous:
        ratio = len(content) / len(previous)
        if ratio < 0.2 or ratio > 5:
            raise RuntimeError(f"abnormal script size change ({ratio:.2f}x): {url}")


def fetch_script(url: str, previous: bytes = b"") -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read()
    validate_script(content, url, previous)
    return content


def mirror_scripts() -> list[str]:
    """Mirror every remote script and rewrite modules to the repository copy."""
    script_dir = ROOT / "Module/Scripts"
    manifest: dict[str, dict[str, str]] = {}
    changed: list[str] = []
    for relative in SOURCES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        urls = list(dict.fromkeys(re.findall(r"script-path=(https?[^,\s]+)", text)))
        for url in urls:
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            filename = f"{digest}.js"
            destination = script_dir / filename
            old = destination.read_bytes() if destination.exists() else b""
            content = fetch_script(url, old)
            if old != content:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                changed.append(destination.relative_to(ROOT).as_posix())
            manifest[url] = {
                "file": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            local = f"https://raw.githubusercontent.com/cbzy-3p/Surge/main/Module/Scripts/{filename}"
            text = text.replace(url, local)
        if write(path, text):
            changed.append(relative)
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if write(script_dir / "manifest.json", manifest_text):
        changed.append("Module/Scripts/manifest.json")
    stale = {path.name for path in script_dir.glob("*.js")} - {entry["file"] for entry in manifest.values()}
    for filename in sorted(stale):
        (script_dir / filename).unlink()
        changed.append(f"Module/Scripts/{filename}")
    changed_scripts = [path for path in changed if path.startswith("Module/Scripts/") and path.endswith(".js")]
    if len(changed_scripts) > MAX_CHANGED_SCRIPTS:
        raise RuntimeError(f"too many script changes in one run: {len(changed_scripts)}")
    return changed


def validate_repository() -> None:
    script_dir = ROOT / "Module/Scripts"
    manifest_path = script_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files: set[str] = set()
    local_prefix = "https://raw.githubusercontent.com/cbzy-3p/Surge/main/Module/Scripts/"
    referenced_files: set[str] = set()

    for url, entry in manifest.items():
        filename = entry.get("file", "")
        if filename != f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.js":
            raise RuntimeError(f"manifest filename mismatch: {url}")
        path = script_dir / filename
        if not path.is_file():
            raise RuntimeError(f"manifest script missing: {filename}")
        content = path.read_bytes()
        validate_script(content, url)
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            raise RuntimeError(f"manifest hash mismatch: {filename}")
        expected_files.add(filename)

    for module in sorted((ROOT / "Module").glob("**/*.sgmodule")):
        content = module.read_text(encoding="utf-8")
        validate_source(content, module.as_posix())
        names: set[str] = set()
        for line in section(content, "Script").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            name = line.split("=", 1)[0].strip()
            if name in names:
                raise RuntimeError(f"duplicate script name in {module}: {name}")
            names.add(name)
        for local in re.findall(r"script-path=" + re.escape(local_prefix) + r"([^,\s]+)", content):
            referenced_files.add(local)

    actual_files = {path.name for path in script_dir.glob("*.js")}
    if actual_files != expected_files:
        raise RuntimeError("script directory and manifest do not match")
    if referenced_files != expected_files:
        missing = sorted(expected_files - referenced_files)
        unknown = sorted(referenced_files - expected_files)
        raise RuntimeError(f"module script references do not match manifest; missing={missing}, unknown={unknown}")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--validate-only":
        validate_repository()
        print("Module validation passed.")
        return 0
    changed = []
    for relative, url in SOURCES.items():
        path = ROOT / relative
        if write(path, fetch(url)): changed.append(relative)
    changed.extend(mirror_scripts())
    for relative, content in (("Module/18+/18+-recommended.sgmodule", aggregate_18()), ("Module/Tools/Tools-recommended.sgmodule", aggregate_tools())):
        if write(ROOT / relative, content): changed.append(relative)
    validate_repository()
    print("Updated: " + ", ".join(changed) if changed else "No module source changes.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
