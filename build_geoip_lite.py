#!/usr/bin/env python3
"""Build a verified GeoIPList with selected RunetFreedom categories.

GeoIPList and GeoSiteList share the same protobuf entry/code envelope.
The existing geosite subset builder copies encoded entries byte-for-byte;
reusing its parser/filter avoids schema-specific data loss.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_geosite_lite import (
    RELEASE_API,
    MAX_SOURCE_BYTES,
    atomic_write,
    download,
    protobuf_fields,
    trim,
    varint_read,
)


def verify_geoip(dat: bytes, wanted) -> dict[str, int]:
    """Validate selected IPv4/IPv6 CIDRs without altering encoded entries."""
    from build_geosite_lite import parse_geosites
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional full RunetFreedom geoip.dat input")
    parser.add_argument("--output", type=Path, default=Path("geoip.dat"))
    args = parser.parse_args()
    if args.input:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Input and output must differ")
        source = args.input.read_bytes()
        if len(source) > MAX_SOURCE_BYTES:
            raise ValueError("Input is too large")
        metadata = {"origin_file": str(args.input)}
    else:
        release = json.loads(download(RELEASE_API, 1_000_000))
        assets = {asset["name"]: asset for asset in release["assets"]}
        file_asset = assets["geoip.dat"]
        source = download(file_asset["browser_download_url"], MAX_SOURCE_BYTES)
        digest = file_asset.get("digest") or ""
        if digest.startswith("sha256:"):
            expected = digest.split(":", 1)[1].lower()
        else:
            sums = download(assets["geoip.dat.sha256sum"]["browser_download_url"], 4096)
            expected = sums.decode().strip().split()[0].lower()
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError("RunetFreedom geoip.dat SHA-256 mismatch")
        metadata = {
            "origin_repo": "runetfreedom/russia-v2ray-rules-dat",
            "release_tag": release["tag_name"],
            "published_at": release.get("published_at"),
        }

    from category_config import read_categories
    wanted = read_categories(Path(__file__).with_name('geoip-categories.txt'), 'geoip')
    output, stats = trim(source, wanted)
    counts = verify_geoip(output, wanted)
    cidr_count = counts.get('private', 0)
    atomic_write(args.output, output)
    metadata.update({
        **stats,
        "geoip_private_cidr_count": cidr_count,
        "category_counts": counts,
        "rule_count": sum(counts.values()),
        "source_sha256": hashlib.sha256(source).hexdigest()
    })
    atomic_write(
        args.output.with_suffix(args.output.suffix + ".json"),
        (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode(),
    )
    print(f"OK: {args.output} {len(source):,} -> {len(output):,} bytes, {sum(counts.values())} CIDRs across {len(counts)} categories")
    print("SHA256:", stats["output_sha256"])


if __name__ == "__main__":
    main()


