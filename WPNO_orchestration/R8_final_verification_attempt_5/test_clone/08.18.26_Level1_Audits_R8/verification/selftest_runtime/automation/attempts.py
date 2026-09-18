"""Phase attempts.

R6 had one attempt per phase and no word for it. `results/L1-A31/RUN-A/plan.json`
was *the* plan, `evidence/L1-A31/RUN-A/SEAL.json` was *the* seal, and when that
seal recorded ERROR the phase was finished. The ERROR was not a finding about
the audited target. It was three wrong parameters in the plan the controller
had been handed. There was no lawful way to hand it a corrected one.

This module introduces the missing distinction, and only that distinction:

    an ATTEMPT is one plan, approved once, executed once, sealed once,
    and never touched again;

    a PHASE is the question the audit asks, which may have taken more than
    one attempt to answer.

Everything immutable stays immutable. A sealed attempt is not editable, not
deletable and not replaceable — including the sealed R6 ERROR, which is
preserved in R7's lineage exactly as it was written. What changes is that the
*phase* is no longer required to die with its first attempt.

Three rules keep this from becoming a way to retry until something passes.

1.  Only a defect in our own machinery is retryable. A verdict that says
    something about the target — PASS, PASS_WITH_WARNINGS, FAIL, UNVERIFIED —
    is a substantive result. It seals the phase and stops. `prepare_retry`
    refuses it by name, not by omission.

2.  A retry must differ. The new plan bytes must differ from the sealed
    attempt's plan bytes, and the caller must name the root cause and point at
    the evidence that the cause was actually repaired. Re-running the same
    plan in the hope of a different answer is refused.

3.  Attempts are bounded. MAX_ATTEMPTS_PER_PHASE is a ceiling, not a budget to
    spend.
"""

import json
import os
import re

from . import hashing, path_policy, policy


class AttemptError(Exception):
    """A rule of the attempt model was broken. The message names which one."""


ATTEMPT_DIR_PREFIX = "attempt-"
_ATTEMPT_DIR_RE = re.compile(r"^attempt-(\d+)$")

# --- classification --------------------------------------------------------
# What kind of thing the sealed attempt turned out to be. This is not a
# free-text label: it decides whether the phase may be attempted again, so it
# is a closed set and the controller derives it under a verdict-specific
# allowlist.
CLASSIFICATIONS = (
    "SUBSTANTIVE_AUDIT_RESULT",
    "INTERNAL_REPAIRABLE_DEFECT",
    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
    "CONTROL_PLANE_INTEGRITY_FAILURE",
    "INDEPENDENT_METHOD_MATERIAL_MISSING",
)

# Which classifications each verdict admits. A PASS cannot be an internal
# defect and an ERROR cannot be a substantive result; allowing either would
# let a caller relabel one into the other and unlock a retry that the verdict
# does not permit.
VERDICT_CLASSIFICATIONS = {
    "PASS": ("SUBSTANTIVE_AUDIT_RESULT",),
    "PASS_WITH_WARNINGS": ("SUBSTANTIVE_AUDIT_RESULT",),
    "FAIL": ("SUBSTANTIVE_AUDIT_RESULT",),
    "UNVERIFIED": ("SUBSTANTIVE_AUDIT_RESULT",),
    "ERROR": ("INTERNAL_REPAIRABLE_DEFECT",
              "CONTROL_PLANE_INTEGRITY_FAILURE",
              "INDEPENDENT_METHOD_MATERIAL_MISSING"),
    "BLOCKED": ("MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
                "CONTROL_PLANE_INTEGRITY_FAILURE"),
    "CONTAMINATED": ("CONTROL_PLANE_INTEGRITY_FAILURE",),
}

