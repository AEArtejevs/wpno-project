"""The R7 phase-attempt model, and the R6 dead end it repairs.

R6 sealed L1-A31 RUN-A with verdict ERROR. The ERROR said nothing about the
audited target. It said that the approved plan asked OpenSSL to verify a
certificate for a purpose the certificate does not carry, at a validation time
outside its own control fixture's validity, against a mutation fixture that
could not be parsed. All three are defects in our own machinery. None of them
is a finding. And none of them could be corrected, because SEALED is terminal
and one phase was one attempt.

The repair separates the two. An attempt is still sealed exactly once and is
never edited again — that part is untouched, because the sealed ERROR is real
evidence and destroying it would be worse than the dead end. What changes is
that a phase whose attempt failed on us can host another attempt.

The whole risk of that change is that "retry" becomes "run it again until it
passes". These tests exist to hold that shut. In order:

  * the transitions the model adds, and only those;
  * a sealed attempt is immutable, and a retry built on moved bytes is refused;
  * a substantive FAIL is terminal and has no retry route, by name;
  * a blocked phase resumes only on material a human actually supplied;
  * attempts are bounded and the bound is a stop;
  * an approval is still one-time, across attempts as well as within one.

Runs only inside the isolated replica: it writes state/, results/ and
evidence/.
"""

import io
import json
import os
import shutil
import unittest

from automation import (attempts, controller, evidence, hashing, path_policy,
                        policy, state_machine)

AUDIT = "L1-A31"
PHASE = "RUN-A"

SANDBOX = os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest",
                       "attempts")


def _require_replica():
    if os.path.basename(path_policy.LEVEL1_ROOT) != "selftest_runtime":
        raise AssertionError(
            "these tests write controller state and must run only inside the "
            "isolated replica at verification/selftest_runtime; LEVEL1_ROOT "
            "is %s" % path_policy.LEVEL1_ROOT)


def _reset_state():
    for path in (controller.PROGRESS_PATH, controller.APPROVALS_PATH,
                 controller.TRANSITIONS_PATH):
        if os.path.exists(path):
            os.unlink(path)
    lock = os.path.join(controller.STATE_DIR, "controller.lock")
    if os.path.exists(lock):
        os.unlink(lock)
    for tree in ("results", "evidence", "work"):
        directory = os.path.join(path_policy.LEVEL1_ROOT, tree, AUDIT)
        if os.path.isdir(directory):
            shutil.rmtree(directory)
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)


def _plan_document(target_path, target_sha, scope, phase=PHASE):
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": AUDIT,
        "run_phase": phase,
        "scope": scope,
        "target": {"path": target_path, "sha256": target_sha,
                   "identity_evidence": "created by the attempt-model test"},
        "steps": [
            {"step_id": "S1", "operation": "SHA256_FILE",
             "params": {"path": target_path}, "purpose": "identity"},
            {"step_id": "S2", "operation": "OPENSSL_PARSE_CERT",
             "params": {"cert": target_path},
             "purpose": "a gated operation, so approval is required"},
        ],
        "test_matrix": [{"case": "identity"}],
    }


class _Args(object):
    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def _silently(fn, args):
    """Run a controller route, keeping its JSON out of the test output."""
    import sys
    out = io.StringIO()
    saved, sys.stdout = sys.stdout, out
    try:
        code = fn(args)
    finally:
        sys.stdout = saved
    return code, out.getvalue()


