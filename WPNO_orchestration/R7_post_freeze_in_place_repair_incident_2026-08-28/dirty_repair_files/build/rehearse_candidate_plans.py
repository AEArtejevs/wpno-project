#!/usr/bin/env python3
"""Rehearse every candidate live plan, with the exact argv builder.

This is the check R6 did not have. Its pre-freeze readiness fixture exercised
the operation catalogue generically and passed; the live L1-A31 plan then
failed on a purpose, an epoch and a mutation fixture that the fixture had
never executed. So this harness does not build its own parameters. It reads
the plans, hands each step's params to `operation_catalog.build_argv` - the
same function the controller calls - and runs the result.

R7 change. The harness covered nine phases across three audits, named in the
source. It now covers every phase the plan-coverage manifest lists, and the
manifest is reconciled against the registry, so a phase that gained a plan
without gaining a rehearsal is visible rather than absent.

What is rehearsed and what is not, per step, with the reason recorded either
way. A step is executed when every input it names exists and executing it is
not itself the live audit. Otherwise its argv is built and recorded and the
reason it was not run is stated. The four reasons are:

  LIVE_PHASE_MATERIAL_NOT_STAGED   the step reads something the approved phase
                                   creates - a sandbox copy of a target, a
                                   generated document, an external-host intake
                                   record. Building it here would be the live
                                   preparation, not a rehearsal of it.

  EXECUTING_WOULD_BE_THE_LIVE_PHASE   a COMPARISON step reads sealed evidence
                                   of two phases that have not run.

  OPERATOR_PERFORMED_ON_ANOTHER_HOST   the operation happens on the operator's
                                   machine under an approval bound to an
                                   execution packet. This controller never
                                   launches it.

  GIT_OPERATION_NOT_RUN_IN_THIS_SESSION   the orchestration that produced this
                                   package is forbidden to use Git. The argv is
                                   built and checked; the live phase runs it.

A rehearsal that started a phase, recorded an approval, sealed anything or
wrote under `results/`, `evidence/` or `logs/` would be the live run. The live
state files are hashed before and after and byte identity is required.
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import (hashing, in_process_ops, mutation_fixtures,  # noqa: E402
                        operation_catalog, path_policy, policy,
                        schema_validation)

PLANS = os.path.join(ROOT, "build", "candidate_plans_r7")
COVERAGE = os.path.join(PLANS, "PLAN_COVERAGE_MANIFEST.json")
OUTDIR = os.path.join(ROOT, "work", "_rehearsal_r7")

# The live state a rehearsal must leave exactly as it found it.
LIVE_STATE_FILES = (os.path.join("state", "progress.json"),
                    os.path.join("state", "approvals.jsonl"),
                    os.path.join("state", "transitions.jsonl"),
                    os.path.join("state", "REVISION.json"),
                    "MODE")

NOT_RUN_LIVE_MATERIAL = "LIVE_PHASE_MATERIAL_NOT_STAGED"
NOT_RUN_WOULD_BE_LIVE = "EXECUTING_WOULD_BE_THE_LIVE_PHASE"
NOT_RUN_OPERATOR_HOST = "OPERATOR_PERFORMED_ON_ANOTHER_HOST"
NOT_RUN_GIT = "GIT_OPERATION_NOT_RUN_IN_THIS_SESSION"
NOT_RUN_UNCONFINED_OUTPUT = "OUTPUT_PATH_OUTSIDE_THE_WRITABLE_WORK_AREA"
NOT_RUN_MISSING_UPSTREAM = "INPUT_PRODUCED_BY_AN_EARLIER_STEP_NOT_RUN_HERE"

# Parameter keys that name a file an in-process operation reads.
INPUT_PARAM_KEYS = ("path", "left", "right", "root", "export")


def _deferred_input_reason(step):
    """Why an in-process step could not run here, when that is legitimate.

    Two absences are expected during a rehearsal and neither is a defect:

      * an intermediate under `work/`, written by an earlier subprocess step
        of the same phase, which the rehearsal does not run;
      * live-phase material under `evidence/` or `results/`, which only
        exists once the phase it belongs to has actually been executed and
        sealed.

    Everything else -- a missing reference, tool or target -- is a real
    finding and must fail the step. The exemption is returned by name so the
    report says which of the two applied rather than swallowing both into a
    silent pass, because a blanket "the input was not there, so never mind"
    is precisely how the defect this accompanies stayed invisible.
    """
    deferred = {
        os.path.join(ROOT, "work") + os.sep: NOT_RUN_MISSING_UPSTREAM,
        os.path.join(ROOT, "evidence") + os.sep: NOT_RUN_LIVE_MATERIAL,
        os.path.join(ROOT, "results") + os.sep: NOT_RUN_LIVE_MATERIAL,
    }
    params = step.get("params") or {}
    found = None
    for key in INPUT_PARAM_KEYS:
        value = params.get(key)
        if not isinstance(value, str) or os.path.exists(value):
            continue
        canonical = os.path.abspath(value)
        for prefix, reason in deferred.items():
            if canonical.startswith(prefix):
                found = reason
                break
        else:
            return None
    return found

GIT_OPERATIONS = {"GIT_STATUS_READONLY", "GIT_LOG_READONLY",
                  "GIT_SHOW_READONLY"}

# Params whose value is a path the step reads. A path named under a key not
# listed here is not treated as an input, so a missing output path does not
# make a step look unrunnable.
INPUT_PARAM_KEYS = ("path", "cert", "cms", "content", "archive", "leaf",
                    "anchor", "intermediates", "certfile", "script", "target",
                    "rootdir", "left", "right", "repo", "export", "packet",
                    "intake", "roster", "corpus", "cases", "text", "source")

# Options in an audit module's argv whose following value is a destination the
# step writes, not a source it reads.
#
# This distinction was missing and the cost was precise. Every absolute string
# in `args` was treated as an input, so a step whose `--out` file did not exist
# yet looked unrunnable and was skipped. Two steps were skipped that way -
# L1-A19's two sabotage controls - and the record then said
# LIVE_PHASE_MATERIAL_NOT_STAGED with the output named under `absent_inputs`.
# A control that never ran cannot demonstrate anything, and CLAUDE.md section 6
# is explicit that a sabotage has to be shown effective or the test is void.
#
# An output is not merely ignored. It must lie under `work/`, which is where
# this package permits writing; a plan naming a destination anywhere else is
# refused rather than run.
OUTPUT_FLAGS = ("--out", "--work-dir")

# Param keys whose value is a destination rather than a source. `out` was
# already absent from INPUT_PARAM_KEYS; naming these makes the intent explicit
# and lets the confinement check below see them.
OUTPUT_PARAM_KEYS = ("out", "dest", "work_dir")


def run(argv, timeout):
    return subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=timeout,
        env=policy.base_environment(), cwd=ROOT, check=False)


def matrix_for(plan):
    by_step = {}
    for entry in plan.get("test_matrix", []):
        if "step_id" in entry:
            by_step[entry["step_id"]] = entry
    return by_step


def step_outputs(step):
    """The paths this step writes: named params and values after an output flag."""
    params = step.get("params", {})
    out = []
    for key in OUTPUT_PARAM_KEYS:
        value = params.get(key)
        if isinstance(value, str) and value.startswith("/"):
            out.append(value)
    args = params.get("args", []) or []
    for index, value in enumerate(args):
        if index == 0:
            continue
        if args[index - 1] in OUTPUT_FLAGS and isinstance(value, str) \
                and value.startswith("/"):
            out.append(value)
    return out


def step_inputs(step):
    """The paths this step reads, as the catalogue would resolve them.

    A destination is not a source. An `--out` value is excluded here, so a
    step is not held back because the file it is about to write does not exist
    yet.
    """
    params = step.get("params", {})
    destinations = set(step_outputs(step))
    out = []
    for key in INPUT_PARAM_KEYS:
        value = params.get(key)
        if isinstance(value, str) and value.startswith("/") \
                and value not in destinations:
            out.append(value)
    args = params.get("args", []) or []
    for index, value in enumerate(args):
        if not isinstance(value, str) or not value.startswith("/"):
            continue
        if index and args[index - 1] in OUTPUT_FLAGS:
            continue
        if value in destinations:
            continue
        out.append(value)
    return out


def missing_inputs(step):
    return [p for p in step_inputs(step) if not os.path.exists(p)]


def unconfined_outputs(step):
    """Destinations outside the writable work area. A plan naming one is refused."""
    work_root = os.path.join(ROOT, "work")
    bad = []
    for destination in step_outputs(step):
        canonical = os.path.normpath(destination)
        if not (canonical == work_root
                or canonical.startswith(work_root + os.sep)):
            bad.append(destination)
    return bad


def judge(step, entry, proc):
    """Did this step do what the plan said it would, and for the stated reason?"""
    stderr = proc.stderr.decode("utf-8", "replace")
    expected = entry.get("expected_exit_code") if entry else None
    verdict = {"step_id": step["step_id"],
               "control_role": step.get("control_role"),
               "exit_code": proc.returncode,
               "expected_exit_code": expected}

    if expected is None:
        verdict["result"] = "NO_EXPECTATION_STATED"
        verdict["ok"] = proc.returncode == 0
    elif expected == "NONZERO":
        verdict["ok"] = proc.returncode != 0
        verdict["result"] = ("FAILS_AS_DESIGNED" if verdict["ok"]
                             else "DID_NOT_FAIL")
    else:
        verdict["ok"] = proc.returncode == expected
        verdict["result"] = "AS_EXPECTED" if verdict["ok"] else "UNEXPECTED_EXIT"

    # Only a reason stated in the harness's own vocabulary is asserted
    # mechanically. A prose reason is for the reader and for the live audit,
    # and asserting it by substring would be a check that passes on wording.
    reason = (entry or {}).get("expected_failure_reason_canonical")
    if reason:
        present = mutation_fixtures.reason_is_present(stderr, reason)
        verdict["expected_failure_reason_canonical"] = reason
        verdict["failure_reason_observed"] = present
        # A control that fails for the wrong reason has not been exercised.
        # This is the assertion R6 did not make.
        if not present:
            verdict["ok"] = False
            verdict["result"] = "FAILED_FOR_THE_WRONG_REASON"
    elif (entry or {}).get("expected_failure_reason"):
        verdict["expected_failure_reason_prose"] = \
            entry["expected_failure_reason"]
        verdict["failure_reason_asserted_mechanically"] = False
    verdict["stderr_head"] = stderr[:400]
    return verdict


def rehearse_plan(audit_id, phase):
    path = os.path.join(PLANS, audit_id, phase, "plan.json")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    plan = schema_validation.parse_strict(raw)
    schema_validation.validate_named(plan, "execution_plan.schema.json")
    gated = operation_catalog.validate_plan_operations(plan)

    report = {
        "audit_id": audit_id,
        "run_phase": phase,
        "plan_path": os.path.relpath(path, ROOT),
        "plan_sha256": hashing.sha256_text(raw),
        "schema_valid": True,
        "gated_operations": sorted(set(gated)),
        "target_path": plan["target"]["path"],
        "target_sha256_in_plan": plan["target"]["sha256"],
        "target_sha256_on_disk": (hashing.sha256_file(plan["target"]["path"])
                                  if os.path.isfile(plan["target"]["path"])
                                  else None),
        "steps": [],
    }
    report["target_identity_holds"] = (
        report["target_sha256_in_plan"] == report["target_sha256_on_disk"])

    by_step = matrix_for(plan)

    for step in plan["steps"]:
        name = step["operation"]
        record = {"step_id": step["step_id"], "operation": name,
                  "control_role": step.get("control_role")}

        if name in operation_catalog.IN_PROCESS:
            # This branch used to set executed False and ok True together and
            # move on. That combination is what let twelve phases -- every one
            # of them built entirely from in-process steps -- rehearse as
            # PASS_READY without a single operation having run, and it is why
            # the 43/43 result reported before the freeze meant less than it
            # appeared to. An unexecuted step is not a passing step.
            #
            # The operation is now really performed. The one failure that is
            # still tolerated here is a missing artefact that an earlier
            # subprocess step of the same phase would have produced, because
            # the rehearsal does not run those. That exemption is narrow and
            # is recorded by name; every other failure fails the step.
            deferred = _deferred_input_reason(step)
            if deferred:
                record["argv"] = []
                record["executed"] = False
                record["not_executed_reason"] = deferred
                record["ok"] = True
                report["steps"].append(record)
                continue

            record["argv"] = []
            record["note"] = ("in-process; performed by the controller with "
                              "the standard library, no subprocess")
            code, result = in_process_ops.perform(name, step.get("params", {}))
            record["executed"] = True
            record["exit_code"] = code
            record["result_sha256"] = hashing.sha256_text(
                json.dumps(result, sort_keys=True, default=str))

            # A control is judged against what the plan said it would do. A
            # negative control that fails has behaved correctly, and treating
            # its non-zero exit as a phase failure would be the mirror image
            # of the defect being repaired: reporting a result the run did
            # not actually have.
            entry = by_step.get(step["step_id"]) or {}
            expected = entry.get("expected_exit_code")
            record["expected_exit_code"] = expected
            if expected is None:
                record["ok"] = code == 0
                record["result"] = "NO_EXPECTATION_STATED"
            elif expected == "NONZERO":
                record["ok"] = code != 0
                record["result"] = ("FAILS_AS_DESIGNED" if record["ok"]
                                    else "DID_NOT_FAIL")
            else:
                record["ok"] = code == expected
                record["result"] = ("AS_EXPECTED" if record["ok"]
                                    else "UNEXPECTED_EXIT")
            if code != 0:
                record["failure_reason"] = str(result.get("reason", ""))[:400]
            report["steps"].append(record)
            continue

        if name in operation_catalog.OPERATOR_PERFORMED:
            record["argv"] = None
            record["executed"] = False
            record["not_executed_reason"] = NOT_RUN_OPERATOR_HOST
            record["note"] = (
                "the operation has no argv on this machine; it is carried out "
                "on the external host named in its execution packet and "
                "returns a hash-bound intake record")
            record["ok"] = True
            report["steps"].append(record)
            continue

        try:
            argv = operation_catalog.build_argv(name, step.get("params", {}))
        except Exception as exc:                      # noqa: BLE001
            record["ok"] = False
            record["executed"] = False
            record["argv_error"] = "%s: %s" % (type(exc).__name__, exc)
            report["steps"].append(record)
            continue
        record["argv"] = argv
        record["argv_built"] = True

        if phase == "COMPARISON":
            record["executed"] = False
            record["not_executed_reason"] = NOT_RUN_WOULD_BE_LIVE
            record["ok"] = True
            report["steps"].append(record)
            continue

        if name in GIT_OPERATIONS:
            record["executed"] = False
            record["not_executed_reason"] = NOT_RUN_GIT
            record["ok"] = True
            report["steps"].append(record)
            continue

        stray = unconfined_outputs(step)
        if stray:
            record["ok"] = False
            record["executed"] = False
            record["unconfined_outputs"] = stray
            record["not_executed_reason"] = NOT_RUN_UNCONFINED_OUTPUT
            report["steps"].append(record)
            continue

        for destination in step_outputs(step):
            parent = os.path.dirname(destination)
            if parent:
                path_policy.ensure_dir(parent)

        absent = missing_inputs(step)
        if absent:
            record["executed"] = False
            record["not_executed_reason"] = NOT_RUN_LIVE_MATERIAL
            record["absent_inputs"] = [os.path.relpath(p, ROOT)
                                       if p.startswith(ROOT) else p
                                       for p in absent]
            record["ok"] = True
            report["steps"].append(record)
            continue

        proc = run(argv, step.get("timeout_seconds", 120))
        record["executed"] = True
        record.update(judge(step, by_step.get(step["step_id"]), proc))
        report["steps"].append(record)

    report["steps_total"] = len(report["steps"])
    report["steps_executed"] = sum(1 for s in report["steps"]
                                   if s.get("executed"))
    report["steps_argv_built"] = sum(1 for s in report["steps"]
                                     if s.get("argv") is not None)
    report["ok"] = (report["target_identity_holds"]
                    and all(s.get("ok") for s in report["steps"]))
    return report


def live_state_digests():
    out = {}
    for rel in LIVE_STATE_FILES:
        full = os.path.join(ROOT, rel)
        out[rel] = hashing.sha256_file(full) if os.path.isfile(full) else None
    return out


def required_phases():
    with open(COVERAGE, encoding="utf-8") as fh:
        coverage = json.load(fh)
    return coverage, [(row["audit_id"], row["run_phase"])
                      for row in coverage["plans"]]


def main():
    """Rehearse every phase, or refresh only the ones named.

    `--only AUDIT/PHASE` re-measures those phases and carries the rest forward
    from the existing report, unchanged and marked as carried forward. That is
    not a shortcut for a full run: a carried-forward entry is only admitted if
    its plan still hashes to the digest that entry recorded, so an entry can
    never describe a plan that has since moved.
    """
    parser = argparse.ArgumentParser(prog="rehearse-candidate-plans")
    parser.add_argument("--only", action="append", default=None,
                        metavar="AUDIT/PHASE",
                        help="refresh just this phase; repeatable")
    args = parser.parse_args()

    path_policy.ensure_dir(OUTDIR)
    coverage, phases = required_phases()

    selected = None
    if args.only:
        selected = []
        for spec in args.only:
            if spec.count("/") != 1:
                raise SystemExit("--only takes AUDIT/PHASE, got %r" % spec)
            audit_id, phase = spec.split("/")
            if (audit_id, phase) not in phases:
                raise SystemExit("%s is not a required phase" % spec)
            selected.append((audit_id, phase))

    for audit_id, phase in phases:
        path_policy.ensure_dir(os.path.join(ROOT, "work", audit_id, phase))
    path_policy.ensure_dir(os.path.join(
        ROOT, "work", "L1-A31", "preparation_r7_2026-08-26", "outputs"))

    before = live_state_digests()

    carried = {}
    if selected is not None:
        out_path = os.path.join(OUTDIR, "REHEARSAL_REPORT.json")
        if not os.path.isfile(out_path):
            raise SystemExit(
                "--only refreshes an existing report and there is none at %s"
                % out_path)
        with open(out_path, encoding="utf-8") as fh:
            previous = json.load(fh)
        for entry in previous["reports"]:
            key = (entry["audit_id"], entry["run_phase"])
            if key in selected:
                continue
            plan_path = os.path.join(PLANS, key[0], key[1], "plan.json")
            with open(plan_path, encoding="utf-8") as fh:
                current = hashing.sha256_text(fh.read())
            if current != entry["plan_sha256"]:
                raise SystemExit(
                    "%s/%s cannot be carried forward: its plan is now %s and "
                    "the recorded entry describes %s"
                    % (key[0], key[1], current, entry["plan_sha256"]))
            entry = dict(entry, carried_forward=True)
            carried[key] = entry

    reports = []
    for audit_id, phase in phases:
        key = (audit_id, phase)
        if key in carried:
            reports.append(carried[key])
        else:
            report = rehearse_plan(audit_id, phase)
            report["carried_forward"] = False
            reports.append(report)

    after = live_state_digests()
    live_unchanged = before == after

    out = os.path.join(OUTDIR, "REHEARSAL_REPORT.json")
    payload = {
        "schema": "wpno.level1.plan-rehearsal/3",
        "revision": "R7",
        "phases_refreshed_this_run": sorted(
            "%s/%s" % (r["audit_id"], r["run_phase"])
            for r in reports if not r.get("carried_forward")),
        "phases_carried_forward": sorted(
            "%s/%s" % (r["audit_id"], r["run_phase"])
            for r in reports if r.get("carried_forward")),
        "carried_forward_rule": (
            "an entry is carried forward only when its plan still hashes to "
            "the digest that entry recorded; otherwise the run refuses"),
        "phases_rehearsed": len(reports),
        "phases_required": coverage["REQUIRED_PLAN_COUNT"],
        "all_pass_ready": all(r["ok"] for r in reports) and live_unchanged,
        "live_state_before": before,
        "live_state_after": after,
        "LIVE_STATE_UNCHANGED": live_unchanged,
        "steps_total": sum(r["steps_total"] for r in reports),
        "steps_executed": sum(r["steps_executed"] for r in reports),
        "not_executed_reasons": {
            reason: sum(1 for r in reports for s in r["steps"]
                        if s.get("not_executed_reason") == reason)
            for reason in (NOT_RUN_LIVE_MATERIAL, NOT_RUN_WOULD_BE_LIVE,
                           NOT_RUN_OPERATOR_HOST, NOT_RUN_GIT,
                           NOT_RUN_UNCONFINED_OUTPUT,
                           NOT_RUN_MISSING_UPSTREAM)},
        "coverage_manifest_sha256": hashing.sha256_file(COVERAGE),
        "reports": reports,
    }
    with open(path_policy.assert_writable(out), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "rehearsal_report": os.path.relpath(out, ROOT),
        "rehearsal_report_sha256": hashing.sha256_file(out),
        "phases_rehearsed": payload["phases_rehearsed"],
        "phases_required": payload["phases_required"],
        "phases_refreshed_this_run": payload["phases_refreshed_this_run"],
        "phases_carried_forward": len(payload["phases_carried_forward"]),
        "all_pass_ready": payload["all_pass_ready"],
        "LIVE_STATE_UNCHANGED": live_unchanged,
        "steps_total": payload["steps_total"],
        "steps_executed": payload["steps_executed"],
        "not_executed_reasons": payload["not_executed_reasons"],
        "not_pass_ready": [
            "%s/%s" % (r["audit_id"], r["run_phase"])
            for r in reports if not r["ok"]],
        "failing_steps": [
            {"phase": "%s/%s" % (r["audit_id"], r["run_phase"]),
             "step_id": s["step_id"],
             "result": s.get("result") or s.get("argv_error"),
             "stderr_head": s.get("stderr_head", "")[:200]}
            for r in reports for s in r["steps"] if not s.get("ok")],
    }, indent=2, sort_keys=True))
    return 0 if payload["all_pass_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
