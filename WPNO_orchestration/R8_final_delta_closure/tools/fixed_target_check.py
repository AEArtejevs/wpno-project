#!/usr/bin/env python3
"""The fixed R8 target, measured before any verifier work.

Nine values. Every one is read from bytes on disk; none is taken from an
earlier attempt's record. If one differs the delta closure does not start,
because a delta rests on a base and a base that has moved is not a base.

Usage: fixed_target_check.py <r8> <r7> <out.json>
Exit 0 only when every value matches.
"""

import collections
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


def verify_manifest(root, rel):
    path = os.path.join(root, rel)
    ok = bad = 0
    missing, mismatched, malformed, dup = [], [], [], []
    seen = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            if "  " not in line:
                malformed.append(line)
                continue
            digest, relpath = line.split("  ", 1)
            if relpath in seen:
                dup.append(relpath)
            seen.add(relpath)
            target = os.path.join(root, relpath)
            if not os.path.isfile(target):
                missing.append(relpath)
                bad += 1
                continue
            if sha256_file(target) != digest:
                mismatched.append(relpath)
                bad += 1
                continue
            ok += 1
    return {"manifest": path, "manifest_sha256": sha256_file(path),
            "entries": len(seen), "ok": ok, "bad": bad,
            "missing": missing, "mismatched": mismatched,
            "malformed": malformed, "duplicates": dup}


def main():
    r8, r7, out_path = (os.path.realpath(sys.argv[1]),
                        os.path.realpath(sys.argv[2]), sys.argv[3])
    checks = {}

    mode = open(os.path.join(r8, "MODE"), encoding="utf-8").read().strip()
    checks["mode"] = {"measured": mode, "expected": "GENERATED_UNVERIFIED",
                      "PASS": mode == "GENERATED_UNVERIFIED"}

    man = verify_manifest(r8, os.path.join("build", "R8_BUILD_MANIFEST.sha256"))
    checks["build_manifest"] = {
        "measured": {k: man[k] for k in ("manifest_sha256", "entries", "ok",
                                         "bad", "missing", "mismatched",
                                         "malformed", "duplicates")},
        "expected": {"manifest_sha256": ("6dfd1af689754be61f2ea6ef77f01d2e5"
                                         "bdb8929ef8c0799e15db203755b945a"),
                     "entries": 724, "ok": 724, "bad": 0},
        "PASS": (man["manifest_sha256"] == ("6dfd1af689754be61f2ea6ef77f01d2e5"
                                            "bdb8929ef8c0799e15db203755b945a")
                 and man["entries"] == 724 and man["ok"] == 724
                 and man["bad"] == 0 and not man["malformed"]
                 and not man["duplicates"])}

    with open(os.path.join(r8, "state", "progress.json"),
              encoding="utf-8") as fh:
        progress = json.load(fh)
    states = collections.Counter()
    audits = len(progress["audits"])
    for phases in progress["audits"].values():
        for rec in phases.values():
            states[rec["state"]] += 1
    checks["active_phases"] = {
        "measured": {"audits": audits, "phases": sum(states.values()),
                     "states": dict(states)},
        "expected": {"phases": 43, "states": {"NOT_STARTED": 43}},
        "PASS": sum(states.values()) == 43 and dict(states) == {"NOT_STARTED": 43}}

    approvals = os.path.getsize(os.path.join(r8, "state", "approvals.jsonl"))
    results = os.listdir(os.path.join(r8, "results"))
    evidence = os.listdir(os.path.join(r8, "evidence"))
    checks["approvals_results_evidence"] = {
        "measured": {"approvals_bytes": approvals, "results": len(results),
                     "evidence": len(evidence)},
        "expected": {"approvals_bytes": 0, "results": 0, "evidence": 0},
        "PASS": approvals == 0 and not results and not evidence}

    mig_dir = os.path.join(r8, "build", "migration_plan_r7_to_r8")
    with open(os.path.join(mig_dir, "MIGRATION_PLAN.json"),
              encoding="utf-8") as fh:
        raw = fh.read()
    plan = json.loads(raw)
    declared = open(os.path.join(mig_dir, "MIGRATION_PLAN.sha256"),
                    encoding="utf-8").read().split()[0]
    actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    ledger = os.path.join(r8, "state", "migrations.jsonl")
    consumed = os.path.exists(ledger) and os.path.getsize(ledger) > 0
    route = sha256_file(os.path.join(r8, "automation", "migration.py"))
    checks["migration_packet"] = {
        "measured": {"plan_sha256_declared": declared,
                     "plan_sha256_actual": actual,
                     "applied_before_freeze": plan["applied_before_freeze"],
                     "consumed": consumed,
                     "route_module_sha256_declared":
                         plan.get("route_module_sha256"),
                     "route_module_sha256_actual": route,
                     "migratable": ["%s/%s" % (p["source_audit_id"],
                                               p["source_run_phase"])
                                    for p in plan["migratable_attempts"]],
                     "excluded": ["%s/%s" % (e["audit_id"], e["run_phase"])
                                  for e in plan["excluded_attempts"]]},
        "expected": "VALID / BOUND / UNCONSUMED",
        "PASS": (declared == actual and not plan["applied_before_freeze"]
                 and not consumed
                 and plan.get("route_module_sha256") == route)}

    r7man = verify_manifest(r7, "CONTROL_MANIFEST.sha256")
    checks["r7_control_manifest"] = {
        "measured": {"entries": r7man["entries"], "ok": r7man["ok"],
                     "bad": r7man["bad"], "mismatched": r7man["mismatched"]},
        "expected": {"entries": 15804, "ok": 15804, "bad": 0},
        "PASS": r7man["entries"] == 15804 and r7man["ok"] == 15804
        and r7man["bad"] == 0}

    successor = os.path.join(os.path.dirname(r8),
                             "08.18.26_Level1_Audits_R9")
    checks["r9_absent"] = {"measured": os.path.exists(successor),
                           "expected": False,
                           "PASS": not os.path.exists(successor)}

    checks["no_freeze_attempt_recorded"] = {
        "measured": os.path.exists(os.path.join(r8, "state",
                                                "freeze_attempts.jsonl")),
        "expected": False,
        "PASS": not os.path.exists(os.path.join(r8, "state",
                                                "freeze_attempts.jsonl"))}

    failed = sorted(k for k, v in checks.items() if not v["PASS"])
    doc = {"schema": "wpno.r8.delta-fixed-target/1", "r8_root": r8,
           "r7_root": r7, "checks": checks, "failed": failed,
           "FIXED_TARGET_UNCHANGED": not failed}
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"FIXED_TARGET_UNCHANGED": doc["FIXED_TARGET_UNCHANGED"],
                      "failed": failed,
                      "per_check": {k: v["PASS"] for k, v in checks.items()}},
                     indent=1, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
