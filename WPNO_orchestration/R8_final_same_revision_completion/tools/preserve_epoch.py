#!/usr/bin/env python3
"""Preserve freeze attempt 3 and execution epoch 1 outside R8, before revocation.

Nothing in R8 is read destructively and nothing is written there. Every
preserved file is copied byte-for-byte and then re-hashed at its destination,
because a copy that is not verified is a copy that might not have happened.

No raw token is preserved. Neither ledger holds one -- the controller records
digests and bindings only -- and that is measured here rather than assumed: any
preserved byte containing an approval or freeze token prefix aborts the run.

Usage: preserve_epoch.py <r8> <out> 
"""

import hashlib
import json
import os
import re
import shutil
import sys

# A RAW token, not the token GRAMMAR. The first version of this guard matched
# the bare prefixes and fired on
# `"token_grammar": "FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> ..."` -- a template
# with literal `<64hex>` placeholders, which is documentation, not a secret.
# A boundary-less match finds what it was not looking for; this project has
# now recorded that failure four times. A token is only a token when its
# fields carry real 64-hex digests.
RAW_TOKEN_PATTERNS = (
    re.compile(rb"FREEZE-LEVEL1 PACKAGE-SHA256=[0-9a-f]{64} "
               rb"VERIFICATION-SHA256=[0-9a-f]{64} "
               rb"FREEZE-PLAN-SHA256=[0-9a-f]{64} RUN-ONCE"),
    re.compile(rb"APPROVE-EXECUTION [A-Za-z0-9-]+ RUN=[A-Za-z-]+ "
               rb"PLAN-SHA256=[0-9a-f]{64} TARGET-SHA256=[0-9a-f]{64} "
               rb"RUN-ONCE"),
)


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def main():
    r8, out = os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])
    dest_root = os.path.join(out, "preserved")
    os.makedirs(dest_root, exist_ok=True)

    families = [
        ("FROZEN_PUBLICATION", ["MODE", "CONTROL_MANIFEST.sha256",
                                "BASELINE_MANIFEST.json",
                                "state/PACKAGE_VERIFIED.json"]),
        ("FREEZE_LEDGER", ["state/freeze_attempts.jsonl"]),
        ("ACTIVE_STATE", ["state/progress.json", "state/transitions.jsonl",
                          "state/approvals.jsonl", "state/migrations.jsonl"]),
        ("MIGRATION_PACKET",
         ["build/migration_plan_r7_to_r8/MIGRATION_PLAN.json",
          "build/migration_plan_r7_to_r8/MIGRATION_PLAN.sha256",
          "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-A.json",
          "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-B.json"]),
        ("COMPARISON_PLAN",
         ["results/L1-A31/COMPARISON/attempt-1/plan.json"]),
    ]
    preserved, missing = [], []
    for family, rels in families:
        for rel in rels:
            src = os.path.join(r8, rel)
            if not os.path.isfile(src):
                missing.append({"family": family, "path": rel})
                continue
            dst = os.path.join(dest_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            src_sha, dst_sha = sha256_file(src), sha256_file(dst)
            preserved.append({"family": family, "relative": rel,
                              "source_sha256": src_sha,
                              "preserved_sha256": dst_sha,
                              "bytes_equal": src_sha == dst_sha,
                              "size": os.path.getsize(dst)})

    # whole trees: the freeze plan, the verification it rests on, and every
    # evidence directory of the epoch
    trees = [
        ("FREEZE_PLAN_ATTEMPT_3", "build/freeze_plan_attempt_3"),
        ("FINAL_VERIFICATION_FOR_ATTEMPT_3",
         "verification_codex_final_pre_freeze_attempt_6"),
        ("EXECUTION_EPOCH_1_EVIDENCE", "evidence/L1-A31"),
        ("EXECUTION_EPOCH_1_RESULTS", "results/L1-A31"),
        ("RUNTIME_LOGS", "logs"),
    ]
    for family, rel in trees:
        src_root = os.path.join(r8, rel)
        if not os.path.isdir(src_root):
            missing.append({"family": family, "path": rel})
            continue
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames.sort()
            for name in sorted(filenames):
                src = os.path.join(dirpath, name)
                rel_full = os.path.relpath(src, r8)
                dst = os.path.join(dest_root, rel_full)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                src_sha, dst_sha = sha256_file(src), sha256_file(dst)
                preserved.append({"family": family, "relative": rel_full,
                                  "source_sha256": src_sha,
                                  "preserved_sha256": dst_sha,
                                  "bytes_equal": src_sha == dst_sha,
                                  "size": os.path.getsize(dst)})

    # no raw token may leave R8 in a preserved byte
    leaked = []
    for row in preserved:
        path = os.path.join(dest_root, row["relative"])
        try:
            with open(path, "rb") as fh:
                blob = fh.read()
        except OSError:
            continue
        for pattern in RAW_TOKEN_PATTERNS:
            if pattern.search(blob):
                leaked.append({"path": row["relative"],
                               "pattern": pattern.pattern.decode("ascii")[:60]})
    if leaked:
        raise SystemExit("a preserved byte contains a raw token: %s" % leaked)

    mismatched = [p for p in preserved if not p["bytes_equal"]]
    doc = {
        "schema": "wpno.r8.pre-revocation-preservation/1",
        "r8_root": r8, "destination": dest_root,
        "preserved": preserved, "preserved_count": len(preserved),
        "missing": missing,
        "byte_mismatches": mismatched,
        "raw_token_leaks": leaked,
        "total_bytes": sum(p["size"] for p in preserved),
        "PRESERVATION_VALID": not mismatched and not leaked,
    }
    with open(os.path.join(out, "PRE_REVOCATION_PRESERVATION.json"), "w",
              encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")

    lines = []
    for dirpath, dirnames, filenames in os.walk(dest_root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            lines.append("%s  %s\n" % (sha256_file(full),
                                       os.path.relpath(full, dest_root)))
    with open(os.path.join(out, "PRE_REVOCATION_MANIFEST.sha256"), "w",
              encoding="utf-8") as fh:
        fh.writelines(sorted(lines, key=lambda s: s.split("  ", 1)[1]))

    print(json.dumps({k: doc[k] for k in
                      ("preserved_count", "total_bytes", "missing",
                       "byte_mismatches", "raw_token_leaks",
                       "PRESERVATION_VALID")}, indent=1, sort_keys=True))
    return 0 if doc["PRESERVATION_VALID"] else 1


if __name__ == "__main__":
    sys.exit(main())
