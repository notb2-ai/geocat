#!/usr/bin/env python3
"""Build a lossless category subset of RunetFreedom geosite.dat (Xray/V2Ray protobuf).

Standard-library only; for v2rayNG, preserve the output filename geosite.dat.
Source: pinned latest RunetFreedom release and SHA-256 digest from GitHub API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

RELEASE_API = "https://api.github.com/repos/runetfreedom/russia-v2ray-rules-dat/releases/latest"
MAX_SOURCE_BYTES = 160_000_000
CATEGORIES = (
    "ru-available-only-inside",
    "category-bank-ru",
    "category-ecommerce-ru",
    "category-retail-ru",
    "category-entertainment-ru",
    "yandex",
    "mailru-group",
    "category-ai-ru",
    "category-medicine-ru",
    "category-travel-ru",
    "megafon",
    "mts-ru",
    "rostelecom",
    "t2-ru",
    "category-public-tracker",  # existing tracker-block rule
)


def download(url: str, max_bytes: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GeoCat-Builder/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Remote file exceeds allowed {max_bytes} bytes: {url}")
    return data


def fetch_latest_release() -> tuple[bytes, dict]:
    release = json.loads(download(RELEASE_API, 1_000_000))
    assets = {a["name"]: a for a in release["assets"]}
    asset = assets["geosite.dat"]
    data = download(asset["browser_download_url"], MAX_SOURCE_BYTES)
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        expected = digest.partition(":")[2].lower()
    else:
        checksums = download(assets["geosite.dat.sha256sum"]["browser_download_url"], 4096).decode()
        expected = checksums.strip().split()[0].lower()
    actual = hashlib.sha256(data).hexdigest()
    if expected != actual:
        raise ValueError(f"Upstream SHA-256 mismatch: expected {expected}, got {actual}")
    return data, {
        "origin_repo": "runetfreedom/russia-v2ray-rules-dat",
        "release_tag": release["tag_name"],
        "published_at": release.get("published_at"),
        "source_sha256": actual,
    }


def varint_read(buf: bytes, pos: int, end: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if pos >= end:
            raise ValueError("Truncated protobuf varint")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, pos
    raise ValueError("Invalid protobuf varint")


def varint_write(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative varint")
    result = bytearray()
    while value >= 128:
        result.append((value & 0x7f) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def protobuf_fields(buf: bytes):
    """Yield (field_number, wire_type, value_start, value_end, whole_field_start, whole_field_end).

    Covers protobuf wire types used in Xray's common/geodata/geodat.proto.
    """
    pos, end = 0, len(buf)
    while pos < end:
        start = pos
        key, pos = varint_read(buf, pos, end)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("Protobuf field number 0")
        if wire == 2:
            size, pos = varint_read(buf, pos, end)
            value_start, value_end = pos, pos + size
            if value_end > end:
                raise ValueError("Truncated protobuf length-delimited field")
            pos = value_end
        elif wire == 0:
            value_start = pos
            _, pos = varint_read(buf, pos, end)
            value_end = pos
        elif wire in (1, 5):
            value_start = pos
            pos += 8 if wire == 1 else 4
            value_end = pos
            if pos > end:
                raise ValueError("Truncated fixed protobuf field")
        else:
            raise ValueError(f"Unsupported protobuf wire type: {wire}")
        yield number, wire, value_start, value_end, start, pos


def geosite_code(payload: bytes) -> str:
    codes = [payload[start:end].decode("utf-8").lower()
             for number, wire, start, end, _, _ in protobuf_fields(payload)
             if number == 1 and wire == 2]
    if len(codes) != 1 or not codes[0]:
        raise ValueError("Malformed GeoSite: expected exactly one nonempty code")
    return codes[0]


def parse_geosites(data: bytes) -> dict[str, bytes]:
    result = {}
    for number, wire, start, end, _, _ in protobuf_fields(data):
        if number != 1 or wire != 2:
            raise ValueError("Unexpected top-level GeoSiteList field")
        payload = data[start:end]
        code = geosite_code(payload)
        if code in result:
            raise ValueError(f"Duplicate GeoSite category: {code}")
        result[code] = payload
    if not result:
        raise ValueError("Empty GeoSiteList")
    return result


def trim(data: bytes, wanted: tuple[str, ...]) -> tuple[bytes, dict]:
    entries = parse_geosites(data)
    missing = [name for name in wanted if name not in entries]
    if missing:
        raise ValueError(f"Missing categories in RunetFreedom source: {', '.join(missing)}")
    out = bytearray()
    for code in wanted:
        payload = entries[code]  # original encoded GeoSite entry, unchanged byte-for-byte
        out += b"\x0a" + varint_write(len(payload)) + payload
    final = bytes(out)
    check = parse_geosites(final)
    if set(check) != set(wanted) or any(check[c] != entries[c] for c in wanted):
        raise AssertionError("Post-build verification failed: category contents differ")
    return final, {"source_categories": len(entries), "selected_categories": list(wanted),
                   "source_bytes": len(data), "output_bytes": len(final),
                   "output_sha256": hashlib.sha256(final).hexdigest()}


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".geosite-lite-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Local full RunetFreedom geosite.dat; otherwise download latest release")
    parser.add_argument("--output", type=Path, default=Path("geosite.dat"), help="Path of slim geosite.dat")
    parser.add_argument("--extra", action="append", default=[], help="Retain extra categories, e.g. --extra google or --extra cn")
    args = parser.parse_args()

    if args.input:
        data = args.input.read_bytes()
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("Input too large")
        source = {"origin_file": str(args.input), "source_sha256": hashlib.sha256(data).hexdigest()}
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Source and output paths must differ")
    else:
        data, source = fetch_latest_release()

    wanted = tuple(dict.fromkeys(CATEGORIES + tuple(x.strip().lower() for x in args.extra)))
    output, stats = trim(data, wanted)
    atomic_write(args.output, output)
    metadata = {**source, **stats}
    atomic_write(args.output.with_suffix(args.output.suffix + ".json"),
                 (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode())
    print(f"OK: {args.output}: {len(data):,} -> {len(output):,} bytes; "
          f"{100 * (1 - len(output) / len(data)):.1f}% smaller")
    print("Preserved categories:", ", ".join(wanted))
    print("SHA256:", stats["output_sha256"])


if __name__ == "__main__":
    main()
