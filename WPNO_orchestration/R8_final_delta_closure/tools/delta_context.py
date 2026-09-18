#!/usr/bin/env python3
"""Load, once, every document the delta predicates read.

One loader for the self-test and for the real run, so the predicates cannot
be exercised against one shape and then run against another.

Reads ORIGINAL R8 for every value. Imports `automation` from the CLONE, which
is proved byte-identical, so no import can leave a `__pycache__` inside the
package even if the bytecode redirect were to fail.
"""

import hashlib
import json
import os
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(r8, clone, tool_inventory_path=None, writers_path=None):
    r8 = os.path.realpath(r8)
    clone = os.path.realpath(clone)
    sys.path.insert(0, clone)
    from automation import freeze, operation_catalog, in_process_ops

    docs = {}
    docs["r8_root"] = r8
    docs["clone"] = clone
    docs["recon"] = load_json(os.path.join(
        r8, "build", "IN_PROCESS_COUNT_RECONCILIATION.json"))
    docs["rehearsal"] = load_json(os.path.join(
        r8, "work", "_rehearsal_r8", "REHEARSAL_REPORT.json"))
    docs["lineage"] = load_json(os.path.join(r8, "lineage",
                                             "R8_LINEAGE.json"))

    # the 43 plans, read from disk
    plans = []
    base = os.path.join(r8, "build", "candidate_plans_r8")
    for audit_id in sorted(os.listdir(base)):
        audit_dir = os.path.join(base, audit_id)
        if not os.path.isdir(audit_dir):
            continue
        for phase in sorted(os.listdir(audit_dir)):
            plan_path = os.path.join(audit_dir, phase, "plan.json")
            if os.path.isfile(plan_path):
                plans.append((audit_id, phase, load_json(plan_path)))
    docs["plans"] = plans

    docs["in_process_operations"] = set(operation_catalog.IN_PROCESS)
    docs["handlers"] = set(in_process_ops.HANDLERS)

    # freeze capability, measured without producing the real token
    docs["freeze_revision"] = freeze.PACKAGE_REVISION
    docs["freeze_platform"] = freeze.PACKAGE_PLATFORM
    baseline_rel = freeze.PREDECESSOR_BASELINE_REL
    baseline_path = os.path.join(r8, baseline_rel)
    docs["baseline_rel"] = baseline_rel
    docs["baseline_file_sha256"] = (sha256_file(baseline_path)
                                    if os.path.isfile(baseline_path) else None)
    docs["lineage_baseline_sha256"] = (
        docs["lineage"].get("r7", {}).get("baseline_manifest_sha256"))
    try:
        baseline, provenance = freeze.build_baseline_from_predecessor(
            clone, docs["baseline_file_sha256"])
        docs["baseline_raised"] = False
        docs["baseline_project_members"] = provenance["project_members"]
        docs["baseline_discovery_members"] = provenance["discovery_members"]
    except Exception as exc:                                # noqa: BLE001
        docs["baseline_raised"] = True
        docs["baseline_error"] = "%s: %s" % (type(exc).__name__, exc)
        docs["baseline_project_members"] = 0
        docs["baseline_discovery_members"] = 0

    # DUMMY digests only. The real token is not computed here and must not be.
    dummy = [hashlib.sha256(x).hexdigest() for x in (b"a", b"b", b"c")]
    token = freeze.token_for(*dummy)
    parsed = freeze.parse_freeze_token(token)
    docs["dummy_digests"] = dummy
    docs["token_field_count"] = len(token.split())
    docs["token_trailing_newline"] = token.endswith("\n")
    docs["token_roundtrip_ok"] = (
        parsed.get("package_sha256") == dummy[0]
        and parsed.get("verification_sha256") == dummy[1]
        and parsed.get("freeze_plan_sha256") == dummy[2])
    docs["dummy_token_is_not_the_real_token"] = True

    ledger = os.path.join(r8, "state", "freeze_attempts.jsonl")
    docs["freeze_attempts"] = len(freeze.recorded_attempts(ledger))
    docs["mode"] = open(os.path.join(r8, "MODE"),
                        encoding="utf-8").read().strip()
    docs["r9_exists"] = os.path.exists(
        os.path.join(os.path.dirname(r8), "08.18.26_Level1_Audits_R9"))

    tpath = os.path.join(r8, "state", "transitions.jsonl")
    docs["transitions"] = [json.loads(l) for l in
                           open(tpath, encoding="utf-8") if l.strip()]

    if tool_inventory_path and os.path.isfile(tool_inventory_path):
        inv = load_json(tool_inventory_path)
        docs["tool_inventory"] = inv
        bad = []
        for row in inv.get("tools", []):
            path = row.get("CANONICAL_PATH")
            declared = row.get("SHA256")
            if declared == "NOT_USED" or path == "NOT_USED":
                continue
            if "::" in str(path):          # a function, not a file
                continue
            if not os.path.isfile(path):
                bad.append({"path": path, "problem": "absent"})
            elif sha256_file(path) != declared:
                bad.append({"path": path, "declared": declared,
                            "actual": sha256_file(path)})
        docs["tool_digest_mismatches"] = bad
    else:
        docs["tool_inventory"] = {}
        docs["tool_digest_mismatches"] = []

    docs["writers"] = (load_json(writers_path)
                       if writers_path and os.path.isfile(writers_path)
                       else {})
    return docs
