#!/usr/bin/env python3
"""Build the attempt-5 machine-readable tool inventory.

One row per tool, with ROLE, PATH, SHA256, MANIFEST_COVERED and BOUND_BY.

Roles are separated deliberately. Attempt 4's record did not distinguish the
verification INSTRUCTIONS from the verification RUNNER from the verification
RESULT, and `VERIFICATION_RESULT.json` -- an output -- sat in a list of tools.
A result is not a verifier. It is not in this inventory; it is bound by the
freeze plan as an artefact, under its own role.

If a tool named here cannot be identified or read, this script exits non-zero
with VERIFICATION_FAIL_UNIDENTIFIED_TOOL and no inventory is written.
"""

import hashlib
import inspect
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A5_ROOT = os.path.dirname(HERE)
ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
CLONE = os.path.join(A5_ROOT, "test_clone", "08.18.26_Level1_Audits_R8")

MANIFEST = os.path.join(ROOT, "build", "R8_BUILD_MANIFEST.sha256")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_paths():
    out = set()
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            out.add(line[66:])
    return out


# (ROLE, PATH, BOUND_BY)
#
# BOUND_BY says where this row's digest is carried forward so that a later
# change to the tool invalidates something. "R8_BUILD_MANIFEST" means the
# build manifest covers it and the manifest digest is the token's first field.
# "FREEZE_PLAN_ATTEMPT_2.external_bound_artifacts" means the plan carries the
# digest directly. "ENVIRONMENT" means the tool is a system executable whose
# digest is recorded for provenance and which no artefact binds -- stated
# rather than left implicit.
IN_PACKAGE = [
    ("STATIC_SAFETY_REVIEWER", "build/r8_static_safety_review.py"),
    ("FREEZE_MODULE", "automation/freeze.py"),
    ("FREEZE_ROUTE_DRIVER", "automation/controller.py"),
    ("IN_PROCESS_EXECUTOR", "automation/in_process_executor.py"),
    ("IN_PROCESS_OPS", "automation/in_process_ops.py"),
    ("OPERATION_CATALOG", "automation/operation_catalog.py"),
    ("MIGRATION_ROUTE", "automation/migration.py"),
    ("PATH_POLICY", "automation/path_policy.py"),
    ("POLICY_CONSTANTS", "automation/policy.py"),
    ("HASHING", "automation/hashing.py"),
    ("REHEARSAL_HARNESS", "build/rehearse_candidate_plans.py"),
    ("BUILD_MANIFEST_BUILDER", "build/build_r8_build_manifest.py"),
    ("CONTROL_EXPECTATION_BUILDER", "build/control_expectations.py"),
    ("MIGRATION_PLAN_BUILDER", "build/build_migration_plan.py"),
    ("CLOSURE_RECORD_BUILDER", "build/build_r8_closure_record.py"),
    ("MEASUREMENT_RECORDS_BUILDER", "build/build_r8_measurement_records.py"),
    ("RESUME_STATUS_BUILDER", "build/build_r8_resume_status.py"),
    ("PREDECESSOR_INTEGRITY_VERIFIER", "build/verify_predecessor_integrity.py"),
    ("TEST_SUITE_RUNNER_NOT_USED_BY_ATTEMPT_5", "build/run_test_suites.py"),
]

ATTEMPT_1_BUILDER = "build/freeze_plan_attempt_1/build_r8_freeze_plan.py"

EXTERNAL = [
    ("VERIFICATION_INSTRUCTIONS",
     os.path.join(A5_ROOT, "tools", "VERIFY_PROMPT_ATTEMPT_5.md")),
    ("VERIFICATION_RUNNER",
     os.path.join(A5_ROOT, "tools", "run_verification_attempt_5.sh")),
    ("VERIFIER_HELPER_INVENTORY",
     os.path.join(A5_ROOT, "tools", "inventory_r8.py")),
    ("VERIFIER_HELPER_INVENTORY_COMPARE",
     os.path.join(A5_ROOT, "tools", "compare_inventories.py")),
    ("VERIFIER_HELPER_TOOL_INVENTORY_BUILDER",
     os.path.join(A5_ROOT, "tools", "build_tool_inventory.py")),
    ("FREEZE_PLAN_BUILDER",
     os.path.join(A5_ROOT, "tools", "build_r8_freeze_plan_attempt_2.py")),
    ("FREEZE_PLAN_VALIDATOR",
     os.path.join(A5_ROOT, "tools", "validate_freeze_plan_attempt_2.py")),
]

SYSTEM = [
    ("VERIFIER_EXECUTABLE_CODEX", "codex"),
    ("PYTHON_INTERPRETER", "/usr/bin/python3"),
    ("TOKEN_HASH_EXECUTABLE_SHA256SUM", "/usr/bin/sha256sum"),
    ("SHELL", "/usr/bin/bash"),
]


