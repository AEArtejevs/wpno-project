"""The one entry point for performing a plan-bound IN_PROCESS step.

The live controller and the rehearsal harness both call `execute`. That is
the point of the module. In R7 they had two different ideas of what an
IN_PROCESS step was, and both were wrong in the same direction: the
controller appended the note "in-process; performed by the worker" and moved
on, and the rehearsal recorded `executed: false` together with `ok: true`. A
step that had not run counted as a step that had passed, in both. Twelve of
the 43 phases are built entirely from such steps, so twelve phases could
report success having measured nothing, and did.

Two implementations cannot drift apart if there is one implementation. So the
harness does not judge an in-process step and the controller does not judge
one either; this module does, and both read its answer.

What `execute` is responsible for, in order:

     1  the operation name is in the catalogue and has a handler here
     2  the structured arguments match the operation's schema, exactly
     3  an assertion the operation carries is present when the plan requires it
     4  every path is admitted by `path_policy`
     5  traversal expressed in a path is refused
     6  a symlink leaving the allowed roots is refused
     7  an input path and an output destination are told apart
     8  an input must exist
     9  an output need not exist
    10  an output is confined to the writable work area
    11  a read outside the plan's declared allowed reads is refused
    12  a write outside the plan's declared allowed writes is refused
    13  the operation is actually performed
    14  input and output are bounded
    15  input digests are recorded
    16  output digests are recorded
    17  the actual result is recorded
    18  the declared expectation is evaluated against the actual result
    19  evidence is written
    20  a typed result is returned

Nothing here decides whether an audit passes. It decides whether the step ran
and whether what happened is what the plan said would happen. Those are two
different questions from the audit's finding and are kept apart from it.
"""

import fnmatch
import hashlib
import json
import os
import time

from . import hashing, in_process_ops, operation_catalog, path_policy, policy


class ExecutorError(Exception):
    """The step could not be executed as written. Not a measurement."""


# --------------------------------------------------------------- statuses
#
# A step is in exactly one of these. `SKIPPED` and `DEFERRED` are distinct
# from each other and both are distinct from `EXECUTED`: R7's accounting
# collapsed all three into "executed" and that is how a hollow phase reported
# success. `REFUSED` is separate again -- the step never reached its handler
# because the plan or the path policy would not allow it, which is a defect
# in the plan, not a finding about the target.
EXECUTED = "EXECUTED"
FAILED = "FAILED"
REFUSED = "REFUSED"
SKIPPED = "SKIPPED"
DEFERRED = "DEFERRED"
OPERATOR_ACTION = "OPERATOR_ACTION"

TERMINAL_WITH_EVIDENCE = (EXECUTED, FAILED)


# ------------------------------------------------------- argument schemas
#
# Derived from the 43 plans, not invented: every key below is a key some plan
# step actually carries, and every operation's required set is what every one
# of its steps supplies. An unknown key is refused rather than ignored,
# because a parameter that is accepted and never read is indistinguishable
# from a check that happened.
#
#   required   keys that must be present, with their permitted types
#   optional   keys that may be present, with their permitted types
#   inputs     keys whose value is a path the step reads
#   outputs    keys whose value is a path the step writes
#   assertions keys that carry an expectation the handler itself enforces

STR = (str,)
INT = (int,)
BOOL = (bool,)
LIST = (list,)

