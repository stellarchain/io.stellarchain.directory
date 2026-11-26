"""Validate directory.csv and generate the static JSON API."""

import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from strkey import address_type


ROOT = Path(__file__).resolve().parents[1]
NETWORKS = ("mainnet", "testnet", "futurenet")
BASE_COLUMNS = ["network", "address", "label", "source", "verification", "asset_code"]
COLUMNS = BASE_COLUMNS + ["role"]
SOURCES = {
    "circle", "community", "issuer", "project", "stellar", "stellar-expert",
    "stellar-ledger", "stellar-registry", "stellarchain",
}
VERIFICATION = {"unverified", "first_party", "sep1_domain", "stellarchain_verified"}
MAX_ASSETS = 20_000
MAX_ASSET_BYTES = 25 * 1024 * 1024
HEADERS = """\
/*
  Access-Control-Allow-Origin: *
  Access-Control-Expose-Headers: ETag
  X-Content-Type-Options: nosniff
  ! Cache-Control
  Cache-Control: public, max-age=60, must-revalidate
"""


def validate_label(label):
    if len(label) > 120 or not label.isprintable() or label != label.strip():
        raise ValueError("expected a printable label of 1–120 characters without surrounding spaces")


def make_record(network, address, asset_code):
    if not asset_code:
        return {"network": network, "address": address, "type": address_type(address)}

    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", asset_code):
        raise ValueError("expected an alphanumeric asset code of 1–12 characters")
    if address and address_type(address) != "account":
        raise ValueError("asset issuer must be an account")
    if not address and asset_code != "XLM":
        raise ValueError("only native XLM can have an empty asset issuer")

    return {
        "network": network,
        "id": f"{asset_code}-{address}" if address else "native",
        "type": "asset",
        "asset_code": asset_code,
        "issuer": address or None,
    }


def collect(source):
    records = {}
    with source.open(encoding="utf-8-sig", newline="") as contents:
        reader = csv.reader(contents, strict=True)
        try:
            header = next(reader, None)
            if header not in (BASE_COLUMNS, COLUMNS):
                raise ValueError(f"expected header {','.join(COLUMNS)}")
            for row in reader:
                if not row:
                    continue
                if len(row) != len(header):
                    raise ValueError(f"expected {len(header)} columns")
                network, address, label, origin, verification, asset_code, *roles = row
                role = roles[0] if roles else ""
                if network not in NETWORKS:
                    raise ValueError("expected mainnet, testnet, or futurenet")
                if origin not in SOURCES:
                    raise ValueError("unknown public source")
                if verification not in VERIFICATION:
                    raise ValueError(f"expected one of {', '.join(sorted(VERIFICATION))}")
                if not label and verification != "unverified":
                    raise ValueError("verification requires a label")
                record = make_record(network, address, asset_code)
                if role:
                    if role != "validator":
                        raise ValueError("expected validator or an empty role")
                    if record["type"] != "account":
                        raise ValueError("validator role requires a classic public key")
                    record["role"] = role
                if verification == "sep1_domain" and record["type"] != "account" and not record.get("issuer"):
                    raise ValueError("SEP-1 domain verification requires an account or asset issuer")
                if verification == "stellarchain_verified" and (
                    network, origin, record["type"]
                ) != ("mainnet", "stellarchain", "account"):
                    raise ValueError("StellarChain verification requires a StellarChain mainnet account")

                key = (network, "assets", record["id"]) if asset_code else (network, "addresses", address)
                if key in records:
                    raise ValueError("duplicate asset on the same network" if asset_code else "duplicate address on the same network")
                if label:
                    validate_label(label)
                    record["label"] = label
                record["source"] = origin
                record["verification"] = verification
                records[key] = record
        except (csv.Error, ValueError) as error:
            raise ValueError(f"{source.name}:{max(reader.line_num, 1)}: {error}") from error

    if not records:
        raise ValueError("the directory is empty")
    return records


def write_json(path, value):
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_ASSET_BYTES:
        raise ValueError(f"{path.name} exceeds the Cloudflare 25 MiB asset limit")
    path.write_bytes(payload)
    return payload


def write_collection(network_dir, folder, filename, id_field, entries):
    item_dir = network_dir / folder
    item_dir.mkdir(parents=True)
    for entry in entries:
        write_json(item_dir / f"{entry[id_field]}.json", entry)

    directory = write_json(network_dir / filename, entries)
    return {
        "count": len(entries),
        "directory": f"/{network_dir.name}/{filename}",
        "lookup": f"/{network_dir.name}/{folder}/{{{id_field}}}.json",
        "bytes": len(directory),
        "sha256": hashlib.sha256(directory).hexdigest(),
    }


def build(source, output_dir):
    records = collect(source)
    networks = defaultdict(lambda: {"addresses": [], "assets": []})
    for (network, folder, _), record in sorted(records.items()):
        networks[network][folder].append(record)

    files = len(records) + sum(1 + bool(groups["assets"]) for groups in networks.values()) + 2
    if files > MAX_ASSETS:
        raise ValueError(f"{files:,} JSON files exceed the Cloudflare Free asset limit of {MAX_ASSETS:,}")

    with tempfile.TemporaryDirectory(prefix=".directory-", dir=output_dir.parent) as temp_dir:
        staging = Path(temp_dir) / "dist"
        manifest = {"networks": {}, "schema": "/schema.json"}
        for network, groups in networks.items():
            network_dir = staging / network
            summary = write_collection(network_dir, "addresses", "directory.json", "address", groups["addresses"])
            if groups["assets"]:
                summary["assets"] = write_collection(network_dir, "assets", "assets.json", "id", groups["assets"])
            manifest["networks"][network] = summary

        write_json(staging / "manifest.json", manifest)
        write_json(staging / "schema.json", json.loads((ROOT / "schema.json").read_text(encoding="utf-8")))
        (staging / "_headers").write_text(HEADERS, encoding="utf-8")
        (staging / "_redirects").write_text("/ /manifest.json 302\n", encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging.rename(output_dir)

    print(f"Built {len(records):,} directory entries in {files:,} JSON files")


if __name__ == "__main__":
    try:
        build(ROOT / "directory.csv", ROOT / "dist")
    except (OSError, ValueError) as error:
        sys.exit(f"Directory build failed: {error}")
