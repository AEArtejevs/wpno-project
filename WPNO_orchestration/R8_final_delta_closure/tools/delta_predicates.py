#!/usr/bin/env python3
"""The predicates the delta closure evaluates, and the only way they look up.

Attempt 8 ended because `doc["IN_PROCESS_HANDLER_INVOCATIONS"]` raised on a
record that holds `R8_IN_PROCESS_HANDLER_INVOCATIONS`. Two things went wrong
at once: the name was a guess, and the failure arrived as a `KeyError` that
aborted the run instead of as a verdict that could be recorded.

`get` fixes both. It names the container, it type-checks, and it raises
`SchemaError` -- one controlled type the runner converts into a recorded
INVALID verdict. No predicate here indexes a mapping directly, and no key
appears that VERIFIER_SCHEMA_MAP.json has not first proved present. There is
no fallback lookup: a fallback would let a wrong name succeed by finding
something else, which is the same defect with a softer landing.

Every predicate is a pure function of already-loaded documents, so the
self-test can hand it a fixture and see what it does before a real run
depends on it.
"""

import os


class SchemaError(Exception):
    """A lookup that could not be satisfied. Never a bare KeyError."""


def get(container, key, expect=None, where="document"):
    if not isinstance(container, dict):
        raise SchemaError("%s is %s, not an object; cannot read %r"
                          % (where, type(container).__name__, key))
    if key not in container:
        raise SchemaError("%s has no key %r; it has %s"
                          % (where, key, sorted(container)[:12]))
    value = container[key]
    if expect is not None and not isinstance(value, expect):
        names = (expect.__name__ if isinstance(expect, type)
                 else "/".join(t.__name__ for t in expect))
        raise SchemaError("%s[%r] is %s, expected %s"
                          % (where, key, type(value).__name__, names))
    if expect in (int,) and isinstance(value, bool):
        raise SchemaError("%s[%r] is a bool, expected int" % (where, key))
    return value


def verdict(name, expected, measured, source, note=None):
    row = {"predicate": name, "expected": expected, "measured": measured,
           "source": source, "PASS": expected == measured}
    if note:
        row["note"] = note
    return row


# ---------------------------------------------------------------- item 23
RECON = "build/IN_PROCESS_COUNT_RECONCILIATION.json"
REHEARSAL = "work/_rehearsal_r8/REHEARSAL_REPORT.json"


def p_recon_handler_invocations(d):
    return verdict("recon.R8_IN_PROCESS_HANDLER_INVOCATIONS", 169,
                   get(d["recon"], "R8_IN_PROCESS_HANDLER_INVOCATIONS", int,
                       RECON), RECON)


def p_recon_unique_steps(d):
    return verdict("recon.R8_UNIQUE_IN_PROCESS_PLAN_STEPS", 169,
                   get(d["recon"], "R8_UNIQUE_IN_PROCESS_PLAN_STEPS", int,
                       RECON), RECON)


def p_recon_total_plan_steps(d):
    return verdict("recon.R8_TOTAL_PLAN_STEPS", 311,
                   get(d["recon"], "R8_TOTAL_PLAN_STEPS", int, RECON), RECON)


def p_recon_no_unexplained_difference(d):
    exp = get(d["recon"], "explanation", dict, RECON)
    value = get(exp, "UNEXPLAINED_COUNT_DIFFERENCE", (int, str),
                RECON + "$.explanation")
    return verdict("recon.explanation.UNEXPLAINED_COUNT_DIFFERENCE", 0,
                   int(value) if str(value).lstrip("-").isdigit() else value,
                   RECON,
                   "the two counts must reconcile with nothing left over")


def p_recon_rows_derive_unique_count(d):
    """Re-derive 169 from the 311 per-step rows, not from the summary."""
    steps = get(d["recon"], "steps", list, RECON)
    unique = 0
    for i, row in enumerate(steps):
        where = "%s$.steps[%d]" % (RECON, i)
        if get(row, "R8_FINAL_CLASSIFICATION", str, where) != "IN_PROCESS":
            continue
        if get(row, "UNIQUE_PLAN_STEP", bool, where):
            unique += 1
    return verdict("recon rows -> unique in-process plan steps", 169, unique,
                   RECON + "$.steps[*]",
                   "derived from the rows; a summary that quotes itself is "
                   "not evidence")


def p_recon_rows_derive_invocations(d):
    steps = get(d["recon"], "steps", list, RECON)
    total = 0
    for i, row in enumerate(steps):
        where = "%s$.steps[%d]" % (RECON, i)
        if get(row, "R8_FINAL_CLASSIFICATION", str, where) != "IN_PROCESS":
            continue
        total += get(row, "EXECUTION_INVOCATION_COUNT", int, where)
    return verdict("recon rows -> handler invocations", 169, total,
                   RECON + "$.steps[*]")


