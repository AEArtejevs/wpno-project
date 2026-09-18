#!/usr/bin/env python3
"""Check that a status record does not name a path that is not there.

R7_RESUME_STATUS.json recorded a superseded build manifest stamped 074524Z.
No such file was ever written; the file on disk is stamped 074734Z. The
record's digest and entry count matched that file exactly, so the content was
right and only the name was wrong - which is precisely the failure CLAUDE.md
section 4 warns about, a filename standing in a place the evidence rank does
not admit it.

A dangling path in a status record binds nothing and gates nothing, so it
cannot break a run. It can mislead a reader into looking for evidence that is
there under another name and concluding it is missing. This check makes that
class of error visible rather than leaving it to be noticed.

The rule is narrow on purpose. A string is treated as a path only when it
looks like one and resolves inside the package, so a sentence that happens to
contain a slash is not turned into a failing assertion.
"""

import argparse
import json
import os
import sys

# Two dirnames, not three: this file moved from build/resume_r7/ to build/
# when R8 renamed the R7-specific tooling, and the extra level would have
# resolved ROOT to the directory above the package.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing  # noqa: E402

PATH_SUFFIXES = (".json", ".sha256", ".md", ".py", ".txt", ".jsonl", ".sha2")

# Where a record names a path and a digest of it side by side, the digest is
# checked too. The key holding the digest is the path's key with this suffix.
DIGEST_SUFFIXES = ("_sha256", "_SHA256")

# Keys whose whole purpose is to record a path that is deliberately not there
# any more: what a record used to name, or what a value used to be. Requiring
# those to resolve would make it impossible to document a correction, which is
# the opposite of what this check is for.
#
# The list is exact names and one suffix, not a substring test. A key called
# `report_previously` would not match, and neither would a live binding whose
# value happens to mention history.
HISTORICAL_KEYS = frozenset(("previously_named", "corrected_from",
                             "superseded_preserved_previously"))
HISTORICAL_SUFFIXES = ("_superseded", "_previously_named")


def is_historical(key):
    return key in HISTORICAL_KEYS or key.endswith(HISTORICAL_SUFFIXES)


def path_like(value):
    if not isinstance(value, str) or not value or value.startswith("http"):
        return False
    if value.startswith("/"):
        return False                     # absolute paths belong to other hosts
    if "/" not in value and not value.endswith(PATH_SUFFIXES):
        return False
    return value.endswith(PATH_SUFFIXES) or value.endswith("/")


def walk(node, trail, findings):
    if isinstance(node, dict):
        for key, value in node.items():
            walk(value, trail + [key], findings)
            if path_like(value) and not is_historical(key):
                findings.append({"json_pointer": "/".join(trail + [key]),
                                 "value": value, "sibling_digest": _sibling(
                                     node, key)})
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk(value, trail + ["[%d]" % index], findings)


def _sibling(node, key):
    for suffix in DIGEST_SUFFIXES:
        candidate = key + suffix
        if candidate in node and isinstance(node[candidate], str):
            return node[candidate]
    # `superseded_preserved` and `superseded_sha256` do not share a stem, so
    # the pairing is looked for by prefix as well.
    stem = key.rsplit("_", 1)[0]
    for candidate in (stem + "_sha256",):
        if candidate in node and isinstance(node[candidate], str):
            return node[candidate]
    return None


def validate(record_path):
    with open(record_path, encoding="utf-8") as fh:
        record = json.load(fh)
    findings = []
    walk(record, [], findings)

    problems = []
    checked = []
    for finding in findings:
        target = os.path.join(ROOT, finding["value"])
        exists = os.path.exists(target)
        entry = {"json_pointer": finding["json_pointer"],
                 "value": finding["value"], "exists": exists}
        if not exists:
            entry["problem"] = "NAMED_PATH_DOES_NOT_EXIST"
            problems.append(entry)
        elif finding["sibling_digest"] and os.path.isfile(target):
            measured = hashing.sha256_file(target)
            entry["recorded_sha256"] = finding["sibling_digest"]
            entry["measured_sha256"] = measured
            if measured != finding["sibling_digest"]:
                entry["problem"] = "NAMED_PATH_DIGEST_DOES_NOT_MATCH"
                problems.append(entry)
        checked.append(entry)

    return {"record": os.path.relpath(record_path, ROOT),
            "paths_checked": len(checked),
            "problems": problems,
            "ok": not problems,
            "checked": checked}


def main():
    parser = argparse.ArgumentParser(prog="validate-status-record")
    parser.add_argument("records", nargs="*", default=None)
    args = parser.parse_args()
    records = args.records or [os.path.join(ROOT, "build", "resume_r7",
                                            "R7_RESUME_STATUS.json")]
    worst = 0
    for record in records:
        result = validate(record)
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["ok"]:
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