class AttemptCase(unittest.TestCase):
    """A phase driven through real attempts by the real controller routes."""

    def setUp(self):
        _require_replica()
        _reset_state()
        os.makedirs(SANDBOX, exist_ok=True)
        self.target = os.path.join(SANDBOX, "target.bin")
        with io.open(self.target, "wb") as fh:
            fh.write(b"target bytes for the attempt-model self-test\n")
        self.target_sha = hashing.sha256_file(self.target)
        self.repair_evidence = os.path.join(SANDBOX, "repair.json")
        with io.open(self.repair_evidence, "w", encoding="utf-8") as fh:
            fh.write('{"repaired": "the scope string"}\n')

    def tearDown(self):
        _reset_state()

    # -- helpers ----------------------------------------------------------
    def write_plan(self, attempt, scope):
        directory = path_policy.audit_attempt_results_dir(AUDIT, PHASE, attempt)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "plan.json")
        raw = json.dumps(_plan_document(self.target, self.target_sha, scope),
                         indent=2, sort_keys=True) + "\n"
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        return path, hashing.sha256_text(raw)

    def prepare_first(self, scope="attempt 1"):
        path, sha = self.write_plan(1, scope)
        _silently(controller.cmd_prepare_execution,
                  _Args(audit_id=AUDIT, run_phase=PHASE, plan_path=path,
                        target_path=self.target))
        return path, sha

    def approve(self, plan_sha):
        token = ("APPROVE-EXECUTION %s RUN=%s PLAN-SHA256=%s "
                 "TARGET-SHA256=%s RUN-ONCE"
                 % (AUDIT, PHASE, plan_sha, self.target_sha))
        _silently(controller.cmd_record_approval, _Args(token=token))
        return token

    def execute(self):
        _silently(controller.cmd_execute_approved,
                  _Args(audit_id=AUDIT, run_phase=PHASE))

    def finalize(self, verdict, classification=None):
        return _silently(
            controller.cmd_finalize_current,
            _Args(audit_id=AUDIT, run_phase=PHASE, verdict=verdict,
                  classification=classification, critical_finding_id=None))

    def run_attempt(self, attempt, scope, verdict, classification=None,
                    prior_attempt=None, fingerprint=None):
        if attempt == 1:
            path, sha = self.prepare_first(scope)
        else:
            path, sha = self.write_plan(attempt, scope)
            _silently(controller.cmd_prepare_retry, _Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE,
                                                     prior_attempt),
                prior_classification="INTERNAL_REPAIRABLE_DEFECT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint=fingerprint or ("cause/%d" % attempt),
                repair_evidence=self.repair_evidence,
                material_manifest=None))
        self.approve(sha)
        self.execute()
        self.finalize(verdict, classification)
        return path, sha

    def node(self):
        progress = controller._load_progress()
        return attempts.phase_node(progress, AUDIT, PHASE)

    def state(self):
        return controller._audit_state(controller._load_progress(),
                                       AUDIT, PHASE)


