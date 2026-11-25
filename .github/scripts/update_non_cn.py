"""Maintain an independent domain classification, never the complement of CN IPs."""
import json
import os
import re
from itertools import product
from pathlib import Path
from update_rules import fetch
from update_media_rules import compact, covering_suffix, validate_snapshot
from validate_rule_files import strip_comment, validate_rule_line, validate_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'Rule' / 'NonCN.list'
SNAPSHOT = ROOT / '.github' / 'non-cn-source-snapshot.json'
SOURCE = 'https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/geolocation-!cn.list'
MINIMUM = 20_000


# Expand only anchored literal sequences, finite character classes and literal
# alternatives. Bound each expansion to keep broad upstream patterns reviewable.
TOKEN = re.compile(r'([a-z0-9-]+|\\\.|\[(?:[a-z0-9]|[a-z0-9]-[a-z0-9])+\]|\([a-z0-9-]+(?:\|[a-z0-9-]+)+\))')


def expand_regex(pattern):
    if pattern.startswith(r'(^|\.)'):
        kind, body = 'DOMAIN-SUFFIX', pattern[6:]
    elif pattern.startswith('^'):
        kind, body = 'DOMAIN', pattern[1:]
    else:
        return set()
    if not body.endswith('$'):
        return set()
    body = body[:-1]
    choices = ['']
    while body:
        match = TOKEN.match(body)
        if not match:
            return set()
        token = match[0]
        body = body[match.end():]
        if token.startswith('['):
            ranges = re.findall(r'([a-z0-9])-([a-z0-9])', token)
            if any(start > end or start.isdigit() != end.isdigit() for start, end in ranges):
                return set()
            variants = [char for char in 'abcdefghijklmnopqrstuvwxyz0123456789'
                        if re.fullmatch(token, char)]
        elif token.startswith('('):
            variants = token[1:-1].split('|')
        else:
            variants = [token.replace(r'\.', '.')]
        if not variants or len(choices) * len(variants) > 32:
            return set()
        choices = [a + b for a, b in product(choices, variants)]
    if not all(re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', d) for d in choices):
        return set()
    return {(kind, domain) for domain in choices}


def build(text):
    rules = set()
    regex_review = {}
    expanded = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if line.startswith('DOMAIN-REGEX,') and line.removeprefix('DOMAIN-REGEX,').strip():
            pattern = line.split(',', 1)[1]
            entries = expand_regex(pattern)
            expanded.update(entries)
            regex_review[pattern] = sorted(domain for _, domain in entries)
            continue
        canonical, kind, value = validate_rule_line(TARGET, number, line)
        if kind not in {'DOMAIN', 'DOMAIN-SUFFIX'} or len(canonical.split(',')) != 2:
            raise RuntimeError(f'NonCN source format changed at line {number}')
        rules.add((kind, value))
    if regex_review:
        suffixes = {domain for kind, domain in rules if kind == 'DOMAIN-SUFFIX'}
        covered = {}
        for pattern, entries in regex_review.items():
            body = pattern.removeprefix(r'(^|\.)')
            # A literal terminal suffix is mandatory in a branch-free pattern.
            tail = re.search(r'(?:\\\.[a-z0-9-]+)+\$$', body)
            if not entries and tail and '|' not in body:
                domain = tail[0][2:-1].replace(r'\.', '.')
                parent = covering_suffix(domain, suffixes)
                if parent:
                    covered[pattern] = parent
        pending = sum(not entries for entries in regex_review.values()) - len(covered)
        print(f'NonCN: {sum(bool(v) for v in regex_review.values())} regexes expanded, {len(covered)} covered by suffix, {pending} need coverage review')
        audit = os.environ.get('RULE_AUDIT_DIR')
        if audit:
            path = Path(audit) / 'non-cn-regex-review.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'expansions': regex_review, 'covered_by_suffix': covered}, indent=2, sort_keys=True) + '\n')
    if len(rules) < MINIMUM:
        raise RuntimeError(f'NonCN source unexpectedly small: {len(rules)}')
    output_rules = compact(rules | expanded)
    output = '\n'.join([
        '# NAME: NonCN', '# FORMAT: Surge Rule Set',
        f'# SOURCE: {SOURCE}', f'# RULE COUNT: {len(output_rules)}',
        '# NOTE: Maintained domain classification, not the complement of CN/IP ranges.',
        '# ORDER: Specific services and domestic DIRECT rules precede this broad Proxy set.',
        '', *[f'{kind},{value}' for kind, value in sorted(output_rules)], ''])
    validate_text(TARGET, output)
    return output, {'source': len(rules), 'output': len(output_rules)}


def main():
    previous = TARGET.read_text() if TARGET.exists() else ''
    if previous:
        validate_text(TARGET, previous)
    output, counts = build(fetch(SOURCE))
    if SNAPSHOT.exists():
        snapshot = json.loads(SNAPSHOT.read_text())
        if snapshot.get('version') != 1:
            raise RuntimeError('unsupported NonCN snapshot version')
        validate_snapshot(snapshot['counts'], counts)
    if previous:
        validate_snapshot({'output': validate_text(TARGET, previous)['rules']}, counts)
    if output != previous:
        TARGET.write_text(output, encoding='utf-8')
    SNAPSHOT.write_text(json.dumps({'version': 1, 'counts': counts}, indent=2, sort_keys=True) + '\n')
    print(f'NonCN: {counts["source"]} source entries -> {counts["output"]} rules')


if __name__ == '__main__':
    main()