def p_recon_every_in_process_row_executed(d):
    steps = get(d["recon"], "steps", list, RECON)
    not_executed = []
    for i, row in enumerate(steps):
        where = "%s$.steps[%d]" % (RECON, i)
        if get(row, "R8_FINAL_CLASSIFICATION", str, where) != "IN_PROCESS":
            continue
        if not get(row, "R8_REHEARSAL_EXECUTED", bool, where):
            not_executed.append("%s/%s/%s"
                                % (get(row, "AUDIT_ID", str, where),
                                   get(row, "PHASE", str, where),
                                   get(row, "STEP_ID", str, where)))
    return verdict("in-process rows not executed in the R8 rehearsal", [],
                   not_executed, RECON + "$.steps[*]")


def p_rehearsal_aggregate_invocations(d):
    return verdict("rehearsal.IN_PROCESS_HANDLER_INVOCATIONS", 169,
                   get(d["rehearsal"], "IN_PROCESS_HANDLER_INVOCATIONS", int,
                       REHEARSAL), REHEARSAL)


def p_rehearsal_aggregate_step_count(d):
    return verdict("rehearsal.IN_PROCESS_STEP_COUNT", 169,
                   get(d["rehearsal"], "IN_PROCESS_STEP_COUNT", int,
                       REHEARSAL), REHEARSAL)


def p_rehearsal_note_only(d):
    return verdict("rehearsal.NOTE_ONLY_IN_PROCESS_STEPS", 0,
                   get(d["rehearsal"], "NOTE_ONLY_IN_PROCESS_STEPS", int,
                       REHEARSAL), REHEARSAL)


def p_rehearsal_without_evidence(d):
    return verdict("rehearsal.REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE", 0,
                   get(d["rehearsal"],
                       "REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE", int,
                       REHEARSAL), REHEARSAL)


def p_rehearsal_hollow_phases(d):
    return verdict("rehearsal.HOLLOW_PHASES", [],
                   get(d["rehearsal"], "HOLLOW_PHASES", list, REHEARSAL),
                   REHEARSAL)


def p_per_phase_invocations_sum(d):
    """The 43 per-phase records must sum to the aggregate, not merely agree."""
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    total = 0
    for i, rep in enumerate(reports):
        total += get(rep, "IN_PROCESS_HANDLER_INVOCATIONS", int,
                     "%s$.reports[%d]" % (REHEARSAL, i))
    return verdict("sum of per-phase IN_PROCESS_HANDLER_INVOCATIONS", 169,
                   total, REHEARSAL + "$.reports[*]")


def p_per_phase_step_count_sum(d):
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    total = 0
    for i, rep in enumerate(reports):
        total += get(rep, "IN_PROCESS_STEP_COUNT", int,
                     "%s$.reports[%d]" % (REHEARSAL, i))
    return verdict("sum of per-phase IN_PROCESS_STEP_COUNT", 169, total,
                   REHEARSAL + "$.reports[*]")


def p_per_phase_note_only_sum(d):
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    total = 0
    for i, rep in enumerate(reports):
        total += get(rep, "NOTE_ONLY_IN_PROCESS_STEPS", int,
                     "%s$.reports[%d]" % (REHEARSAL, i))
    return verdict("sum of per-phase NOTE_ONLY_IN_PROCESS_STEPS", 0, total,
                   REHEARSAL + "$.reports[*]")


def p_per_phase_without_evidence_sum(d):
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    total = 0
    for i, rep in enumerate(reports):
        total += get(rep, "IN_PROCESS_STEPS_WITHOUT_EVIDENCE", int,
                     "%s$.reports[%d]" % (REHEARSAL, i))
    return verdict("sum of per-phase IN_PROCESS_STEPS_WITHOUT_EVIDENCE", 0,
                   total, REHEARSAL + "$.reports[*]")


def p_per_phase_none_hollow(d):
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    hollow = []
    for i, rep in enumerate(reports):
        where = "%s$.reports[%d]" % (REHEARSAL, i)
        if get(rep, "HOLLOW", bool, where):
            hollow.append("%s/%s" % (get(rep, "audit_id", str, where),
                                     get(rep, "run_phase", str, where)))
    return verdict("phases marked HOLLOW", [], hollow,
                   REHEARSAL + "$.reports[*]")


def p_per_phase_count(d):
    return verdict("rehearsal phase records", 43,
                   len(get(d["rehearsal"], "reports", list, REHEARSAL)),
                   REHEARSAL + "$.reports")


