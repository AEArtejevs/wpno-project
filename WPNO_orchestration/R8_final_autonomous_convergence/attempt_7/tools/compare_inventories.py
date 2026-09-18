#!/usr/bin/env python3
"""Compare two inventories produced by inventory_r8.py.

Roots may differ; paths are relative and are compared as sets. `inode` and
`nlink` are never compared -- a copy has different inodes by definition and
that is not a difference in the tree's content or metadata.

Usage:
  compare_inventories.py <a.json> <b.json> <out.json> [--ignore-mtime]

Exit 0 when the two are equal on every compared field, 1 otherwise.
"""

import hashlib
import json
import sys

FIELDS = ("type", "size", "sha256", "symlink_target", "mode", "uid", "gid",
          "mtime_ns")


def load(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc, {e["path"]: e for e in doc["entries"]}


def main():
    a_path, b_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    fields = [f for f in FIELDS
              if not (f == "mtime_ns" and "--ignore-mtime" in sys.argv)]

    a_doc, a = load(a_path)
    b_doc, b = load(b_path)

    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    differing = []
    for path in sorted(set(a) & set(b)):
        deltas = {f: [a[path][f], b[path][f]]
                  for f in fields if a[path][f] != b[path][f]}
        if deltas:
            differing.append({"path": path, "fields": deltas})

    def count(paths, key):
        return sum(1 for d in differing if key in d["fields"])

    equal = not (only_a or only_b or differing)
    doc = {
        "schema": "wpno.r8.attempt6-inventory-compare/1",
        "a": {"path": a_path, "root": a_doc["root"],
              "entry_count": a_doc["entry_count"]},
        "b": {"path": b_path, "root": b_doc["root"],
              "entry_count": b_doc["entry_count"]},
        "compared_fields": fields,
        "paths_only_in_a": only_a,
        "paths_only_in_b": only_b,
        "paths_added": len(only_b),
        "paths_removed": len(only_a),
        "paths_differing": len(differing),
        "differences": differing,
        "written_paths": len([d for d in differing
                              if "sha256" in d["fields"]
                              or "size" in d["fields"]]),
        "mtimes_changed": count(differing, "mtime_ns"),
        "modes_changed": count(differing, "mode"),
        "symlink_targets_changed": count(differing, "symlink_target"),
        "contents_changed": count(differing, "sha256"),
        "uid_changed": count(differing, "uid"),
        "gid_changed": count(differing, "gid"),
        "EQUAL": equal,
    }
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(raw)
    summary = {k: doc[k] for k in (
        "paths_added", "paths_removed", "paths_differing", "written_paths",
        "mtimes_changed", "modes_changed", "symlink_targets_changed",
        "contents_changed", "uid_changed", "gid_changed", "EQUAL")}
    summary["compare_record_sha256"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if equal else 1


if __name__ == "__main__":
    sys.exit(main())
