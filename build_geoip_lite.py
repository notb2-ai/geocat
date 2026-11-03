#!/usr/bin/env python3
"""Build a verified GeoIPList containing only PRIVATE from RunetFreedom.

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


def verify_private_geoip(dat: bytes) -> int:
    """Check output is a one-entry, non-reverse PRIVATE GeoIPList with valid CIDRs."""
    entries = list(protobuf_fields(dat))
    if len(entries) != 1 or entries[0][0:2] != (1, 2):
        raise ValueError("Expected exactly one GeoIPList entry")
    _, _, start, end, _, _ = entries[0]
    entry = dat[start:end]
    codes = []
    count = 0
    for number, wire, start, end, _, _ in protobuf_fields(entry):
        if number == 1 and wire == 2:
            codes.append(entry[start:end].decode("utf-8").lower())
        elif number == 2 and wire == 2:
            cidr = entry[start:end]
            addresses, prefixes = [], []
            for fn, fw, vs, ve, _, _ in protobuf_fields(cidr):
                if fn == 1 and fw == 2:
                    addresses.append(cidr[vs:ve])
                elif fn == 2 and fw == 0:
                    val, _ = varint_read(cidr, vs, ve)
                    prefixes.append(val)
            if len(addresses) != 1 or len(prefixes) > 1:
                raise ValueError("Malformed GeoIP CIDR")
            prefix = prefixes[0] if prefixes else 0  # proto3 default
            if len(addresses[0]) not in (4, 16) or prefix > len(addresses[0]) * 8:
                raise ValueError("Invalid GeoIP CIDR prefix or IP")
            if prefix == 0:
                raise ValueError("Default route /0 is not allowed in PRIVATE")
            count += 1
        elif number == 3 and wire == 0:
            reversed_match, _ = varint_read(entry, start, end)
            if reversed_match:
                raise ValueError("Unexpected reverse_match in PRIVATE category")
    if codes != ["private"] or count == 0:
        raise ValueError("Output must contain non-empty PRIVATE GeoIP category only")
    return count


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

    output, stats = trim(source, ("private",))
    cidr_count = verify_private_geoip(output)
    atomic_write(args.output, output)
    metadata.update({
        **stats,
        "geoip_private_cidr_count": cidr_count,
        "source_sha256": hashlib.sha256(source).hexdigest()
    })
    atomic_write(
        args.output.with_suffix(args.output.suffix + ".json"),
        (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode(),
    )
    print(f"OK: {args.output} {len(source):,} -> {len(output):,} bytes, {cidr_count} private CIDRs")
    print("SHA256:", stats["output_sha256"])


if __name__ == "__main__":
    main()