class TestAggregateTransitions(AttemptCase):
    """The states the model adds, and where each verdict actually lands."""

    def test_internal_error_leaves_the_phase_retryable_not_terminal(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        self.assertEqual(self.state(), "RETRYABLE_INTERNAL_ERROR")
        self.assertFalse(state_machine.is_terminal(self.state()))
        record = attempts.attempt_record(self.node(), 1)
        self.assertEqual(record["state"], "SEALED")
        self.assertEqual(record["verdict"], "ERROR")
        self.assertFalse(record["usable"])
        self.assertIsNone(attempts.accepted_attempt_number(self.node()))

    def test_this_is_exactly_the_r6_dead_end_that_is_now_open(self):
        """R6's own state machine had no exit from the sealed ERROR."""
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        # The attempt is sealed and stays sealed.
        ok, differences = attempts.verify_attempt_immutable(AUDIT, PHASE, 1)
        self.assertTrue(ok, differences)
        # The phase is not.
        self.assertIn("PLANNING",
                      state_machine.TRANSITIONS["RETRYABLE_INTERNAL_ERROR"])
        self.assertEqual(state_machine.TRANSITIONS["SEALED"], ())

    def test_pass_seals_the_phase_and_records_the_accepted_attempt(self):
        self.run_attempt(1, "attempt 1", "PASS")
        self.assertEqual(self.state(), "SEALED")
        self.assertTrue(state_machine.is_terminal(self.state()))
        self.assertEqual(attempts.accepted_attempt_number(self.node()), 1)
        self.assertTrue(attempts.attempt_record(self.node(), 1)["usable"])

    def test_blocked_moves_the_phase_to_await_external_material(self):
        self.run_attempt(1, "attempt 1", "BLOCKED",
                         "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT")
        self.assertEqual(self.state(), "BLOCKED_FOR_EXTERNAL_MATERIAL")
        self.assertFalse(state_machine.is_terminal(self.state()))

    def test_retry_returns_the_phase_to_the_approval_gate_not_past_it(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        path, _ = self.write_plan(2, "attempt 2, scope corrected")
        _silently(controller.cmd_prepare_retry, _Args(
            audit_id=AUDIT, run_phase=PHASE,
            prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
            prior_classification="INTERNAL_REPAIRABLE_DEFECT",
            plan_path=path, target_path=self.target,
            root_cause_fingerprint="selftest/scope",
            repair_evidence=self.repair_evidence, material_manifest=None))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertEqual(attempts.current_attempt_number(self.node()), 2)
        # prepare-retry recorded no approval of its own. Attempt 1's approval
        # is on record because attempt 1 was legitimately approved; what must
        # not exist is a second one that no human supplied.
        recorded = controller._recorded_approvals()
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["plan_sha256"],
                         attempts.attempt_record(self.node(), 1)["plan_sha256"])

    def test_the_full_two_attempt_history_is_kept_and_marked(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        self.run_attempt(2, "attempt 2, corrected", "PASS",
                         prior_attempt=1, fingerprint="selftest/scope")
        node = self.node()
        self.assertEqual(self.state(), "SEALED")
        self.assertEqual(attempts.accepted_attempt_number(node), 2)
        history = attempts.history_summary(node)
        self.assertEqual([h["attempt_number"] for h in history], [1, 2])
        self.assertTrue(history[0]["superseded"])
        self.assertEqual(history[0]["superseded_by"], 2)
        self.assertEqual(history[0]["root_cause_fingerprint"],
                         "selftest/scope")
        self.assertFalse(history[1]["superseded"])

    def test_superseded_attempts_are_not_hidden_from_comparison(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        self.run_attempt(2, "attempt 2, corrected", "PASS",
                         prior_attempt=1, fingerprint="selftest/scope")
        payload = attempts.comparison_inputs(controller._load_progress(),
                                             AUDIT)
        run_a = payload["phases"]["RUN-A"]
        self.assertEqual(run_a["accepted_attempt"]["attempt_number"], 2)
        self.assertEqual(
            [r["attempt_number"] for r in run_a["superseded_attempts"]], [1])

    def test_comparison_refuses_without_an_accepted_attempt_on_both_runs(self):
        self.run_attempt(1, "attempt 1", "PASS")
        payload = attempts.comparison_inputs(controller._load_progress(),
                                             AUDIT)
        self.assertFalse(payload["usable"])
        self.assertIn("Comparing a run against nothing", payload["refusal"])


class TestSubstantiveFailIsTerminal(AttemptCase):
    """The rule the whole model exists to keep: a FAIL is not a retry."""

    def test_fail_seals_the_phase(self):
        self.run_attempt(1, "attempt 1", "FAIL")
        self.assertEqual(self.state(), "SEALED")
        self.assertTrue(state_machine.is_terminal(self.state()))

    def test_retry_after_a_fail_is_refused_by_name(self):
        self.run_attempt(1, "attempt 1", "FAIL")
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
                prior_classification="SUBSTANTIVE_AUDIT_RESULT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/whatever",
                repair_evidence=self.repair_evidence, material_manifest=None))
        message = str(ctx.exception)
        self.assertIn("SEALED", message)
        self.assertEqual(self.state(), "SEALED")

    def test_a_fail_cannot_be_relabelled_as_a_harness_defect(self):
        self.prepare_first()
        _, sha = self.write_plan(1, "attempt 1")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller._classification_for("FAIL",
                                           "INTERNAL_REPAIRABLE_DEFECT")
        self.assertIn("statement about the audited target",
                      str(ctx.exception))

    def test_every_substantive_verdict_is_refused_a_defect_label(self):
        for verdict in attempts.SUBSTANTIVE_VERDICTS:
            with self.assertRaises(controller.ControllerError):
                controller._classification_for(verdict,
                                               "INTERNAL_REPAIRABLE_DEFECT")

    def test_an_error_cannot_be_relabelled_as_a_substantive_result(self):
        with self.assertRaises(attempts.AttemptError):
            attempts.assert_classification("ERROR", "SUBSTANTIVE_AUDIT_RESULT")

    def test_a_nonsubstantive_verdict_requires_an_explicit_classification(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            controller._classification_for("ERROR", None)
        self.assertIn("--classification", str(ctx.exception))


class TestSealedAttemptImmutability(AttemptCase):
    """A sealed attempt is evidence. Nothing may be built on moved bytes."""

    def test_a_sealed_attempt_verifies_against_its_own_manifest(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        ok, differences = attempts.verify_attempt_immutable(AUDIT, PHASE, 1)
        self.assertTrue(ok, differences)

    def test_a_second_seal_of_the_same_attempt_is_refused(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        recorder = evidence.EvidenceRecorder(AUDIT, PHASE, attempt=1)
        with self.assertRaises(evidence.EvidenceError):
            recorder.seal("PASS")

    def test_recording_into_a_sealed_attempt_is_refused(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        recorder = evidence.EvidenceRecorder(AUDIT, PHASE, attempt=1)
        with self.assertRaises(evidence.EvidenceError):
            recorder.record_operation(
                operation="SHA256_FILE", argv=["/usr/bin/true"], exit_code=0,
                stdout=b"", stderr=b"", timeout_seconds=1,
                output_limit_bytes=1024, started=0.0, finished=1.0)

    def test_retry_is_refused_when_the_sealed_evidence_moved(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        sealed = path_policy.audit_attempt_evidence_dir(AUDIT, PHASE, 1)
        victim = os.path.join(sealed, "commands.jsonl")
        with io.open(victim, "a", encoding="utf-8") as fh:
            fh.write('{"tampered": true}\n')
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
                prior_classification="INTERNAL_REPAIRABLE_DEFECT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/scope",
                repair_evidence=self.repair_evidence, material_manifest=None))
        self.assertIn("does not verify", str(ctx.exception))

    def test_a_retry_does_not_touch_the_attempt_it_supersedes(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        sealed = path_policy.audit_attempt_evidence_dir(AUDIT, PHASE, 1)
        before = {}
        for dirpath, _, names in os.walk(sealed):
            for name in sorted(names):
                full = os.path.join(dirpath, name)
                before[os.path.relpath(full, sealed)] = hashing.sha256_file(full)
        self.run_attempt(2, "attempt 2, corrected", "PASS",
                         prior_attempt=1, fingerprint="selftest/scope")
        after = {}
        for dirpath, _, names in os.walk(sealed):
            for name in sorted(names):
                full = os.path.join(dirpath, name)
                after[os.path.relpath(full, sealed)] = hashing.sha256_file(full)
        self.assertEqual(before, after)

    def test_two_attempts_do_not_share_an_evidence_id(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        self.run_attempt(2, "attempt 2, corrected", "PASS",
                         prior_attempt=1, fingerprint="selftest/scope")
        ids = []
        for number in (1, 2):
            directory = path_policy.audit_attempt_evidence_dir(AUDIT, PHASE,
                                                               number)
            with io.open(os.path.join(directory, "commands.jsonl"),
                         encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        ids.append(json.loads(line)["evidence_id"])
        self.assertEqual(len(ids), len(set(ids)),
                         "two attempts produced the same evidence id")


class TestRetryAdmission(AttemptCase):
    """Every reason a retry is refused, each refused by name."""

    def setUp(self):
        AttemptCase.setUp(self)
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")

    def retry(self, **overrides):
        kw = dict(audit_id=AUDIT, run_phase=PHASE,
                  prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
                  prior_classification="INTERNAL_REPAIRABLE_DEFECT",
                  plan_path=None, target_path=self.target,
                  root_cause_fingerprint="selftest/scope",
                  repair_evidence=self.repair_evidence,
                  material_manifest=None)
        kw.update(overrides)
        return controller.cmd_prepare_retry(_Args(**kw))

    def test_an_identical_plan_is_refused(self):
        path, _ = self.write_plan(2, "attempt 1")   # same scope, same bytes
        with self.assertRaises(controller.ControllerError) as ctx:
            self.retry(plan_path=path)
        self.assertIn("byte-identical", str(ctx.exception))

    def test_a_missing_root_cause_fingerprint_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.retry(plan_path=path, root_cause_fingerprint="")
        self.assertIn("root cause", str(ctx.exception))

    def test_absent_repair_evidence_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        missing = os.path.join(SANDBOX, "not_here.json")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.retry(plan_path=path, repair_evidence=missing)
        self.assertIn("repair evidence", str(ctx.exception))

    def test_a_classification_that_was_not_recorded_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.retry(plan_path=path,
                       prior_classification="CONTROL_PLANE_INTEGRITY_FAILURE")
        self.assertIn("not the classification recorded", str(ctx.exception))

    def test_another_phases_attempt_id_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.retry(plan_path=path,
                       prior_attempt_id="L1-A34/RUN-A/attempt-1")
        self.assertIn("does not belong to", str(ctx.exception))

    def test_a_control_plane_integrity_failure_is_not_retryable(self):
        self.assertFalse(
            attempts.is_retryable("CONTROL_PLANE_INTEGRITY_FAILURE"))
        self.assertEqual(
            attempts.aggregate_state_for("CONTROL_PLANE_INTEGRITY_FAILURE"),
            "HALT_CRITICAL")


class TestExternalMaterialResumption(AttemptCase):
    """A blocked phase resumes on supplied material, and on nothing else."""

    def setUp(self):
        AttemptCase.setUp(self)
        self.run_attempt(1, "attempt 1", "BLOCKED",
                         "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT")

    def test_retry_without_a_material_manifest_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
                prior_classification=
                    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/missing-ref",
                repair_evidence=self.repair_evidence, material_manifest=None))
        self.assertIn("--material-manifest", str(ctx.exception))
        self.assertEqual(self.state(), "BLOCKED_FOR_EXTERNAL_MATERIAL")

    def test_an_empty_material_manifest_is_refused(self):
        path, _ = self.write_plan(2, "attempt 2")
        empty = os.path.join(SANDBOX, "empty.sha256")
        with io.open(empty, "wb") as fh:
            fh.write(b"")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
                prior_classification=
                    "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/missing-ref",
                repair_evidence=self.repair_evidence,
                material_manifest=empty))
        self.assertIn("Nothing was supplied", str(ctx.exception))

    def test_supplied_material_reopens_the_phase_at_the_approval_gate(self):
        path, _ = self.write_plan(2, "attempt 2, with the reference")
        manifest = os.path.join(SANDBOX, "material.sha256")
        with io.open(manifest, "w", encoding="utf-8") as fh:
            fh.write("%s  REF-10.crl\n" % ("0" * 64))
        _silently(controller.cmd_prepare_retry, _Args(
            audit_id=AUDIT, run_phase=PHASE,
            prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
            prior_classification=
                "MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT",
            plan_path=path, target_path=self.target,
            root_cause_fingerprint="selftest/missing-ref",
            repair_evidence=self.repair_evidence,
            material_manifest=manifest))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertEqual(attempts.current_attempt_number(self.node()), 2)
        # Only attempt 1's approval exists; unblocking did not approve.
        self.assertEqual(len(controller._recorded_approvals()), 1)


class TestAttemptLimits(AttemptCase):
    """Ceilings, not budgets."""

    def test_the_ceiling_is_three_and_it_is_a_stop(self):
        self.assertEqual(policy.MAX_ATTEMPTS_PER_PHASE, 3)
        for number in (1, 2, 3):
            self.run_attempt(number, "attempt %d" % number, "ERROR",
                             "INTERNAL_REPAIRABLE_DEFECT",
                             prior_attempt=number - 1 or None,
                             fingerprint="selftest/cause-%d" % number)
        path, _ = self.write_plan(3, "attempt 4")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 3),
                prior_classification="INTERNAL_REPAIRABLE_DEFECT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/cause-4",
                repair_evidence=self.repair_evidence, material_manifest=None))
        message = str(ctx.exception)
        self.assertIn("all 3 permitted attempts", message)
        self.assertIn("ceiling, not a budget", message)

    def test_one_root_cause_may_not_be_repaired_indefinitely(self):
        """Two tested repairs of one cause, and the loop stops naming it.

        The distinction this test holds is between running out of attempts and
        failing to converge. Both end the phase, but they say different things
        and the message has to say the right one: three attempts against three
        different causes is a hard problem, three attempts against one cause is
        a repair that is not working.
        """
        self.assertEqual(policy.MAX_REPAIRS_PER_ROOT_CAUSE, 2)
        for number in (1, 2, 3):
            self.run_attempt(number, "attempt %d" % number, "ERROR",
                             "INTERNAL_REPAIRABLE_DEFECT",
                             prior_attempt=number - 1 or None,
                             fingerprint="selftest/same-cause")
        path, _ = self.write_plan(3, "attempt 4, same cause again")
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_prepare_retry(_Args(
                audit_id=AUDIT, run_phase=PHASE,
                prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 3),
                prior_classification="INTERNAL_REPAIRABLE_DEFECT",
                plan_path=path, target_path=self.target,
                root_cause_fingerprint="selftest/same-cause",
                repair_evidence=self.repair_evidence, material_manifest=None))
        message = str(ctx.exception)
        self.assertIn("STOP_REPEATED_IDENTICAL_REPAIR_FAILURE", message)
        self.assertIn("selftest/same-cause", message)
        # The repeated-cause rule is checked before the attempt ceiling, so
        # the message says why it is not converging rather than merely that it
        # ran out of tries.
        self.assertNotIn("ceiling, not a budget", message)

    def test_an_attempt_number_above_the_ceiling_is_rejected_outright(self):
        with self.assertRaises(attempts.AttemptError):
            attempts.assert_attempt_number(policy.MAX_ATTEMPTS_PER_PHASE + 1)
        with self.assertRaises(attempts.AttemptError):
            attempts.assert_attempt_number(0)

    def test_there_is_no_revision_after_the_final_one(self):
        """The finality rule, stated as a rule rather than as a revision name.

        This asserted `FINAL_REVISION == "R7"`. That was true when it was
        written and it stopped being true when the human authorised R8, and
        the test then failed for the one reason a test must never fail: the
        thing it names changed while the property it was protecting did not.

        The property is that the package declares exactly one final revision
        and grants itself no budget to escalate past it. R7 escalated once,
        and the escalation was a human decision recorded in `policy` -- one,
        not unlimited. So the assertions below are about the shape of the
        rule: the final revision is the last of the chain, every superseded
        revision precedes it, and the budget after the final revision is
        zero.
        """
        self.assertEqual(policy.FINAL_REVISION, "R8")
        self.assertEqual(policy.MAX_REVISION_ESCALATIONS_AFTER_R8, 0)
        # R7 escalated exactly once, by human authorisation, and the budget
        # records that as one rather than as an open door.
        self.assertEqual(policy.MAX_REVISION_ESCALATIONS_AFTER_R7, 1)
        # The final revision is not among the superseded ones, and every
        # superseded revision precedes it.
        self.assertNotIn(policy.FINAL_REVISION, policy.SUPERSEDED_REVISIONS)
        self.assertEqual(policy.SUPERSEDED_REVISIONS,
                         ("R4", "R5", "R6", "R7"))
        ordinal = int(policy.FINAL_REVISION[1:])
        for name in policy.SUPERSEDED_REVISIONS:
            self.assertLess(int(name[1:]), ordinal)

        # The "no successor exists on disk" half of the finality rule is
        # asserted in the package suite, which runs at the real package root.
        # This suite runs inside the isolated replica at
        # verification/selftest_runtime, whose siblings are the replica's own
        # roots, so a filesystem check here would pass by looking at the
        # wrong directory -- which is the shape of a check that measures
        # something other than what it names.


