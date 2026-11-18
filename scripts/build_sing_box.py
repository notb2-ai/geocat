"""Compile the aggregate GeoCat GeoSite category for sing-box."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from scripts.build_geosite_lite import AGGREGATE_CODE, parse_geosites, protobuf_fields, varint_read


# Xray Domain.Type: Plain, Regex, RootDomain, Full.
DOMAIN_FIELDS = ("domain_keyword", "domain_regex", "domain_suffix", "domain")


def site_rule(entry):
    rule = {}
    for number, wire, start, end, _, _ in protobuf_fields(entry):
        if (number, wire) != (2, 2):
            continue
        domain = entry[start:end]
        kind, value = 0, ""
        for field, encoding, first, last, _, _ in protobuf_fields(domain):
            if (field, encoding) == (1, 0):
                kind, _ = varint_read(domain, first, last)
            elif (field, encoding) == (2, 2):
                value = domain[first:last].decode("utf-8")
        if kind >= len(DOMAIN_FIELDS) or not value:
            raise ValueError(f"Invalid GeoSite rule: {kind}, {value!r}")
        rule.setdefault(DOMAIN_FIELDS[kind], []).append(value)
    return rule


def build(root, compiler):
    entries = parse_geosites((root / "geosite.dat").read_bytes())
    if AGGREGATE_CODE not in entries:
        raise ValueError(f"Missing GeoSite category: {AGGREGATE_CODE}")
    rule = site_rule(entries[AGGREGATE_CODE])
    if not rule:
        raise ValueError(f"Empty rule set: {AGGREGATE_CODE}")

    output = root / "sing-box"
    filename = f"{AGGREGATE_CODE}.srs"
    with TemporaryDirectory(dir=root) as directory:
        staging = Path(directory)
        source = staging / "rules.json"
        target = staging / filename
        # Version 2 supports all emitted fields and is readable since sing-box 1.10.
        source.write_text(json.dumps({"version": 2, "rules": [rule]}), encoding="utf-8")
        subprocess.run([compiler, "rule-set", "compile", "--output", str(target), str(source)], check=True)
        if not target.stat().st_size:
            raise ValueError(f"Empty compiled rule set: {filename}")

        output.mkdir(exist_ok=True)
        target.replace(output / filename)
        for obsolete in output.glob("*.srs"):
            if obsolete.name != filename:
                obsolete.unlink()
    print(f"Compiled sing-box/{filename}")


if __name__ == "__main__":
    build(Path.cwd(), sys.argv[1])
