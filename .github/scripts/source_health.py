"""Capture public upstream fetch evidence in a per-run directory."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def body_lines(text: str) -> list[str]:
    return [line.strip() for line in text.lstrip("\ufeff").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "//", ";", "!"))]


def validate_response(text: str) -> None:
    if not text.strip():
        raise ValueError("empty upstream response")
    start = text.lstrip("\ufeff \t\r\n")[:1024].lower()
    if start.startswith(("{", "[")):
        json.loads(text.lstrip("\ufeff"))
        return
    if re.search(r"<(?:!doctype\s+html|html\b|head\b|body\b)", start):
        raise ValueError("HTML upstream response")


def write_event(url: str, status: str, text: str | None = None,
                error: str | None = None) -> None:
    directory = os.environ.get("RULE_AUDIT_DIR")
    if not directory:
        return
    root = Path(directory)
    events = root / "events"
    events.mkdir(parents=True, exist_ok=True)
    event = {"url": safe_url(url), "status": status,
             "fetched_at": datetime.now(timezone.utc).isoformat()}
    if text is not None:
        data = text.encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        lines = body_lines(text)
        body = "\n".join(sorted(set(lines))).encode("utf-8")
        event.update(sha256=digest, bytes=len(data), non_comment_lines=len(lines),
                     body_sha256=hashlib.sha256(body).hexdigest())
        sources = root / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        url_digest = hashlib.sha256(safe_url(url).encode("utf-8")).hexdigest()
        relative = Path("sources") / f"{url_digest}-{digest}.txt"
        # Each event has a separate temporary file, including concurrent calls.
        temporary = root / (str(relative) + f".{uuid4().hex}.tmp")
        temporary.write_bytes(data)
        temporary.replace(root / relative)
        event["content_file"] = str(relative)
    if error:
        event["error"] = error
    event_path = events / f"{uuid4().hex}.json"
    temporary = event_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(event_path)


def record_validation_failure(url: str, reason: str) -> None:
    write_event(url, "invalid", error=reason)


def record_source(function=None, *, url: str | None = None):
    def decorate(fetch):
        @wraps(fetch)
        def recorded(*args, **kwargs):
            source_url = url or kwargs.get("url") or args[0]
            response = None
            try:
                response = fetch(*args, **kwargs)
                validate_response(response)
            except Exception as error:
                # Exception strings may embed authentication or query values.
                reason = type(error).__name__
                code = getattr(error, "code", None)
                if isinstance(code, int):
                    reason += f" HTTP {code}"
                write_event(source_url, "failed", text=response, error=reason)
                raise
            write_event(source_url, "success", text=response)
            return response
        return recorded
    return decorate(function) if function else decorate


def finalize(directory: Path) -> dict:
    events = [json.loads(path.read_text(encoding="utf-8"))
              for path in sorted((directory / "events").glob("*.json"))]
    events.sort(key=lambda item: (item["url"], item["fetched_at"], item["status"]))
    successes = [event for event in events if event["status"] == "success"]
    failures = [event for event in events if event["status"] != "success"]
    digests = defaultdict(set)
    for event in successes:
        if event["non_comment_lines"]:
            digests[event["body_sha256"]].add(event["url"])
    identical = [sorted(urls) for _, urls in sorted(digests.items()) if len(urls) > 1]
    report = {"version": 1, "fetch_calls": len(events),
              "successful_calls": len(successes), "failed_or_invalid_calls": len(failures),
              "identical_body_url_groups": identical, "events": events}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "source-health.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["## Upstream fetch evidence", "",
             f"Recorded {len(events)} calls, {len(successes)} successful responses, "
             f"{len(failures)} failed or invalid responses.", "",
             "Success describes retrieval. Rule parsing and category review are checked separately.",
             "Identical bodies identify matching data and do not establish independent maintenance.", ""]
    for event in failures:
        lines.append(f"- {event['status']} {event['url']} ({event.get('error', 'unknown')})")
    if identical:
        lines.extend(["", "Matching bodies across URLs", ""])
        lines.extend("- " + " | ".join(urls) for urls in identical)
    if not events:
        lines.append("No upstream calls were recorded for this run.")
    if failures:
        print(f"::warning::{len(failures)} upstream calls failed or returned invalid data; see source-health.json")
    summary = "\n".join(lines) + "\n"
    (directory / "source-health.md").write_text(summary, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
    print(summary)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--directory", default=os.environ.get("RULE_AUDIT_DIR"))
    record = commands.add_parser("record-file")
    record.add_argument("url")
    record.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "finalize":
        if not args.directory:
            parser.error("set RULE_AUDIT_DIR or provide --directory")
        finalize(Path(args.directory))
    else:
        @record_source(url=args.url)
        def read_file():
            return args.path.read_text(encoding="utf-8-sig")
        read_file()


if __name__ == "__main__":
    main()
