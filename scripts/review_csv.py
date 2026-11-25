"""Summarize directory changes for a pull request."""

import json
import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from build import ROOT, collect


MARKDOWN_ENTITIES = {ord(char): f"&#{ord(char)};" for char in "|[]`*_~"}


def summarize(before, after):
    added = after.keys() - before.keys()
    removed = before.keys() - after.keys()
    common = before.keys() & after.keys()
    fields = ("label", "source", "verification")
    changed = {
        key: [field for field in fields if before[key].get(field) != after[key].get(field)]
        for key in common if before[key] != after[key]
    }
    counts = ", ".join(
        f"{sum(field in changes for changes in changed.values())} {field} changes" for field in fields
    )
    lines = [
        "## Directory changes", "",
        f"{len(added)} added, {len(removed)} removed, {counts}.", "",
    ]
    rows = []
    for keys, change in ((added, "Added"), (removed, "Removed"), (changed, "Updated")):
        for key in sorted(keys):
            if change == "Updated":
                detail = ", ".join(
                    f"{field} {before[key].get(field, '—')} → {after[key].get(field, '—')}"
                    for field in changed[key]
                )
            else:
                records = after if change == "Added" else before
                detail = records[key].get("label", "—")
            rows.append((change, key[0], key[2], detail))
    if rows:
        lines += ["| Change | Network | Identifier | Details |", "| --- | --- | --- | --- |"]
        for row in rows[:50]:
            cells = [escape(cell).translate(MARKDOWN_ENTITIES) for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
        if len(rows) > 50:
            lines += ["", f"Showing 50 of {len(rows)} changed records."]
    needs_source = (
        any(after[key].get("label") for key in added)
        or any(
            "label" in changes or ("verification" in changes and after[key]["verification"] != "unverified")
            for key, changes in changed.items()
        )
    )
    return "\n".join(lines) + "\n", needs_source


def has_source(body):
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    for candidate in re.findall(r"https://[^\s<>()\[\]\"'`]+", body):
        try:
            url = urlsplit(candidate)
            if not url.username and not url.password and url.hostname and "." in url.hostname:
                return True
        except ValueError:
            continue
    return False


if __name__ == "__main__":
    base = sys.argv[1]
    with TemporaryDirectory() as temporary:
        baseline = Path(temporary) / "directory.csv"
        baseline.write_bytes(subprocess.check_output(["git", "show", f"{base}:directory.csv"], cwd=ROOT))
        summary, needs_source = summarize(collect(baseline), collect(ROOT / "directory.csv"))
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
        output.write(summary)
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if needs_source and not has_source(event["pull_request"]["body"]):
        sys.exit("Add a public HTTPS source to the PR description for new labels, corrections, and verification upgrades.")
