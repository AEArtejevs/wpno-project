#!/usr/bin/env python3
"""Decide, item by item, what attempt 8 may hand forward.

A result is carried forward only when it is DURABLE: written to a file, that
file's digest verified, the thing it measured still present unchanged, and the
record holding an actual measurement rather than a sentence saying one was
made. Attempt 7 is the reason that last clause is here -- it reported twelve
items it had genuinely measured as `pass: false` because the numbers had lived
only in memory when the process died.

Six conditions, each recorded per item:

  1 evidence file exists
  2 evidence file digest verified against attempt 8's own manifest
  3 the measured target is the current R8 package
  4 the current R8 inventory equals the inventory attempt 8 measured
  5 the record holds a measured result, not a narrative
  6 no relevant dependency changed

Condition 6 is answered once, for everything, and answered the strongest way
available: the whole R8 tree is compared path by path against the inventory
attempt 8 took at its end -- type, size, SHA-256, symlink target, mode, uid,
gid and mtime_ns over all 1362 paths. If nothing in the package differs, then
nothing any item depended on differs. A per-item dependency list would be
weaker, because it could omit a dependency nobody thought of.

Usage: build_durable_matrix.py <attempt8_root> <r8> <now_inventory> <out.json>
"""

import hashlib
import json
import os
import sys

# Files each item rests on beyond its own line in ITEM_RESULTS.jsonl.
SUPPORTING = {
    18: ["CONTROLLER_SUITE.stderr.txt", "CONTROLLER_SUITE.stdout.txt"],
    19: ["PACKAGE_SUITE.json", "PACKAGE_SUITE.stdout.txt",
         "PACKAGE_SUITE.stderr.txt"],
    20: ["STATIC.stdout.txt", "STATIC.stderr.txt",
         "static_safety_outputs/R8_STATIC_SAFETY_REPORT.json",
         "static_safety_outputs/R8_CHANGED_FILES.sha256"],
    31: ["ORIGINAL_INVENTORY_BEFORE.json", "ORIGINAL_INVENTORY_AFTER.json",
         "ORIGINAL_INVENTORY_COMPARE.json"],
    32: ["ORIGINAL_INVENTORY_BEFORE.json", "ORIGINAL_INVENTORY_AFTER.json",
         "ORIGINAL_INVENTORY_COMPARE.json",
         "ORIGINAL_INVENTORY_COMPARE.summary.json"],
    33: ["ITEM33_BEFORE.json", "ITEM33_AFTER.json", "ITEM33_COMPARE.json"],
}

# The R8 artefacts each substantive item read. Recorded per item so a reader
# can see what a carried result rests on, in addition to the whole-tree proof.
DEPENDENCIES = {
    12: ["work/_rehearsal_r8/REHEARSAL_REPORT.json"],
    15: ["build/CONTROL_EXPECTATION_COVERAGE.json",
         "automation/in_process_executor.py"],
    16: ["build/migration_plan_r7_to_r8/MIGRATION_PLAN.json",
         "automation/migration.py"],
    18: ["automation/tests"],
    19: ["automation/package_tests", "build/candidate_plans_r8"],
    20: ["build/r8_static_safety_review.py",
         "build/R8_STATIC_SAFETY_REPORT.json"],
    21: ["build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json"],
    22: ["work/_rehearsal_r8/REHEARSAL_REPORT.json"],
    23: ["work/_rehearsal_r8/REHEARSAL_REPORT.json",
         "build/IN_PROCESS_COUNT_RECONCILIATION.json"],
    24: ["work/_rehearsal_r8/REHEARSAL_REPORT.json"],
    25: ["state/progress.json"],
    26: ["state/approvals.jsonl"],
    27: ["build/R8_BUILD_MANIFEST.sha256"],
}

