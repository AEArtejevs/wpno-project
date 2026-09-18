#!/usr/bin/env python3
"""Record a file's identity so a before/after pair cannot address two files.

Attempt 5's item 33 recorded a control file's "before" by one path and its
"after" by another, because the second was relative and resolved against a
different directory. The two numbers were then compared as though they
described one file. They did not, and the giveaway was in the record: the
"after" mtime was EARLIER than the "before" mtime.

So every observation here carries, together:

    requested_path      exactly what the caller asked for
    resolved_path       os.path.realpath of it, absolute
    root                which declared root it belongs to, or OUTSIDE_ALL_ROOTS
    mtime_ns, sha256, size, type, mode

and a pair is only comparable when the two resolved_path values are equal.
`compare` refuses the pair otherwise, and refuses a pair whose mtime runs
backwards, instead of reporting it as a pass.

Usage:
  measure_path.py observe <path> [--root NAME=PATH ...]
  measure_path.py compare <before.json> <after.json>

`compare` exits 0 when the pair is VALID evidence -- which is not the same as
"the file did not change". It says the two observations describe one file and
time ran forwards. What changed is reported for the caller to judge.
"""

import hashlib
import json
import os
import stat
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def observe(requested, roots):
    resolved = os.path.realpath(requested)
    owning = "OUTSIDE_ALL_ROOTS"
    best = -1
    for name, root in roots.items():
        root = os.path.realpath(root)
        if resolved == root or resolved.startswith(root + os.sep):
            if len(root) > best:
                owning, best = name, len(root)
    doc = {
        "schema": "wpno.r8.attempt8-observation/1",
        "requested_path": requested,
        "requested_was_absolute": os.path.isabs(requested),
        "resolved_path": resolved,
        "root": owning,
        "roots_declared": {k: os.path.realpath(v) for k, v in roots.items()},
        "exists": os.path.lexists(resolved),
    }
    if not doc["exists"]:
        doc.update(type=None, size=None, mode=None, mtime_ns=None, sha256=None)
        return doc
    st = os.lstat(resolved)
    kind = ("symlink" if stat.S_ISLNK(st.st_mode) else
            "dir" if stat.S_ISDIR(st.st_mode) else
            "file" if stat.S_ISREG(st.st_mode) else "other")
    doc.update(type=kind, size=st.st_size, mode=oct(stat.S_IMODE(st.st_mode)),
               mtime_ns=st.st_mtime_ns,
               sha256=sha256_file(resolved) if kind == "file" else None)
    return doc


def compare(before, after):
    problems = []
    if before["resolved_path"] != after["resolved_path"]:
        problems.append(
            "the two observations resolve to different files: %s vs %s"
            % (before["resolved_path"], after["resolved_path"]))
    b, a = before.get("mtime_ns"), after.get("mtime_ns")
    if b is not None and a is not None and a < b:
        problems.append(
            "after_mtime_ns (%d) is EARLIER than before_mtime_ns (%d); an "
            "mtime cannot run backwards, so these observations do not "
            "describe one file and one interval" % (a, b))
    doc = {
        "schema": "wpno.r8.attempt8-observation-compare/1",
        "before": before, "after": after,
        "resolved_path_stable": before["resolved_path"] == after["resolved_path"],
        "mtime_moved": (b is not None and a is not None and a > b),
        "mtime_unchanged": b == a,
        "content_changed": before.get("sha256") != after.get("sha256"),
        "problems": problems,
        "EVIDENCE_VALID": not problems,
    }
    return doc


def main():
    if sys.argv[1] == "observe":
        roots = {}
        args = sys.argv[2:]
        path = args[0]
        for i, a in enumerate(args):
            if a == "--root":
                name, _, value = args[i + 1].partition("=")
                roots[name] = value
        print(json.dumps(observe(path, roots), indent=1, sort_keys=True))
        return 0
    if sys.argv[1] == "compare":
        with open(sys.argv[2], encoding="utf-8") as fh:
            before = json.load(fh)
        with open(sys.argv[3], encoding="utf-8") as fh:
            after = json.load(fh)
        doc = compare(before, after)
        print(json.dumps(doc, indent=1, sort_keys=True))
        return 0 if doc["EVIDENCE_VALID"] else 1
    raise SystemExit("usage: measure_path.py observe|compare ...")


if __name__ == "__main__":
    sys.exit(main())
