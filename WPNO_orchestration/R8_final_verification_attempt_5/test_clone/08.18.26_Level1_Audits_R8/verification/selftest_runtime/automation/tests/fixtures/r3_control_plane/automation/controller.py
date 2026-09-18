#!/usr/bin/env python3
"""Level-1 audit controller.

One audit phase per process. No parallelism. No automatic approval. Writes
only below LEVEL1_ROOT.

Commands:
    verify-structure   structural checks over the package, no execution
    status             registry and state summary
    prepare-next       select the next audit and phase from the fixed order
    show-plan          display the current plan and its SHA-256
    record-approval    record an exact human approval token
    execute-approved   run the approved plan's operations
    finalize-current   record the Reviewer's verdict
    verify-evidence    verify seals and manifests
    consolidate        preconditions for consolidation

This file was generated and has not been executed, imported or byte-compiled
by its build. Codex verification runs the self-tests under `automation/tests/`
inside an isolated replica before the package may be frozen.
"""

import argparse
import json
import os
import subprocess
import sys
import time

from . import (audit_context, codex_adapter, evidence, hashing, locking,
               operation_catalog, path_policy, policy, redaction,
               schema_validation, state_machine)


class ControllerError(Exception):
    pass


STATE_DIR = os.path.join(path_policy.LEVEL1_ROOT, "state")
APPROVALS_PATH = os.path.join(STATE_DIR, "approvals.jsonl")
PROGRESS_PATH = os.path.join(STATE_DIR, "progress.json")


# ------------------------------------------------------------------ state
def _load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {"audits": {}, "halt_critical": None}
    with open(path_policy.assert_readable(PROGRESS_PATH), encoding="utf-8") as fh:
        return schema_validation.parse_strict(fh.read())


