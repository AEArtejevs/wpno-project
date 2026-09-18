#!/usr/bin/env python3
"""Write the two pre-revocation records section 3 requires.

Read-only against R8. Neither record carries a raw token: the controller's
ledgers store digests and bindings only, and that is measured in
`preserve_epoch.py` rather than assumed here.

Usage: write_pre_revocation_records.py <r8> <out>
"""

import hashlib
import io
import json
import os
import sys
import time


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path):
    if not os.path.isfile(path):
        return []
    with io.open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def tree(r8, relative):
    base = os.path.join(r8, relative)
    rows = []
    if not os.path.isdir(base):
        return rows
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rows.append({"relative": os.path.relpath(full, r8),
                         "sha256": sha256_file(full),
                         "size": os.path.getsize(full)})
    return rows


def freeze_record(r8):
    ledger = load_jsonl(os.path.join(r8, "state", "freeze_attempts.jsonl"))
    plan_rel = os.path.join("build", "freeze_plan_attempt_3",
                            "FREEZE_PLAN_R8_ATTEMPT_3.json")
    plan_path = os.path.join(r8, plan_rel)
    with io.open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    with io.open(os.path.join(r8, "state", "PACKAGE_VERIFIED.json"),
                 encoding="utf-8") as handle:
        verified = json.load(handle)
    with io.open(os.path.join(r8, "BASELINE_MANIFEST.json"),
                 encoding="utf-8") as handle:
        baseline = json.load(handle)
    with io.open(os.path.join(r8, "CONTROL_MANIFEST.sha256"),
                 encoding="utf-8") as handle:
        entries = sum(1 for line in handle if line.strip())

    return {
        "schema": "wpno.r8.pre-revocation-freeze-record/1",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode_at_record": io.open(
            os.path.join(r8, "MODE"), encoding="utf-8").read().strip(),
        "freeze_attempt_number": plan["attempt_number"],
        "freeze_plan_path": plan_rel.replace(os.sep, "/"),
        "freeze_plan_sha256": sha256_file(plan_path),
        "package_sha256_bound_by_plan": plan["package_sha256"],
        "verification_result_sha256_bound_by_plan":
            plan["verification_result_sha256"],
        "verification_directory": plan["verification_path"],
        "bound_artifacts": len(plan["bound_artifacts"]),
        "predecessor_lineage_required":
            plan["predecessor_lineage"]["required_artifacts"],
        "control_manifest_sha256": sha256_file(
            os.path.join(r8, "CONTROL_MANIFEST.sha256")),
        "control_manifest_entries": entries,
        "baseline_manifest_sha256": sha256_file(
            os.path.join(r8, "BASELINE_MANIFEST.json")),
        "project_baseline_members": len(baseline["project_files"]),
        "discovery_baseline_members": len(baseline["discovery_files"]),
        "package_verified_sha256": sha256_file(
            os.path.join(r8, "state", "PACKAGE_VERIFIED.json")),
        "package_verified_frozen_at_utc": verified["frozen_at_utc"],
        "freeze_ledger": [
            {k: row.get(k) for k in
             ("outcome", "attempt_number", "token_sha256", "recorded_at")}
            for row in ledger],
        "freeze_token_sha256_only": sorted(
            {row.get("token_sha256") for row in ledger
             if row.get("token_sha256")}),
        "raw_token_preserved": False,
        "freeze_was_valid_when_created": True,
        "why_being_revoked": (
            "the frozen specification left 'the purpose in question' for EKU "
            "undefined; the frozen L1-A31 RUN-A and RUN-B plans produced no "
            "explicit machine-checkable key-usage or EKU determination; and "
            "the frozen COMPARISON plan hashed two attempt indexes instead of "
            "comparing the five substantive dimensions its own test_matrix "
            "names. None of that is repairable without changing "
            "manifest-covered bytes, and R8 is the final revision."),
    }


def execution_record(r8):
    with io.open(os.path.join(r8, "state", "progress.json"),
                 encoding="utf-8") as handle:
        progress = json.load(handle)
    a31 = progress["audits"]["L1-A31"]
    indexes = {}
    for phase in ("RUN-A", "RUN-B"):
        path = os.path.join(r8, "evidence", "L1-A31", phase,
                            "ATTEMPT_INDEX.json")
        if os.path.isfile(path):
            indexes[phase] = sha256_file(path)

    return {
        "schema": "wpno.r8.pre-revocation-execution-record/1",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "epoch": "EXECUTION_EPOCH_1",
        "L1-A31_phase_states": {k: v["state"] for k, v in sorted(a31.items())},
        "L1-A31_attempt_states": {
            k: {n: a.get("state") for n, a in (v.get("attempts") or {}).items()}
            for k, v in sorted(a31.items())},
        "run_a_origin": ("imported predecessor attempt from R7, sealed, "
                         "verdict UNVERIFIED"),
        "run_b_origin": ("imported predecessor attempt from R7, sealed, "
                         "verdict UNVERIFIED"),
        "comparison_origin": ("executed in R8 under a consumed one-time "
                              "approval; attempt OPEN and unsealed"),
        "comparison_approval_recorded": load_jsonl(
            os.path.join(r8, "state", "approvals.jsonl")),
        "migration_ledger": load_jsonl(
            os.path.join(r8, "state", "migrations.jsonl")),
        "evidence_files": tree(r8, os.path.join("evidence", "L1-A31")),
        "results_files": tree(r8, os.path.join("results", "L1-A31")),
        "attempt_indexes": indexes,
        "the_finding": (
            "COMPARISON executed 3 of 3 planned steps with 0 failures and "
            "produced 3 hash-bound evidence records, but it did NOT measure "
            "the five substantive dimensions its own test_matrix names -- "
            "chain path validation outcome, CMS signature outcome, key-usage "
            "conformance determination, validation time used, anchor "
            "identity. Its steps parsed state/progress.json and hashed the "
            "two ATTEMPT_INDEX.json files. Every step reported "
            "NO_MACHINE_CHECKABLE_EXPECTATION, so the run could not have "
            "detected a disagreement between RUN-A and RUN-B, and its clean "
            "result is not evidence that none exists."),
        "raw_token_preserved": False,
    }


def main():
    r8, out = os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])
    written = {}
    for name, payload in (
            ("PRE_REVOCATION_FREEZE_RECORD.json", freeze_record(r8)),
            ("PRE_REVOCATION_EXECUTION_RECORD.json", execution_record(r8))):
        path = os.path.join(out, name)
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=1, sort_keys=True) + "\n")
        written[name] = sha256_file(path)

    execution = execution_record(r8)
    print(json.dumps({
        "written": written,
        "evidence_files": len(execution["evidence_files"]),
        "results_files": len(execution["results_files"]),
        "attempt_indexes": sorted(execution["attempt_indexes"]),
        "phase_states": execution["L1-A31_phase_states"],
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
