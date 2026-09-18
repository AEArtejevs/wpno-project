#!/usr/bin/env python3
"""Create R7 as a sibling revision of R6, with per-file SHA-256 verification.

Nothing under R4, R5 or R6 is opened for writing. Every file that lands in R7
is hashed at the source and re-hashed at the destination, and the two digests
must agree before the file is accepted. A copy that is merely "successful"
according to the copy tool is not evidence; the digest is.

Layout produced:

    R7/<package bytes carried forward verbatim from R6>
    R7/lineage/R6_EXECUTION/       complete byte copy of R6, history included
    R7/state|results|evidence|work|logs|verification|build/   empty runtime
    R7/MODE = GENERATED_UNVERIFIED

The predecessor's runtime state is deliberately NOT carried into R7's active
state. It is preserved under lineage and R7's active state is written by the
controller's own init-revision route.
"""
import hashlib
import json
import os
import shutil
import sys

R6 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6"
R7 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7"

# Top-level names carried into R7 verbatim from R6.
CARRY = (
    "00_BUILD_STATUS.md",
    "00_CLAUDE_VERIFY_R5_PASS_READINESS.md",
    "00_CODEX_VERIFY_R5_PASS_READINESS.md",
    "00_COMMON_RULES.md",
    "00_OPERATOR_CLAUDE_VERIFY_R5.md",
    "00_OPERATOR_CODEX_VERIFY_R5.md",
    "00_OPERATOR_RUNBOOK_LV.md",
    "01_CODEX_RUN_LEVEL1.md",
    "02_CODEX_CONSOLIDATE_LEVEL1.md",
    "03_CODEX_LEVEL2_ADVERSARIAL.md",
    "AGENTS.md",
    "BASELINE_MANIFEST.json",
    "audit_registry.json",
    "paths.json",
    "automation",
    "bindings",
    "corpora",
    "discovery_reconciliation",
    "prompts",
    "references",
    "tools",
    "transfer",
)

# Runtime directories that must exist and must start empty.
EMPTY = ("state", "results", "evidence", "work", "logs", "verification",
         "build", "verification_codex_pre_freeze")

EXCLUDE_DIRS = ("__pycache__",)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_verified(src, dst, records, tag):
    """Copy one file and prove the copy by digest. Returns nothing; raises."""
    src_digest = sha256_file(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    dst_digest = sha256_file(dst)
    if src_digest != dst_digest:
        raise SystemExit(
            "COPY DIGEST MISMATCH\n  src %s %s\n  dst %s %s"
            % (src, src_digest, dst, dst_digest))
    records.append({"tag": tag, "src": src, "dst": dst, "sha256": src_digest})


def walk_files(root, skip_top=()):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            dirnames[:] = [d for d in dirnames if d not in skip_top]
            filenames = [f for f in filenames if f not in skip_top]
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            yield full, os.path.relpath(full, root)


def main():
    if os.path.lexists(R7):
        raise SystemExit("R7 already exists: %s" % R7)
    os.makedirs(R7, exist_ok=False)

    records = []

    # 1. Package bytes carried forward.
    for name in CARRY:
        src = os.path.join(R6, name)
        if os.path.isfile(src):
            copy_verified(src, os.path.join(R7, name), records, "PACKAGE")
        elif os.path.isdir(src):
            for full, rel in walk_files(src):
                copy_verified(full, os.path.join(R7, name, rel), records,
                              "PACKAGE")
        else:
            raise SystemExit("carry-forward source missing: %s" % src)
    package_count = len(records)

    # 2. Complete R6, preserved as lineage. __pycache__ is excluded here too:
    #    it is not control-plane bytes and is absent from R6's own manifest.
    lineage_root = os.path.join(R7, "lineage", "R6_EXECUTION")
    for full, rel in walk_files(R6):
        copy_verified(full, os.path.join(lineage_root, rel), records,
                      "LINEAGE_R6")
    lineage_count = len(records) - package_count

    # 3. Empty runtime directories.
    for name in EMPTY:
        os.makedirs(os.path.join(R7, name), exist_ok=True)

    # 4. Revision markers.
    with open(os.path.join(R7, "MODE"), "w", encoding="utf-8") as fh:
        fh.write("GENERATED_UNVERIFIED\n")
    with open(os.path.join(R7, "BUILD_ID"), "w", encoding="utf-8") as fh:
        fh.write("L1BUILD-R7-2026-08-26-UBUNTU-PHASE-ATTEMPT-MODEL\n")

    # 5. Migration manifest.
    mig = os.path.join(R7, "lineage", "MIGRATION_MANIFEST.sha256")
    os.makedirs(os.path.dirname(mig), exist_ok=True)
    with open(mig, "wb") as fh:
        for rec in sorted(records, key=lambda r: r["dst"].encode("utf-8")):
            rel = os.path.relpath(rec["dst"], R7)
            fh.write(("%s  %s  %s\n" % (rec["sha256"], rec["tag"], rel))
                     .encode("utf-8"))

    print(json.dumps({
        "r7_root": R7,
        "package_files_carried": package_count,
        "lineage_files_preserved": lineage_count,
        "total_files_verified": len(records),
        "every_file_digest_matched": True,
        "migration_manifest": mig,
        "migration_manifest_sha256": sha256_file(mig),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