# Where the aggregate phase stands once the attempt is sealed and classified.
AGGREGATE_AFTER_SEAL = {
    "SUBSTANTIVE_AUDIT_RESULT": "SEALED",
    "INTERNAL_REPAIRABLE_DEFECT": "RETRYABLE_INTERNAL_ERROR",
    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT":
        "BLOCKED_FOR_EXTERNAL_MATERIAL",
    "INDEPENDENT_METHOD_MATERIAL_MISSING": "BLOCKED_FOR_EXTERNAL_MATERIAL",
    # A control-plane integrity failure is not an audit result and is not a
    # thing this loop may repair by itself. It stops for a human.
    "CONTROL_PLANE_INTEGRITY_FAILURE": "HALT_CRITICAL",
}

RETRYABLE_CLASSIFICATIONS = (
    "INTERNAL_REPAIRABLE_DEFECT",
    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
    "INDEPENDENT_METHOD_MATERIAL_MISSING",
)

# A classification that requires new material from a human before any retry is
# even considered. Repairing our own code cannot conjure a missing reference.
REQUIRES_EXTERNAL_MATERIAL = (
    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
    "INDEPENDENT_METHOD_MATERIAL_MISSING",
)

# A verdict that is a statement about the target. Named explicitly so the
# refusal message can say *which* rule refused, rather than reporting the
# absence of a permission.
SUBSTANTIVE_VERDICTS = ("PASS", "PASS_WITH_WARNINGS", "FAIL", "UNVERIFIED")


def assert_classification(verdict, classification):
    """Refuse a classification the verdict does not admit."""
    if verdict not in policy.VERDICTS:
        raise AttemptError("unknown verdict: %r" % (verdict,))
    if classification not in CLASSIFICATIONS:
        raise AttemptError(
            "unknown attempt classification: %r. The permitted set is %r"
            % (classification, list(CLASSIFICATIONS)))
    allowed = VERDICT_CLASSIFICATIONS[verdict]
    if classification not in allowed:
        raise AttemptError(
            "verdict %s cannot be classified %s; the only classifications a "
            "%s admits are %r. A substantive verdict is a statement about the "
            "target and relabelling it as a defect in our own harness is the "
            "one move this model exists to refuse."
            % (verdict, classification, verdict, list(allowed)))
    return classification


def aggregate_state_for(classification):
    return AGGREGATE_AFTER_SEAL[classification]


def is_retryable(classification):
    return classification in RETRYABLE_CLASSIFICATIONS


# --- attempt identity and paths -------------------------------------------
def attempt_dirname(number):
    assert_attempt_number(number)
    return "%s%d" % (ATTEMPT_DIR_PREFIX, number)


def attempt_id(audit_id, run_phase, number):
    """The attempt's name, everywhere. One spelling, computed in one place."""
    assert_attempt_number(number)
    return "%s/%s/attempt-%d" % (audit_id, run_phase, number)


def assert_attempt_number(number):
    if not isinstance(number, int) or isinstance(number, bool):
        raise AttemptError("attempt number must be an int, got %r"
                           % (type(number).__name__,))
    if number < 1:
        raise AttemptError("attempt numbers start at 1, got %d" % number)
    if number > policy.MAX_ATTEMPTS_PER_PHASE:
        raise AttemptError(
            "attempt %d exceeds MAX_ATTEMPTS_PER_PHASE=%d"
            % (number, policy.MAX_ATTEMPTS_PER_PHASE))
    return number


def results_dir(audit_id, run_phase, number):
    return path_policy.assert_writable(os.path.join(
        path_policy.audit_results_dir(audit_id, run_phase),
        attempt_dirname(number)))


def evidence_dir(audit_id, run_phase, number):
    return path_policy.assert_writable(os.path.join(
        path_policy.audit_evidence_dir(audit_id, run_phase),
        attempt_dirname(number)))


def work_dir(audit_id, run_phase, number):
    return path_policy.assert_writable(os.path.join(
        path_policy.audit_work_dir(audit_id, run_phase),
        attempt_dirname(number)))


def plan_path(audit_id, run_phase, number):
    return os.path.join(results_dir(audit_id, run_phase, number), "plan.json")


