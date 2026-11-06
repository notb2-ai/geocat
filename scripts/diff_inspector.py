"""Explain content changes between two GeoCat Xray GeoSite/GeoIP protobuf files.

Read-only, standard-library only; this tool does not resolve domains or change routes.
"""
from __future__ import annotations

from collections import Counter
from html import escape
from ipaddress import ip_address
from typing import Any

from scripts.build_geosite_lite import parse_geosites, protobuf_fields, varint_read

TYPE_NAMES = {0: 'keyword', 1: 'regexp', 2: 'domain', 3: 'full'}
MAX_DISPLAY_ITEMS = 4000
MAX_FIELD_LENGTH = 500


def _int_field(buf: bytes, begin: int, end: int) -> int:
    value, pos = varint_read(buf, begin, end)
    if pos != end:
        raise ValueError('Trailing bytes in protobuf varint')
    return value


def _text(buf: bytes) -> str:
    return buf.decode('utf-8', errors='strict')


def _unique_field(fields: list[tuple], number: int, wire: int, *, default: Any = None):
    items = [(a, b) for n, w, a, b, *_ in fields if n == number and w == wire]
    if len(items) > 1:
        raise ValueError(f'Duplicate protobuf field: {number}')
    if any(n == number and w != wire for n, w, *_ in fields):
        raise ValueError(f'Invalid wire type for field {number}')
    return items[0] if items else default


def _opaque_fields(buf: bytes, fields: list[tuple], known: set[int]) -> tuple:
    """Make unknown fields visible to the diff rather than silently ignoring them."""
    return tuple(sorted((n, w, buf[whole_start:whole_end].hex())
                        for n, w, _a, _b, whole_start, whole_end in fields if n not in known))


def _attribute(payload: bytes) -> tuple:
    fields = list(protobuf_fields(payload))
    key_span = _unique_field(fields, 1, 2)
    if key_span is None:
        raise ValueError('GeoSite attribute missing key')
    key = _text(payload[key_span[0]:key_span[1]])
    bool_span = _unique_field(fields, 2, 0)
    int_span = _unique_field(fields, 3, 0)
    if bool_span and int_span:
        raise ValueError('Conflicting GeoSite attribute value')
    if bool_span:
        value = ('bool', bool(_int_field(payload, *bool_span)))
    elif int_span:
        value = ('int', _int_field(payload, *int_span))
    else:
        value = ('none', None)
    return (key, *value, _opaque_fields(payload, fields, {1, 2, 3}))


def _geosite_items(entry: bytes) -> Counter:
    count = Counter()
    for n, w, start, end, *_ in protobuf_fields(entry):
        if n != 2:
            continue
        if w != 2:
            raise ValueError('GeoSite domain has invalid wire type')
        payload = entry[start:end]
        fields = list(protobuf_fields(payload))
        type_span = _unique_field(fields, 1, 0)
        kind = _int_field(payload, *type_span) if type_span else 0
        value_span = _unique_field(fields, 2, 2)
        if kind not in TYPE_NAMES or value_span is None:
            raise ValueError('Invalid GeoSite rule type or missing value')
        value = _text(payload[value_span[0]:value_span[1]])
        attrs = tuple(sorted(_attribute(payload[a:b]) for num, wire, a, b, *_ in fields
                             if num == 3 and wire == 2))
        if any(num == 3 and wire != 2 for num, wire, *_ in fields):
            raise ValueError('Invalid GeoSite attribute encoding')
        item = (kind, value, attrs, _opaque_fields(payload, fields, {1, 2, 3}))
        count[item] += 1
    return count


def _geoip_items(entry: bytes) -> Counter:
    count = Counter()
    fields = list(protobuf_fields(entry))
    rev_span = _unique_field(fields, 3, 0)
    reverse = bool(_int_field(entry, *rev_span)) if rev_span else False
    for n, w, start, end, *_ in fields:
        if n != 2:
            continue
        if w != 2:
            raise ValueError('GeoIP CIDR has invalid wire type')
        payload = entry[start:end]
        sub = list(protobuf_fields(payload))
        ip_span = _unique_field(sub, 1, 2)
        prefix_span = _unique_field(sub, 2, 0)
        if ip_span is None:
            raise ValueError('GeoIP CIDR missing IP')
        raw_ip = payload[ip_span[0]:ip_span[1]]
        address = ip_address(raw_ip)
        prefix = _int_field(payload, *prefix_span) if prefix_span else 0
        if prefix > address.max_prefixlen:
            raise ValueError('GeoIP CIDR invalid prefix')
        item = (str(address), prefix, reverse, _opaque_fields(payload, sub, {1, 2}))
        count[item] += 1
    return count