NARRATIVE = ("NOT_VERIFIED_AFTER_STOP", "NOT VERIFIED", "NOT RUN",
             "Measurement process aborted")


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def sha256_tree(path):
    """One digest over a directory's relative paths and file contents."""
    if os.path.isfile(path):
        return sha256_file(path)
    d = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            d.update(os.path.relpath(full, path).encode("utf-8"))
            d.update(sha256_file(full).encode("ascii"))
    return d.hexdigest()


def main():
    a8, r8, now_inv, out_path = (os.path.realpath(sys.argv[1]),
                                 os.path.realpath(sys.argv[2]),
                                 sys.argv[3], sys.argv[4])
    out = os.path.join(a8, "codex_output")

    # -- attempt 8's own manifest, re-verified here ------------------------
    declared = {}
    with open(os.path.join(out, "VERIFICATION_MANIFEST.sha256"),
              encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                digest, rel = line.split("  ", 1)
                declared[rel] = digest
    manifest_bad = []
    for rel, digest in sorted(declared.items()):
        full = os.path.join(out, rel)
        if not os.path.isfile(full):
            manifest_bad.append({"path": rel, "problem": "absent"})
        elif sha256_file(full) != digest:
            manifest_bad.append({"path": rel, "declared": digest,
                                 "actual": sha256_file(full)})

    # -- condition 4, answered once for everything -------------------------
    with open(os.path.join(a8, "original_inventory", "INVENTORY_FINAL.json"),
              encoding="utf-8") as fh:
        base = {e["path"]: e for e in json.load(fh)["entries"]}
    with open(now_inv, encoding="utf-8") as fh:
        now = {e["path"]: e for e in json.load(fh)["entries"]}
    fields = ("type", "size", "sha256", "symlink_target", "mode", "uid",
              "gid", "mtime_ns")
    drift = sorted(p for p in set(base) | set(now)
                   if p not in base or p not in now
                   or any(base[p][f] != now[f2] if False else
                          base[p][f] != now[p][f] for f in fields))
    tree_unchanged = not drift

    # -- the durable records ------------------------------------------------
    rows = [json.loads(line) for line in
            open(os.path.join(out, "ITEM_RESULTS.jsonl"), encoding="utf-8")
            if line.strip()]
    by_id = {}
    for r in rows:
        by_id[r["id"]] = r
    item_results_sha = sha256_file(os.path.join(out, "ITEM_RESULTS.jsonl"))

    current_manifest = sha256_file(os.path.join(r8, "build",
                                                "R8_BUILD_MANIFEST.sha256"))

    matrix = []
    for item_id in sorted(by_id):
        rec = by_id[item_id]
        measured = rec.get("measured")
        text = json.dumps(measured) if not isinstance(measured, str) else measured
        narrative_only = any(n in text for n in NARRATIVE)

        if rec.get("pass") is True and not narrative_only:
            status = "DURABLE_PASS"
        elif rec.get("pass") is False and narrative_only:
            status = "NOT_COMPLETED_AFTER_STOP"
        elif rec.get("pass") is False:
            status = "FAILED_VERIFIER_PREDICATE"
        else:
            status = "MISSING_DURABLE_EVIDENCE"

        evidence = [{"path": os.path.join(out, "ITEM_RESULTS.jsonl"),
                     "sha256": item_results_sha,
                     "digest_verified": item_results_sha == declared.get(
                         "ITEM_RESULTS.jsonl")}]
        for rel in SUPPORTING.get(item_id, []):
            full = os.path.join(out, rel)
            evidence.append({
                "path": full,
                "sha256": sha256_file(full) if os.path.isfile(full) else None,
                "digest_verified": (os.path.isfile(full)
                                    and sha256_file(full) == declared.get(rel))})

        deps = {}
        for rel in DEPENDENCIES.get(item_id, []):
            full = os.path.join(r8, rel)
            deps[rel] = sha256_tree(full) if os.path.exists(full) else None

        conditions = {
            "1_evidence_file_exists": all(
                os.path.isfile(e["path"]) for e in evidence),
            "2_evidence_digest_verified": all(
                e["digest_verified"] for e in evidence),
            "3_target_is_current_r8_package":
                current_manifest == ("6dfd1af689754be61f2ea6ef77f01d2e5"
                                     "bdb8929ef8c0799e15db203755b945a"),
            "4_r8_inventory_equals_attempt_8": tree_unchanged,
            "5_record_holds_a_measurement": not narrative_only,
            "6_no_relevant_dependency_changed": tree_unchanged,
        }
        allowed = status == "DURABLE_PASS" and all(conditions.values())
        if allowed:
            reason = ("durable: measured value recorded in a digest-verified "
                      "file, target package byte-identical to what attempt 8 "
                      "measured")
        elif status == "FAILED_VERIFIER_PREDICATE":
            reason = ("attempt 8's own predicate returned an adverse result; "
                      "must be remeasured in the delta")
        elif status == "NOT_COMPLETED_AFTER_STOP":
            reason = ("never measured -- NOT VERIFIED is not FAILED; must be "
                      "measured in the delta")
        else:
            reason = "no durable measurement on file; must be measured"

        matrix.append({
            "ITEM_ID": item_id,
            "ATTEMPT_8_STATUS": status,
            "CLAIM": rec.get("claim"),
            "ROOT": rec.get("root"),
            "MEASURED": measured,
            "EVIDENCE_PATH": [e["path"] for e in evidence],
            "EVIDENCE_SHA256": {e["path"]: e["sha256"] for e in evidence},
            "TARGET_MANIFEST_SHA256": current_manifest,
            "DEPENDENCY_HASHES": deps,
            "CONDITIONS": conditions,
            "CARRY_FORWARD_ALLOWED": allowed,
            "REASON": reason,
        })

    carry = [m["ITEM_ID"] for m in matrix if m["CARRY_FORWARD_ALLOWED"]]
    delta = [m["ITEM_ID"] for m in matrix if not m["CARRY_FORWARD_ALLOWED"]]
    doc = {
        "schema": "wpno.r8.delta-durable-matrix/1",
        "base_attempt": 8,
        "base_attempt_root": a8,
        "r8_root": r8,
        "attempt_8_output_manifest": os.path.join(
            out, "VERIFICATION_MANIFEST.sha256"),
        "attempt_8_output_manifest_sha256": sha256_file(
            os.path.join(out, "VERIFICATION_MANIFEST.sha256")),
        "attempt_8_output_manifest_entries": len(declared),
        "attempt_8_output_manifest_failures": manifest_bad,
        "attempt_8_output_manifest_valid": not manifest_bad,
        "r8_tree_paths_compared": len(set(base) | set(now)),
        "r8_tree_paths_differing": len(drift),
        "r8_tree_unchanged_since_attempt_8": tree_unchanged,
        "current_manifest_sha256": current_manifest,
        "items": matrix,
        "ITEM_COUNT": len(matrix),
        "CARRY_FORWARD_ITEMS": carry,
        "CARRY_FORWARD_COUNT": len(carry),
        "DELTA_ITEM_SET": delta,
        "DELTA_ITEM_COUNT": len(delta),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "attempt_8_output_manifest_valid", "attempt_8_output_manifest_entries",
        "r8_tree_paths_compared", "r8_tree_paths_differing",
        "r8_tree_unchanged_since_attempt_8", "ITEM_COUNT",
        "CARRY_FORWARD_COUNT", "CARRY_FORWARD_ITEMS", "DELTA_ITEM_COUNT",
        "DELTA_ITEM_SET")}, indent=1, sort_keys=True))
    for m in matrix:
        if not m["CARRY_FORWARD_ALLOWED"]:
            print("  delta item %-3d %s" % (m["ITEM_ID"],
                                            m["ATTEMPT_8_STATUS"]))
    return 0 if not manifest_bad and tree_unchanged else 1


if __name__ == "__main__":
    sys.exit(main())