def existing_attempt_numbers(audit_id, run_phase):
    """Attempt numbers with a directory on disk, ascending.

    Read from the filesystem rather than from state, because this is the
    question `prepare-retry` must answer before it trusts state: an attempt
    directory that exists but is unknown to state is a contradiction that must
    surface, not be averaged away.
    """
    root = path_policy.audit_evidence_dir(audit_id, run_phase)
    if not os.path.isdir(root):
        return []
    found = []
    for name in os.listdir(root):
        match = _ATTEMPT_DIR_RE.match(name)
        if match and os.path.isdir(os.path.join(root, name)):
            found.append(int(match.group(1)))
    return sorted(found)


# --- attempt records in progress.json -------------------------------------
def phase_node(progress, audit_id, run_phase):
    return progress.get("audits", {}).get(audit_id, {}).get(run_phase, {})


def attempt_records(node):
    """The immutable history, oldest first. Never rewritten, only appended."""
    raw = node.get("attempts") or {}
    return [raw[key] for key in sorted(raw, key=int)]


def attempt_record(node, number):
    return (node.get("attempts") or {}).get(str(number))


def current_attempt_number(node):
    return node.get("attempt_number")


def accepted_attempt_number(node):
    return node.get("accepted_attempt")


def accepted_attempt(node):
    number = accepted_attempt_number(node)
    if number is None:
        return None
    return attempt_record(node, number)


def next_attempt_number(node):
    records = node.get("attempts") or {}
    if not records:
        return 1
    return max(int(k) for k in records) + 1


def open_attempt(node, number, binding):
    """Register a new attempt in the phase node. Never overwrites one."""
    assert_attempt_number(number)
    records = node.setdefault("attempts", {})
    key = str(number)
    if key in records:
        raise AttemptError(
            "attempt %d already exists for this phase; an attempt is written "
            "once. Prepare the next attempt number instead." % number)
    record = {
        "attempt_number": number,
        "attempt_id": attempt_id(binding["audit_id"], binding["run_phase"],
                                 number),
        "state": "OPEN",
    }
    record.update(binding)
    records[key] = record
    node["attempt_number"] = number
    return record


def close_attempt(node, number, verdict, classification, seal,
                  seal_sha256, superseded=False):
    """Record the sealed outcome of an attempt. Called once per attempt."""
    record = attempt_record(node, number)
    if record is None:
        raise AttemptError("no attempt %d to close" % number)
    if record.get("state") == "SEALED":
        raise AttemptError(
            "attempt %d is already sealed; a sealed attempt is never "
            "re-closed, re-verdicted or re-classified" % number)
    record["state"] = "SEALED"
    record["verdict"] = verdict
    record["classification"] = classification
    record["sealed_at"] = seal.get("sealed_at")
    record["evidence_manifest_sha256"] = seal.get("manifest_sha256")
    record["evidence_file_count"] = seal.get("file_count")
    record["seal_sha256"] = seal_sha256
    record["usable"] = classification == "SUBSTANTIVE_AUDIT_RESULT"
    record["superseded"] = bool(superseded)
    if record["usable"]:
        node["accepted_attempt"] = number
    return record


def mark_superseded(node, number, by_number, root_cause_fingerprint,
                    repair_evidence_path):
    """Record why an attempt was superseded. The attempt itself is untouched.

    Only the phase's index of its own history is written here. The sealed
    attempt directory — its manifest, its seal, its stdout and stderr — is not
    opened for writing by this or any other function in the model.
    """
    record = attempt_record(node, number)
    if record is None:
        raise AttemptError("no attempt %d to supersede" % number)
    if record.get("state") != "SEALED":
        raise AttemptError(
            "attempt %d is not sealed; only a sealed attempt can be "
            "superseded" % number)
    record["superseded"] = True
    record["superseded_by"] = by_number
    record["superseded_root_cause_fingerprint"] = root_cause_fingerprint
    record["superseded_repair_evidence"] = repair_evidence_path
    return record