ARGUMENT_SCHEMA = {
    "READ_FILE_RANGE": {
        "required": {"path": STR, "length": INT},
        "optional": {"start": INT},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "LIST_DIRECTORY": {
        "required": {"path": STR},
        "optional": {"recursive": BOOL, "name_contains": STR},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "STAT_FILE": {
        "required": {"path": STR},
        "optional": {},
        # STAT_FILE is the one operation whose input may legitimately be
        # absent: "nothing is here" is the measurement a negative control
        # about an impossible path is built to take. The path is still
        # admitted by policy; it is only existence that is not required.
        "inputs": (), "input_may_be_absent": ("path",),
        "outputs": (), "assertions": ()},
    "SHA256_FILE": {
        "required": {"path": STR},
        "optional": {"expected_sha256": STR},
        "inputs": ("path",), "outputs": (),
        "assertions": ("expected_sha256",)},
    "COMPARE_HASHES": {
        "required": {"left": STR, "right": STR},
        "optional": {"algorithms": LIST, "expected_sha256": STR},
        "inputs": ("left", "right"), "outputs": (),
        "assertions": ("expected_sha256",)},
    "COMPARE_BINARY_FILES": {
        "required": {"left": STR, "right": STR},
        "optional": {},
        "inputs": ("left", "right"), "outputs": (), "assertions": ()},
    "PYTHON_AST_PARSE": {
        "required": {"path": STR},
        "optional": {},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "PARSE_JSON_READONLY": {
        "required": {"path": STR},
        "optional": {"expect_contains": STR, "expect_absent": STR},
        "inputs": ("path",), "outputs": (),
        "assertions": ("expect_contains", "expect_absent")},
    "PARSE_CSV_READONLY": {
        "required": {"path": STR},
        "optional": {},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "COUNT_TEXT_MATCHES": {
        "required": {"patterns": LIST},
        "optional": {"path": STR, "root": STR, "include_globs": LIST,
                     "word_boundary": BOOL, "normal_form": STR},
        "inputs": ("path", "root"), "outputs": (), "assertions": ()},
    "ZIP_LIST": {
        "required": {"path": STR},
        "optional": {},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "TAR_LIST": {
        "required": {"path": STR},
        "optional": {},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "XML_PARSE_SANDBOX": {
        "required": {"path": STR, "no_network": BOOL,
                     "resolve_entities": BOOL, "load_dtd": BOOL},
        "optional": {"xinclude": BOOL},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "DOCX_PARSE_SANDBOX": {
        "required": {"path": STR, "no_network": BOOL,
                     "resolve_entities": BOOL, "load_dtd": BOOL},
        "optional": {"select": STR, "xinclude": BOOL},
        "inputs": ("path",), "outputs": (), "assertions": ()},
    "DOCKER_METADATA_IMPORT": {
        "required": {"export": STR, "no_socket": BOOL},
        "optional": {},
        "inputs": ("export",), "outputs": (), "assertions": ()},
    "DATABASE_EVIDENCE_IMPORT": {
        "required": {"export": STR, "no_connection": BOOL},
        "optional": {},
        "inputs": ("export",), "outputs": (), "assertions": ()},
    "MIME_EXTRACT_XML_PART_SANDBOX": {
        "required": {"path": STR, "out": STR, "no_network": BOOL,
                     "resolve_entities": BOOL},
        "optional": {"select_content_type": STR, "select_content_id": STR},
        "inputs": ("path",), "outputs": ("out",), "assertions": ()},
    "PROVE_SET_NOVELTY": {
        "required": {"candidate_root": STR, "reference_root": STR,
                     "reference_set_id": STR},
        "optional": {"include_globs": LIST,
                     "expected_reference_entry_count": INT,
                     "require_non_empty_reference": BOOL},
        "inputs": ("candidate_root", "reference_root"), "outputs": (),
        "assertions": ("expected_reference_entry_count",)},
}


# ------------------------------------------------------ expectation model
#
# Section 14's vocabulary. A control must carry at least one of these, and
# the one it carries must be appropriate to what its operation returns. An
# exit code is right for an operation that either completes or refuses; it is
# not right for one whose whole answer is a number, and requiring it there
# would push a plan towards an assertion that does not measure the thing.
EXPECTATION_KEYS = (
    "expected_exit_code",
    "expected_status",
    "expected_count",
    "expected_minimum_count",
    "expected_hash_relation",
    "expected_boolean",
    "expected_difference_count",
    "expected_failure_reason_canonical",
    "expected_parse_result",
    "expected_validation_result",
)

# `expected_status` values, and what each one actually asserts.
#
# COMPLETED_OUTCOME_IS_SUBSTANTIVE is the one that needed inventing, and it
# is the reason this vocabulary is not simply "exit code". Several controls
# are built around an outcome the plan deliberately does not predetermine --
# L1-A02's three modified-document fixtures say "Expected: open" in as many
# words, and L1-A01's determinism control exists precisely to find out
# whether the two runs agree. Demanding an exit code there would mean writing
# down an answer the audit has not measured yet, which CLAUDE.md section 3
# forbids and which is how a control comes to pass by construction.
#
# What can still be demanded, and is, is that the step really ran: that it
# reached its handler or its subprocess, produced an exit code, and left
# evidence. That is not a weaker check than an exit code. It is the exact
# check whose absence let 165 steps report success without running, and no
# control may satisfy it by being skipped.
STATUS_EXPECTATIONS = {
    "COMPLETED_OUTCOME_IS_SUBSTANTIVE": (
        "the step must actually have run and produced a recorded exit code "
        "and evidence; the value of the outcome is the audit's finding and "
        "is not predetermined here"),
    "EXECUTED": "the operation must complete without error",
    "FAILED": "the operation must fail",
    "OPERATOR_ACTION": (
        "the step is performed on another host and must be recorded as an "
        "operator action here, never as an operation this machine ran"),
}

# Where a numeric or boolean expectation reads its answer from, per
# operation. Named here rather than guessed from the result dictionary,
# because a key that happens to be absent would otherwise score as a pass.
EXPECTATION_FIELD = {
    "expected_count": {
        "PROVE_SET_NOVELTY": "duplicate_count",
        "COUNT_TEXT_MATCHES": "total_matches",
        "LIST_DIRECTORY": "match_count",
        "ZIP_LIST": "entry_count",
        "TAR_LIST": "entry_count",
        "DOCKER_METADATA_IMPORT": "record_count",
        "DATABASE_EVIDENCE_IMPORT": "record_count",
        "DOCX_PARSE_SANDBOX": "paragraph_count",
    },
    "expected_boolean": {
        "PROVE_SET_NOVELTY": "all_novel",
        "COMPARE_HASHES": "equal",
        "COMPARE_BINARY_FILES": "identical",
        "STAT_FILE": "exists",
        "SHA256_FILE": "matches_expected",
        "PARSE_JSON_READONLY": "parsed",
        "XML_PARSE_SANDBOX": "parsed",
        "DOCX_PARSE_SANDBOX": "parsed",
        "PYTHON_AST_PARSE": "parsed",
        "MIME_EXTRACT_XML_PART_SANDBOX": "source_unchanged",
    },
    "expected_difference_count": {
        "COMPARE_BINARY_FILES": "differing_byte_count",
    },
    "expected_hash_relation": {
        "COMPARE_HASHES": "equal",
        "COMPARE_BINARY_FILES": "identical",
    },
}


def expectation_keys_present(entry):
    """The machine-checkable expectations this test-matrix entry declares."""
    if not entry:
        return []
    return [key for key in EXPECTATION_KEYS if entry.get(key) is not None]


def expectation_is_applicable(operation, key):
    """Whether `key` can actually be evaluated against `operation`'s result."""
    if key in ("expected_exit_code", "expected_status",
               "expected_failure_reason_canonical", "expected_parse_result",
               "expected_validation_result"):
        return True
    if key == "expected_minimum_count":
        return operation in EXPECTATION_FIELD["expected_count"]
    return operation in EXPECTATION_FIELD.get(key, {})


# ------------------------------------------------------------ path policy

def _admit_input(value, *, must_exist):
    path_policy.assert_no_symlink_escape(value)
    canonical = path_policy.assert_readable(value)
    if must_exist and not os.path.exists(canonical):
        raise ExecutorError("input does not exist: %s" % canonical)
    return canonical


def _admit_output(value):
    """An output is admitted for writing and need not exist yet."""
    canonical = path_policy.assert_writable(value)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not canonical.startswith(work_root + os.sep):
        raise ExecutorError(
            "output is outside the writable work area: %s" % canonical)
    if os.path.lexists(canonical) and os.path.islink(canonical):
        raise ExecutorError("output destination is a symlink: %s" % canonical)
    return canonical


def _matches_allowance(canonical, allowance):
    """Does `canonical` fall under one declared allowance entry?

    An allowance is written either absolutely or relative to the package
    root, and may end in `/` to mean a directory or carry a `*` to mean a
    glob. All three forms occur in the plans, so all three are handled here
    rather than in three different call sites.
    """
    entry = allowance.rstrip("/")
    if "<n>" in entry:
        entry = entry.split("<n>")[0].rstrip("/")
    if not entry:
        return False
    if not os.path.isabs(entry):
        entry = os.path.join(path_policy.LEVEL1_ROOT, entry)
    entry = os.path.normpath(entry)
    if "*" in entry or "?" in entry:
        return (fnmatch.fnmatch(canonical, entry)
                or fnmatch.fnmatch(canonical, entry + os.sep + "*"))
    return canonical == entry or canonical.startswith(entry + os.sep)


def _classify_allowance(canonical, allowances):
    """Where a path stands against a declared allowance list.

    Three answers, and the third is deliberately not a refusal.

    ALLOWED                     the path is inside a declared entry.
    NOT_DECLARED_BY_PLAN        the plan declares no allowance of this kind.
                                Nine of the 43 plans carry no binding
                                envelope, so this is recorded rather than
                                silently satisfied: an allowance that was
                                never declared has not been checked, and a
                                check that always passes is worse than none.
    OUTSIDE_DECLARED_ALLOWANCE  the path is admitted by the path policy but
                                falls outside what the plan wrote down.

    The third refuses, and it refuses because it can. When the check was
    first written, three L1-A17 steps scanned PROJECT_ROOT while that plan's
    envelope declared three subdirectories, so refusing would have broken a
    phase whose specification requires exactly that scan: "Record the search
    set exhaustively, including every location searched and found empty, so
    absence is documented rather than assumed." The envelope was
    under-declared, not the steps over-reaching, and the envelope has been
    corrected. Two further reads introduced by the L1-A33 repair were
    declared narrowly, by exact filename.

    With the count at zero across all 43 plans, the check no longer has to
    choose between refusing correct work and recording a finding nobody
    acts on. A read outside what the plan wrote down is now refused, so the
    declaration is a gate rather than a description, and a plan that grows a
    read it did not declare fails at that step instead of quietly widening.

    Confinement was never what this check provided. Every path also passes
    `path_policy`, which admits three roots and refuses traversal and
    symlink escape.
    """
    if not allowances:
        return "NOT_DECLARED_BY_PLAN"
    for entry in allowances:
        if _matches_allowance(canonical, entry):
            return "ALLOWED"
    return "OUTSIDE_DECLARED_ALLOWANCE"


# ----------------------------------------------------------------- schema

def validate_arguments(operation, params):
    """Check the structured arguments against the operation's schema.

    Returns (inputs, outputs, may_be_absent). Raises rather than returning a
    verdict: a step whose arguments the schema does not admit has not been
    measured and must not be recorded as though it had.
    """
    schema = ARGUMENT_SCHEMA.get(operation)
    if schema is None:
        raise ExecutorError(
            "%s: no argument schema for %s"
            % (in_process_ops.UNSUPPORTED, operation))
    if not isinstance(params, dict):
        raise ExecutorError("params must be an object, got %r"
                            % type(params).__name__)

    known = dict(schema["required"])
    known.update(schema["optional"])
    for key in sorted(params):
        if key not in known:
            raise ExecutorError(
                "%s does not accept parameter %r; the accepted keys are %s"
                % (operation, key, sorted(known)))
        value = params[key]
        types = known[key]
        # bool is a subclass of int; an operation expecting a count must not
        # silently accept True as 1.
        if types == INT and isinstance(value, bool):
            raise ExecutorError("%s parameter %r must be an int, got a bool"
                                % (operation, key))
        if not isinstance(value, types):
            raise ExecutorError(
                "%s parameter %r must be %s, got %s"
                % (operation, key, "/".join(t.__name__ for t in types),
                   type(value).__name__))
    for key in sorted(schema["required"]):
        if key not in params:
            raise ExecutorError("%s requires parameter %r" % (operation, key))

    if operation == "COUNT_TEXT_MATCHES" and not (
            "path" in params or "root" in params):
        raise ExecutorError(
            "COUNT_TEXT_MATCHES requires either path or root")

    inputs = [params[k] for k in schema["inputs"] if k in params]
    outputs = [params[k] for k in schema["outputs"] if k in params]
    absent_ok = [params[k] for k in schema.get("input_may_be_absent", ())
                 if k in params]
    return inputs, outputs, absent_ok


def required_assertions_present(operation, params, entry):
    """Assertion fields the plan's expectation implies the step must carry.

    A negative control asserted through `expect_absent` needs that parameter
    on the step, not only a sentence in the test matrix. Where the plan
    declares an expectation whose evaluation depends on a parameter, the
    parameter is required here rather than discovered missing at run time.
    """
    missing = []
    schema = ARGUMENT_SCHEMA.get(operation) or {}
    if (entry or {}).get("expected_hash_relation") is not None \
            and operation == "SHA256_FILE" \
            and "expected_sha256" not in params:
        missing.append("expected_sha256")
    for key in schema.get("assertions", ()):
        declared = (entry or {}).get("requires_assertion") or ()
        if key in declared and key not in params:
            missing.append(key)
    return missing


# ------------------------------------------------------------- evaluation

def evaluate(operation, entry, exit_code, result):
    """Judge the actual outcome against the declared expectation.

    Returns a dict, never a bare boolean. What the plan expected, what
    actually happened and whether they agree are three separate facts and are
    recorded as three.

    A control with no declared expectation is not scored as a pass. It is
    recorded as NO_MACHINE_CHECKABLE_EXPECTATION and the caller decides what
    that means -- which, for a control role, is a defect.
    """
    declared = expectation_keys_present(entry)
    out = {
        "expected_outcome": None,
        "actual_outcome": None,
        "expected_failure_reason": (entry or {}).get(
            "expected_failure_reason_canonical")
        or (entry or {}).get("expected_failure_reason"),
        "actual_failure_reason": (result.get("reason")
                                  if isinstance(result, dict) else None),
        "declared_expectations": declared,
        "expectations_evaluated": [],
        "expectation_satisfied": None,
        "expectation_result": None,
    }

    if not declared:
        out["expectation_result"] = "NO_MACHINE_CHECKABLE_EXPECTATION"
        out["actual_outcome"] = {"exit_code": exit_code}
        return out

    verdicts = []
    expected_summary = {}
    actual_summary = {"exit_code": exit_code}

    for key in declared:
        want = entry[key]
        expected_summary[key] = want

        if key == "expected_exit_code":
            if want == "NONZERO":
                ok = exit_code != 0
            else:
                ok = exit_code == int(want)
            verdicts.append((key, ok))
            continue

        if key == "expected_status":
            got = EXECUTED if exit_code == 0 else FAILED
            actual_summary["status"] = got
            if want == "COMPLETED_OUTCOME_IS_SUBSTANTIVE":
                # The step ran. Whether it exited 0 is the audit's finding.
                # `exit_code is not None` is the whole assertion, and it is
                # not satisfiable by a step that was skipped, deferred or
                # refused: those never reach this function.
                ok = exit_code is not None
                actual_summary["outcome_is_substantive"] = True
            elif want == "OPERATOR_ACTION":
                # Reached here at all means this machine performed it, which
                # is exactly what an operator-performed step must not do.
                ok = False
                actual_summary["refused_reason"] = (
                    "a step expected to be an operator action was performed "
                    "in process")
            else:
                ok = got == want
            verdicts.append((key, ok))
            continue

        if key == "expected_failure_reason_canonical":
            got = str((result or {}).get("reason", ""))
            actual_summary["failure_reason"] = got[:400]
            verdicts.append((key, want in got))
            continue

        if key in ("expected_parse_result", "expected_validation_result"):
            got = "PARSED" if exit_code == 0 else "REFUSED"
            actual_summary[key.replace("expected_", "actual_")] = got
            verdicts.append((key, got == want))
            continue

        # `expected_minimum_count` reads the same measured field as
        # `expected_count`; it differs only in the comparison.
        lookup = ("expected_count" if key == "expected_minimum_count"
                  else key)
        field = EXPECTATION_FIELD.get(lookup, {}).get(operation)
        if field is None:
            verdicts.append((key, False))
            actual_summary[key] = "NOT_APPLICABLE_TO_%s" % operation
            continue
        if exit_code != 0:
            # The operation refused, so the field it would have measured does
            # not exist. That is a failed expectation, not a missing one.
            verdicts.append((key, False))
            actual_summary[key] = "OPERATION_FAILED_BEFORE_MEASURING"
            continue
        got = (result or {}).get(field)
        actual_summary[field] = got
        if key == "expected_minimum_count":
            ok = isinstance(got, int) and got >= want
            verdicts.append((key, ok))
            continue
        if key == "expected_hash_relation":
            ok = (bool(got) is True) if want == "EQUAL" else (
                (bool(got) is False) if want == "DIFFERENT" else False)
        else:
            ok = got == want
        verdicts.append((key, ok))

    out["expected_outcome"] = expected_summary
    out["actual_outcome"] = actual_summary
    out["expectations_evaluated"] = [
        {"expectation": key, "satisfied": ok} for key, ok in verdicts]
    out["expectation_satisfied"] = all(ok for _, ok in verdicts)
    out["expectation_result"] = ("AS_EXPECTED" if out["expectation_satisfied"]
                                 else "NOT_AS_EXPECTED")
    return out


# -------------------------------------------------------------- execution

def _digest(path):
    if not os.path.isfile(path):
        return None
    return hashing.sha256_file(path)


def execute(step, entry=None, *, allowed_reads=(), allowed_writes=(),
            substitutions=None, require_expectation=False):
    """Perform one plan-bound IN_PROCESS step and return a typed result.

    `substitutions` maps a planned path to the path actually read. It exists
    for one purpose: a COMPARISON phase names the sealed evidence of two
    phases that have not run yet, and a rehearsal of it must read something.
    The substitution is recorded in the result, both sides of it, so a reader
    can never mistake a rehearsal against a fixture for a live comparison.
    It is never used by the live controller, which passes none.
    """
    operation = step["operation"]
    params = dict(step.get("params") or {})
    substitutions = dict(substitutions or {})

    record = {
        "step_id": step.get("step_id"),
        "operation": operation,
        "control_role": step.get("control_role"),
        "structured_arguments": params,
        "input_paths": [],
        "input_sha256": {},
        "output_paths": [],
        "output_sha256": {},
        "started_utc": None,
        "ended_utc": None,
        "duration_ms": None,
        "executed": False,
        "status": None,
        "expected_outcome": None,
        "actual_outcome": None,
        "expected_failure_reason": None,
        "actual_failure_reason": None,
        "result_artifact": None,
        "error_artifact": None,
        "path_substitutions": {},
        "allowed_reads_enforcement": None,
        "allowed_writes_enforcement": None,
        "in_process": True,
        "argv": [],
        "argv_note": ("no argv: no process is launched. A reconstructed "
                      "command line for an operation that never ran a "
                      "command would be a plausible artefact of a thing that "
                      "did not happen."),
    }

    started = time.time()
    record["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime(started))

    def finish(status, *, result=None, error=None):
        ended = time.time()
        record["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime(ended))
        record["duration_ms"] = int((ended - started) * 1000)
        record["status"] = status
        record["executed"] = status in TERMINAL_WITH_EVIDENCE
        if result is not None:
            record["result_artifact"] = result
        if error is not None:
            record["error_artifact"] = error
            record["actual_failure_reason"] = (
                record["actual_failure_reason"] or error)
        return record

    # 1 -- the operation is known, catalogued and implemented here.
    if operation not in operation_catalog.IN_PROCESS:
        return finish(REFUSED, error="NOT_AN_IN_PROCESS_OPERATION: %s"
                      % operation)
    if not in_process_ops.supported(operation):
        return finish(REFUSED, error="%s: %s"
                      % (in_process_ops.UNSUPPORTED, operation))

    # 2/3 -- arguments and required assertions.
    try:
        inputs, outputs, absent_ok = validate_arguments(operation, params)
    except ExecutorError as exc:
        return finish(REFUSED, error="ARGUMENT_SCHEMA_REFUSED: %s" % exc)

    missing = required_assertions_present(operation, params, entry)
    if missing:
        return finish(REFUSED,
                      error="REQUIRED_ASSERTION_MISSING: %s" % sorted(missing))

    if require_expectation and not expectation_keys_present(entry):
        return finish(REFUSED, error="NO_MACHINE_CHECKABLE_EXPECTATION")

    # 4-12 -- paths.
    effective = dict(params)
    schema = ARGUMENT_SCHEMA[operation]
    # A phase may read what it is allowed to write. Its own work directory is
    # where it stages the control fixtures its later steps compare, and five
    # phases do exactly that; requiring the same directory to be listed twice
    # would be a bookkeeping rule, not a safety one.
    readable_allowances = tuple(allowed_reads) + tuple(allowed_writes)

    reads = []
    writes = []
    try:
        for key in schema["inputs"] + schema.get("input_may_be_absent", ()):
            if key not in params:
                continue
            planned = params[key]
            actual = substitutions.get(planned, planned)
            if actual != planned:
                record["path_substitutions"][planned] = actual
            must_exist = key not in schema.get("input_may_be_absent", ())
            canonical = _admit_input(actual, must_exist=must_exist)
            # The allowance is a statement about the plan, so it is checked
            # against the path the plan names. The substituted path is a
            # rehearsal artefact and is recorded, not judged against a
            # declaration that could not have anticipated it. The path
            # policy, which is the safety check, is applied to the path
            # actually opened.
            reads.append(_classify_allowance(planned, readable_allowances))
            record["input_paths"].append(canonical)
            record["input_sha256"][canonical] = _digest(canonical)
            effective[key] = canonical
        for key in schema["outputs"]:
            if key not in params:
                continue
            canonical = _admit_output(params[key])
            writes.append(_classify_allowance(params[key], allowed_writes))
            record["output_paths"].append(canonical)
            effective[key] = canonical
    except (ExecutorError, path_policy.PathPolicyError) as exc:
        return finish(REFUSED, error="PATH_REFUSED: %s: %s"
                      % (type(exc).__name__, exc))

    def worst(values):
        for level in ("OUTSIDE_DECLARED_ALLOWANCE", "NOT_DECLARED_BY_PLAN",
                      "ALLOWED"):
            if level in values:
                return level
        return None

    record["allowed_reads_enforcement"] = worst(reads)
    record["allowed_writes_enforcement"] = worst(writes)
    record["reads_outside_declared_allowance"] = [
        params[key] for key, value in zip(
            [k for k in schema["inputs"] + schema.get("input_may_be_absent", ())
             if k in params], reads)
        if value == "OUTSIDE_DECLARED_ALLOWANCE"]
    record["writes_outside_declared_allowance"] = [
        params[key] for key, value in zip(
            [k for k in schema["outputs"] if k in params], writes)
        if value == "OUTSIDE_DECLARED_ALLOWANCE"]
    if record["reads_outside_declared_allowance"]:
        return finish(REFUSED, error="READ_OUTSIDE_DECLARED_ALLOWANCE: %s"
                      % record["reads_outside_declared_allowance"])
    if record["writes_outside_declared_allowance"]:
        return finish(REFUSED, error="WRITE_OUTSIDE_DECLARED_ALLOWANCE: %s"
                      % record["writes_outside_declared_allowance"])

    # 14 -- bounded input.
    for canonical in record["input_paths"]:
        if os.path.isfile(canonical):
            size = os.path.getsize(canonical)
            limit = (in_process_ops.MAX_MIME_INPUT_BYTES
                     if operation == "MIME_EXTRACT_XML_PART_SANDBOX"
                     else in_process_ops.MAX_READ_BYTES)
            if size > limit and operation not in (
                    "SHA256_FILE", "COMPARE_HASHES", "COMPARE_BINARY_FILES",
                    "ZIP_LIST", "TAR_LIST", "DOCX_PARSE_SANDBOX",
                    "LIST_DIRECTORY", "STAT_FILE", "COUNT_TEXT_MATCHES"):
                return finish(REFUSED,
                              error="INPUT_EXCEEDS_BOUND: %s is %d bytes"
                              % (canonical, size))

    # 13 -- perform it.
    try:
        exit_code, result = in_process_ops.perform(operation, effective)
    except in_process_ops.UnsupportedInProcessOperation as exc:
        return finish(REFUSED, error=str(exc))
    except Exception as exc:                                  # noqa: BLE001
        return finish(REFUSED, error="HANDLER_RAISED: %s: %s"
                      % (type(exc).__name__, exc))

    # 16 -- output digests, measured after the operation ran.
    for canonical in record["output_paths"]:
        record["output_sha256"][canonical] = _digest(canonical)

    # 14 -- bounded output.
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True,
                         indent=2, default=str)
    truncated = len(payload.encode("utf-8")) > policy.MAX_OUTPUT_BYTES
    record["result_truncated"] = truncated

    # 17/18 -- the actual result and the declared expectation.
    record["exit_code"] = exit_code
    judgement = evaluate(operation, entry, exit_code, result)
    record.update({k: v for k, v in judgement.items()
                   if k in ("expected_outcome", "actual_outcome",
                            "expected_failure_reason", "actual_failure_reason",
                            "declared_expectations", "expectations_evaluated",
                            "expectation_satisfied", "expectation_result")})

    status = EXECUTED if exit_code == 0 else FAILED
    return finish(status, result=result,
                  error=(None if exit_code == 0
                         else str((result or {}).get("reason", ""))[:2000]))


def result_payload(record):
    """The canonical bytes an executed step contributes as its stdout.

    Canonical JSON, so the evidence manifest hashes something stable, and the
    same bytes whether the caller was the controller or the rehearsal.
    """
    return json.dumps(record.get("result_artifact"), ensure_ascii=False,
                      sort_keys=True, indent=2, default=str).encode("utf-8")


def self_check():
    """Every catalogued IN_PROCESS operation has a schema and a handler.

    Run by the tests and by the plan builder. A catalogue entry with no
    handler is the defect this package was built to stop shipping, so it is
    detected by a check rather than by a phase reporting success.
    """
    catalogued = set(operation_catalog.IN_PROCESS)
    handled = set(in_process_ops.HANDLERS)
    schemad = set(ARGUMENT_SCHEMA)
    return {
        "catalogued": sorted(catalogued),
        "handled": sorted(handled),
        "schemad": sorted(schemad),
        "catalogued_without_handler": sorted(catalogued - handled),
        "catalogued_without_schema": sorted(catalogued - schemad),
        "handler_without_schema": sorted(handled - schemad),
        "schema_without_handler": sorted(schemad - handled),
        "ok": not (catalogued - handled) and not (catalogued - schemad)
              and not (handled - schemad) and not (schemad - handled),
    }
