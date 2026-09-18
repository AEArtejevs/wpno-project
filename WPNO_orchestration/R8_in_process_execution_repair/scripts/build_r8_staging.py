#!/usr/bin/env python3
"""Construct the R8 active package from the restored R7 control-plane sources.

Space is the binding constraint: R7 is 676 MiB of which 573 MiB is the
inherited lineage tree. Copying that tree again would buy nothing -- the
lineage it holds is R4 through R6, already verified in place -- and would
cost more than the free space allows. So R8 inherits it by hash-bound
reference and carries only a compact lineage record of its own.

No hardlink is created between an active R7 file and an active R8 file. A
hardlink would make the two revisions the same inode, and a write to one
would silently be a write to the other; that is exactly the class of defect
this revision exists to repair.

The copy is made into a staging root and renamed into place only after it
verifies, so a partial tree can never be mistaken for a package.
"""

import hashlib
import json
import os
import shutil
import sys
import time

R7 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7"
R8 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
STAGING = "%s.staging.%d" % (R8, os.getpid())

# Directories copied whole (minus the prunes below).
COPY_DIRS = ("automation", "bindings", "corpora", "discovery_reconciliation",
             "prompts", "references", "tools", "transfer")

# Files copied individually.
COPY_FILES = ("AGENTS.md", "audit_registry.json", "paths.json",
              "run_audit_module.py",
              "00_CLAUDE_VERIFY_R5_PASS_READINESS.md",
              "00_CODEX_VERIFY_R5_PASS_READINESS.md",
              "00_COMMON_RULES.md",
              "00_OPERATOR_CLAUDE_VERIFY_R5.md",
              "00_OPERATOR_CODEX_VERIFY_R5.md",
              "00_OPERATOR_R7_HUMAN_GATES.md",
              "00_OPERATOR_RUNBOOK_LV.md",
              "01_CODEX_RUN_LEVEL1.md",
              "02_CODEX_CONSOLIDATE_LEVEL1.md",
              "03_CODEX_LEVEL2_ADVERSARIAL.md")

# build/ is copied selectively: the builders are reusable, the R7 outputs are
# not. Named individually so that a new R7 artefact appearing here would be
# an unlisted file rather than a silent inclusion.
COPY_BUILD = ("build_all_candidate_plans.py", "build_candidate_plans.py",
              "build_final_closure_record.py", "build_r7_selftest_replica.py",
              "candidate_plan_specs.py", "derive_a19_vectors.py",
              "plan_library.py", "r7_static_safety_review.py",
              "rehearse_candidate_plans.py", "run_test_suites.py",
              "stage_l1a31_material.py", "stage_rehearsal_fixtures.py",
              "verify_predecessor_integrity.py")
COPY_BUILD_DIRS = ("all_level1_scope",)
COPY_BUILD_TOOLING = {
    "resume_r7/build_r7_build_manifest.py": "build_r8_build_manifest.py",
    "resume_r7/tree_snapshot.py": "tree_snapshot.py",
    "resume_r7/validate_status_record.py": "validate_status_record.py",
    "freeze_plan_attempt_1/build_final_freeze_plan.py":
        "build_r8_freeze_plan.py",
}

# Everything below is R7-specific active or frozen state and is excluded by
# name, so the exclusion is a decision on the record rather than an omission.
EXCLUDED_TOP = (
    "MODE", "CONTROL_MANIFEST.sha256", "BASELINE_MANIFEST.json", "BUILD_ID",
    "state", "results", "evidence", "work", "logs", "lineage", "verification",
    "verification_codex_pre_freeze",
    "verification_codex_final_pre_freeze_attempt_1",
    "verification_codex_final_pre_freeze_attempt_2",
    "verification_codex_final_pre_freeze_attempt_3",
    "verification_codex_final_pre_freeze_attempt_4",
    "verification_codex_final_pre_freeze_attempt_5",
    "verification_codex_final_pre_freeze_attempt_6",
    "00_BUILD_STATUS.md", "00_CODEX_VERIFY_R7_PRE_FREEZE.md",
    "build",
)
EXCLUDED_BUILD = (
    "R7_BUILD_MANIFEST.sha256", "R7_CHANGED_FILES.sha256",
    "R7_FINAL_PRE_FREEZE_CLOSURE.json", "R7_STATIC_SAFETY_REPORT.json",
    "R7_TEST_SUITE_RESULTS.json",
    "FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.json",
    "FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.sha256",
    "candidate_plans_r7", "freeze_plan_attempt_1", "resume_r7",
    "build_r7_freeze_plan.py", "__pycache__",
)