class TestApprovalIsStillOneTime(AttemptCase):
    """Replay protection survives the introduction of attempts."""

    def test_the_same_token_cannot_approve_twice(self):
        _, sha = self.prepare_first()
        token = self.approve(sha)
        self.execute()
        self.finalize("ERROR", "INTERNAL_REPAIRABLE_DEFECT")
        path, _ = self.write_plan(2, "attempt 2, corrected")
        _silently(controller.cmd_prepare_retry, _Args(
            audit_id=AUDIT, run_phase=PHASE,
            prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
            prior_classification="INTERNAL_REPAIRABLE_DEFECT",
            plan_path=path, target_path=self.target,
            root_cause_fingerprint="selftest/scope",
            repair_evidence=self.repair_evidence, material_manifest=None))
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_record_approval(_Args(token=token))
        self.assertIn("replay", str(ctx.exception))

    def test_each_attempt_needs_its_own_token(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        path, sha2 = self.write_plan(2, "attempt 2, corrected")
        _silently(controller.cmd_prepare_retry, _Args(
            audit_id=AUDIT, run_phase=PHASE,
            prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
            prior_classification="INTERNAL_REPAIRABLE_DEFECT",
            plan_path=path, target_path=self.target,
            root_cause_fingerprint="selftest/scope",
            repair_evidence=self.repair_evidence, material_manifest=None))
        approvals_before = len(controller._recorded_approvals())
        self.approve(sha2)
        self.assertEqual(len(controller._recorded_approvals()),
                         approvals_before + 1)
        first = controller._recorded_approvals()[0]["plan_sha256"]
        self.assertNotEqual(first, sha2,
                            "the two attempts share a plan hash")

    def test_execution_still_requires_approval_after_a_retry(self):
        self.run_attempt(1, "attempt 1", "ERROR",
                         "INTERNAL_REPAIRABLE_DEFECT")
        path, _ = self.write_plan(2, "attempt 2, corrected")
        _silently(controller.cmd_prepare_retry, _Args(
            audit_id=AUDIT, run_phase=PHASE,
            prior_attempt_id=attempts.attempt_id(AUDIT, PHASE, 1),
            prior_classification="INTERNAL_REPAIRABLE_DEFECT",
            plan_path=path, target_path=self.target,
            root_cause_fingerprint="selftest/scope",
            repair_evidence=self.repair_evidence, material_manifest=None))
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_execute_approved(
                _Args(audit_id=AUDIT, run_phase=PHASE))
        self.assertIn("requires APPROVED", str(ctx.exception))


class TestNoBypassWasIntroduced(unittest.TestCase):
    """The new routes did not bring a new way around the gate."""

    def test_the_retry_route_has_no_bypass_option(self):
        rendered = controller.build_parser().format_help()
        for forbidden in policy.FORBIDDEN_CLI_OPTIONS:
            self.assertNotIn(forbidden, rendered)
        self.assertIn("prepare-retry", rendered)

    def test_the_retry_route_takes_no_token_and_no_verdict(self):
        parser = controller.build_parser()
        args = parser.parse_args([
            "prepare-retry", "--audit-id", AUDIT, "--run-phase", PHASE,
            "--prior-attempt-id", "L1-A31/RUN-A/attempt-1",
            "--prior-classification", "INTERNAL_REPAIRABLE_DEFECT",
            "--plan-path", "/x", "--target-path", "/y",
            "--root-cause-fingerprint", "c", "--repair-evidence", "/z"])
        self.assertFalse(hasattr(args, "token"))
        self.assertFalse(hasattr(args, "verdict"))

    def test_state_and_transition_tables_stayed_total(self):
        self.assertEqual(set(state_machine.STATES),
                         set(state_machine.TRANSITIONS))
        for terminal in state_machine.TERMINAL:
            self.assertEqual(state_machine.TRANSITIONS[terminal], ())
        for retryable in state_machine.RETRYABLE_AGGREGATE_STATES:
            self.assertNotIn(retryable, state_machine.TERMINAL)
            self.assertEqual(state_machine.TRANSITIONS[retryable],
                             ("PLANNING",))


if __name__ == "__main__":
    unittest.main()
