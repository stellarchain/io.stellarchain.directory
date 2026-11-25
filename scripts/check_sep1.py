"""Recheck published SEP-1 claims using Horizon and public issuer files."""

import json
import os
import re
import sys
import tomllib
from functools import cache
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

from build import ROOT, collect


HORIZON = {
    "mainnet": ("https://horizon.stellar.org", "Public Global Stellar Network ; September 2015"),
    "testnet": ("https://horizon-testnet.stellar.org", "Test SDF Network ; September 2015"),
    "futurenet": ("https://horizon-futurenet.stellar.org", "Test SDF Future Network ; October 2022"),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url, limit):
    request = Request(url, headers={"User-Agent": "stellarchain-directory-sep1-check/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError(f"response exceeds {limit:,} bytes")
    return payload


@cache
def account_domain(network, address):
    host, _ = HORIZON[network]
    account = json.loads(fetch(f"{host}/accounts/{address}", 128 * 1024))
    if account["account_id"] != address:
        raise ValueError("Horizon returned a different account")
    return account.get("home_domain", "").lower()


@cache
def stellar_toml(domain):
    return tomllib.loads(fetch(f"https://{domain}/.well-known/stellar.toml", 100 * 1024).decode("utf-8-sig"))


def check(record, approved_domains):
    network = record["network"]
    address = record.get("issuer") or record["address"]
    domain = account_domain(network, address)
    if domain not in approved_domains:
        raise ValueError("ledger home domain does not match a public SEP-1 source in NOTICE")
    document = stellar_toml(domain)
    passphrase = HORIZON[network][1]
    if document.get("NETWORK_PASSPHRASE", passphrase) != passphrase:
        raise ValueError("stellar.toml declares a different Stellar network")
    if record["type"] == "asset":
        if not any(
            isinstance(item, dict) and item.get("issuer") == address and item.get("code") == record["asset_code"]
            for item in document.get("CURRENCIES", [])
        ):
            raise ValueError("stellar.toml no longer lists the exact asset code and issuer")
    elif address not in document.get("ACCOUNTS", []):
        raise ValueError("stellar.toml no longer lists the exact account")
    return domain


if __name__ == "__main__":
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    approved_domains = set(re.findall(r"https://([a-z0-9.-]+)/\.well-known/stellar\.toml\b", notice))
    lines = ["## SEP-1 checks", ""]
    failures = 0
    for record in collect(ROOT / "directory.csv").values():
        if record["verification"] != "sep1_domain":
            continue
        identifier = record.get("id") or record["address"]
        try:
            domain = check(record, approved_domains)
            lines.append(f"- {record['network']} `{identifier}` matched {domain}.")
        except (OSError, KeyError, TypeError, ValueError) as error:
            failures += 1
            lines.append(f"- {record['network']} `{identifier}` needs review. {error}.")
    summary = "\n".join(lines) + "\n"
    print(summary, end="")
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(path).open("a", encoding="utf-8") as output:
            output.write(summary)
    sys.exit(bool(failures))
