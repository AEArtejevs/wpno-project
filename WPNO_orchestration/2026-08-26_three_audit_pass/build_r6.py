#!/usr/bin/env python3
"""Create the R6 sibling without mutating R4 or R5.

The complete R5 tree is copied beneath R6 lineage.  The active package is a
clean derivative of R5: immutable inputs and control-plane sources are copied,
but frozen artefacts and runtime state are not inherited.  Active state is
created later, exclusively by ``automation.controller init-revision``.
"""

import hashlib
import json
import os
import shutil
import sys


R5 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5"
R6 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6"
ORCH = "/home/ubuntu/project/WPNO_orchestration/2026-08-26_three_audit_pass"

EXCLUDE_TOP = {
    "BASELINE_MANIFEST.json",
    "BUILD_MANIFEST.sha256",
    "CONTROL_MANIFEST.sha256",
    "MODE",
    "evidence",
    "lineage",
    "logs",
    "results",
    "state",
    "verification_claude_2",
    "verification_claude_3",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_complete_predecessor():
    lineage = os.path.join(R6, "lineage")
    os.makedirs(lineage)
    target = os.path.join(lineage, "R5_EXECUTION")
    shutil.copytree(R5, target, symlinks=True, copy_function=shutil.copy2)
    return target


def copy_active_derivative():
    for name in sorted(os.listdir(R5)):
        if name in EXCLUDE_TOP:
            continue
        source = os.path.join(R5, name)
        target = os.path.join(R6, name)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        elif os.path.isdir(source):
            shutil.copytree(source, target, symlinks=True,
                            copy_function=shutil.copy2)
        else:
            shutil.copy2(source, target)
    for name in ("state", "results", "evidence", "logs", "work"):
        os.makedirs(os.path.join(R6, name), exist_ok=True)
    with open(os.path.join(R6, "MODE"), "w", encoding="utf-8") as handle:
        handle.write("GENERATED_UNVERIFIED\n")


def write_lineage_manifest(predecessor_copy):
    rows = []
    for directory, dirnames, filenames in os.walk(predecessor_copy,
                                                  followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(directory, name)
            if os.path.islink(full):
                raise RuntimeError("R5 lineage contains symlink: %s" % full)
            if not os.path.isfile(full):
                raise RuntimeError("R5 lineage contains non-file: %s" % full)
            relative = os.path.relpath(full, os.path.dirname(predecessor_copy))
            rows.append((relative, sha256_file(full)))
    manifest = os.path.join(R6, "lineage", "R5_EXECUTION_MANIFEST.sha256")
    with open(manifest, "w", encoding="utf-8") as handle:
        for relative, digest in sorted(rows):
            handle.write("%s  %s\n" % (digest, relative))
    return manifest, len(rows)


def verify_lineage(predecessor_copy, manifest):
    checked = 0
    with open(manifest, encoding="utf-8") as handle:
        for line in handle:
            digest, relative = line.rstrip("\n").split("  ", 1)
            full = os.path.join(os.path.dirname(predecessor_copy), relative)
            if sha256_file(full) != digest:
                raise RuntimeError("lineage copy mismatch: %s" % relative)
            checked += 1
    source_files = sum(len(files) for _, _, files in os.walk(R5))
    if checked != source_files:
        raise RuntimeError("lineage count mismatch: %d != %d" %
                           (checked, source_files))
    return checked


def write_classification(manifest, count):
    record = {
        "schema": "wpno.level1.lineage-classification/1",
        "predecessor_revision": "R5",
        "successor_revision": "R6",
        "classification":
            "SUPERSEDED_INVALID_FREEZE_MODE_MANIFEST_ORDERING",
        "predecessor_root": R5,
        "predecessor_mutated_by_r6_build": False,
        "complete_copy_path": "lineage/R5_EXECUTION",
        "complete_copy_manifest": "lineage/R5_EXECUTION_MANIFEST.sha256",
        "complete_copy_manifest_sha256": sha256_file(manifest),
        "complete_copy_file_count": count,
        "known_manifest_failure": {
            "failed_entries": 1,
            "failed_path": "MODE",
            "recorded_digest":
                "0dba1cc2928ed5a2a3259b8d9aa4188feb6b775c91d7eab990bb75fa49cd6eee",
            "disk_digest":
                "67885f01edc72c2991b2ae9be04afc14a743b79c9d382262620be8ac154fa5fa",
        },
        "raw_r5_freeze_token_copied_into_new_active_evidence": False,
        "r5_snapshot_sha256":
            "7a9410d1e8dfbe504d6dc6a1684e83e0baec1a632003a629e67b85473a064e1b",
    }
    path = os.path.join(R6, "lineage", "R5_LINEAGE_CLASSIFICATION.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def main():
    if not os.path.isdir(R5):
        raise SystemExit("R5 is absent")
    if os.path.lexists(R6):
        raise SystemExit("R6 already exists; refusing to overwrite")
    os.mkdir(R6)
    try:
        predecessor_copy = copy_complete_predecessor()
        copy_active_derivative()
        manifest, count = write_lineage_manifest(predecessor_copy)
        checked = verify_lineage(predecessor_copy, manifest)
        classification = write_classification(manifest, checked)
    except Exception:
        print("R6 construction failed; partial sibling preserved at %s" % R6,
              file=sys.stderr)
        raise
    print(json.dumps({
        "created": R6,
        "lineage_copy": predecessor_copy,
        "lineage_manifest": manifest,
        "lineage_manifest_sha256": sha256_file(manifest),
        "lineage_files_verified": checked,
        "classification": classification,
        "active_mode": "GENERATED_UNVERIFIED",
        "active_state_initialised": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