def p_plan_steps_derive_in_process(d):
    """Derive the in-process step set from the PLANS and the catalogue.

    The reconciliation record and the rehearsal report are both outputs of the
    same build. Deriving the same number a third time, from the 43 plan files
    and `operation_catalog.IN_PROCESS`, is what makes the agreement mean
    something rather than being two copies of one claim.
    """
    in_process_ops = d["in_process_operations"]
    found = 0
    for audit_id, phase, plan in d["plans"]:
        where = "plan %s/%s" % (audit_id, phase)
        for i, step in enumerate(get(plan, "steps", list, where)):
            op = get(step, "operation", str, "%s$.steps[%d]" % (where, i))
            if op in in_process_ops:
                found += 1
    return verdict("in-process steps derived from the 43 plans", 169, found,
                   "build/candidate_plans_r8/*/*/plan.json + "
                   "automation.operation_catalog.IN_PROCESS")


def p_every_in_process_operation_has_a_handler(d):
    missing = sorted(set(d["in_process_operations"]) - set(d["handlers"]))
    return verdict("in-process operations without a handler", [], missing,
                   "automation.operation_catalog.IN_PROCESS vs "
                   "automation.in_process_ops.HANDLERS")


def p_every_in_process_rehearsal_step_executed(d):
    """Per STEP, not per phase: an aggregate can hide one skipped step."""
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    ops = d["in_process_operations"]
    not_executed = []
    for i, rep in enumerate(reports):
        where = "%s$.reports[%d]" % (REHEARSAL, i)
        for j, step in enumerate(get(rep, "steps", list, where)):
            swhere = "%s.steps[%d]" % (where, j)
            if get(step, "operation", str, swhere) not in ops:
                continue
            if not get(step, "executed", bool, swhere):
                not_executed.append("%s/%s/%s"
                                    % (get(rep, "audit_id", str, where),
                                       get(rep, "run_phase", str, where),
                                       get(step, "step_id", str, swhere)))
    return verdict("in-process rehearsal steps not executed", [],
                   not_executed, REHEARSAL + "$.reports[*].steps[*]")


def p_no_note_only_step_in_any_phase(d):
    reports = get(d["rehearsal"], "reports", list, REHEARSAL)
    offenders = []
    for i, rep in enumerate(reports):
        where = "%s$.reports[%d]" % (REHEARSAL, i)
        for j, step in enumerate(get(rep, "steps", list, where)):
            swhere = "%s.steps[%d]" % (where, j)
            note = step.get("note") if isinstance(step, dict) else None
            if isinstance(note, str) and "performed by the worker" in note:
                offenders.append("%s/%s/%s"
                                 % (get(rep, "audit_id", str, where),
                                    get(rep, "run_phase", str, where),
                                    get(step, "step_id", str, swhere)))
    return verdict("rehearsal steps carrying the note-only fallback", [],
                   offenders, REHEARSAL + "$.reports[*].steps[*]")


# ---------------------------------------------------------------- item 28
def p_freeze_package_revision(d):
    return verdict("freeze.PACKAGE_REVISION", "R8", d["freeze_revision"],
                   "automation/freeze.py")


def p_freeze_package_platform(d):
    return verdict("freeze.PACKAGE_PLATFORM", "UBUNTU", d["freeze_platform"],
                   "automation/freeze.py")


def p_predecessor_baseline_digest_matches_lineage(d):
    return verdict("predecessor baseline digest equals lineage r7 record",
                   d["lineage_baseline_sha256"], d["baseline_file_sha256"],
                   "automation/freeze.py PREDECESSOR_BASELINE_REL vs "
                   "lineage/R8_LINEAGE.json $.r7.baseline_manifest_sha256")


def p_baseline_builds(d):
    return verdict("build_baseline_from_predecessor raised", False,
                   d["baseline_raised"], "automation/freeze.py")


def p_baseline_project_members_nonzero(d):
    return verdict("baseline project members > 0", True,
                   d["baseline_project_members"] > 0, "automation/freeze.py")


def p_baseline_discovery_members_nonzero(d):
    return verdict("baseline discovery members > 0", True,
                   d["baseline_discovery_members"] > 0, "automation/freeze.py")


def p_token_grammar_roundtrips(d):
    return verdict("token_for/parse_freeze_token round-trip on DUMMY digests",
                   True, d["token_roundtrip_ok"], "automation/freeze.py")


def p_token_five_fields(d):
    return verdict("dummy token field count", 5, d["token_field_count"],
                   "automation/freeze.py token_for")


def p_token_no_trailing_newline(d):
    return verdict("dummy token ends with a newline", False,
                   d["token_trailing_newline"], "automation/freeze.py")


def p_no_freeze_attempt_recorded(d):
    return verdict("recorded freeze attempts", 0, d["freeze_attempts"],
                   "state/freeze_attempts.jsonl")


def p_mode_generated_unverified(d):
    return verdict("MODE", "GENERATED_UNVERIFIED", d["mode"], "MODE")