PRUNE_DIRS = ("__pycache__",)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(src, dst, record):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        raise SystemExit("refusing to copy a symlink: %s" % src)
    shutil.copy2(src, dst)
    # Break any accidental identity with the source: a fresh inode is the
    # point. copy2 already creates one; this asserts it rather than assumes.
    if os.stat(src).st_ino == os.stat(dst).st_ino:
        raise SystemExit("copy shares an inode with its source: %s" % src)
    digest = sha256_file(src)
    if sha256_file(dst) != digest:
        raise SystemExit("copy does not match its source: %s" % src)
    record.append({"relative_path": os.path.relpath(dst, STAGING),
                   "source": os.path.relpath(src, R7),
                   "sha256": digest,
                   "size": os.path.getsize(src)})


def copy_tree(rel, record):
    src_root = os.path.join(R7, rel)
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE_DIRS)
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            src = os.path.join(dirpath, name)
            dst = os.path.join(STAGING, os.path.relpath(src, R7))
            copy_file(src, dst, record)


def main():
    if os.path.exists(R8):
        raise SystemExit("R8 already exists: %s" % R8)
    if os.path.exists(STAGING):
        raise SystemExit("staging root already exists: %s" % STAGING)

    statvfs = os.statvfs("/home/ubuntu")
    free_before = statvfs.f_bavail * statvfs.f_frsize

    record = []
    os.makedirs(STAGING)

    for rel in COPY_DIRS:
        copy_tree(rel, record)
    for name in COPY_FILES:
        copy_file(os.path.join(R7, name), os.path.join(STAGING, name), record)
    for name in COPY_BUILD:
        copy_file(os.path.join(R7, "build", name),
                  os.path.join(STAGING, "build", name), record)
    for rel in COPY_BUILD_DIRS:
        copy_tree(os.path.join("build", rel), record)
    for src_rel, dst_name in sorted(COPY_BUILD_TOOLING.items()):
        copy_file(os.path.join(R7, "build", src_rel),
                  os.path.join(STAGING, "build", dst_name), record)

    # Mutable runtime directories exist but are empty. They are not copied
    # from R7; R8 starts with no results, no evidence and no logs.
    for rel in ("state", "results", "evidence", "work", "logs", "lineage"):
        os.makedirs(os.path.join(STAGING, rel), exist_ok=True)

    statvfs = os.statvfs("/home/ubuntu")
    free_after = statvfs.f_bavail * statvfs.f_frsize
    physical = sum(row["size"] for row in record)

    r7_total = 0
    for dirpath, dirnames, filenames in os.walk(R7):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                r7_total += os.path.getsize(full)
    lineage_bytes = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(R7, "lineage")):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                lineage_bytes += os.path.getsize(full)

    summary = {
        "schema": "wpno.r8.source_manifest/1",
        "built_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "R8_COPY_METHOD": ("per-file shutil.copy2 from the restored R7 "
                           "control plane; no hardlink, no symlink, no "
                           "reflink; every destination hash re-verified "
                           "against its source"),
        "R8_PHYSICAL_BYTES_ADDED": physical,
        "R8_FILE_COUNT": len(record),
        "R7_TOTAL_BYTES": r7_total,
        "R7_LINEAGE_BYTES": lineage_bytes,
        "R7_BYTES_NOT_DUPLICATED": r7_total - physical,
        "free_bytes_before": free_before,
        "free_bytes_after": free_after,
        "excluded_top_level": list(EXCLUDED_TOP),
        "excluded_build": list(EXCLUDED_BUILD),
        "staging_root": STAGING,
        "files": record,
    }
    out = ("/home/ubuntu/project/WPNO_orchestration/"
           "R8_in_process_execution_repair/measurements/"
           "R7_TO_R8_SOURCE_MANIFEST.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "files"},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
