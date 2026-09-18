#!/usr/bin/env python3
"""Build every candidate execution plan that R7 did not already have.

Nine plans already exist, for L1-A18, L1-A31 and L1-A34. They were built by
build/build_candidate_plans.py before the evidence intake completed and their
dependencies are byte-identical to what their rehearsal recorded, so they are
not rebuilt here: a rebuild that produced the same bytes would prove nothing,
and one that produced different bytes would discard a rehearsed plan for no
reason.

This builder writes the other thirty-four and then reconciles the whole set
against the registry, so that "43 plans exist" is a measurement rather than an
arithmetic claim. A plan for an audit-phase pair the registry does not name is
as much a defect as a missing one, and both are reported.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import candidate_plan_specs as specs                       # noqa: E402
import plan_library as lib                                 # noqa: E402
from automation import hashing, path_policy, state_machine  # noqa: E402

# The thirty-four this builder owns, in controller order.
BUILDERS = [
    ("L1-A19", "RUN-A", specs.a19_run_a),
    ("L1-A19", "RUN-B", specs.a19_run_b),
    ("L1-A19", "COMPARISON", specs.a19_comparison),
    ("L1-A17", "RUN-A", specs.a17_run_a),
    ("L1-A20", "RUN-A", specs.a20_run_a),
    ("L1-A21", "RUN-A", specs.a21_run_a),
    ("L1-A22", "RUN-A", specs.a22_run_a),
    ("L1-A05", "RUN-A", specs.a05_run_a),
    ("L1-A06", "RUN-A", specs.a06_run_a),
    ("L1-A07", "RUN-A", specs.a07_run_a),
    ("L1-A08", "RUN-A", specs.a08_run_a),
    ("L1-A09", "RUN-A", specs.a09_run_a),
    ("L1-A10", "RUN-A", specs.a10_run_a),
    ("L1-A11", "RUN-A", specs.a11_run_a),
    ("L1-A12", "RUN-A", specs.a12_run_a),
    ("L1-A13", "RUN-A", specs.a13_run_a),
    ("L1-A14", "RUN-A", specs.a14_run_a),
    ("L1-A15", "RUN-A", specs.a15_run_a),
    ("L1-A16", "RUN-A", specs.a16_run_a),
    ("L1-A01", "RUN-A", specs.a01_run_a),
    ("L1-A02", "RUN-A", specs.a02_run_a),
    ("L1-A03", "RUN-A", specs.a03_run_a),
    ("L1-A04", "RUN-A", specs.a04_run_a),
    ("L1-A23", "RUN-A", specs.a23_run_a),
    ("L1-A24", "RUN-A", specs.a24_run_a),
    ("L1-A25", "RUN-A", specs.a25_run_a),
    ("L1-A26", "RUN-A", specs.a26_run_a),
    ("L1-A27", "RUN-A", specs.a27_run_a),
    ("L1-A28", "RUN-A", specs.a28_run_a),
    ("L1-A29", "RUN-A", specs.a29_run_a),
    ("L1-A30", "RUN-A", specs.a30_run_a),
    ("L1-A32", "RUN-A", specs.a32_run_a),
    ("L1-A33", "RUN-A", specs.a33_run_a),
    ("L1-A35", "RUN-A", specs.a35_run_a),
]

# Steps whose operation is operator-performed on another host and therefore
# has no argv here. Named per step so that a step which silently failed to
# build an argv could not pass as one that was never checked.
OPERATOR_PERFORMED_STEPS = {
    ("L1-A24", "RUN-A"): ("external_launch_outside_project",
                          "external_launch_inside_project",
                          "external_launch_sibling_directory"),
}

PREBUILT = {("L1-A18", "RUN-A"), ("L1-A18", "RUN-B"), ("L1-A18", "COMPARISON"),
            ("L1-A31", "RUN-A"), ("L1-A31", "RUN-B"), ("L1-A31", "COMPARISON"),
            ("L1-A34", "RUN-A"), ("L1-A34", "RUN-B"), ("L1-A34", "COMPARISON")}

COVERAGE_JSON = os.path.join(lib.OUT, "PLAN_COVERAGE_MANIFEST.json")
COVERAGE_SHA = os.path.join(lib.OUT, "PLAN_COVERAGE_MANIFEST.sha256")


def required_pairs():
    """Every audit-phase pair the registry requires, from the registry."""
    with open(os.path.join(ROOT, "audit_registry.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    pairs = []
    for audit in sorted(registry["audits"], key=lambda a: a["execution_order"]):
        for phase in state_machine.phase_order(audit["replications"]):
            pairs.append((audit["audit_id"], phase))
    return registry, pairs


def existing_plans():
    found = {}
    if not os.path.isdir(lib.OUT):
        return found
    for audit_id in sorted(os.listdir(lib.OUT)):
        audit_dir = os.path.join(lib.OUT, audit_id)
        if not os.path.isdir(audit_dir):
            continue
        for phase in sorted(os.listdir(audit_dir)):
            plan = os.path.join(audit_dir, phase, "plan.json")
            if os.path.isfile(plan):
                found[(audit_id, phase)] = plan
    return found


def build_all():
    written = []
    for audit_id, phase, builder in BUILDERS:
        plan = builder()
        if plan["audit_id"] != audit_id or plan["run_phase"] != phase:
            raise lib.PlanBuildError(
                "builder for %s/%s produced %s/%s"
                % (audit_id, phase, plan["audit_id"], plan["run_phase"]))
        result = lib.write_plan(
            plan,
            allow_unbuildable_argv=OPERATOR_PERFORMED_STEPS.get(
                (audit_id, phase), ()))
        result.update({"audit_id": audit_id, "run_phase": phase,
                       "steps": len(plan["steps"]),
                       "test_matrix_entries": len(plan["test_matrix"])})
        written.append(result)
    return written


def reconcile():
    registry, pairs = required_pairs()
    found = existing_plans()

    required = set(pairs)
    present = set(found)
    missing = sorted(required - present)
    unknown = sorted(present - required)

    duplicates = []
    seen = set()
    for pair in pairs:
        if pair in seen:
            duplicates.append(pair)
        seen.add(pair)

    rows = []
    for audit_id, phase in pairs:
        plan_path = found.get((audit_id, phase))
        with open(plan_path, encoding="utf-8") as fh:
            raw = fh.read()
        plan = json.loads(raw)
        rows.append({
            "audit_id": audit_id,
            "run_phase": phase,
            "plan_path": os.path.relpath(plan_path, ROOT),
            "plan_sha256": hashing.sha256_text(raw),
            "steps": len(plan["steps"]),
            "test_matrix_entries": len(plan["test_matrix"]),
            "target_path": plan["target"]["path"],
            "target_sha256": plan["target"]["sha256"],
            "built_by": ("build/build_candidate_plans.py"
                         if (audit_id, phase) in PREBUILT
                         else "build/build_all_candidate_plans.py"),
        })

    manifest = {
        "schema": "wpno.level1.plan-coverage/1",
        "revision": "R8",
        "REQUIRED_PLAN_COUNT": len(pairs),
        "CANDIDATE_PLAN_COUNT": len(present & required),
        "MISSING_PLAN_COUNT": len(missing),
        "DUPLICATE_PLAN_COUNT": len(duplicates),
        "UNKNOWN_PLAN_COUNT": len(unknown),
        "missing": [{"audit_id": a, "run_phase": p} for a, p in missing],
        "unknown": [{"audit_id": a, "run_phase": p} for a, p in unknown],
        "duplicates": [{"audit_id": a, "run_phase": p} for a, p in duplicates],
        "phase_totals_by_kind": {
            kind: sum(1 for _, p in pairs if p == kind)
            for kind in ("RUN-A", "RUN-B", "COMPARISON")},
        "registry_build_id": registry["build_id"],
        "prebuilt_reused": sorted("%s/%s" % pair for pair in PREBUILT),
        "newly_built": sorted("%s/%s" % (a, p) for a, p, _ in BUILDERS),
        "plans": rows,
    }
    return manifest


def main():
    parser = argparse.ArgumentParser(prog="build-all-candidate-plans")
    parser.add_argument("--reconcile-only", action="store_true")
    args = parser.parse_args()

    written = [] if args.reconcile_only else build_all()
    manifest = reconcile()

    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(COVERAGE_JSON), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    digest = hashing.sha256_text(text)
    with open(path_policy.assert_writable(COVERAGE_SHA), "w",
              encoding="utf-8") as fh:
        fh.write("%s  PLAN_COVERAGE_MANIFEST.json\n" % digest)

    print(json.dumps({
        "newly_written": len(written),
        "REQUIRED_PLAN_COUNT": manifest["REQUIRED_PLAN_COUNT"],
        "CANDIDATE_PLAN_COUNT": manifest["CANDIDATE_PLAN_COUNT"],
        "MISSING_PLAN_COUNT": manifest["MISSING_PLAN_COUNT"],
        "DUPLICATE_PLAN_COUNT": manifest["DUPLICATE_PLAN_COUNT"],
        "UNKNOWN_PLAN_COUNT": manifest["UNKNOWN_PLAN_COUNT"],
        "phase_totals_by_kind": manifest["phase_totals_by_kind"],
        "coverage_manifest": os.path.relpath(COVERAGE_JSON, ROOT),
        "coverage_manifest_sha256": digest,
    }, indent=2, sort_keys=True))
    ok = (manifest["MISSING_PLAN_COUNT"] == 0
          and manifest["DUPLICATE_PLAN_COUNT"] == 0
          and manifest["UNKNOWN_PLAN_COUNT"] == 0
          and manifest["CANDIDATE_PLAN_COUNT"]
          == manifest["REQUIRED_PLAN_COUNT"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
