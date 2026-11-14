"""Persistent category selection shared by manual and scheduled builds."""
from pathlib import Path
import re

from scripts.build_geosite_lite import AGGREGATE_CODE

FILES = {'geosite.dat': 'geosite-categories.txt', 'geoip.dat': 'geoip-categories.txt'}
MANUAL_DOMAINS_FILE = 'geocat-ru-domains.txt'

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
        if kind == 'geosite' and token == AGGREGATE_CODE:
            raise ValueError(f'{kind}: {token} is generated automatically')
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


def parse_domains(text):
    domains = []
    for token in re.split(r'[\s,]+', text.strip().lower()):
        if not token:
            continue
        domain = token.removeprefix('domain:')
        try:
            domain = domain.encode('idna').decode('ascii').removesuffix('.')
        except UnicodeError as exc:
            raise ValueError(f'Invalid domain: {token!r}') from exc
        labels = domain.split('.')
        if (len(domain) > 253 or len(labels) < 2 or labels[-1].isdigit()
                or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                       for label in labels)):
            raise ValueError(f'Invalid domain: {token!r}')
        domains.append(domain)
    return tuple(dict.fromkeys(domains))


def manual_domains(path, add, remove):
    try:
        current = parse_domains(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        current = ()
    additions, removals = parse_domains(add), set(parse_domains(remove))
    overlap = removals.intersection(additions)
    if overlap:
        raise ValueError(f'Domains both added and removed: {sorted(overlap)}')
    return tuple(dict.fromkeys(domain for domain in (*current, *additions) if domain not in removals))


def render_catalog(readme, selected, domains):
    start, end = '<!-- categories:start -->', '<!-- categories:end -->'
    if readme.count(start) != 1 or readme.count(end) != 1 or readme.index(start) >= readme.index(end):
        raise ValueError('README: missing or ambiguous category markers')
    lines = ['']
    for name, title in [('geosite.dat', 'GeoSite'), ('geoip.dat', 'GeoIP')]:
        names = selected[name]
        lines += ['<details>', f'<summary>{title} — категорий: {len(names)} — показать список</summary>',
                  '', '```text', *names, '```', '', '</details>', '']
    domain_list = ['```text', *domains, '```'] if domains else ['Ручных доменов пока нет.']
    lines += ['<details>', f'<summary>Ручные домены geocat-ru — {len(domains)}</summary>',
              '', *domain_list, '', '</details>', '']
    return readme.split(start)[0] + start + '\n'.join(lines) + end + readme.split(end)[1]
