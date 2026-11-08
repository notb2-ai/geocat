#!/usr/bin/env python3
"""Lossless protobuf category filtering and bounded downloads for GeoCat.

Standard-library only; for v2rayNG, preserve the output filename geosite.dat.
Source: pinned latest RunetFreedom release and SHA-256 digest from GitHub API.
"""
from __future__ import annotations

import hashlib
from email.utils import parsedate_to_datetime
import math
import os
from pathlib import Path
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import http.client
import socket
import time

RELEASE_API = "https://api.github.com/repos/runetfreedom/russia-v2ray-rules-dat/releases/latest"
MAX_SOURCE_BYTES = 160_000_000
SOCKET_TIMEOUT = 60
MAX_ATTEMPTS = 3
RETRY_DELAYS = (10, 30)
METADATA_BUDGET = 120
DATABASE_BUDGET = 240


def retry_delay(error: Exception, attempt: int) -> int | None:
    """Respect server rate-limit delays; never retry ordinary permission errors."""
    delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
    if not isinstance(error, urllib.error.HTTPError):
        return delay
    headers = error.headers or {}
    retry_after = headers.get("Retry-After", "")
    exhausted = headers.get("X-RateLimit-Remaining") == "0"
    limited = error.code == 429 or (error.code == 403 and
        (exhausted or bool(retry_after) or "rate limit" in str(error.reason).lower()))
    if error.code == 403 and not limited:
        # Secondary limits can be reported only in the JSON body, with HTTP Forbidden.
        try:
            limited = "rate limit" in (error.read(4096) or b"").decode("utf-8", errors="replace").lower()
        except OSError:
            pass
    if not limited and error.code not in (408, 500, 502, 503, 504):
        return None
    waits = []
    if retry_after:
        try:
            waits.append(int(retry_after) if retry_after.isdigit() else
                         math.ceil(parsedate_to_datetime(retry_after).timestamp() - time.time()))
        except (ValueError, TypeError, OverflowError):
            pass
    if exhausted:
        reset = headers.get("X-RateLimit-Reset", "")
        if reset.isdigit():
            waits.append(math.ceil(int(reset) - time.time()) + 1)
    if limited and not waits:
        waits.append(60)
    return max(delay, *waits) if waits else delay


def download(url: str, max_bytes: int) -> bytes:
    """Download with scoped API auth, bounded retries and per-file diagnostics."""
    target = urllib.parse.urlsplit(url)
    github_api = target.scheme == "https" and target.netloc.lower() == "api.github.com"
    label = "GitHub API" if github_api else (target.path.rsplit("/", 1)[-1] or "download")
    token = os.environ.get("GITHUB_TOKEN", "").strip() if github_api else ""
    if github_api:
        print(f"GitHub API authentication: {'GITHUB_TOKEN' if token else 'anonymous'}", flush=True)
    budget = METADATA_BUDGET if max_bytes <= 1_000_000 else DATABASE_BUDGET
    deadline = time.monotonic() + budget
    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.monotonic()
        try:
            remaining = deadline - started
            if remaining <= 0:
                raise TimeoutError(f"Download exceeded {budget}s retry budget")
            req = urllib.request.Request(url, headers={"User-Agent": "GeoCat-Builder/2.0"})
            if github_api:
                req.add_header("Accept", "application/vnd.github+json")
                if token:
                    # urllib must not copy credentials to redirects or release/CDN hosts.
                    req.add_unredirected_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=min(SOCKET_TIMEOUT, remaining)) as resp:
                chunks, total, next_log = [], 0, 16_000_000
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Download exceeded {budget}s retry budget")
                    chunk = resp.read(min(1_048_576, max_bytes + 1 - total))
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Download exceeded {budget}s retry budget")
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"{label}: remote file exceeds {max_bytes} bytes")
                    if total >= next_log:
                        print(f"{label}: downloaded {total:,} bytes ({time.monotonic()-started:.1f}s)", flush=True)
                        next_log += 16_000_000
                return b"".join(chunks)
        except (urllib.error.URLError, TimeoutError, socket.timeout,
                http.client.IncompleteRead, ConnectionError) as exc:
            detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            delay = retry_delay(exc, attempt)
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            if delay is None:
                print(f"{label}: {detail}; permanent error, not retried", flush=True)
                raise
            if attempt == MAX_ATTEMPTS:
                raise OSError(f"{label}: download failed after {attempt} attempts ({detail})") from exc
            if time.monotonic() + delay >= deadline:
                raise OSError(f"{label}: {detail}; retry needs {delay}s, beyond remaining download budget") from exc
            print(f"{label}: temporary download error ({detail}); retry {attempt+1}/{MAX_ATTEMPTS} in {delay}s", flush=True)
            time.sleep(delay)
    raise AssertionError("Unreachable")


def varint_read(buf: bytes, pos: int, end: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if pos >= end:
            raise ValueError("Truncated protobuf varint")
        byte = buf[pos]
        pos += 1
        if shift == 63 and byte > 1:
            raise ValueError("Protobuf varint overflow")
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
        if number == 0 or number > 0x1fffffff:
            raise ValueError("Invalid protobuf field number")
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
