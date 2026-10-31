"""Maintain an independent domain classification, never the complement of CN IPs."""
import json
from pathlib import Path
from update_rules import fetch
from update_media_rules import compact, validate_snapshot
from validate_rule_files import strip_comment, validate_rule_line, validate_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'Rule' / 'NonCN.list'
SNAPSHOT = ROOT / '.github' / 'non-cn-source-snapshot.json'
SOURCE = 'https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/geolocation-!cn.list'
MINIMUM = 20_000


def build(text):
    rules = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        canonical, kind, value = validate_rule_line(TARGET, number, line)
        if kind not in {'DOMAIN', 'DOMAIN-SUFFIX'} or len(canonical.split(',')) != 2:
            raise RuntimeError(f'NonCN source format changed at line {number}')
        rules.add((kind, value))
    if len(rules) < MINIMUM:
        raise RuntimeError(f'NonCN source unexpectedly small: {len(rules)}')
    output_rules = compact(rules)
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