def _save_progress(progress):
    path_policy.ensure_dir(STATE_DIR)
    canonical = path_policy.assert_writable(PROGRESS_PATH)
    with open(canonical, "w", encoding="utf-8") as fh:
        json.dump(progress, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def _audit_state(progress, audit_id, run_phase):
    return (progress["audits"]
            .get(audit_id, {})
            .get(run_phase, {})
            .get("state", "NOT_STARTED"))


def _set_audit_state(progress, audit_id, run_phase, new_state, extra=None):
    current = _audit_state(progress, audit_id, run_phase)
    state_machine.transition(current, new_state)
    node = progress["audits"].setdefault(audit_id, {}).setdefault(run_phase, {})
    node["state"] = new_state
    node["updated"] = time.time()
    if extra:
        node.update(extra)
    return progress


def _phases_for(entry):
    return state_machine.phase_order(entry["replications"])


# --------------------------------------------------------------- approval
def parse_approval(token):
    """Parse and structurally validate an approval token.

    Format, exactly:
      APPROVE-EXECUTION L1-Axx RUN=<phase> PLAN-SHA256=<64hex>
      TARGET-SHA256=<64hex> RUN-ONCE
    """
    if not isinstance(token, str):
        raise ControllerError("approval token must be a string")
    parts = token.split()
    if len(parts) != 6:
        raise ControllerError("approval token must have exactly 6 fields")
    if parts[0] != policy.APPROVAL_PREFIX:
        raise ControllerError("approval must begin with %s" % policy.APPROVAL_PREFIX)
    if parts[5] != policy.APPROVAL_SUFFIX:
        raise ControllerError("approval must end with %s" % policy.APPROVAL_SUFFIX)
    audit_id = parts[1]
    if not parts[2].startswith("RUN="):
        raise ControllerError("third field must be RUN=<phase>")
    run_phase = parts[2][4:]
    if not parts[3].startswith("PLAN-SHA256="):
        raise ControllerError("fourth field must be PLAN-SHA256=<64hex>")
    plan_sha = parts[3][len("PLAN-SHA256="):].lower()
    if not parts[4].startswith("TARGET-SHA256="):
        raise ControllerError("fifth field must be TARGET-SHA256=<64hex>")
    target_sha = parts[4][len("TARGET-SHA256="):].lower()
    if not hashing.is_hex64(plan_sha):
        raise ControllerError("PLAN-SHA256 is not 64 hex characters")
    if not hashing.is_hex64(target_sha):
        raise ControllerError("TARGET-SHA256 is not 64 hex characters")
    if run_phase not in ("RUN-A", "RUN-B", "COMPARISON"):
        raise ControllerError("unknown run phase in approval: %r" % run_phase)
    return {
        "audit_id": audit_id,
        "run_phase": run_phase,
        "plan_sha256": plan_sha,
        "target_sha256": target_sha,
    }


def _recorded_approvals():
    if not os.path.exists(APPROVALS_PATH):
        return []
    out = []
    with open(path_policy.assert_readable(APPROVALS_PATH), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(schema_validation.parse_strict(line))
    return out


def assert_not_replayed(approval):
    """An approval is one-time. A second use is a replay, not a retry."""
    key = (approval["audit_id"], approval["run_phase"],
           approval["plan_sha256"], approval["target_sha256"])
    for prior in _recorded_approvals():
        if (prior["audit_id"], prior["run_phase"],
                prior["plan_sha256"], prior["target_sha256"]) == key:
            raise ControllerError(
                "approval replay rejected: this exact approval was already "
                "recorded at %s. Produce a new plan and a new approval."
                % prior.get("recorded_at"))
    return True


def assert_approval_binds(approval, audit_id, run_phase, plan_sha, target_sha):
    """Every binding checked separately, so the error names which one failed."""
    if approval["audit_id"] != audit_id:
        raise ControllerError("approval is for audit %s, not %s"
                              % (approval["audit_id"], audit_id))
    if approval["run_phase"] != run_phase:
        raise ControllerError("approval is for run %s, not %s"
                              % (approval["run_phase"], run_phase))
    if approval["plan_sha256"] != plan_sha:
        raise ControllerError(
            "approval is bound to a different plan; the plan changed after "
            "approval and the approval is void")
    if approval["target_sha256"] != target_sha:
        raise ControllerError(
            "approval is bound to a different target hash; the target changed "
            "after approval and the approval is void")
    return True


def _record_approval(approval):
    path_policy.ensure_dir(STATE_DIR)
    approval = dict(approval)
    approval["recorded_at"] = time.time()
    canonical = path_policy.assert_writable(APPROVALS_PATH)
    with open(canonical, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(approval, sort_keys=True, ensure_ascii=False))
        fh.write("\n")
    return approval


# -------------------------------------------------------------- execution
def _run_operation(op_name, params, recorder, timeout=None):
    """Execute one catalogued operation and record it completely."""
    kind = operation_catalog.classify(op_name)
    if kind == "FORBIDDEN":
        raise operation_catalog.ForbiddenOperation(op_name)
    if op_name in operation_catalog.IN_PROCESS:
        raise ControllerError(
            "%s is an in-process operation; the caller performs it directly "
            "and records the result" % op_name)

    argv = operation_catalog.build_argv(op_name, params)
    timeout = timeout or policy.DEFAULT_TIMEOUT_SECONDS
    if timeout > policy.MAX_TIMEOUT_SECONDS:
        raise ControllerError("timeout exceeds MAX_TIMEOUT_SECONDS")

    started = time.time()
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, no shell
            argv,
            shell=False,
            capture_output=True,
            timeout=timeout,
            env=policy.base_environment(),
            cwd=path_policy.LEVEL1_ROOT,
            check=False,
        )
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = (exc.stderr or b"") + b"\n[CONTROLLER] timeout after %ds\n" % timeout
        code = None
        timed_out = True

    limit = policy.MAX_OUTPUT_BYTES
    trunc_out = len(stdout) > limit
    trunc_err = len(stderr) > limit
    if trunc_out:
        stdout = stdout[:limit]
    if trunc_err:
        stderr = stderr[:limit]

    eid = recorder.record_operation(
        operation=op_name, argv=argv, exit_code=code,
        stdout=stdout, stderr=stderr,
        timeout_seconds=timeout, output_limit_bytes=limit,
        started=started, finished=time.time(),
        truncated_stdout=trunc_out, truncated_stderr=trunc_err,
        note="TIMEOUT" if timed_out else None)
    return {"evidence_id": eid, "exit_code": code, "timed_out": timed_out,
            "stdout_truncated": trunc_out, "stderr_truncated": trunc_err}


# --------------------------------------------------------------- commands
def cmd_verify_structure(args):
    """Structural checks only. Nothing is executed and nothing is written."""
    problems = []
    registry = audit_context.load_registry()
    audits = registry["audits"]

    if len(audits) != 35:
        problems.append("registry has %d entries, expected 35" % len(audits))
    ids = [a["audit_id"] for a in audits]
    if len(set(ids)) != len(ids):
        problems.append("duplicate audit ids in registry")
    orders = sorted(a["execution_order"] for a in audits)
    if orders != list(range(1, len(audits) + 1)):
        problems.append("execution_order is not a unique 1..N sequence")

    for entry in audits:
        aid = entry["audit_id"]
        prompt = os.path.join(path_policy.LEVEL1_ROOT, entry["prompt_file"])
        binding = os.path.join(path_policy.LEVEL1_ROOT, entry["binding_file"])
        if not os.path.exists(prompt):
            problems.append("missing prompt for %s" % aid)
        if not os.path.exists(binding):
            problems.append("missing binding for %s" % aid)
        expected = 2 if aid in policy.CRITICAL_REPLICATED_AUDITS else 1
        if entry["replications"] != expected:
            problems.append("%s replications=%s, expected %d"
                            % (aid, entry["replications"], expected))
        if entry["status"] not in ("NOT_STARTED",) and not args.allow_started:
            problems.append("%s status is %s, expected NOT_STARTED"
                            % (aid, entry["status"]))

    report = {"ok": not problems, "problems": problems,
              "audit_count": len(audits)}
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


def cmd_status(args):
    registry = audit_context.load_registry()
    progress = _load_progress()
    rows = []
    for entry in sorted(registry["audits"], key=lambda x: x["execution_order"]):
        aid = entry["audit_id"]
        rows.append({
            "order": entry["execution_order"],
            "audit_id": aid,
            "risk": entry["risk"],
            "replications": entry["replications"],
            "phases": {p: _audit_state(progress, aid, p)
                       for p in _phases_for(entry)},
        })
    print(json.dumps({"halt_critical": progress.get("halt_critical"),
                      "audits": rows}, indent=2))
    return 0


def cmd_prepare_next(args):
    """Select the next audit and phase. Never reorders.

    An impossible completed-phase history is not smoothed over here. The state
    machine raises, the error names the missing prerequisite, and a human
    decides what happened.
    """
    progress = _load_progress()
    if progress.get("halt_critical"):
        print(json.dumps({
            "blocked": True,
            "reason": "HALT_CRITICAL",
            "detail": progress["halt_critical"],
            "required": "%s <L1-Axx> FINDING-ID=<ID>" % policy.ACK_PREFIX,
        }, indent=2))
        return 2

    registry = audit_context.load_registry()
    for entry in sorted(registry["audits"], key=lambda x: x["execution_order"]):
        aid = entry["audit_id"]
        phases = _phases_for(entry)
        completed = [p for p in phases
                     if state_machine.is_terminal(_audit_state(progress, aid, p))]
        nxt = state_machine.next_run_phase(entry["replications"], completed)
        if nxt is not None:
            print(json.dumps({
                "audit_id": aid,
                "run_phase": nxt,
                "execution_order": entry["execution_order"],
                "state": _audit_state(progress, aid, nxt),
                "prompt_file": entry["prompt_file"],
                "binding_file": entry["binding_file"],
            }, indent=2))
            return 0
    print(json.dumps({"done": True,
                      "note": "all audits have a terminal status"}, indent=2))
    return 0


def cmd_show_plan(args):
    plan_path = os.path.join(path_policy.LEVEL1_ROOT, "results",
                             args.audit_id, args.run_phase, "plan.json")
    if not os.path.exists(plan_path):
        raise ControllerError("no plan at %s" % plan_path)
    with open(path_policy.assert_readable(plan_path), encoding="utf-8") as fh:
        raw = fh.read()
    plan = schema_validation.parse_strict(raw)
    schema_validation.validate_named(plan, "execution_plan.schema.json")
    gated = operation_catalog.validate_plan_operations(plan)
    print(json.dumps({
        "audit_id": args.audit_id,
        "run_phase": args.run_phase,
        "plan_sha256": hashing.sha256_text(raw),
        "gated_operations": sorted(set(gated)),
        "step_count": len(plan.get("steps", [])),
        "approval_required": bool(gated),
    }, indent=2))
    return 0


def cmd_record_approval(args):
    """Record a human approval. The controller never generates one."""
    approval = parse_approval(args.token)
    assert_not_replayed(approval)

    plan_path = os.path.join(path_policy.LEVEL1_ROOT, "results",
                             approval["audit_id"], approval["run_phase"],
                             "plan.json")
    with open(path_policy.assert_readable(plan_path), encoding="utf-8") as fh:
        plan_sha = hashing.sha256_text(fh.read())
    assert_approval_binds(approval, approval["audit_id"], approval["run_phase"],
                          plan_sha, approval["target_sha256"])

    with locking.ControllerLock():
        progress = _load_progress()
        _set_audit_state(progress, approval["audit_id"], approval["run_phase"],
                         "APPROVED", {"plan_sha256": plan_sha})
        _save_progress(progress)
        recorded = _record_approval(approval)
    print(json.dumps({"recorded": True, "audit_id": recorded["audit_id"],
                      "run_phase": recorded["run_phase"]}, indent=2))
    return 0


def cmd_execute_approved(args):
    """Execute an approved plan. Refuses without a valid, unreplayed approval."""
    with locking.ControllerLock():
        progress = _load_progress()
        state = _audit_state(progress, args.audit_id, args.run_phase)
        if state != "APPROVED":
            raise ControllerError(
                "state is %s; execution requires APPROVED. There is no flag "
                "that skips approval." % state)

        results_dir = path_policy.audit_results_dir(args.audit_id, args.run_phase)
        plan_path = os.path.join(results_dir, "plan.json")
        with open(path_policy.assert_readable(plan_path), encoding="utf-8") as fh:
            raw = fh.read()
        plan = schema_validation.parse_strict(raw)
        schema_validation.validate_named(plan, "execution_plan.schema.json")
        plan_sha = hashing.sha256_text(raw)

        node = progress["audits"][args.audit_id][args.run_phase]
        if node.get("plan_sha256") != plan_sha:
            raise ControllerError(
                "the plan changed after approval; the approval is void")

        target_path = plan["target"]["path"]
        before = hashing.sha256_file(target_path)
        if before != plan["target"]["sha256"]:
            _set_audit_state(progress, args.audit_id, args.run_phase, "CONTAMINATED")
            _save_progress(progress)
            raise ControllerError(
                "target hash differs from the plan before execution: "
                "CONTAMINATED")

        recorder = evidence.EvidenceRecorder(args.audit_id, args.run_phase)
        _set_audit_state(progress, args.audit_id, args.run_phase, "EXECUTING")
        _save_progress(progress)

        outcomes = []
        for step in plan["steps"]:
            if step["operation"] in operation_catalog.IN_PROCESS:
                outcomes.append({"operation": step["operation"],
                                 "note": "in-process; performed by the worker"})
                continue
            outcomes.append(_run_operation(step["operation"], step.get("params", {}),
                                           recorder, step.get("timeout_seconds")))

        after = hashing.sha256_file(target_path)
        if after != before:
            _set_audit_state(progress, args.audit_id, args.run_phase, "CONTAMINATED")
            _save_progress(progress)
            raise ControllerError(
                "target hash changed during execution: CONTAMINATED")

        _set_audit_state(progress, args.audit_id, args.run_phase, "EXECUTED",
                         {"target_sha256_before": before,
                          "target_sha256_after": after})
        _save_progress(progress)

    print(json.dumps({"executed": len(outcomes),
                      "target_sha256_before": before,
                      "target_sha256_after": after,
                      "outcomes": outcomes}, indent=2))
    return 0


def cmd_finalize_current(args):
    """Record the Reviewer's verdict and seal the phase."""
    if args.verdict not in policy.VERDICTS:
        raise ControllerError("unknown verdict: %r" % args.verdict)
    with locking.ControllerLock():
        progress = _load_progress()
        state = _audit_state(progress, args.audit_id, args.run_phase)
        if state not in ("EXECUTED", "REVIEWING"):
            raise ControllerError("state is %s; cannot finalize" % state)
        if state == "EXECUTED":
            _set_audit_state(progress, args.audit_id, args.run_phase, "REVIEWING")
        _set_audit_state(progress, args.audit_id, args.run_phase, "FINALIZED",
                         {"verdict": args.verdict})

        recorder = evidence.EvidenceRecorder(args.audit_id, args.run_phase)
        seal = recorder.seal(args.verdict)

        if args.critical_finding_id:
            _set_audit_state(progress, args.audit_id, args.run_phase,
                             "HALT_CRITICAL",
                             {"critical_finding_id": args.critical_finding_id})
            progress["halt_critical"] = {
                "audit_id": args.audit_id,
                "run_phase": args.run_phase,
                "finding_id": args.critical_finding_id,
            }
        else:
            _set_audit_state(progress, args.audit_id, args.run_phase, "SEALED")
        _save_progress(progress)
    print(json.dumps({"verdict": args.verdict, "seal": seal}, indent=2))
    return 0


def cmd_verify_evidence(args):
    """Verify every seal. A sealed tree that changed is reported, not repaired."""
    root = os.path.join(path_policy.LEVEL1_ROOT, "evidence")
    report = []
    if os.path.isdir(root):
        for audit_id in sorted(os.listdir(root)):
            audit_dir = os.path.join(root, audit_id)
            if not os.path.isdir(audit_dir):
                continue
            for phase in sorted(os.listdir(audit_dir)):
                phase_dir = os.path.join(audit_dir, phase)
                if not os.path.isdir(phase_dir):
                    continue
                recorder = evidence.EvidenceRecorder(audit_id, phase)
                if not os.path.exists(recorder.seal_path):
                    report.append({"audit_id": audit_id, "run_phase": phase,
                                   "sealed": False})
                    continue
                ok, diffs = recorder.verify_seal()
                report.append({"audit_id": audit_id, "run_phase": phase,
                               "sealed": True, "intact": ok,
                               "differences": diffs})
    bad = [r for r in report if r.get("sealed") and not r.get("intact")]
    print(json.dumps({"ok": not bad, "tampered": bad, "report": report}, indent=2))
    return 0 if not bad else 1


def cmd_consolidate(args):
    """Check the preconditions for consolidation. Does not consolidate."""
    registry = audit_context.load_registry()
    progress = _load_progress()
    incomplete = []
    for entry in registry["audits"]:
        aid = entry["audit_id"]
        for phase in _phases_for(entry):
            st = _audit_state(progress, aid, phase)
            if not state_machine.is_terminal(st):
                incomplete.append({"audit_id": aid, "run_phase": phase,
                                   "state": st})
    ready = not incomplete and not progress.get("halt_critical")
    print(json.dumps({
        "ready_for_consolidation": ready,
        "halt_critical": progress.get("halt_critical"),
        "incomplete": incomplete,
        "note": ("Consolidation is performed by 02_CODEX_CONSOLIDATE_LEVEL1.md. "
                 "The controller only reports whether its preconditions hold."),
    }, indent=2))
    return 0 if ready else 1


# ------------------------------------------------------------------- main
def build_parser():
    parser = argparse.ArgumentParser(
        prog="controller",
        description="Level-1 audit controller. One audit phase per process.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify-structure")
    p.add_argument("--allow-started", action="store_true",
                   help="permit non-NOT_STARTED registry statuses (resume case)")
    p.set_defaults(func=cmd_verify_structure)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("prepare-next").set_defaults(func=cmd_prepare_next)

    p = sub.add_parser("show-plan")
    p.add_argument("--audit-id", required=True)
    p.add_argument("--run-phase", required=True)
    p.set_defaults(func=cmd_show_plan)

    p = sub.add_parser("record-approval")
    p.add_argument("--token", required=True,
                   help="the exact human approval token, quoted")
    p.set_defaults(func=cmd_record_approval)

    p = sub.add_parser("execute-approved")
    p.add_argument("--audit-id", required=True)
    p.add_argument("--run-phase", required=True)
    p.set_defaults(func=cmd_execute_approved)

    p = sub.add_parser("finalize-current")
    p.add_argument("--audit-id", required=True)
    p.add_argument("--run-phase", required=True)
    p.add_argument("--verdict", required=True, choices=list(policy.VERDICTS))
    p.add_argument("--critical-finding-id", default=None)
    p.set_defaults(func=cmd_finalize_current)

    sub.add_parser("verify-evidence").set_defaults(func=cmd_verify_evidence)
    sub.add_parser("consolidate").set_defaults(func=cmd_consolidate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - the message is the product
        print(json.dumps({"error": type(exc).__name__,
                          "message": redaction.safe_quote(str(exc), 600)},
                         indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
