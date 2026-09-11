#!/usr/bin/env python3
"""Sync fixed upstream Surge modules and rebuild local aggregate modules."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import shutil
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "cbzy-3p-Surge-Module-Updater/1.0"
LOCAL_SCRIPT_BASE = "https://raw.githubusercontent.com/cbzy-3p/Surge/main/Module/Scripts/"
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

AD_SOURCES = {
    "Module/AdBlock/google.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/Google%E6%90%9C%E7%B4%A2%E9%87%8D%E5%AE%9A%E5%90%91.sgmodule",
    "Module/AdBlock/soul.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/Soul%E5%8E%BB%E5%B9%BF%E5%91%8A.sgmodule",
    "Module/AdBlock/wechat-public.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7%E5%8E%BB%E5%B9%BF%E5%91%8A.sgmodule",
    "Module/AdBlock/wechat-mini.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/%E5%BE%AE%E4%BF%A1%E5%B0%8F%E7%A8%8B%E5%BA%8F%E5%8E%BB%E5%B9%BF%E5%91%8A.sgmodule",
    "Module/AdBlock/taobao.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/%E6%B7%98%E5%AE%9D%E5%8E%BB%E5%B9%BF%E5%91%8A.sgmodule",
    "Module/AdBlock/amap.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/%E9%AB%98%E5%BE%B7%E5%9C%B0%E5%9B%BE%E5%8E%BB%E5%B9%BF%E5%91%8A.sgmodule",
    "Module/AdBlock/wechat-unlock.sgmodule": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/Beta/%E5%BE%AE%E4%BF%A1%E5%A4%96%E9%83%A8%E9%93%BE%E6%8E%A5%E8%A7%A3%E9%94%81.beta.sgmodule",
}
GOOFISH_SOURCE = "https://raw.githubusercontent.com/ddgksf2013/Rewrite/refs/heads/master/AdBlock/GoofishAds.conf"


HOSTNAME_RE = re.compile(r"^[A-Za-z0-9*](?:[A-Za-z0-9*-]{0,61}[A-Za-z0-9*])?(?:\.[A-Za-z0-9*](?:[A-Za-z0-9*-]{0,61}[A-Za-z0-9*])?)+$")
SCRIPT_HOSTS = {"github.com", "raw.githubusercontent.com"}
SCRIPT_REPOS = {"7452323/QuantumultX", "Yu9191/Rewrite", "Script-Hub-Org/Script-Hub", "sub-store-org/Sub-Store", "chavyleung/scripts", "QingRex/LoonKissSurge", "ddgksf2013/Rewrite", "ddgksf2013/Scripts"}
EXTERNAL_SCRIPT_PREFIXES = (
    "https://kelee.one/Resource/JavaScript/",
    "https://raw.githubusercontent.com/ddgksf2013/Scripts/refs/heads/master/",
)


def check_url(url: str) -> None:
    parsed = urlparse(url)
    repo = "/".join(parsed.path.strip("/").split("/")[:2])
    if parsed.scheme != "https" or parsed.username or parsed.port not in (None, 443):
        raise RuntimeError(f"unapproved URL: {url}")
    if parsed.hostname == "one-api.zzxu.de" and parsed.path == "/one/one.sgmodule":
        return
    if parsed.hostname not in SCRIPT_HOSTS or repo not in SCRIPT_REPOS:
        raise RuntimeError(f"unapproved repository: {url}")


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        source = urlparse(req.full_url)
        release = (source.hostname == "github.com" and source.path.lower().startswith("/sub-store-org/sub-store/releases/"))
        if not (release and parsed.scheme == "https" and parsed.hostname == "release-assets.githubusercontent.com" and not parsed.username):
            check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_checked(url: str, timeout: int):
    check_url(url)
    return urllib.request.build_opener(CheckedRedirect()).open(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout)
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
    with open_checked(url, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    validate_source(text, url)
    return text


def fetch_text(url: str) -> str:
    with open_checked(url, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


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


def normalize_module(text: str) -> str:
    """Remove Loon-only metadata and make Surge script identifiers unique."""
    lines = [line for line in text.splitlines() if not line.startswith("#!loon_version=")]
    in_scripts = False
    names: dict[str, int] = {}
    normalized: list[str] = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            in_scripts = line == "[Script]"
        if in_scripts and line.strip() and not line.lstrip().startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            base = name.strip()
            names[base] = names.get(base, 0) + 1
            if names[base] > 1:
                line = f"{base}（{names[base]}） =" + value
        normalized.append(line.rstrip())
    return "\n".join(normalized).strip() + "\n"


def convert_goofish(text: str) -> str:
    rules: list[str] = []
    rewrites: list[str] = []
    body_rewrites: list[str] = []
    scripts: list[str] = []
    hosts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("hostname ="):
            hosts.extend(items(line.split("=", 1)[1]))
        elif line.lower().startswith("host-suffix,"):
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 2:
                rules.append(f"DOMAIN-SUFFIX,{parts[1]},REJECT")
        elif match := re.match(r"^(.*?)\s+url\s+reject-200$", line):
            rewrites.append(f"{match.group(1)} - reject-200")
        elif match := re.match(r"^(.*?)\s+url\s+jsonjq-response-body\s+(.+)$", line):
            body_rewrites.append(f"http-response-jq {match.group(1)} {match.group(2)}")
        elif match := re.match(r"^(.*?)\s+url\s+script-response-body\s+(https://\S+)$", line):
            scripts.append("闲鱼设备信息净化 = type=http-response, pattern=" + match.group(1) +
                           ", script-path=" + match.group(2) + ", requires-body=true")
    if not hosts or not (rewrites or body_rewrites or scripts):
        raise RuntimeError("Goofish conversion produced an incomplete Surge module")
    blocks = [
        "#!name=闲鱼去广告", "#!desc=过滤闲鱼开屏、首页、搜索、推荐及设备调度内容",
        "#!author=ddgksf2013（Surge 转换：cbzy-3p）", "#!homepage=https://github.com/cbzy-3p/Surge", "#!category=去广告",
    ]
    for name, values in (("Rule", rules), ("URL Rewrite", rewrites), ("Body Rewrite", body_rewrites), ("Script", scripts)):
        if values:
            blocks.extend(["", f"[{name}]", *unique(values)])
    blocks.extend(["", "[MITM]", "hostname = %APPEND% " + ", ".join(unique(hosts)), ""])
    return "\n".join(blocks)


def aggregate_adblock() -> str:
    order = ("wechat-public", "wechat-mini", "taobao", "amap", "goofish", "soul", "google", "wechat-unlock")
    texts = [(ROOT / "Module/AdBlock" / f"{name}.sgmodule").read_text(encoding="utf-8") for name in order]
    blocks = [
        "#!name=应用净化推荐合集", "#!desc=微信、淘宝、高德、闲鱼、Soul 去广告，Google 重定向及微信外链解锁",
        "#!author=cbzy-3p（整合；原作者见 README.md）", "#!homepage=https://github.com/cbzy-3p/Surge", "#!category=去广告",
    ]
    for name in ("Rule", "URL Rewrite", "Body Rewrite", "Map Local", "Script"):
        lines = unique([
            line.rstrip() for text in texts for line in section(text, name).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ])
        if lines:
            blocks.extend(["", f"[{name}]", *lines])
    hosts = unique([host for text in texts for host in items(section(text, "MITM").split("=", 1)[-1])])
    blocks.extend(["", "[MITM]", "hostname = %APPEND% " + ", ".join(hosts), ""])
    return normalize_module("\n".join(blocks))


def external_script_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme == "https" and not parsed.username and parsed.port in (None, 443)
            and url.endswith(".js") and any(url.startswith(prefix) for prefix in EXTERNAL_SCRIPT_PREFIXES))


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
    check_url(url)
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
    with open_checked(url, timeout=45) as response:
        content = response.read(MAX_SCRIPT_BYTES + 1)
    validate_script(content, url, previous)
    return content


def mirror_scripts() -> list[str]:
    """Mirror every remote script and rewrite modules to the repository copy."""
    script_dir = ROOT / "Module/Scripts"
    manifest_path = script_dir / "manifest.json"
    manifest: dict[str, dict[str, str]] = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    changed: list[str] = []
    for relative in SOURCES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        urls = list(dict.fromkeys(re.findall(r"script-path=(https?[^,\s]+)", text)))
        # Local mirror URLs are already controlled files; only fetch upstream URLs.
        urls = [url for url in urls if not url.startswith(LOCAL_SCRIPT_BASE)]
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
        checked = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        if checked.returncode:
            raise RuntimeError(f"JavaScript syntax error: {filename}\n{checked.stderr[:1000]}")
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            raise RuntimeError(f"manifest hash mismatch: {filename}")
        expected_files.add(filename)

    for module in sorted((ROOT / "Module").glob("**/*.sgmodule")):
        content = module.read_text(encoding="utf-8")
        validate_source(content, module.as_posix())
        for url in re.findall(r"script-path=(https?[^,\s]+)", content):
            if not url.startswith(local_prefix) and not external_script_allowed(url):
                raise RuntimeError(f"unmirrored script in {module}: {url}")
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


def update_staged() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--validate-only":
        validate_repository()
        print("Module validation passed.")
        return 0
    changed = []
    failures = {}
    for relative, url in SOURCES.items():
        path = ROOT / relative
        try:
            content = fetch(url)
            if write(path, content): changed.append(relative)
        except Exception as exc:
            if not path.exists():
                raise
            validate_source(path.read_text(encoding="utf-8"), relative)
            failures[relative] = f"{type(exc).__name__}: {exc}"
    for relative, url in AD_SOURCES.items():
        path = ROOT / relative
        try:
            content = normalize_module(fetch(url))
            if write(path, content): changed.append(relative)
        except Exception as exc:
            if not path.exists():
                raise
            validate_source(path.read_text(encoding="utf-8"), relative)
            failures[relative] = f"{type(exc).__name__}: {exc}"
    if failures:
        print("Retained previous versions for failed sources:")
        for relative, reason in failures.items():
            print(f"::warning::{relative}: {reason}")
    goofish_path = "Module/AdBlock/goofish.sgmodule"
    if write(ROOT / goofish_path, convert_goofish(fetch_text(GOOFISH_SOURCE))):
        changed.append(goofish_path)
    changed.extend(mirror_scripts())
    for relative, content in (("Module/18+/18+-recommended.sgmodule", aggregate_18()), ("Module/Tools/Tools-recommended.sgmodule", aggregate_tools()), ("Module/AdBlock/AdBlock-recommended.sgmodule", aggregate_adblock())):
        if write(ROOT / relative, content): changed.append(relative)
    validate_repository()
    print("Updated: " + ", ".join(changed) if changed else "No module source changes.")
    return 0


def main() -> int:
    global ROOT
    if sys.argv[1:] == ["--validate-only"]:
        return update_staged()
    original = ROOT
    # No source download, validation failure, or aggregate error touches the live tree.
    with tempfile.TemporaryDirectory(prefix="surge-modules-") as directory:
        staged = Path(directory)
        shutil.copytree(original / "Module", staged / "Module")
        try:
            ROOT = staged
            update_staged()
        finally:
            ROOT = original
        for path in sorted((staged / "Module").rglob("*")):
            if path.is_file():
                target = original / path.relative_to(staged)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() or target.read_bytes() != path.read_bytes():
                    shutil.copyfile(path, target)
        for path in (original / "Module/Scripts").glob("*.js"):
            if not (staged / path.relative_to(original)).exists():
                path.unlink()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