# ---------------------------------------------------------------- item 29
def p_r9_absent(d):
    return verdict("08.18.26_Level1_Audits_R9 exists", False, d["r9_exists"],
                   "the directory beside the package")


# ---------------------------------------------------------------- item 30
def p_transitions_row_count(d):
    return verdict("state/transitions.jsonl rows", 1, len(d["transitions"]),
                   "state/transitions.jsonl")


def p_transitions_route(d):
    rows = d["transitions"]
    routes = [get(r, "route", str, "state/transitions.jsonl[%d]" % i)
              for i, r in enumerate(rows)]
    return verdict("transition routes", ["init-revision"], routes,
                   "state/transitions.jsonl")


# ---------------------------------------------------------------- item 34
def p_tool_inventory_unidentified(d):
    return verdict("TOOL_INVENTORY.UNIDENTIFIED_TOOLS", 0,
                   get(d["tool_inventory"], "UNIDENTIFIED_TOOLS", int,
                       "TOOL_INVENTORY.json"), "TOOL_INVENTORY.json")


def p_tool_inventory_digests(d):
    return verdict("tool inventory rows whose digest does not match disk", [],
                   d["tool_digest_mismatches"], "TOOL_INVENTORY.json")


def p_tool_inventory_roles_present(d):
    required = {"FINAL_VERIFICATION_INSTRUCTIONS", "VERIFICATION_RUNNER",
                "INVENTORY_SCRIPT", "INVENTORY_COMPARATOR", "TEST_RUNNER",
                "STATIC_SAFETY_RUNNER", "FREEZE_PLAN_BUILDER",
                "FREEZE_PLAN_VALIDATOR", "FREEZE_PLAN_WRAPPER",
                "FREEZE_MODULE", "TOKEN_GENERATION_FUNCTION_SOURCE",
                "CLONE_PREFLIGHT", "SCHEMA_MAP", "DELTA_VERIFIER_SELF_TEST",
                "DURABLE_ITEM_MATRIX"}
    roles = {get(t, "ROLE", str, "TOOL_INVENTORY.json$.tools[*]")
             for t in get(d["tool_inventory"], "tools", list,
                          "TOOL_INVENTORY.json")}
    return verdict("required tool roles absent from the inventory", [],
                   sorted(required - roles), "TOOL_INVENTORY.json")


def p_result_is_not_a_verifier(d):
    offenders = []
    for t in get(d["tool_inventory"], "tools", list, "TOOL_INVENTORY.json"):
        where = "TOOL_INVENTORY.json$.tools[*]"
        path = get(t, "CANONICAL_PATH", str, where)
        role = get(t, "ROLE", str, where)
        if os.path.basename(path) == "VERIFICATION_RESULT.json" and role in (
                "VERIFICATION_RUNNER", "FINAL_VERIFICATION_INSTRUCTIONS",
                "VERIFICATION_HELPER"):
            offenders.append(path)
    return verdict("VERIFICATION_RESULT.json labelled as a verifier", [],
                   offenders, "TOOL_INVENTORY.json")


# ---------------------------------------------------------------- item 35
def p_no_concurrent_writer(d):
    return verdict("processes holding a writable descriptor below R8", 0,
                   get(d["writers"], "BLOCKING_COUNT", int,
                       "WRITER_INSPECTION.json"), "/proc/<pid>/fd + fdinfo")


def p_writer_method_not_pgrep(d):
    return verdict("writer inspection used pgrep -f", False,
                   get(d["writers"], "pgrep_used", bool,
                       "WRITER_INSPECTION.json"), "/proc/<pid>/fd + fdinfo")


PREDICATES = {name: fn for name, fn in sorted(globals().items())
              if name.startswith("p_") and callable(fn)}
PREDICATE_ITEMS = {
    23: [n for n in PREDICATES if n.startswith(
        ("p_recon", "p_rehearsal", "p_per_phase", "p_plan_steps",
         "p_every_in_process", "p_no_note_only"))],
    28: ["p_freeze_package_revision", "p_freeze_package_platform",
         "p_predecessor_baseline_digest_matches_lineage", "p_baseline_builds",
         "p_baseline_project_members_nonzero",
         "p_baseline_discovery_members_nonzero", "p_token_grammar_roundtrips",
         "p_token_five_fields", "p_token_no_trailing_newline",
         "p_no_freeze_attempt_recorded", "p_mode_generated_unverified"],
    29: ["p_r9_absent"],
    30: ["p_transitions_row_count", "p_transitions_route"],
    34: ["p_tool_inventory_unidentified", "p_tool_inventory_digests",
         "p_tool_inventory_roles_present", "p_result_is_not_a_verifier"],
    35: ["p_no_concurrent_writer", "p_writer_method_not_pgrep"],
}
