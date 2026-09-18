#!/usr/bin/env python3
"""Level-1 audit controller.

One audit phase per process. No parallelism. No automatic approval. Writes
only below LEVEL1_ROOT.

Commands:
    init-revision      initialise a new package revision's active state
    verify-structure   structural checks over the package, no execution
    status             registry and state summary
    prepare-next       select the next audit and phase from the fixed order
    show-plan          display the current plan and its SHA-256
    prepare-execution  advance NOT_STARTED to AWAITING_APPROVAL and print the
                       exact approval token a human must supply
    record-approval    record an exact human approval token
    execute-approved   run the approved plan's operations
    finalize-current   record the Reviewer's verdict
    verify-evidence    verify seals and manifests
    consolidate        preconditions for consolidation

Why `prepare-execution` exists (R4). The state machine permits

    NOT_STARTED -> PLANNING -> PLAN_READY -> AWAITING_APPROVAL -> APPROVED

and `record-approval` performs only the last of those four transitions. The R3
package shipped no public route that performed the first three, so a correct,
correctly bound six-field approval token was refused from NOT_STARTED with
`invalid transition NOT_STARTED -> APPROVED` and the audit could not start.
The defect was the missing route, not the state machine and not the token
grammar, and neither of those is changed here. A plan file sitting in `work/`
is not controller state; only a controller transition is.

`prepare-execution` does not approve and does not execute. It validates, binds
and advances, then prints the token. A human still types the token, and
`record-approval` still performs the one transition it always performed.

This file was generated and has not been executed, imported or byte-compiled
by its build. Codex verification runs the self-tests under `automation/tests/`
inside an isolated replica before the package may be frozen.
"""

import argparse
import io
import json
import os
import subprocess
import sys
import time
import unicodedata

from . import (audit_context, codex_adapter, evidence, freeze, hashing,
               locking, operation_catalog, path_policy, policy, redaction,
               schema_validation, state_machine)


class ControllerError(Exception):
    pass


STATE_DIR = os.path.join(path_policy.LEVEL1_ROOT, "state")
APPROVALS_PATH = os.path.join(STATE_DIR, "approvals.jsonl")
PROGRESS_PATH = os.path.join(STATE_DIR, "progress.json")
TRANSITIONS_PATH = os.path.join(STATE_DIR, "transitions.jsonl")

# The three states `prepare-execution` walks, in order. Membership and index
# are both needed: membership answers "is this phase already prepared", index
# answers "which transitions still remain".
PREPARATION_SEQUENCE = ("PLANNING", "PLAN_READY", "AWAITING_APPROVAL")

# The plan file the controller owns for a phase. `record-approval` and
# `execute-approved` have always read exactly this path, so preparation binds
# exactly this path and refuses to bind any other. A plan somewhere else would
# be a plan that is approved and then not the one that runs.
PLAN_FILENAME = "plan.json"

# The controller's own record of which revision this package is and what it
# succeeds. Written by `init-revision` and by nothing else.
REVISION_PATH = os.path.join(STATE_DIR, "REVISION.json")


# ------------------------------------------------------------------ state
def _load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {"audits": {}, "halt_critical": None}
    with open(path_policy.assert_readable(PROGRESS_PATH), encoding="utf-8") as fh:
        return schema_validation.parse_strict(fh.read())


