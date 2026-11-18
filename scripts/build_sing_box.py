"""Compile sing-box rule sets from the GeoCat databases staged for publication."""

from ipaddress import ip_network
import json
from pathlib import Path
import re
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


def ip_rule(entry):
    networks = []
    inverted = False
    for number, wire, start, end, _, _ in protobuf_fields(entry):
        if (number, wire) == (3, 0):
            inverted = bool(varint_read(entry, start, end)[0])
        elif (number, wire) == (2, 2):
            cidr = entry[start:end]
            address, prefix = b"", 0
            for field, encoding, first, last, _, _ in protobuf_fields(cidr):
                if (field, encoding) == (1, 2):
                    address = cidr[first:last]
                elif (field, encoding) == (2, 0):
                    prefix, _ = varint_read(cidr, first, last)
            networks.append(str(ip_network((address, prefix), strict=False)))

    rule = {"ip_cidr": networks} if networks else {}
    if inverted and rule:
        rule["invert"] = True
    return rule


def rule_sets(root):
    for kind, convert in (("geosite", site_rule), ("geoip", ip_rule)):
        for category, entry in parse_geosites((root / f"{kind}.dat").read_bytes()).items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", category):
                raise ValueError(f"Invalid {kind} category: {category!r}")
            name = category if kind == "geosite" and category == AGGREGATE_CODE else f"{kind}-{category}"
            rule = convert(entry)
            if not rule:
                raise ValueError(f"Empty rule set: {name}")
            yield name, rule


def build(root, compiler):
    output = root / "sing-box"
    with TemporaryDirectory(dir=root) as directory:
        staging = Path(directory)
        source = staging / "rules.json"
        compiled = []
        for name, rule in rule_sets(root):
            # Version 2 supports all emitted fields and is readable since sing-box 1.10.
            source.write_text(json.dumps({"version": 2, "rules": [rule]}), encoding="utf-8")
            target = staging / f"{name}.srs"
            subprocess.run([compiler, "rule-set", "compile", "--output", str(target), str(source)], check=True)
            if not target.stat().st_size:
                raise ValueError(f"Empty compiled rule set: {name}")
            compiled.append(target)

        output.mkdir(exist_ok=True)
        keep = {target.name for target in compiled}
        for target in compiled:
            target.replace(output / target.name)
        for obsolete in output.glob("*.srs"):
            if obsolete.name not in keep:
                obsolete.unlink()
    print(f"Compiled {len(compiled)} sing-box rule sets")


if __name__ == "__main__":
    build(Path.cwd(), sys.argv[1])