def diff_file(filename: str, old: bytes, new: bytes) -> dict:
    """Compare logical records, preserving category and duplicate-count changes."""
    if filename not in ('geosite.dat', 'geoip.dat'):
        raise ValueError('Unsupported database filename')
    if not old:
        return {'file': filename, 'state': 'no_baseline', 'added': 0, 'removed': 0, 'categories': []}
    if old == new:
        return {'file': filename, 'state': 'unchanged', 'added': 0, 'removed': 0, 'categories': []}
    previous, current = parse_geosites(old), parse_geosites(new)
    extract = _geosite_items if filename == 'geosite.dat' else _geoip_items
    categories, total_add, total_remove = [], 0, 0
    for category in dict.fromkeys((*current, *previous)):
        before = extract(previous[category]) if category in previous else Counter()
        after = extract(current[category]) if category in current else Counter()
        added, removed = after - before, before - after
        if not (added or removed):
            continue
        total_add += sum(added.values())
        total_remove += sum(removed.values())
        categories.append({'category': category,
                           'before': sum(before.values()), 'after': sum(after.values()),
                           'added': sorted(added.items(), key=lambda pair: repr(pair[0])),
                           'removed': sorted(removed.items(), key=lambda pair: repr(pair[0]))})
    return {'file': filename, 'state': 'changed' if categories else 'same_rules',
            'added': total_add, 'removed': total_remove, 'categories': categories}


def _display(item: tuple, filename: str) -> str:
    if filename == 'geoip.dat':
        address, prefix, reverse, unknown = item
        result = f'{address}/{prefix}' + (' [reverse]' if reverse else '')
        if unknown:
            result += ' [unknown protobuf fields: ' + repr(unknown) + ']'
        return result
    kind, value, attrs, unknown = item
    result = f'{TYPE_NAMES[kind]}:{value}'
    if attrs:
        descriptions = [f'{k}={v}' if typ == 'none' else f'{k}={typ}:{v}' for k, typ, v, _ in attrs]
        result += ' [attrs: ' + ', '.join(descriptions) + ']'
        if any(extra for _, _, _, extra in attrs):
            result += ' [unknown attribute fields: ' + repr(
                [(key, extra) for key, _, _, extra in attrs if extra]) + ']'
    if unknown:
        result += ' [unknown protobuf fields: ' + repr(unknown) + ']'
    return result


def _safe(s: str) -> str:
    if len(s) > MAX_FIELD_LENGTH:
        s = s[:MAX_FIELD_LENGTH] + '… [обрезано]'
    return escape(s, quote=True).replace('\n', '&#10;').replace('\r', '&#13;')


def render_diffs(diffs: list[dict]) -> list[str]:
    """Return Markdown lines for STATUS.md. No changes -> no extra section."""
    interesting = [d for d in diffs if d['state'] != 'unchanged']
    if not interesting:
        return []
    lines = ['', '## 🔍 Что изменилось', '']
    for d in interesting:
        name = d['file']
        state = d['state']
        if state == 'no_baseline':
            lines += [f'**' + chr(96) + name + chr(96) + '**: нет предыдущего файла для сравнения (первая сборка).', '']
            continue
        if state == 'unavailable':
            lines += [f'**' + chr(96) + name + chr(96) + '**: ⚠️ подробное сравнение недоступно; сборка баз выполнена штатно.', '']
            continue
        if state == 'same_rules':
            lines += [f'**' + chr(96) + name + chr(96) + '**: бинарный файл изменился, но состав правил не изменился.', '']
            continue
        lines += [f'**' + chr(96) + name + chr(96) + f'**: добавлено **{d["added"]}**, удалено **{d["removed"]}**.', '']
        shown = 0
        for category in d['categories']:
            plus = sum(n for _, n in category['added'])
            minus = sum(n for _, n in category['removed'])
            lines += [f'<details>',
                      f'<summary><code>{_safe(category["category"])}</code>: +{plus} / −{minus} (было {category["before"]}, стало {category["after"]})</summary>', '']
            for sign, items in (('➕', category['added']), ('➖', category['removed'])):
                for item, times in items:
                    if shown >= MAX_DISPLAY_ITEMS:
                        break
                    label = _safe(_display(item, name))
                    lines.append(f'- {sign} <code>{label}</code>' + (f' ×{times}' if times != 1 else ''))
                    shown += 1
            lines += ['', '</details>', '']
        omitted = sum(len(c['added']) + len(c['removed']) for c in d['categories']) - shown
        if omitted:
            lines += [f'⚠️ В отчёте скрыты ещё {omitted} уникальных записей из-за лимита вывода.', '']
    lines += ['Изменение типа или атрибутов правила отображается как удаление старой записи и добавление новой.', '']
    return lines