def main():
    covered = manifest_paths()
    rows = []
    unidentified = []

    def add(role, path, bound_by, manifest_covered, extra=None):
        if not os.path.isfile(path):
            unidentified.append({"ROLE": role, "PATH": path,
                                 "PROBLEM": "absent"})
            return
        row = {"ROLE": role, "PATH": path, "SHA256": sha256_file(path),
               "MANIFEST_COVERED": manifest_covered, "BOUND_BY": bound_by,
               "SIZE": os.path.getsize(path)}
        if extra:
            row.update(extra)
        rows.append(row)

    for role, rel in IN_PACKAGE:
        add(role, os.path.join(ROOT, rel),
            "R8_BUILD_MANIFEST + FREEZE_PLAN_ATTEMPT_2.bound_artifacts"
            if rel in covered else "FREEZE_PLAN_ATTEMPT_2.bound_artifacts",
            rel in covered, {"REL": rel})

    add("FREEZE_PLAN_BUILDER_ATTEMPT_1_DERIVATION_SOURCE",
        os.path.join(ROOT, ATTEMPT_1_BUILDER),
        "FREEZE_PLAN_ATTEMPT_2.bound_artifacts_derivation.source_sha256",
        ATTEMPT_1_BUILDER in covered,
        {"REL": ATTEMPT_1_BUILDER,
         "NOTE": ("read by the attempt-2 builder for its bound list, so a "
                  "transcription slip cannot drop a binding. Its stale "
                  "attempt-3 verification constant and its own self-reference "
                  "are removed and the removal is asserted. It is not "
                  "executed as attempt 5's builder.")})

    for role, path in EXTERNAL:
        add(role, path, "FREEZE_PLAN_ATTEMPT_2.external_bound_artifacts",
            False)

    for role, name in SYSTEM:
        resolved = shutil.which(name) if not os.path.isabs(name) else name
        if resolved:
            resolved = os.path.realpath(resolved)
        if not resolved or not os.path.isfile(resolved):
            unidentified.append({"ROLE": role, "PATH": name,
                                 "PROBLEM": "not resolvable on PATH"})
            continue
        add(role, resolved, "ENVIRONMENT", False,
            {"INVOKED_AS": name,
             "NOTE": ("system executable; digest recorded for provenance. No "
                      "artefact binds it and this row says so rather than "
                      "leaving it implied.")})

    # The token generator, which is a function and not a file.
    sys.path.insert(0, CLONE)
    from automation import freeze
    source = inspect.getsource(freeze.token_for)
    rows.append({
        "ROLE": "FREEZE_TOKEN_GENERATOR",
        "PATH": "automation/freeze.py::token_for",
        "SHA256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "MANIFEST_COVERED": "automation/freeze.py" in covered,
        "BOUND_BY": "FREEZE_PLAN_ATTEMPT_2.token_generator.source_sha256",
        "SIZE": len(source.encode("utf-8")),
        "NOTE": ("the digest is over the exact source of the function, not "
                 "over its module. The module's own digest is the "
                 "FREEZE_MODULE row."),
    })

    rows.append({
        "ROLE": "PLAN_RUNNER",
        "PATH": "NOT_USED",
        "SHA256": "NOT_USED",
        "MANIFEST_COVERED": False,
        "BOUND_BY": "NOT_USED",
        "SIZE": 0,
        "NOTE": ("attempt 4 used a wrapper, "
                 "R8_in_process_execution_repair/attempt_4/"
                 "run_freeze_plan_builder.py, to override the builder's "
                 "stale VERIFICATION_DIR constant at run time. That wrapper "
                 "determined which verification the plan bound and was not "
                 "itself bound by the plan. Attempt 5 uses no wrapper: its "
                 "builder carries no constant that needs overriding, and it "
                 "is executed directly."),
    })

    if unidentified:
        sys.stderr.write("VERIFICATION_FAIL_UNIDENTIFIED_TOOL\n")
        sys.stderr.write(json.dumps(unidentified, indent=1) + "\n")
        return 3

    rows.sort(key=lambda r: (r["ROLE"], r["PATH"]))
    doc = {
        "schema": "wpno.r8.attempt5-tool-inventory/1",
        "attempt": 5,
        "r8_root": ROOT,
        "attempt5_root": A5_ROOT,
        "roles_are_distinct": (
            "VERIFICATION_INSTRUCTIONS, VERIFICATION_RUNNER and the "
            "verification RESULT are three different things. The result is "
            "not listed here; it is an output, bound by the freeze plan under "
            "role ATTEMPT5_VERIFICATION_RESULT."),
        "tool_count": len(rows),
        "unidentified_tools": [],
        "tools": rows,
    }
    out_path = os.path.join(A5_ROOT, "TOOL_INVENTORY.json")
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(raw)
    print(json.dumps({
        "out": out_path,
        "tool_count": len(rows),
        "manifest_covered": sum(1 for r in rows
                                if r["MANIFEST_COVERED"] is True),
        "unidentified_tools": 0,
        "tool_inventory_sha256":
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
