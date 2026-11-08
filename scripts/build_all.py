#!/usr/bin/env python3
"""Check one upstream release, build both GeoCat databases, and report changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import time

from scripts.build_geosite_lite import (RELEASE_API, MAX_SOURCE_BYTES,
    atomic_write, download, parse_geosites, protobuf_fields, trim)
from scripts.build_geoip_lite import verify_geoip
from scripts.category_config import FILES, selections, render_catalog
from scripts.diff_inspector import diff_file, render_diffs

ROOT = Path(__file__).resolve().parent.parent

NAMES = ('geosite.dat', 'geoip.dat')
ORIGIN = 'runetfreedom/russia-v2ray-rules-dat'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').encode()

def fingerprint():
    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in ('build_all.py', 'build_geosite_lite.py', 'build_geoip_lite.py', 'category_config.py'):
        h.update(name.encode()); h.update((root / name).read_bytes())
    return h.hexdigest()

def read_json(path):
    try:
        result = json.loads(path.read_text())
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}

def validate(name, data, wanted):
    entries = parse_geosites(data)
    if set(entries) != set(wanted):
        raise ValueError(f'{name}: unexpected categories')
    counts = {}
    for code, payload in entries.items():
        counts[code] = sum(n == 2 and w == 2 for n, w, *_ in protobuf_fields(payload))
        if not counts[code]:
            raise ValueError(f'{name}: empty category {code}')
    if name == 'geoip.dat':
        verify_geoip(data, wanted)
    return counts

def expected_hash(asset, assets, name):
    digest = asset.get('digest') or ''
    if digest.startswith('sha256:'):
        value = digest[7:].lower()
    else:
        lines = download(assets[name + '.sha256sum']['browser_download_url'], 4096).decode().splitlines()
        values = [line.split()[0].lower() for line in lines
                  if len(line.split()) == 2 and line.split()[1].lstrip('*') == name]
        if len(values) != 1:
            raise ValueError(f'{name}: checksum file must name exactly one matching asset')
        value = values[0]
    if not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError(f'{name}: invalid upstream SHA-256')
    return value

def build_one(name, release, assets, outdir, build_hash, force=False, *, wanted):
    started = time.monotonic()
    asset = assets[name]
    expected = expected_hash(asset, assets, name)
    if not 0 < asset['size'] <= MAX_SOURCE_BYTES:
        raise ValueError(f'{name}: invalid asset size')
    path = outdir / name
    old_meta = read_json(outdir / 'metadata' / (name + '.json'))
    old = path.read_bytes() if path.exists() else b''
    old_hash = sha(old) if old else None
    reusable = (not force and old_meta.get('builder_sha256') == build_hash
                and old_meta.get('source_sha256') == expected
                and old_meta.get('source_bytes') == asset['size']
                and old_meta.get('source_asset_id') == asset['id']
                and old_meta.get('selected_categories') == list(wanted)
                and old_meta.get('output_sha256') == old_hash
                and old_meta.get('output_bytes') == len(old) and bool(old))
    if reusable:
        try:
            counts = validate(name, old, wanted)
        except (ValueError, IndexError, UnicodeError):
            reusable = False
    if reusable:
        print(f'{name}: source and verified local file unchanged; download skipped', flush=True)
        output = old
        meta = dict(old_meta)
    else:
        print(f'{name}: downloading {asset["size"]:,} bytes', flush=True)
        source = download(asset['browser_download_url'], MAX_SOURCE_BYTES)
        if len(source) != asset['size'] or sha(source) != expected:
            raise ValueError(f'{name}: upstream size or SHA-256 mismatch; refusing publication')
        output, stats = trim(source, wanted)
        counts = validate(name, output, wanted)
        meta = dict(stats)
    meta.update(origin_repo=ORIGIN, release_tag=release['tag_name'],
                published_at=release.get('published_at'), source_sha256=expected,
                source_asset_id=asset['id'], builder_sha256=build_hash,
                category_counts=counts, rule_count=sum(counts.values()))
    if name == 'geoip.dat':
        meta['geoip_private_cidr_count'] = counts.get('private', 0)
    changed = output != old
    state = 'updated' if changed else ('source_updated' if old_meta.get('release_tag') != release['tag_name'] else 'unchanged')
    row = dict(file=name, state=state, previous_release=old_meta.get('release_tag'),
               release=release['tag_name'], previous_sha256=old_hash,
               sha256=sha(output), bytes=len(output), rules=sum(counts.values()),
               download_skipped=reusable, seconds=round(time.monotonic()-started, 3))
    print(f'{name}: {state}; release {row["previous_release"]} -> {row["release"]}; '
          f'{len(output):,} bytes; SHA256 {row["sha256"]}; {row["seconds"]}s', flush=True)
    return output, meta, row

LAST_CHANGE_PREFIX = '**Последнее изменение правил:** '

def last_change_line(previous_status, diffs, checked_at):
    changes = []
    labels = {'geosite.dat': 'GeoSite', 'geoip.dat': 'GeoIP'}
    for diff in diffs:
        if diff['state'] != 'changed':
            continue
        counts = []
        if diff['added']:
            counts.append(f"+{diff['added']}")
        if diff['removed']:
            counts.append(f"−{diff['removed']}")
        changes.append(f"{labels[diff['file']]} {' / '.join(counts)}")
    if not changes:
        return next((line for line in previous_status.splitlines()
                     if line.startswith(LAST_CHANGE_PREFIX)), '')
    label = ' · '.join([checked_at, *changes])
    repo = os.environ.get('GITHUB_REPOSITORY')
    run_id = os.environ.get('GITHUB_RUN_ID')
    if repo and run_id:
        server = os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')
        label = f'[{label}]({server}/{repo}/actions/runs/{run_id})'
    return LAST_CHANGE_PREFIX + label

def render_report(report, diffs=(), previous_status=''):
    labels = {'updated': '🆕 Обновлён', 'source_updated': '✅ Проверен — изменений нет', 'unchanged': '✅ Проверен — изменений нет'}
    lines = ['# GeoCat — статус обновлений', '',
             f'Последняя успешная проверка: **{report["checked_at_moscow"]}**.', '',
             '| Файл | Статус |',
             '|---|---|']
    for r in report['files']:
        lines.append(f'| {r["file"]} | {labels[r["state"]]} |')
    last_change = last_change_line(previous_status, diffs, report['checked_at_moscow'])
    if last_change:
        lines.extend(['', last_change])
    lines.extend(render_diffs(diffs))
    return '\n'.join(lines) + '\n'


def run(outdir, force=False, config_dir=None, changes=None):
    config_dir = Path(config_dir) if config_dir is not None else ROOT / 'config'
    selected = selections(config_dir, changes)
    status_path = outdir / 'STATUS.md'
    previous_status = status_path.read_text(encoding='utf-8') if status_path.exists() else ''
    readme_path = outdir / 'README.md'
    readme = render_catalog(readme_path.read_text(encoding='utf-8'), selected) if readme_path.exists() else None
    started = time.monotonic()
    print('Checking latest RunetFreedom release once for both databases...', flush=True)
    release = json.loads(download(RELEASE_API, 1_000_000))
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'[A-Za-z0-9._-]+', release['tag_name']):
        raise ValueError('Invalid release')
    assets = {a['name']: a for a in release['assets']}
    if len(assets) != len(release['assets']):
        raise ValueError('Duplicate release asset names')
    missing = [name for name in NAMES if name not in assets]
    if missing:
        raise ValueError(f'Upstream release {release["tag_name"]} is incomplete: missing {", ".join(missing)}')
    for name in NAMES:
        if assets[name].get('state', 'uploaded') != 'uploaded':
            raise ValueError(f'Upstream release {release["tag_name"]}: {name} is not fully uploaded')
    build_hash = fingerprint()
    print(f'Pinned upstream release: {release["tag_name"]}', flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(build_one, n, release, assets, outdir, build_hash, force, wanted=selected[n]) for n in NAMES]
        results = [f.result() for f in futures]
    # Observe-only: diff errors do not block verified database publication.
    # Run before writing outputs so existing files remain the baseline.
    diffs = []
    for name, (output, _meta, _row) in zip(NAMES, results):
        try:
            path = outdir / name
            previous = path.read_bytes() if path.exists() else b''
            diffs.append(diff_file(name, previous, output))
        except Exception as exc:
            print(f'::warning::{name}: Diff Inspector unavailable: {type(exc).__name__}', flush=True)
            diffs.append({'file': name, 'state': 'unavailable'})
    # No output is written until BOTH databases have passed all validation.
    for name, (output, meta, _) in zip(NAMES, results):
        if not (outdir / name).exists() or (outdir / name).read_bytes() != output:
            atomic_write(outdir / name, output)
        atomic_write(outdir / 'metadata' / (name + '.json'), encoded(meta))
    for name, filename in FILES.items():
        atomic_write(config_dir / filename, ('\n'.join(selected[name]) + '\n').encode())
    if readme is not None:
        atomic_write(readme_path, readme.encode())
    now = datetime.now(timezone.utc)
    report = dict(checked_at=now.isoformat(timespec='seconds'),
                  checked_at_moscow=now.astimezone(timezone(timedelta(hours=3))).strftime('%d.%m.%Y %H:%M:%S МСК'),
                  release=release['tag_name'], seconds=round(time.monotonic()-started, 3),
                  files=[r[2] for r in results])
    atomic_write(outdir / 'metadata' / 'status.json', encoded(report))
    atomic_write(status_path, render_report(report, diffs, previous_status).encode())
    print(f'Both databases verified successfully in {report["seconds"]}s. Publication is the next workflow step.', flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    parser.add_argument('--force', action='store_true', help='Download and rebuild even when cached outputs match')
    parser.add_argument('--config-dir', type=Path, default=ROOT / 'config')
    for kind in ('geosite', 'geoip'):
        for operation in ('add', 'remove'):
            parser.add_argument(f'--{kind}-{operation}', default=os.environ.get(f'{kind}_{operation}'.upper(), ''))
    args = parser.parse_args()
    changes = {kind + '.dat': (getattr(args, kind + '_add'), getattr(args, kind + '_remove'))
               for kind in ('geosite', 'geoip')}
    try:
        run(args.output_dir, args.force, args.config_dir, changes)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')

if __name__ == '__main__':
    main()
