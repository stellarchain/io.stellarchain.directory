"""Check that the published API matches the build."""

import hashlib
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from build import ROOT


HOSTS = ("https://directory.stellarchain.io", "https://stellarchain-directory.stellarchain.workers.dev")
KNOWN = "/mainnet/addresses/GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO.json"
MISSING = "/mainnet/addresses/does-not-exist.json"


def fetch(url):
    request = Request(url, headers={"User-Agent": "stellarchain-directory-deploy-check/1.0"})
    with urlopen(request, timeout=10) as response:
        return response.read()


def verify(host, expected):
    received = fetch(host + "/manifest.json")
    if hashlib.sha256(received).digest() != hashlib.sha256(expected).digest():
        raise ValueError("manifest checksum differs from the build")
    for path in (KNOWN, json.loads(received)["schema"]):
        if fetch(host + path) != (ROOT / "dist" / path.lstrip("/")).read_bytes():
            raise ValueError(f"published {path} differs from the build")
    try:
        fetch(host + MISSING)
    except HTTPError as error:
        if error.code == 404:
            return
        raise
    raise ValueError(f"{MISSING} returned a successful response")


if __name__ == "__main__":
    expected = (ROOT / "dist/manifest.json").read_bytes()
    pending = set(HOSTS)
    deadline = time.monotonic() + 120
    while pending:
        for host in sorted(pending):
            try:
                verify(host, expected)
            except (URLError, TimeoutError, ValueError) as error:
                print(f"{host} {error}", flush=True)
            else:
                print(f"{host} matches the build and returns 404 for a missing address")
                pending.remove(host)
        if not pending:
            break
        if time.monotonic() >= deadline:
            sys.exit("The latest build could not be verified on " + ", ".join(sorted(pending)))
        time.sleep(5)
