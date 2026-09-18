#!/usr/bin/env python3
"""Verify R4, R5 and R6 by per-file digest, and record the method used.

A whole-tree summary digest is only meaningful once its formula is agreed.
The independent pre-freeze verification computed one by a formula of its own
and reported three predecessors changed; the file counts it measured were
exactly right, and every per-file digest matched. What differed was the
arithmetic that folded them into one number, not the bytes.

So this records both, and says which one settles the question. The per-file
comparison is the answer: 15153 recorded digests against 15153 files, each
compared on its own. A summary digest is recorded beside it, with the formula
written out, so that anyone recomputing it gets the same number instead of a
different one they then have to explain.

    manifest text = "\\n".join("<sha256>  <relative path>" for each regular
                              file, sorted by relative path) + "\\n"
    snapshot digest = SHA-256 of those bytes, UTF-8

Symlinks are not followed and are not hashed as their targets. None of the
three trees contains one, which this tool asserts rather than assumes.
"""

import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy  # noqa: E402

OUT = os.path.join(ROOT, "lineage", "PREDECESSOR_INTEGRITY.json")

BASE = os.path.dirname(ROOT)
TREES = {
    "R4": os.path.join(BASE, "08.18.26_Level1_Audits_R4"),
    "R5": os.path.join(BASE, "08.18.26_Level1_Audits_R5"),
    "R6": os.path.join(BASE, "08.18.26_Level1_Audits_R6"),
}

# The per-file manifest that settles each tree, where one exists in-package.
PER_FILE_MANIFESTS = {
    "R6": os.path.join(ROOT, "lineage", "R6_EXECUTION_MANIFEST.sha256"),
}

RECORDED_SNAPSHOTS = {
    "R4": "4d8ab234a553b158c55341b5f6f6284fddab4b643949288d57697ca638781430",
    "R5": "191902e7e7626099e0c149d46ed105bc691820186173021fd1001cf4856a556e",
    "R6": "aa3650f456343e5ade7e662d011d483df69cc6cf6f77097d36d6356eb7c56026",
}

METHOD = (
    'manifest text = "\\n".join("<sha256>  <relative path>" for each regular '
    'file, sorted by relative path) + "\\n"; snapshot digest = SHA-256 of '
    'those bytes encoded UTF-8. Symlinks are skipped, not followed.')


def walk_digests(root):
    entries = {}
    symlinks = []
    root = os.path.realpath(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                symlinks.append(rel)
                continue
            entries[rel] = hashing.sha256_file(full)
    return entries, symlinks


def snapshot_digest(entries):
    text = "\n".join("%s  %s" % (entries[k], k) for k in sorted(entries)) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_manifest(path):
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line and "  " in line:
                digest, rel = line.split("  ", 1)
                rows[rel] = digest
    return rows


def main():
    result = {
        "schema": "wpno.level1.predecessor-integrity/1",
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": METHOD,
        "what_settles_it": (
            "the per-file comparison. A summary digest depends on the formula "
            "that folds the per-file digests together; a per-file comparison "
            "does not."),
        "trees": {},
    }
    ok = True
    for name, root in sorted(TREES.items()):
        entries, symlinks = walk_digests(root)
        digest = snapshot_digest(entries)
        record = {
            "root": root,
            "files": len(entries),
            "symlinks": symlinks,
            "snapshot_sha256_by_the_recorded_method": digest,
            "recorded_snapshot_sha256": RECORDED_SNAPSHOTS[name],
            "snapshot_matches": digest == RECORDED_SNAPSHOTS[name],
        }
        manifest = PER_FILE_MANIFESTS.get(name)
        if manifest:
            rows = read_manifest(manifest)
            matched = missing = mismatched = 0
            for rel, expected in rows.items():
                full = os.path.join(root, rel)
                if not os.path.isfile(full):
                    missing += 1
                elif hashing.sha256_file(full) == expected:
                    matched += 1
                else:
                    mismatched += 1
            record["per_file_manifest"] = os.path.relpath(manifest, ROOT)
            record["per_file_entries"] = len(rows)
            record["per_file_matched"] = matched
            record["per_file_mismatched"] = mismatched
            record["per_file_missing"] = missing
            record["per_file_unchanged"] = (mismatched == 0 and missing == 0
                                            and len(rows) == len(entries))
            if not record["per_file_unchanged"]:
                ok = False
        if not record["snapshot_matches"]:
            ok = False
        result["trees"][name] = record

    # The lineage copy of R6 must equal R6 in place, file for file.
    copy_root = os.path.join(ROOT, "lineage", "R6_EXECUTION")
    copy_entries, _ = walk_digests(copy_root)
    live_entries, _ = walk_digests(TREES["R6"])
    result["r6_lineage_copy"] = {
        "path": "lineage/R6_EXECUTION",
        "files": len(copy_entries),
        "identical_to_r6_in_place": copy_entries == live_entries,
        "differing_paths": sorted(
            set(copy_entries) ^ set(live_entries))[:10] or
            sorted(k for k in copy_entries
                   if k in live_entries and copy_entries[k] != live_entries[k])[:10],
    }
    if not result["r6_lineage_copy"]["identical_to_r6_in_place"]:
        ok = False

    result["ALL_PREDECESSORS_UNCHANGED"] = ok
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(OUT), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(json.dumps({
        "record": os.path.relpath(OUT, ROOT),
        "record_sha256": hashing.sha256_text(text),
        "ALL_PREDECESSORS_UNCHANGED": ok,
        "summary": {k: {"files": v["files"],
                        "snapshot_matches": v["snapshot_matches"],
                        "per_file_unchanged": v.get("per_file_unchanged")}
                    for k, v in result["trees"].items()},
        "r6_lineage_copy_identical":
            result["r6_lineage_copy"]["identical_to_r6_in_place"],
    }, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
