"""Validate directory.csv and generate the static JSON API."""

import csv
import hashlib
import json
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from strkey import address_type


ROOT = Path(__file__).resolve().parents[1]
NETWORKS = ("mainnet", "testnet", "futurenet")
COLUMNS = ["network", "address", "label"]
MAX_ASSETS = 20_000
MAX_ASSET_BYTES = 25 * 1024 * 1024
HEADERS = """\
/*
  Access-Control-Allow-Origin: *
  X-Content-Type-Options: nosniff
  ! Cache-Control
  Cache-Control: public, max-age=60, must-revalidate
"""


def validate_label(label):
    if len(label) > 120 or not label.isprintable() or label != label.strip():
        raise ValueError("expected a printable label of 1–120 characters without surrounding spaces")


def collect(source):
    records = {}
    with source.open(encoding="utf-8-sig", newline="") as contents:
        reader = csv.reader(contents, strict=True)
        try:
            if next(reader, None) != COLUMNS:
                raise ValueError(f"expected header {','.join(COLUMNS)}")
            for row in reader:
                if not row:
                    continue
                if len(row) != len(COLUMNS):
                    raise ValueError(f"expected {len(COLUMNS)} columns")
                network, address, label = row
                if network not in NETWORKS:
                    raise ValueError("expected mainnet, testnet, or futurenet")
                kind = address_type(address)
                key = (network, address)
                if key in records:
                    raise ValueError("duplicate address on the same network")
                record = {"network": network, "address": address, "type": kind}
                if label:
                    validate_label(label)
                    record["label"] = label
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


def build(source, output_dir):
    records = collect(source)
    networks = defaultdict(list)
    for (network, _), record in sorted(records.items()):
        networks[network].append(record)

    files = len(records) + len(networks) + 1
    if files > MAX_ASSETS:
        raise ValueError(f"{files:,} JSON files exceed the Cloudflare Free asset limit of {MAX_ASSETS:,}")

    with tempfile.TemporaryDirectory(prefix=".directory-", dir=output_dir.parent) as temp_dir:
        staging = Path(temp_dir) / "dist"
        manifest = {"networks": {}}
        for network, entries in networks.items():
            network_dir = staging / network
            address_dir = network_dir / "addresses"
            address_dir.mkdir(parents=True)
            for entry in entries:
                write_json(address_dir / f"{entry['address']}.json", entry)

            directory = write_json(network_dir / "directory.json", entries)
            manifest["networks"][network] = {
                "count": len(entries),
                "directory": f"/{network}/directory.json",
                "lookup": f"/{network}/addresses/{{address}}.json",
                "bytes": len(directory),
                "sha256": hashlib.sha256(directory).hexdigest(),
            }

        write_json(staging / "manifest.json", manifest)
        (staging / "_headers").write_text(HEADERS, encoding="utf-8")
        (staging / "_redirects").write_text("/ /manifest.json 302\n", encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging.rename(output_dir)

    print(f"Built {len(records):,} addresses in {files:,} JSON files")


if __name__ == "__main__":
    try:
        build(ROOT / "directory.csv", ROOT / "dist")
    except (OSError, ValueError) as error:
        sys.exit(f"Directory build failed: {error}")