def _save_progress(progress):
    """Persist progress atomically.

    A reader of the state file sees either the previous state or the next one,
    never a half-written one. The temporary file is created inside the same
    directory so `os.replace` is a rename within one filesystem, which is
    atomic; the data is flushed to the platter before the rename, and the
    directory entry is flushed after it. A crash at any point therefore leaves
    a complete state file — which is what makes `prepare-execution` safely
    restartable.
    """
    path_policy.ensure_dir(STATE_DIR)
    canonical = path_policy.assert_writable(PROGRESS_PATH)
    tmp = path_policy.assert_writable("%s.tmp.%d" % (canonical, os.getpid()))
    payload = json.dumps(progress, indent=2, sort_keys=True,
                         ensure_ascii=False) + "\n"
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, canonical)
    except BaseException:
        # Any failure leaves the previous state file untouched and no debris
        # behind. A half-written temporary that survived would be picked up by
        # the next run's O_EXCL and turn one failure into a permanent one.
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    dir_fd = os.open(os.path.dirname(canonical), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _append_transition(audit_id, run_phase, from_state, to_state, route,
                       binding=None):
    """Append one controller-owned transition record. Append-only, always.

    The journal is opened with O_APPEND, so every write lands at the end of the
    file and no existing byte is reachable. It is the controller's own account
    of what it did and in what order, and it is what lets an interrupted
    preparation be told apart from one that never started.
    """
    path_policy.ensure_dir(STATE_DIR)
    canonical = path_policy.assert_writable(TRANSITIONS_PATH)
    record = {
        "schema": "wpno.level1.transition/1",
        "audit_id": audit_id,
        "run_phase": run_phase,
        "from_state": from_state,
        "to_state": to_state,
        "route": route,
        "recorded_at": time.time(),
        "pid": os.getpid(),
    }
    if binding:
        record["binding"] = dict(binding)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    fd = os.open(canonical, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return record


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


# ------------------------------------------------------------- preparation
def _assert_no_parent_component(raw, what):
    """Reject traversal as the caller wrote it, before it is collapsed away.

    `os.path.abspath` resolves `..` silently, so a path that traversed out of
    the package would arrive at the later checks looking like an ordinary
    absolute path and would be judged on where it landed rather than on what
    it asked for. The component is refused by name instead.
    """
    if not isinstance(raw, str) or raw == "":
        raise ControllerError("%s path must be a non-empty string" % what)
    if ".." in raw.split(os.sep):
        raise ControllerError(
            "%s path contains a parent-directory component: %s" % (what, raw))
    return raw


def _assert_no_symlink_component(raw, what):
    """Reject a path any of whose components is a symlink.

    Stricter than `path_policy.assert_no_symlink_escape`, deliberately. That
    function permits a link that stays inside an allowed root, which is right
    for reading evidence. What preparation binds is a hash of a specific file,
    and a link is a name that can be repointed at another file after the hash
    is taken. Preparation therefore binds real paths only.

    The walk asks `os.path.islink` at each component, which uses lstat and does
    not follow, so the question is answered before the component can disappear.
    """
    lexical = path_policy.lexical_absolute(raw)
    walked = os.sep
    for part in lexical.split(os.sep):
        if not part:
            continue
        walked = os.path.join(walked, part)
        if os.path.islink(walked):
            raise ControllerError(
                "%s path contains a symlink component: %s" % (what, walked))
    return lexical


def _sibling_package_roots():
    """Other Level-1 audit packages beside this one.

    A package is recognised by the two files that make it one: `paths.json`
    and an `automation/` directory. Nothing else in PROJECT_ROOT matches, so
    ordinary audit targets elsewhere in the project are untouched by the check
    that uses this.
    """
    parent = os.path.dirname(path_policy.LEVEL1_ROOT)
    out = []
    if not os.path.isdir(parent):
        return out
    for name in sorted(os.listdir(parent)):
        candidate = os.path.join(parent, name)
        if os.path.islink(candidate) or not os.path.isdir(candidate):
            continue
        if not os.path.isfile(os.path.join(candidate, "paths.json")):
            continue
        if not os.path.isdir(os.path.join(candidate, "automation")):
            continue
        canonical = path_policy.normalize(candidate)
        if canonical != path_policy.LEVEL1_ROOT:
            out.append(canonical)
    return out


def _names_directory(text, directory):
    """True when the text names this directory, rather than merely one whose
    name starts with the same characters.

    `.../08.18.26_Level1_Audits` is a prefix of `.../08.18.26_Level1_Audits_R3`,
    so a plain substring test reports the first whenever the second appears and
    the resulting message accuses the wrong package. A match must therefore end
    at a path separator, or at the end of the path.
    """
    start = 0
    while True:
        index = text.find(directory, start)
        if index < 0:
            return False
        after = text[index + len(directory):index + len(directory) + 1]
        if after in ("", os.sep) or not (after.isalnum() or after in "_-."):
            return True
        start = index + 1


def _assert_no_foreign_package_reference(raw_plan):
    """Refuse a plan that names a different Level-1 package.

    The R3 plans carry absolute R3 paths in twenty places. Copied into R4 they
    would still parse, still validate and still hash — and would then run R4's
    controller against R3's files, recording the result as R4 evidence. The
    plan is preserved as evidence and superseded for execution; this is the
    check that makes 'superseded' mean something the controller enforces.
    """
    text = unicodedata.normalize("NFC", raw_plan)
    foreign = [root for root in _sibling_package_roots()
               if _names_directory(text, root)]
    if foreign:
        raise ControllerError(
            "plan references another Level-1 audit package and is bound to it: "
            "%s. A plan carrying a sibling package's absolute paths is "
            "superseded, not portable: build a new plan against %s."
            % (", ".join(sorted(foreign)), path_policy.LEVEL1_ROOT))
    return True


def _canonical_plan_path(audit_id, run_phase):
    return os.path.join(
        path_policy.audit_results_dir(audit_id, run_phase), PLAN_FILENAME)


def validate_preparation_inputs(audit_id, run_phase, plan_path, target_path):
    """Validate every input and return the binding. Touches no state.

    Nothing here reads or writes `state/`. That is the point: every way this
    can fail, fails before the first transition, so a rejected preparation
    leaves the phase exactly as it found it — NOT_STARTED stays NOT_STARTED.
    """
    entry = audit_context.registry_entry(audit_id)          # unknown id raises
    phases = state_machine.phase_order(entry["replications"])
    if run_phase not in phases:
        raise ControllerError(
            "run phase %r does not exist for %s; this audit has %r"
            % (run_phase, audit_id, list(phases)))

    # --- the plan file ---------------------------------------------------
    _assert_no_parent_component(plan_path, "plan")
    _assert_no_symlink_component(plan_path, "plan")
    canonical_plan = path_policy.assert_readable(plan_path)
    required_plan = _canonical_plan_path(audit_id, run_phase)
    if canonical_plan != required_plan:
        raise ControllerError(
            "the plan for %s %s must be the controller-owned plan at %s, not "
            "%s. `record-approval` and `execute-approved` read that path and "
            "no other, so binding a different one would approve a plan that "
            "is not the plan that runs."
            % (audit_id, run_phase, required_plan, canonical_plan))
    if not os.path.isfile(canonical_plan):
        raise ControllerError("no plan file at %s" % canonical_plan)

    with open(canonical_plan, encoding="utf-8") as fh:
        raw_plan = fh.read()
    plan = schema_validation.parse_strict(raw_plan)
    schema_validation.validate_named(plan, "execution_plan.schema.json")
    operation_catalog.validate_plan_operations(plan)
    _assert_no_foreign_package_reference(raw_plan)

    if plan["audit_id"] != audit_id:
        raise ControllerError("plan is for audit %s, not %s"
                              % (plan["audit_id"], audit_id))
    if plan["run_phase"] != run_phase:
        raise ControllerError("plan is for run %s, not %s"
                              % (plan["run_phase"], run_phase))
    plan_sha = hashing.sha256_text(raw_plan)

    # --- the target ------------------------------------------------------
    _assert_no_parent_component(target_path, "target")
    _assert_no_symlink_component(target_path, "target")
    canonical_target = path_policy.assert_readable(target_path)
    _assert_no_symlink_component(plan["target"]["path"], "plan target")
    declared_target = path_policy.assert_readable(plan["target"]["path"])
    if canonical_target != declared_target:
        raise ControllerError(
            "the target given on the command line (%s) is not the target the "
            "plan declares (%s); one of the two is wrong and the controller "
            "will not guess which"
            % (canonical_target, declared_target))
    if not os.path.isfile(canonical_target):
        raise ControllerError("no target file at %s" % canonical_target)
    target_sha = hashing.sha256_file(canonical_target)
    if target_sha != plan["target"]["sha256"]:
        raise ControllerError(
            "target identity does not match the plan: the plan declares %s, "
            "the file on disk is %s. The target changed after the plan was "
            "written and the plan is void."
            % (plan["target"]["sha256"], target_sha))

    return {
        "audit_id": audit_id,
        "run_phase": run_phase,
        "plan_path": canonical_plan,
        "plan_sha256": plan_sha,
        "target_path": canonical_target,
        "target_sha256": target_sha,
    }


BINDING_FIELDS = ("plan_path", "plan_sha256", "target_path", "target_sha256")


def stored_binding(node):
    """The binding a previous preparation recorded, or None."""
    if not all(node.get(f) for f in BINDING_FIELDS):
        return None
    return {f: node[f] for f in BINDING_FIELDS}


def assert_binding_matches(stored, binding):
    """Fail closed on any difference, naming the field that differs."""
    differing = [f for f in BINDING_FIELDS if stored.get(f) != binding[f]]
    if differing:
        raise ControllerError(
            "PREPARATION_BINDING_MISMATCH: this phase was already prepared "
            "with a different %s. Recorded: %r. Supplied: %r. A prepared "
            "phase is bound to exactly one plan and one target; to bind "
            "another, the phase must be resolved by a human first."
            % (", ".join(differing),
               {f: stored.get(f) for f in differing},
               {f: binding[f] for f in differing}))
    return True


def approval_token_for(binding):
    """The exact token a human must supply. Six fields, no more, no fewer."""
    return "%s %s RUN=%s PLAN-SHA256=%s TARGET-SHA256=%s %s" % (
        policy.APPROVAL_PREFIX,
        binding["audit_id"],
        binding["run_phase"],
        binding["plan_sha256"],
        binding["target_sha256"],
        policy.APPROVAL_SUFFIX,
    )


def _assert_is_next_lawful_phase(progress, entry, audit_id, run_phase):
    phases = state_machine.phase_order(entry["replications"])
    completed = [p for p in phases
                 if state_machine.is_terminal(_audit_state(progress, audit_id, p))]
    nxt = state_machine.next_run_phase(entry["replications"], completed)
    if nxt is None:
        raise ControllerError(
            "%s has no remaining phase; every phase is terminal" % audit_id)
    if run_phase != nxt:
        raise ControllerError(
            "%s is not the next phase for %s; the next phase is %s and the "
            "order %r is fixed" % (run_phase, audit_id, nxt, list(phases)))
    return nxt


def cmd_prepare_execution(args):
    """Advance NOT_STARTED to AWAITING_APPROVAL and print the approval token.

    Approves nothing. Executes nothing. It performs the three transitions the
    state machine has always permitted and for which R3 shipped no public
    route, and then stops at the gate and waits for a human.

    Restartable by construction. Each of the three transitions is persisted
    atomically and journalled before the next is attempted, so an interrupted
    run leaves the phase in one of the three prepared states with its binding
    recorded. An identical invocation resumes from there; an invocation with a
    different binding is refused.
    """
    binding = validate_preparation_inputs(
        args.audit_id, args.run_phase, args.plan_path, args.target_path)

    with locking.ControllerLock():
        progress = _load_progress()
        if progress.get("halt_critical"):
            raise ControllerError(
                "HALT_CRITICAL is set (%r); no phase may be prepared until it "
                "is acknowledged with %s"
                % (progress["halt_critical"], policy.ACK_PREFIX))

        entry = audit_context.registry_entry(args.audit_id)
        _assert_is_next_lawful_phase(progress, entry, args.audit_id,
                                     args.run_phase)

        state = _audit_state(progress, args.audit_id, args.run_phase)
        node = (progress["audits"].get(args.audit_id, {})
                .get(args.run_phase, {}))

        if state in PREPARATION_SEQUENCE:
            prior = stored_binding(node)
            if prior is None:
                raise ControllerError(
                    "state is %s but no binding was recorded; this state was "
                    "not produced by prepare-execution and a human must "
                    "resolve it. State files are never hand-edited." % state)
            assert_binding_matches(prior, binding)
            resumed_from = state
            start = PREPARATION_SEQUENCE.index(state) + 1
        elif state == "NOT_STARTED":
            resumed_from = None
            start = 0
        else:
            raise ControllerError(
                "state is %s; prepare-execution runs from NOT_STARTED, or "
                "resumes from %r. It never moves a phase backwards."
                % (state, list(PREPARATION_SEQUENCE)))

        performed = []
        for target_state in PREPARATION_SEQUENCE[start:]:
            current = _audit_state(progress, args.audit_id, args.run_phase)
            # The binding is written with the very first transition, so a
            # crash anywhere after it leaves enough on disk for an identical
            # invocation to recognise itself and resume.
            first = target_state == PREPARATION_SEQUENCE[0]
            extra = None
            if first:
                extra = {"prepared_route": "prepare-execution"}
                extra.update(binding)
            _set_audit_state(progress, args.audit_id, args.run_phase,
                             target_state, extra)
            _save_progress(progress)
            _append_transition(args.audit_id, args.run_phase, current,
                               target_state, "prepare-execution",
                               binding if first else None)
            performed.append({"from": current, "to": target_state})

        final_state = _audit_state(progress, args.audit_id, args.run_phase)

    if final_state != "AWAITING_APPROVAL":
        raise ControllerError(
            "preparation ended in %s, not AWAITING_APPROVAL" % final_state)

    token = approval_token_for(binding)
    print(json.dumps({
        "audit_id": binding["audit_id"],
        "run_phase": binding["run_phase"],
        "state": final_state,
        "resumed_from": resumed_from,
        "transitions": performed,
        "plan_path": binding["plan_path"],
        "plan_sha256": binding["plan_sha256"],
        "target_path": binding["target_path"],
        "target_sha256": binding["target_sha256"],
        "approval_recorded": False,
        "operations_executed": 0,
        "required_human_approval_token": token,
        "next_step": ("A human supplies the token above, verbatim and quoted, "
                      "to `controller record-approval --token '<token>'`. "
                      "prepare-execution does not approve and does not "
                      "execute."),
    }, indent=2))
    print()
    print(token)
    return 0


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



# --------------------------------------------------- revision initialisation
def cmd_init_revision(args):
    """Initialise the active state of a new package revision.

    Why this route exists (R5). A new revision needs its runtime state to
    begin empty: every audit NOT_STARTED, no approvals, no transitions. The
    obvious way to get there is to copy the predecessor's `state/` and edit
    it, and that is exactly the way that must not exist. A hand-edited state
    file is indistinguishable from one the controller wrote, so a phase could
    appear approved, or already sealed, with no transition journal behind it.
    R4's own history is the argument: its sealed verdicts are real precisely
    because every transition that produced them was recorded as it happened.

    So the predecessor's runtime state is not copied and not edited. It is
    preserved in `lineage/` as historical evidence and this route writes a new
    and empty active state beside it.

    Refuses to run twice. An already-initialised revision has a history, and
    re-initialising would discard it silently.
    """
    if os.path.exists(REVISION_PATH):
        raise ControllerError(
            "revision is already initialised: %s. Re-initialising would "
            "discard the transition journal that gives the current state its "
            "meaning." % REVISION_PATH)

    progress = _load_progress()
    if progress.get("audits"):
        raise ControllerError(
            "state/progress.json already records audits but state/REVISION.json "
            "is absent. That combination means state was placed here by "
            "something other than this controller; it is not initialised, it "
            "is contaminated.")
    for path, label in ((APPROVALS_PATH, "approvals"),
                        (TRANSITIONS_PATH, "transitions")):
        if os.path.exists(path) and os.path.getsize(path) > 0:
            raise ControllerError(
                "%s journal is non-empty before initialisation: %s. A new "
                "revision inherits no approvals and no transitions."
                % (label, path))

    registry = audit_context.load_registry()
    audits = {}
    phase_count = 0
    for entry in registry["audits"]:
        aid = entry["audit_id"]
        phases = {}
        for phase in state_machine.phase_order(entry["replications"]):
            phases[phase] = {
                "state": "NOT_STARTED",
                "audit_id": aid,
                "run_phase": phase,
                "updated": time.time(),
            }
            phase_count += 1
        audits[aid] = phases

    progress = {"audits": audits, "halt_critical": None}
    _save_progress(progress)

    path_policy.ensure_dir(STATE_DIR)
    for path in (APPROVALS_PATH, TRANSITIONS_PATH):
        canonical = path_policy.assert_writable(path)
        if not os.path.exists(canonical):
            fd = os.open(canonical, os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)

    record = {
        "schema": "wpno.level1.revision/1",
        "revision": args.revision,
        "predecessor": args.predecessor,
        "predecessor_root": args.predecessor_root,
        "predecessor_state_disposition":
            "HISTORICAL_ONLY_PRESERVED_IN_LINEAGE_NOT_ACTIVE",
        "predecessor_approvals_authority":
            "NONE. No approval token recorded against the predecessor "
            "authorises any phase of this revision. Every gated phase here "
            "requires a fresh human token bound to this revision's own plan.",
        "lineage_path": args.lineage,
        "platform": args.platform,
        "level1_root": path_policy.LEVEL1_ROOT,
        "audits_initialised": len(audits),
        "phases_initialised": phase_count,
        "initialised_at": time.time(),
        "mode_at_initialisation": _read_mode(),
    }
    canonical = path_policy.assert_writable(REVISION_PATH)
    with open(canonical, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")

    _append_transition(
        audit_id="PACKAGE", run_phase="REVISION",
        from_state="NOT_STARTED", to_state="NOT_STARTED",
        route="init-revision",
        binding={"revision": args.revision,
                 "predecessor": args.predecessor,
                 "phases_initialised": phase_count})

    print(json.dumps({
        "initialised": True,
        "revision": args.revision,
        "audits": len(audits),
        "phases": phase_count,
        "all_phases_state": "NOT_STARTED",
        "predecessor_approvals_carry_over": False,
        "revision_record": os.path.relpath(canonical, path_policy.LEVEL1_ROOT),
    }, indent=2, sort_keys=True))
    return 0


def _read_mode():
    path = os.path.join(path_policy.LEVEL1_ROOT, "MODE")
    if not os.path.exists(path):
        return None
    with open(path_policy.assert_readable(path), encoding="utf-8") as fh:
        return fh.read().strip()


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
    """Record a human approval. The controller never generates one.

    Valid from AWAITING_APPROVAL and from nowhere else. The state machine has
    always refused every other origin — that refusal is what R3 hit — but the
    check is made here as well, before anything is written, so the message
    names the missing step instead of naming a transition.

    Both hashes are recomputed from the files on disk and compared against the
    binding preparation recorded. R3 compared the token's target hash against
    itself, which is a comparison that cannot fail; a target that changed
    between preparation and approval went unnoticed.

    The approval line is appended before the state moves. A crash between the
    two therefore leaves an approval on record and a phase still at the gate,
    which a human must resolve — never a phase cleared for execution with no
    human approval behind it.
    """
    approval = parse_approval(args.token)

    with locking.ControllerLock():
        progress = _load_progress()
        audit_id = approval["audit_id"]
        run_phase = approval["run_phase"]
        state = _audit_state(progress, audit_id, run_phase)

        if state != "AWAITING_APPROVAL":
            raise ControllerError(
                "state is %s; an approval may be recorded only from "
                "AWAITING_APPROVAL. A correct token cannot cure an unprepared "
                "state. Run `prepare-execution --audit-id %s --run-phase %s "
                "--plan-path <plan> --target-path <target>` first. Nothing "
                "was written." % (state, audit_id, run_phase))

        node = progress["audits"][audit_id][run_phase]
        prepared = stored_binding(node)
        if prepared is None:
            raise ControllerError(
                "state is AWAITING_APPROVAL but no preparation binding is "
                "recorded; this state was not produced by prepare-execution "
                "and a human must resolve it. State files are never "
                "hand-edited.")

        assert_not_replayed(approval)

        with open(path_policy.assert_readable(prepared["plan_path"]),
                  encoding="utf-8") as fh:
            plan_sha = hashing.sha256_text(fh.read())
        target_sha = hashing.sha256_file(prepared["target_path"])

        if plan_sha != prepared["plan_sha256"]:
            raise ControllerError(
                "the plan changed after preparation (%s at preparation, %s "
                "now); the preparation is void"
                % (prepared["plan_sha256"], plan_sha))
        if target_sha != prepared["target_sha256"]:
            raise ControllerError(
                "the target changed after preparation (%s at preparation, %s "
                "now); the preparation is void"
                % (prepared["target_sha256"], target_sha))

        assert_approval_binds(approval, audit_id, run_phase,
                              plan_sha, target_sha)

        recorded = _record_approval(approval)
        _set_audit_state(progress, audit_id, run_phase, "APPROVED",
                         {"plan_sha256": plan_sha,
                          "target_sha256": target_sha})
        _save_progress(progress)
        _append_transition(audit_id, run_phase, "AWAITING_APPROVAL",
                           "APPROVED", "record-approval")

    print(json.dumps({"recorded": True, "audit_id": recorded["audit_id"],
                      "run_phase": recorded["run_phase"],
                      "state": "APPROVED",
                      "plan_sha256": plan_sha,
                      "target_sha256": target_sha,
                      "operations_executed": 0,
                      "next_step": ("`controller execute-approved` runs the "
                                    "plan. record-approval does not.")},
                     indent=2))
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



# ----------------------------------------------------------------- freeze
FREEZE_LEDGER_PATH = os.path.join(STATE_DIR, "freeze_attempts.jsonl")
FREEZE_PLAN_REL = os.path.join("build", "freeze_plan_attempt_2",
                               "FREEZE_PLAN_R5_ATTEMPT_2.json")


def _freeze_write(path, text):
    """Write one freeze artefact atomically and prove the bytes landed.

    Written to a temporary file beside the destination, flushed to the disk,
    and renamed into place. A reader therefore never sees a half-written
    artefact, and an interruption leaves either the previous file or the
    complete new one - never a truncated one that would hash to nothing
    anybody expects.
    """
    canonical = path_policy.assert_writable(path)
    path_policy.ensure_dir(os.path.dirname(canonical))
    temporary = canonical + ".freeze-tmp"
    with io.open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, canonical)
    written = hashing.sha256_file(canonical)
    expected = hashing.sha256_text(text)
    if written != expected:
        raise ControllerError(
            "FREEZE_ARTEFACT_WRITE_UNVERIFIED: %s wrote %s, expected %s"
            % (canonical, written, expected))
    return canonical, written


def cmd_freeze_level1(args):
    """Freeze R5. Everything is verified before anything is written.

    The order is the whole point. A package that is half frozen looks
    finished, so no artefact is created until the token, the plan, every bound
    digest, the Ubuntu baseline, the replay state and the R4 lineage have all
    been checked. Any failure before the write stage leaves MODE at
    GENERATED_UNVERIFIED, writes nothing, and does not consume the token.
    """
    root = path_policy.LEVEL1_ROOT
    started = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))

    with locking.ControllerLock():
        # --- 1. token shape, before any digest is computed --------------
        parsed = freeze.parse_freeze_token(args.token)

        # --- 2. the package must not already be frozen ------------------
        freeze.assert_no_freeze_artefact(root)
        mode_path = os.path.join(root, "MODE")
        with io.open(mode_path, encoding="utf-8") as handle:
            mode = handle.read().strip()
        if mode != policy.MODE_GENERATED:
            raise ControllerError(
                "FREEZE_MODE_REFUSED: MODE is %r, expected %r"
                % (mode, policy.MODE_GENERATED))

        # --- 3. no audit phase may have started -------------------------
        progress = _load_progress()
        started_phases = []
        for audit_id, audit in sorted(progress.get("audits", {}).items()):
            for phase, node in sorted(audit.items()):
                if isinstance(node, dict) and node.get("state") != "NOT_STARTED":
                    started_phases.append("%s/%s" % (audit_id, phase))
        if started_phases:
            raise ControllerError(
                "FREEZE_PHASE_ALREADY_STARTED: %r. A package is frozen before "
                "execution, never during it." % started_phases[:5])
        if os.path.exists(APPROVALS_PATH) and os.path.getsize(APPROVALS_PATH):
            raise ControllerError(
                "FREEZE_APPROVAL_ALREADY_RECORDED: state/approvals.jsonl is "
                "not empty; this package has already been executed against.")

        # --- 4. the plan ------------------------------------------------
        plan_path = freeze.confined_path(root, args.plan or FREEZE_PLAN_REL)
        if not os.path.isfile(plan_path):
            raise ControllerError("freeze plan is absent: %s" % plan_path)
        plan, plan_sha256 = freeze.load_r5_freeze_plan(plan_path)

        # --- 5. the token must bind this plan ---------------------------
        freeze.assert_token_binds_plan(parsed, plan, plan_sha256)

        # --- 6. every bound artefact, by digest -------------------------
        freeze.assert_plan_matches_disk(plan, root)

        # --- 7. the Ubuntu baseline -------------------------------------
        baseline, provenance = freeze.build_baseline_from_predecessor(
            root, plan["predecessor_baseline_manifest_sha256"])
        freeze.assert_baseline_matches_plan(baseline, plan)

        # --- 8. replay --------------------------------------------------
        freeze.assert_not_replayed(args.token, plan, FREEZE_LEDGER_PATH)

        # --- 9. R4 lineage ----------------------------------------------
        lineage_key = "lineage/R4_EXECUTION_MANIFEST.sha256"
        if lineage_key not in plan["bound_artifacts"]:
            raise ControllerError(
                "FREEZE_LINEAGE_UNBOUND: the plan does not bind %s"
                % lineage_key)

        # =============== nothing above this line writes =================
        #
        # Staging. Every byte this freeze will publish is computed before
        # anything is published, so the control manifest can be built against
        # the package's final state rather than its current one. That is what
        # lets MODE be published last and still be recorded correctly - the
        # two requirements R5 could not hold at the same time.
        baseline_text = freeze.serialize_baseline(baseline)
        mode_text = policy.MODE_FROZEN + "\n"

        staged = {"BASELINE_MANIFEST.json": baseline_text, "MODE": mode_text}
        manifest = freeze.final_state_manifest(root, staged)
        manifest_text = freeze.serialize_manifest(manifest)
        staged[freeze.CONTROL_MANIFEST_REL] = manifest_text

        if freeze.sha256_text(mode_text) != manifest.get("MODE"):
            raise ControllerError(
                "FREEZE_STAGING_INCONSISTENT: the manifest does not record the "
                "final MODE bytes. This is the R5 regression and the freeze "
                "stops here rather than publishing a package that fails its "
                "own manifest.")

        verified = {
            "schema": "wpno.level1.package-verified/1",
            "revision": freeze.R5_REVISION,
            "platform": freeze.R5_PLATFORM,
            "attempt_number": plan["attempt_number"],
            "frozen_at_utc": stamp,
            "freeze_plan_sha256": plan_sha256,
            "package_sha256": plan["package_sha256"],
            "verification_result_sha256": plan["verification_result_sha256"],
            "baseline_preview_sha256": plan["baseline_preview_sha256"],
            "baseline_provenance": provenance,
            "control_manifest_entries": len(manifest),
            "control_manifest_covers_mode": True,
            "manifest_generation": "FINAL_STATE_STAGED_BYTES",
            "publication_order": ["BASELINE_MANIFEST.json",
                                  "CONTROL_MANIFEST.sha256",
                                  "state/PACKAGE_VERIFIED.json",
                                  "MODE"],
            "independence_limitation": plan.get("independence_limitation"),
        }
        verified_text = json.dumps(verified, indent=2, sort_keys=True) + "\n"
        staged["state/PACKAGE_VERIFIED.json"] = verified_text

        # The attempt is recorded as started before the first byte is
        # published. It burns the token either way: an attempt that got as far
        # as writing must not be retried under the same approval, whatever
        # happens next. Nothing is recorded as successful yet.
        freeze.append_attempt(FREEZE_LEDGER_PATH, args.token, plan,
                              plan_sha256, "PUBLISH_STARTED", stamp)

        # Publication, MODE last. Until MODE lands the package still reads
        # GENERATED_UNVERIFIED, so a failure part way through leaves a package
        # that is visibly unfinished rather than one that falsely claims to be
        # frozen.
        order = ("BASELINE_MANIFEST.json", freeze.CONTROL_MANIFEST_REL,
                 "state/PACKAGE_VERIFIED.json", "MODE")
        written = {}
        try:
            for rel in order:
                destination = (mode_path if rel == "MODE"
                               else os.path.join(root, *rel.split("/")))
                _, written[rel] = _freeze_write(destination, staged[rel])
        except Exception as exc:
            freeze.append_attempt(
                FREEZE_LEDGER_PATH, args.token, plan, plan_sha256,
                "FAILED_DURING_PUBLICATION", stamp)
            raise ControllerError(
                "FREEZE_PUBLICATION_FAILED after %r: %s. MODE is %r. The "
                "attempt is recorded as failed and this approval is spent; a "
                "further attempt needs a new plan and a new token."
                % (sorted(written), exc, _read_mode()))

        # --- post-publication verification, against the real package -----
        #
        # Not a re-read of what was just written - that only proves the write
        # landed, which is what R5 checked and why R5 reported a frozen
        # package that was not one. This verifies the published manifest
        # against the published files, the same question `sha256sum -c` asks.
        report = freeze.verify_manifest_from_disk(root)
        current_mode = _read_mode()
        healthy = (report["failed_count"] == 0
                   and report["missing_count"] == 0
                   and report["unlisted_count"] == 0
                   and report["mode_entry_ok"]
                   and current_mode == policy.MODE_FROZEN)
        if not healthy:
            freeze.append_attempt(
                FREEZE_LEDGER_PATH, args.token, plan, plan_sha256,
                "FAILED_POST_PUBLICATION_VERIFICATION", stamp)
            raise ControllerError(
                "FREEZE_POST_VERIFICATION_FAILED: %s. The package is NOT "
                "valid frozen evidence and is not reported as frozen. It is "
                "preserved as it stands for root-cause work; a repair belongs "
                "in a successor revision, never in this one."
                % json.dumps({"failed": report["failed"][:5],
                              "missing": report["missing"][:5],
                              "unlisted": report["unlisted"][:5],
                              "mode_entry_ok": report["mode_entry_ok"],
                              "mode": current_mode}, sort_keys=True))

        freeze.append_attempt(FREEZE_LEDGER_PATH, args.token, plan,
                              plan_sha256, "FROZEN", stamp)

        print(json.dumps({
            "frozen": True,
            "revision": freeze.R5_REVISION,
            "attempt_number": plan["attempt_number"],
            "freeze_plan_sha256": plan_sha256,
            "artefacts": written,
            "project_baseline_count": len(baseline["project_files"]),
            "discovery_baseline_count": len(baseline["discovery_files"]),
            "control_manifest_verified_from_disk": {
                "entries": report["entries"],
                "ok": report["ok"],
                "failed": report["failed_count"],
                "missing": report["missing_count"],
                "unlisted": report["unlisted_count"],
                "mode_entry_ok": report["mode_entry_ok"],
            },
        }, indent=2, sort_keys=True))
        return 0


# ------------------------------------------------------------------- main
def build_parser():
    parser = argparse.ArgumentParser(
        prog="controller",
        description="Level-1 audit controller. One audit phase per process.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-revision")
    p.add_argument("--revision", required=True)
    p.add_argument("--predecessor", required=True)
    p.add_argument("--predecessor-root", required=True)
    p.add_argument("--lineage", required=True)
    p.add_argument("--platform", required=True)
    p.set_defaults(func=cmd_init_revision)

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

    p = sub.add_parser("prepare-execution")
    p.add_argument("--audit-id", required=True)
    p.add_argument("--run-phase", required=True)
    p.add_argument("--plan-path", required=True,
                   help="absolute path to the sealed execution plan")
    p.add_argument("--target-path", required=True,
                   help="absolute path to the audit target")
    p.set_defaults(func=cmd_prepare_execution)

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

    p = sub.add_parser("freeze-level1")
    p.add_argument("--token", required=True)
    p.add_argument("--plan", default=None)
    p.set_defaults(func=cmd_freeze_level1)
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