# --- immutability ----------------------------------------------------------
def verify_attempt_immutable(audit_id, run_phase, number):
    """Prove a sealed attempt is exactly the bytes it was sealed with.

    Returns (ok, differences). Reads only. A sealed attempt whose bytes moved
    is not repaired here and is not reported as a detail; it is the reason a
    retry is refused.
    """
    from . import evidence as evidence_module

    recorder = evidence_module.EvidenceRecorder(audit_id, run_phase,
                                                attempt=number)
    if not os.path.exists(recorder.seal_path):
        return False, [{"path": "SEAL.json", "reason": "NOT_SEALED"}]
    return recorder.verify_seal()


def seal_digest(audit_id, run_phase, number):
    from . import evidence as evidence_module

    recorder = evidence_module.EvidenceRecorder(audit_id, run_phase,
                                                attempt=number)
    return hashing.sha256_file(recorder.seal_path)


# --- retry admission -------------------------------------------------------
def assert_retry_admissible(node, prior_number, prior_classification,
                            new_plan_sha256, root_cause_fingerprint,
                            repair_evidence_path):
    """Every condition for a new attempt, each refused by name.

    Returns the next attempt number. Writes nothing and executes nothing.
    """
    prior = attempt_record(node, prior_number)
    if prior is None:
        raise AttemptError(
            "no attempt %r exists for this phase; a retry names the attempt "
            "it supersedes" % (prior_number,))

    if prior.get("state") != "SEALED":
        raise AttemptError(
            "attempt %d is %s, not SEALED. An unsealed attempt has no fixed "
            "evidence and nothing to supersede. Finalize it first."
            % (prior_number, prior.get("state")))

    recorded = prior.get("classification")
    if recorded != prior_classification:
        raise AttemptError(
            "the classification supplied (%r) is not the classification "
            "recorded when attempt %d was sealed (%r). The retry route does "
            "not reclassify a sealed attempt."
            % (prior_classification, prior_number, recorded))

    if prior.get("verdict") in SUBSTANTIVE_VERDICTS:
        raise AttemptError(
            "attempt %d sealed a substantive verdict (%s). A substantive "
            "result is a statement about the audited target, not a defect in "
            "this harness, and it seals the phase terminally. There is no "
            "retry route from it. If it is wrong, that is a matter for human "
            "review, not for another attempt."
            % (prior_number, prior.get("verdict")))

    if not is_retryable(recorded):
        raise AttemptError(
            "attempt %d is classified %s, which is not retryable. The "
            "retryable classifications are %r."
            % (prior_number, recorded, list(RETRYABLE_CLASSIFICATIONS)))

    if not root_cause_fingerprint or not isinstance(root_cause_fingerprint,
                                                    str):
        raise AttemptError(
            "a retry must name the root cause it repairs. Without a "
            "fingerprint the loop cannot tell a second repair of one cause "
            "from a first repair of another, and cannot stop repeating "
            "itself.")

    if not repair_evidence_path:
        raise AttemptError(
            "a retry must point at evidence that the cause was repaired. A "
            "repair asserted and not shown is not a repair.")
    if not os.path.exists(repair_evidence_path):
        raise AttemptError(
            "repair evidence does not exist: %s" % repair_evidence_path)

    if prior.get("plan_sha256") == new_plan_sha256:
        raise AttemptError(
            "the new plan is byte-identical to attempt %d's plan (%s). "
            "Re-running an unchanged plan against an unchanged target in an "
            "unchanged environment cannot produce a different answer; it can "
            "only produce the same failure with a later timestamp."
            % (prior_number, new_plan_sha256))

    prior_causes = [r.get("superseded_root_cause_fingerprint")
                    for r in attempt_records(node)]
    repeats = prior_causes.count(root_cause_fingerprint)
    if repeats >= policy.MAX_REPAIRS_PER_ROOT_CAUSE:
        raise AttemptError(
            "root cause %r has already survived %d tested repairs. "
            "MAX_REPAIRS_PER_ROOT_CAUSE=%d. "
            "STOP_REPEATED_IDENTICAL_REPAIR_FAILURE."
            % (root_cause_fingerprint, repeats,
               policy.MAX_REPAIRS_PER_ROOT_CAUSE))

    number = next_attempt_number(node)
    if number > policy.MAX_ATTEMPTS_PER_PHASE:
        raise AttemptError(
            "this phase has used all %d permitted attempts. "
            "MAX_ATTEMPTS_PER_PHASE is a ceiling, not a budget. A human must "
            "decide what happens next." % policy.MAX_ATTEMPTS_PER_PHASE)
    return number


