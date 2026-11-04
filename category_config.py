"""Persistent category selection shared by manual and scheduled builds."""
from pathlib import Path
import re

FILES = {'geosite.dat': 'geosite-categories.txt', 'geoip.dat': 'geoip-categories.txt'}

def read_categories(path, kind):
    result = parse(Path(path).read_text(encoding='utf-8'), kind)
    if not result:
        raise ValueError(f'{path}: empty category list')
    return result

def parse(text, kind):
    values = []
    for token in re.split(r'[\s,]+', text.strip().lower()):
        if not token:
            continue
        token = token.removeprefix(kind + ':')
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', token):
            raise ValueError(f'{kind}: invalid category {token!r}')
        if token not in values:
            values.append(token)
    return tuple(values)

def edit(current, add, remove, kind):
    additions, removals = parse(add, kind), parse(remove, kind)
    overlap = set(additions) & set(removals)
    if overlap:
        raise ValueError(f'{kind}: both added and removed: {sorted(overlap)}')
    # Removing an already absent category is an idempotent no-op.
    result = tuple(dict.fromkeys(x for x in (*current, *additions) if x not in removals))
    if not result:
        raise ValueError(f'{kind}: category selection cannot be empty')
    return result

def selections(root, changes=None):
    changes = changes or {}
    result = {}
    for name, filename in FILES.items():
        kind = name.removesuffix('.dat')
        current = read_categories(Path(root) / filename, kind)
        add, remove = changes.get(name, ('', ''))
        result[name] = edit(current, add, remove, kind)
    return result

def render_catalog(readme, selected):
    start, end = '<!-- categories:start -->', '<!-- categories:end -->'
    if readme.count(start) != 1 or readme.count(end) != 1 or readme.index(start) >= readme.index(end):
        raise ValueError('README: missing or ambiguous category markers')
    lines = ['']
    for name, title in [('geosite.dat', 'GeoSite'), ('geoip.dat', 'GeoIP')]:
        names = selected[name]
        lines += ['<details>', f'<summary>{title} — категорий: {len(names)} — показать список</summary>',
                  '', '```text', *names, '```', '', '</details>', '']
    return readme.split(start)[0] + start + '\n'.join(lines) + end + readme.split(end)[1]
