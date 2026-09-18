"""Shared machinery for building the R7 candidate execution plans.

The nine plans R7 already had were written one at a time, each as its own
block of code. That was right for three audits and would be wrong for
thirty-five: the same envelope repeated thirty-five times is thirty-five
places for it to drift, which is the defect CLAUDE.md section 10 records last.

So the shape is split in two. This module holds everything every plan has in
common - path resolution, reference binding, the binding envelope, the
comparison-phase plan, and the assembly and validation step. The specification
module holds only what differs between audits, as data.

Three rules the assembler enforces rather than trusts.

  Every bound path is hashed from disk at build time. A plan that names a file
  which is absent, or whose bytes have moved, is refused here rather than
  discovered under an approved token.

  Every operation is checked against the catalogue, and every step's argv is
  built with the same builder the controller uses. An operation the catalogue
  does not know, or parameters it will not accept, fails the build.

  Every plan is validated against the execution-plan schema. The schema is not
  extended for this work: what the schema does not carry at the top level -
  references, limitations, human decisions, allowed and forbidden reads,
  approval binding, retry classification - is carried in `test_matrix`, which
  is where the nine existing plans already carry theirs.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation import (hashing, in_process_executor,  # noqa: E402
                        operation_catalog, path_policy, schema_validation)

import control_expectations                                    # noqa: E402

# The roles whose steps must carry a machine-checkable expectation. ORACLE is
# included: an oracle that returned nothing usable is an infrastructure
# failure and has to be distinguishable from one that measured and
# disagreed.
CONTROL_ROLES = ("POSITIVE", "NEGATIVE", "MUTATION", "SABOTAGE", "ORACLE")

PROJECT_ROOT = path_policy.PROJECT_ROOT
LEVEL1_ROOT = path_policy.LEVEL1_ROOT
OUT = os.path.join(ROOT, "build", "candidate_plans_r8")
REFERENCES = os.path.join(ROOT, "references")

# Where a phase writes. Never the control plane, never another phase's area.
def work(audit_id, run_phase, *parts):
    return os.path.join(ROOT, "work", audit_id, run_phase, *parts)


def rehearsal_fixture(*parts):
    """Synthetic material built for rehearsal only, never source evidence."""
    return os.path.join(ROOT, "work", "_rehearsal_r8", "fixtures", *parts)


def pkg(*parts):
    return os.path.join(LEVEL1_ROOT, *parts)


def proj(*parts):
    return os.path.join(PROJECT_ROOT, *parts)


def ref(name):
    return os.path.join(REFERENCES, name)


class PlanBuildError(Exception):
    pass


def sha_of(path):
    if not os.path.isfile(path):
        raise PlanBuildError("bound artefact is absent: %s" % path)
    if os.path.islink(path):
        raise PlanBuildError("bound artefact is a symlink: %s" % path)
    if os.path.getsize(path) == 0:
        raise PlanBuildError("bound artefact is zero bytes: %s" % path)
    return hashing.sha256_file(path)


def bind(paths):
    """Bind a list of paths to the digests they have on disk right now."""
    return [{"path": p, "sha256": sha_of(p)} for p in paths]


def reference_manifest_records():
    with open(os.path.join(REFERENCES, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------- envelope
#
# One test_matrix entry carrying everything the schema does not hold at the
# top level. It is a check with a check_id like any other, so nothing has to
# treat it specially, and it is first so a reader meets the bindings before
# the expectations that rest on them.

def binding_envelope(audit_id, run_phase, *, method, executable,
                     references=(), reference_ids=(), limitations=(),
                     human_decisions=(), validation_time=None,
                     trust_mode=None, allowed_reads=(), allowed_writes=(),
                     forbidden_reads=(), forbidden_operations=(),
                     retry_classification=None,
                     substantive_failure_classification=None,
                     comparison_inputs=None, independent_oracle=None,
                     target_identification_rule=None, notes=()):
    return {
        "check_id": "PLAN_BINDING",
        "question": ("What is this phase bound to, and what may it read, "
                     "write and run?"),
        "revision": "R8",
        "audit_id": audit_id,
        "run_phase": run_phase,
        "plan_schema": "wpno.level1.execution_plan/1",
        "candidate_template_identity": "%s/%s/plan.json" % (audit_id, run_phase),
        "attempt_model": ("Attempt numbers are assigned by the controller at "
                          "preparation. This candidate binds no attempt "
                          "number: a plan that named one would be claiming a "
                          "history it does not have."),
        "method": method,
        "executable": executable,
        "fixed_cwd": LEVEL1_ROOT,
        "environment": ("automation.policy.base_environment(); no inherited "
                        "environment, no PYTHONPATH, no user site directory"),
        "output_limit": "automation.policy.MAX_OUTPUT_BYTES",
        "operation_catalogue": ("automation.operation_catalog; every operation "
                                "below is classified there and its argv is "
                                "built by operation_catalog.build_argv"),
        "reference_ids": list(reference_ids),
        "references": list(references),
        "limitations": list(limitations),
        "human_decisions": list(human_decisions),
        "validation_time": validation_time,
        "trust_mode": trust_mode,
        "independent_oracle": independent_oracle,
        "target_identification_rule": target_identification_rule,
        "allowed_reads": list(allowed_reads),
        "allowed_writes": list(allowed_writes),
        "forbidden_reads": list(forbidden_reads),
        "forbidden_operations": list(forbidden_operations)
            or sorted(operation_catalog.FORBIDDEN),
        "evidence_paths": {
            "attempt_evidence_dir":
                "evidence/%s/%s/attempt-<n>/" % (audit_id, run_phase),
            "commands": "commands.jsonl",
            "stdout": "stdout/", "stderr": "stderr/",
            "manifest": "EVIDENCE_MANIFEST.sha256", "seal": "SEAL.json",
        },
        "evidence_sealing": ("Every operation's complete stdout and stderr are "
                             "written to disk, manifested and sealed. A report "
                             "excerpt is marked as an excerpt and points at "
                             "the complete file."),
        "source_hash_before_and_after": (
            "The controller hashes the target before the first operation and "
            "after the last. A change in either direction is CONTAMINATED and "
            "no result is sealed."),
        "approval_token_binding": {
            "format": ("APPROVE-EXECUTION %s RUN=%s PLAN-SHA256=<64_HEX> "
                       "TARGET-SHA256=<64_HEX> RUN-ONCE"
                       % (audit_id, run_phase)),
            "one_time": True,
            "void_on_plan_change": True,
            "void_on_target_change": True,
            "recorded_never_reproduced_in_a_report": True,
        },
        "retry_classification": retry_classification or (
            "A failed attempt is superseded, never overwritten. A retry needs "
            "a fresh token, a fresh plan digest and a root-cause fingerprint "
            "that differs from the attempt it supersedes."),
        "substantive_failure_classification": (
            substantive_failure_classification or
            "A substantive failure is a finding about the target and is "
            "sealed as one. An infrastructure failure is a defect in this "
            "plan or harness and is classified ERROR, never reported as a "
            "finding about the target."),
        "comparison_inputs": comparison_inputs,
        "expectation_classes": {
            "SUBSTANTIVE_EXPECTATION": (
                "What the target is expected to do. Its outcome is the "
                "audit's finding and is not predetermined here."),
            "INFRASTRUCTURE_EXPECTATION": (
                "What the harness must do for the measurement to mean "
                "anything. Failure here is ERROR, not a finding."),
            "NEGATIVE_CONTROL_EXPECTATION": (
                "A case that must fail, for a stated reason. A nonzero exit "
                "alone is not the oracle: the reason is asserted too."),
            "MUTATION_CONTROL_EXPECTATION": (
                "A deliberate change that must change the answer. Zero "
                "changed results is a measurement error, not a pass."),
        },
        "notes": list(notes),
    }


# ------------------------------------------------------------ comparison
#
# The three existing COMPARISON plans are identical in shape. That shape is
# produced here rather than copied, so all four dual-method audits get the
# same one.

def comparison_plan(audit_id, target, *, run_a_method, run_b_method,
                    what_is_compared, references=(), reference_ids=(),
                    limitations=()):
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit_id,
        "run_phase": "COMPARISON",
        "scope": (
            "Compare the sealed RUN-A and RUN-B results for %s. The comparison "
            "reads sealed attempt evidence and computes nothing substantive "
            "itself: a comparison that recomputed an answer would be a third "
            "run, and a disagreement with it would be unattributable."
            % audit_id),
        "static_analysis": (
            "RUN-A method: %s. RUN-B method: %s. The two are different "
            "expressions of the same question, in different code, so a defect "
            "in one does not reproduce itself in the other. This phase reads "
            "only what those phases sealed, by their attempt manifests, and "
            "refuses to compare a phase whose seal does not verify."
            % (run_a_method, run_b_method)),
        "target": target,
        "steps": [
            {"step_id": "collect_accepted_attempts",
             "operation": "PARSE_JSON_READONLY",
             "control_role": "MEASUREMENT",
             "purpose": ("Read the attempt index of both phases and select the "
                         "accepted attempt of each. A superseded attempt is "
                         "listed and not compared."),
             "params": {"path": os.path.join(ROOT, "state", "progress.json")},
             "timeout_seconds": 120},
            {"step_id": "compare_run_a_seal",
             "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the RUN-A seal that is being compared.",
             "params": {"path": os.path.join(
                 ROOT, "evidence", audit_id, "RUN-A", "SEAL.json")},
             "timeout_seconds": 120},
            {"step_id": "compare_run_b_seal",
             "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the RUN-B seal that is being compared.",
             "params": {"path": os.path.join(
                 ROOT, "evidence", audit_id, "RUN-B", "SEAL.json")},
             "timeout_seconds": 120},
        ],
        "test_matrix": [
            binding_envelope(
                audit_id, "COMPARISON",
                method="read two sealed attempts and compare their recorded answers",
                executable="none; every step is in-process",
                references=references, reference_ids=reference_ids,
                limitations=limitations,
                comparison_inputs={
                    "run_a": "evidence/%s/RUN-A/attempt-<n>/" % audit_id,
                    "run_b": "evidence/%s/RUN-B/attempt-<n>/" % audit_id,
                    "selection": "the accepted attempt of each phase",
                },
                independent_oracle=(
                    "Neither run. The comparison's oracle is agreement itself: "
                    "two independent methods answering the same inputs."),
                allowed_reads=["state/progress.json",
                               "evidence/%s/RUN-A/" % audit_id,
                               "evidence/%s/RUN-B/" % audit_id],
                allowed_writes=["evidence/%s/COMPARISON/attempt-<n>/" % audit_id],
                forbidden_reads=["any unsealed or superseded attempt"],
                notes=["What is compared: %s" % what_is_compared]),
            {"check_id": "compared",
             "question": "Do the two independent methods agree, input by input?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "compared": what_is_compared,
             "required_result": ("Agreement is reported per input, not as a "
                                 "single score. The counts of agreement and "
                                 "disagreement are both reported."),
             "why": ("Two methods that agree corroborate each other. Two that "
                     "disagree locate a defect in one of them, and which one "
                     "is a further question this phase does not decide.")},
            {"check_id": "disagreement",
             "question": "What happens when the two runs disagree?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("A disagreement is a finding and is sealed as "
                                 "one. It is never resolved by preferring the "
                                 "run whose answer is more convenient."),
             "verdict_effect": "A disagreement forbids PASS for this audit."},
            {"check_id": "refusal",
             "question": "What does this phase refuse to do?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "refusal": ("It refuses to compare when either phase has no "
                         "accepted sealed attempt, when either seal does not "
                         "verify against its own manifest, or when the two "
                         "phases were bound to different targets."),
             "superseded_attempts": ("listed in the evidence and excluded from "
                                     "the comparison")},
        ],
    }


# -------------------------------------------------------------- assembly

def apply_control_expectations(plan):
    """Attach each control step's adjudicated expectation to its matrix entry.

    The expectations live in `control_expectations`, in one table, with the
    reading of each step recorded beside it. They are merged in here rather
    than written into thirty-five specification blocks, for the reason the
    module docstring above gives: the same envelope repeated thirty-five
    times is thirty-five places for it to drift.

    A step that already declares an expectation keeps it. The table adds; it
    does not overwrite, so an expectation a specification author wrote by
    hand cannot be silently replaced by one from a table.
    """
    entries = {entry["step_id"]: entry for entry in plan["test_matrix"]
               if isinstance(entry, dict) and "step_id" in entry}
    applied = []
    for step in plan["steps"]:
        if step.get("control_role") not in CONTROL_ROLES:
            continue
        extra = control_expectations.for_step(
            plan["audit_id"], plan["run_phase"], step["step_id"])
        if not extra:
            continue
        entry = entries.get(step["step_id"])
        if entry is None:
            entry = {"check_id": "control_expectation_%s" % step["step_id"],
                     "step_id": step["step_id"],
                     "question": ("What must this control step do for its "
                                  "measurement to count?"),
                     "expectation_class": "INFRASTRUCTURE_EXPECTATION"}
            plan["test_matrix"].append(entry)
            entries[step["step_id"]] = entry
        for key, value in extra.items():
            entry.setdefault(key, value)
        entry.setdefault("expectation_source",
                         "build/control_expectations.py")
        applied.append(step["step_id"])
    return applied


def assert_controls_are_enforced(plan):
    """Refuse a plan whose control steps carry no checkable expectation.

    R7's harness scored a step `ok` when it exited 0 and no expectation was
    stated, which is the wrong polarity for a control built to fail and says
    nothing at all about a control built to find nothing. A control with no
    expectation is not a lenient control; it is not a control.
    """
    entries = {entry["step_id"]: entry for entry in plan["test_matrix"]
               if isinstance(entry, dict) and "step_id" in entry}
    unenforced = []
    inapplicable = []
    for step in plan["steps"]:
        role = step.get("control_role")
        if role not in CONTROL_ROLES:
            continue
        entry = entries.get(step["step_id"])
        declared = in_process_executor.expectation_keys_present(entry)
        if not declared:
            unenforced.append(step["step_id"])
            continue
        if step["operation"] in operation_catalog.IN_PROCESS:
            for key in declared:
                if not in_process_executor.expectation_is_applicable(
                        step["operation"], key):
                    inapplicable.append("%s/%s" % (step["step_id"], key))
    if unenforced:
        raise PlanBuildError(
            "%s/%s: control steps with no machine-checkable expectation: %s"
            % (plan["audit_id"], plan["run_phase"], sorted(unenforced)))
    if inapplicable:
        raise PlanBuildError(
            "%s/%s: expectations that the operation cannot answer: %s"
            % (plan["audit_id"], plan["run_phase"], sorted(inapplicable)))
    return True


def assemble(plan, *, allow_unbuildable_argv=()):
    """Validate one plan completely, or refuse it.

    `allow_unbuildable_argv` names step ids whose argv cannot be built at
    build time because the operation is operator-performed on another host.
    Naming them is deliberate: an operation that silently failed to produce an
    argv would look the same as one that was never checked.
    """
    apply_control_expectations(plan)
    schema_validation.validate_named(plan, "execution_plan.schema.json")
    operation_catalog.validate_plan_operations(plan)
    assert_controls_are_enforced(plan)

    # Every IN_PROCESS operation a plan binds must have a handler and a
    # schema. R7 catalogued sixteen and implemented none, and nothing
    # compared the two lists.
    bound = {step["operation"] for step in plan["steps"]
             if step["operation"] in operation_catalog.IN_PROCESS}
    check = in_process_executor.self_check()
    missing = sorted(bound.intersection(check["catalogued_without_handler"]))
    if missing:
        raise PlanBuildError(
            "%s/%s binds IN_PROCESS operations with no handler: %s"
            % (plan["audit_id"], plan["run_phase"], missing))

    seen = set()
    for step in plan["steps"]:
        if step["step_id"] in seen:
            raise PlanBuildError("duplicate step_id %r in %s/%s"
                                 % (step["step_id"], plan["audit_id"],
                                    plan["run_phase"]))
        seen.add(step["step_id"])

        name = step["operation"]
        if name in operation_catalog.IN_PROCESS:
            continue
        if name in operation_catalog.OPERATOR_PERFORMED:
            if step["step_id"] not in allow_unbuildable_argv:
                raise PlanBuildError(
                    "%s/%s step %r uses operator-performed operation %s but is "
                    "not declared as such"
                    % (plan["audit_id"], plan["run_phase"], step["step_id"],
                       name))
            continue
        operation_catalog.build_argv(name, step.get("params", {}))
    return plan


def write_plan(plan, allow_unbuildable_argv=()):
    assemble(plan, allow_unbuildable_argv=allow_unbuildable_argv)
    directory = os.path.join(OUT, plan["audit_id"], plan["run_phase"])
    path_policy.ensure_dir(directory)
    path = os.path.join(directory, "plan.json")
    text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(path), "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashing.sha256_text(text)
    with open(path_policy.assert_writable(path + ".sha256"), "w",
              encoding="utf-8") as fh:
        fh.write("%s  plan.json\n" % digest)
    return {"path": os.path.relpath(path, ROOT), "sha256": digest}