def assert_external_material_supplied(classification, material_manifest):
    """A blocked phase resumes only on material a human actually supplied.

    `material_manifest` is a path to a manifest of the new material with its
    digests. It is required, it must exist, and it must be non-empty: a
    blocked phase that resumes on nothing is a blocked phase that was never
    unblocked.
    """
    if classification not in REQUIRES_EXTERNAL_MATERIAL:
        return None
    if not material_manifest:
        raise AttemptError(
            "attempt was classified %s. A retry requires --material-manifest "
            "naming the material a human supplied, with its digests. Repairing "
            "our own code cannot supply a reference that is absent."
            % classification)
    if not os.path.isfile(material_manifest):
        raise AttemptError(
            "material manifest does not exist: %s" % material_manifest)
    if os.path.getsize(material_manifest) == 0:
        raise AttemptError(
            "material manifest is empty: %s. Nothing was supplied."
            % material_manifest)
    return material_manifest


# --- comparison inputs -----------------------------------------------------
def comparison_inputs(progress, audit_id):
    """What COMPARISON is allowed to compare, and the history behind it.

    Returns the accepted RUN-A and RUN-B attempts together with every
    superseded attempt. The superseded ones are returned, not filtered out:
    a comparison that silently omits the attempts that failed reads as though
    they never happened.
    """
    out = {"audit_id": audit_id, "phases": {}, "usable": True}
    for phase in ("RUN-A", "RUN-B"):
        node = phase_node(progress, audit_id, phase)
        accepted = accepted_attempt(node)
        history = attempt_records(node)
        out["phases"][phase] = {
            "aggregate_state": node.get("state", "NOT_STARTED"),
            "accepted_attempt": accepted,
            "attempt_history": history,
            "superseded_attempts": [r for r in history if r.get("superseded")],
        }
        if accepted is None or node.get("state") != "SEALED":
            out["usable"] = False
    if not out["usable"]:
        out["refusal"] = (
            "COMPARISON requires an accepted, usable, sealed attempt for both "
            "RUN-A and RUN-B. Comparing a run against nothing is not a "
            "comparison.")
    return out


def history_summary(node):
    """A one-line-per-attempt account, superseded attempts included."""
    lines = []
    for record in attempt_records(node):
        lines.append({
            "attempt_number": record.get("attempt_number"),
            "attempt_id": record.get("attempt_id"),
            "state": record.get("state"),
            "verdict": record.get("verdict"),
            "classification": record.get("classification"),
            "usable": record.get("usable"),
            "superseded": record.get("superseded", False),
            "superseded_by": record.get("superseded_by"),
            "root_cause_fingerprint":
                record.get("superseded_root_cause_fingerprint"),
            "plan_sha256": record.get("plan_sha256"),
            "seal_sha256": record.get("seal_sha256"),
        })
    return lines


def write_attempt_index(audit_id, run_phase, node):
    """Publish the phase's attempt history beside its evidence.

    The index is written under the phase directory, never inside an attempt
    directory, so no sealed manifest is disturbed by writing it.
    """
    root = path_policy.ensure_dir(
        path_policy.audit_evidence_dir(audit_id, run_phase))
    path = path_policy.assert_writable(
        os.path.join(root, "ATTEMPT_INDEX.json"))
    payload = {
        "schema": "wpno.level1.attempt-index/1",
        "audit_id": audit_id,
        "run_phase": run_phase,
        "aggregate_state": node.get("state", "NOT_STARTED"),
        "current_attempt": current_attempt_number(node),
        "accepted_attempt": accepted_attempt_number(node),
        "attempts": history_summary(node),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path
