#!/usr/bin/env python3
"""Build a verified GeoIPList with selected RunetFreedom categories.

GeoIPList and GeoSiteList share the same protobuf entry/code envelope.
The existing geosite subset builder copies encoded entries byte-for-byte;
reusing its parser/filter avoids schema-specific data loss.
"""
from scripts.build_geosite_lite import parse_geosites, protobuf_fields, varint_read


def verify_geoip(dat: bytes, wanted) -> dict[str, int]:
    """Validate selected IPv4/IPv6 CIDRs without altering encoded entries."""
    entries = parse_geosites(dat)
    if set(entries) != set(wanted):
        raise ValueError("Unexpected GeoIP categories")
    counts = {}
    for code, entry in entries.items():
        count, reverse_flags = 0, []
        for number, wire, start, end, _, _ in protobuf_fields(entry):
            if number in (1, 2, 3) and wire != {1: 2, 2: 2, 3: 0}[number]:
                raise ValueError("Invalid GeoIP field type")
            if number == 2:
                cidr = entry[start:end]
                addresses, prefixes = [], []
                for fn, fw, vs, ve, _, _ in protobuf_fields(cidr):
                    if fn in (1, 2) and fw != {1: 2, 2: 0}[fn]:
                        raise ValueError("Invalid CIDR field type")
                    if fn == 1:
                        addresses.append(cidr[vs:ve])
                    elif fn == 2:
                        prefixes.append(varint_read(cidr, vs, ve)[0])
                if len(addresses) != 1 or len(prefixes) > 1:
                    raise ValueError("Malformed GeoIP CIDR")
                prefix = prefixes[0] if prefixes else 0
                if len(addresses[0]) not in (4, 16) or prefix > len(addresses[0]) * 8:
                    raise ValueError("Invalid GeoIP CIDR prefix or IP")
                if code == 'private' and prefix == 0:
                    raise ValueError("Default route /0 is not allowed in PRIVATE")
                count += 1
            elif number == 3:
                reverse_flags.append(varint_read(entry, start, end)[0])
        if len(reverse_flags) > 1 or any(v not in (0, 1) for v in reverse_flags):
            raise ValueError("Invalid reverse_match")
        if code == 'private' and any(reverse_flags):
            raise ValueError("Unexpected reverse_match in PRIVATE")
        if not count:
            raise ValueError(f"Empty GeoIP category: {code}")
        counts[code] = count
    return counts


def verify_private_geoip(dat: bytes) -> int:
    return verify_geoip(dat, ('private',))['private']
