"""The controller-owned preparation route, and the R3 defect it repairs.

R3 shipped a state machine that permitted

    NOT_STARTED -> PLANNING -> PLAN_READY -> AWAITING_APPROVAL -> APPROVED

and a public CLI that could perform only the last of those four transitions.
A correctly formed, correctly bound six-field approval token was therefore
refused from NOT_STARTED, and the audit could not be started at all.

These tests hold both halves of the repair in place. The defect must still
reproduce against the unmodified R3 sources, which are shipped beside this
file as a fixture; the R4 route must reach AWAITING_APPROVAL and stop there;
and every control that stood between a plan and an execution before must still
stand, including the ones the new route now has to satisfy for itself.

Everything here runs inside the isolated replica the verification prompt
builds under `verification/selftest_runtime/`. The module refuses to run
anywhere else, because it writes to `state/` and `results/`, and doing that to
a real package would destroy the record it is supposed to protect.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import unittest

from automation import (controller, hashing, locking, operation_catalog,
                        path_policy, policy, state_machine)
from automation import audit_context

AUDIT = "L1-A31"
PHASE = "RUN-A"

FIXTURE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "r3_control_plane")

SANDBOX = os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest", "prepare")


def _require_replica():
    """Refuse to touch a package that is not a throwaway replica.

    These tests delete `state/progress.json`, `state/approvals.jsonl` and
    `state/transitions.jsonl` between cases. In the replica those files are
    scratch. In a real package they are the audit's memory, and a test suite
    that quietly resets them is worse than no test suite at all.
    """
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
    results = os.path.join(path_policy.LEVEL1_ROOT, "results", AUDIT)
    if os.path.isdir(results):
        shutil.rmtree(results)
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)


def _plan_document(audit=AUDIT, phase=PHASE, target_path=None,
                   target_sha=None, scope="preparation self-test"):
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": scope,
        "target": {"path": target_path, "sha256": target_sha,
                   "identity_evidence": "created by the self-test"},
        "steps": [
            {"step_id": "S1", "operation": "SHA256_FILE",
             "params": {"path": target_path}, "purpose": "identity"},
            {"step_id": "S2", "operation": "OPENSSL_PARSE_CERT",
             "params": {"cert": target_path},
             "purpose": "a gated operation, so approval is required"},
        ],
        "test_matrix": [{"case": "identity"}],
    }


class PreparationCase(unittest.TestCase):
    """A phase with a real plan and a real target, ready to be prepared."""

    def setUp(self):
        _require_replica()
        _reset_state()
        os.makedirs(SANDBOX, exist_ok=True)
        self.target = os.path.join(SANDBOX, "target.bin")
        with io.open(self.target, "wb") as fh:
            fh.write(b"target bytes for the preparation self-test\n")
        self.target_sha = hashing.sha256_file(self.target)
        # R7: a plan belongs to an attempt, and preparation binds the
        # attempt-1 path. Writing it anywhere else no longer produces a plan
        # the controller will accept — which is the point of the change, and
        # is asserted by test_plan_outside_the_controller_path_is_refused.
        self.results_dir = os.path.join(path_policy.LEVEL1_ROOT, "results",
                                        AUDIT, PHASE, "attempt-1")
        os.makedirs(self.results_dir, exist_ok=True)
        self.plan_path = os.path.join(self.results_dir, "plan.json")
        self.write_plan()

    def tearDown(self):
        _reset_state()

    # -- helpers ----------------------------------------------------------
    def write_plan(self, document=None, target_path=None):
        document = document or _plan_document(
            target_path=target_path or self.target, target_sha=self.target_sha)
        raw = json.dumps(document, indent=2, sort_keys=True) + "\n"
        with io.open(self.plan_path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        self.plan_sha = hashing.sha256_text(raw)
        return raw

    def args(self, audit=AUDIT, phase=PHASE, plan=None, target=None):
        class _Args(object):
            pass
        a = _Args()
        a.audit_id = audit
        a.run_phase = phase
        a.plan_path = plan or self.plan_path
        a.target_path = target or self.target
        return a

    def prepare(self, **kw):
        out = io.StringIO()
        saved, sys.stdout = sys.stdout, out
        try:
            code = controller.cmd_prepare_execution(self.args(**kw))
        finally:
            sys.stdout = saved
        return code, out.getvalue()

    def state(self, audit=AUDIT, phase=PHASE):
        return controller._audit_state(controller._load_progress(), audit, phase)

    def journal(self):
        if not os.path.exists(controller.TRANSITIONS_PATH):
            return []
        with io.open(controller.TRANSITIONS_PATH, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def token(self, plan_sha=None, target_sha=None, audit=AUDIT, phase=PHASE):
        return controller.approval_token_for({
            "audit_id": audit, "run_phase": phase,
            "plan_sha256": plan_sha or self.plan_sha,
            "target_sha256": target_sha or self.target_sha})

    def record(self, token):
        class _Args(object):
            pass
        a = _Args()
        a.token = token
        out = io.StringIO()
        saved, sys.stdout = sys.stdout, out
        try:
            code = controller.cmd_record_approval(a)
        finally:
            sys.stdout = saved
        return code, out.getvalue()


# ---------------------------------------------------------------- the defect
class TestTheDefectIsStillForbidden(PreparationCase):
    """The transition R3 attempted must remain impossible."""

    def test_direct_not_started_to_approved_remains_forbidden(self):
        self.assertFalse(
            state_machine.can_transition("NOT_STARTED", "APPROVED"))
        with self.assertRaises(state_machine.StateError):
            state_machine.transition("NOT_STARTED", "APPROVED")
        self.assertNotIn("APPROVED", state_machine.TRANSITIONS["NOT_STARTED"])

    def test_no_shortcut_transition_was_added(self):
        for origin, forbidden in (("NOT_STARTED", "APPROVED"),
                                  ("NOT_STARTED", "EXECUTING"),
                                  ("NOT_STARTED", "RUNNING"),
                                  ("PLANNING", "APPROVED"),
                                  ("PLAN_READY", "APPROVED")):
            if forbidden not in state_machine.STATES:
                continue
            self.assertNotIn(forbidden, state_machine.TRANSITIONS[origin],
                             "%s -> %s must not exist" % (origin, forbidden))

    def test_record_approval_from_not_started_fails_without_state_write(self):
        self.assertEqual(self.state(), "NOT_STARTED")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(self.token())
        message = str(ctx.exception)
        self.assertIn("AWAITING_APPROVAL", message)
        self.assertIn("prepare-execution", message)
        self.assertFalse(os.path.exists(controller.PROGRESS_PATH))
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))
        self.assertEqual(self.state(), "NOT_STARTED")


# ----------------------------------------------------------- the happy path
class TestPreparationAdvances(PreparationCase):

    def test_prepare_execution_advances_exact_legal_sequence(self):
        code, _ = self.prepare()
        self.assertEqual(code, 0)
        steps = [(r["from_state"], r["to_state"]) for r in self.journal()
                 if r["route"] == "prepare-execution"]
        self.assertEqual(steps, [("NOT_STARTED", "PLANNING"),
                                 ("PLANNING", "PLAN_READY"),
                                 ("PLAN_READY", "AWAITING_APPROVAL")])
        for origin, target in steps:
            self.assertTrue(state_machine.can_transition(origin, target))

    def test_prepare_execution_stops_at_awaiting_approval(self):
        self.prepare()
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_prepare_execution_records_no_approval(self):
        self.prepare()
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))
        self.assertEqual(controller._recorded_approvals(), [])

    def test_prepare_execution_executes_no_operation(self):
        calls = []
        original = controller._run_operation
        controller._run_operation = lambda *a, **k: calls.append(a)
        try:
            self.prepare()
        finally:
            controller._run_operation = original
        self.assertEqual(calls, [])
        evidence_dir = os.path.join(path_policy.LEVEL1_ROOT, "evidence",
                                    AUDIT, PHASE)
        self.assertFalse(os.path.exists(os.path.join(evidence_dir,
                                                     "commands.jsonl")))

    def test_prepare_execution_prints_exact_six_field_token(self):
        _, out = self.prepare()
        printed = [ln.strip() for ln in out.splitlines() if ln.strip()]
        token = printed[-1]
        fields = token.split(" ")
        self.assertEqual(len(fields), 6, token)
        self.assertEqual(fields[0], "APPROVE-EXECUTION")
        self.assertEqual(fields[1], AUDIT)
        self.assertEqual(fields[2], "RUN=%s" % PHASE)
        self.assertEqual(fields[3], "PLAN-SHA256=%s" % self.plan_sha)
        self.assertEqual(fields[4], "TARGET-SHA256=%s" % self.target_sha)
        self.assertEqual(fields[5], "RUN-ONCE")
        self.assertEqual(controller.parse_approval(token)["audit_id"], AUDIT)

    def test_prepare_then_approve_reaches_approved(self):
        _, out = self.prepare()
        token = [ln.strip() for ln in out.splitlines() if ln.strip()][-1]
        code, _ = self.record(token)
        self.assertEqual(code, 0)
        self.assertEqual(self.state(), "APPROVED")
        self.assertEqual(len(controller._recorded_approvals()), 1)


# -------------------------------------------------------------- token shape
class TestTokenGrammar(PreparationCase):

    def test_token_with_bare_audit_id_is_accepted(self):
        parsed = controller.parse_approval(self.token())
        self.assertEqual(parsed["audit_id"], AUDIT)

    def test_token_with_AUDIT_equals_prefix_is_rejected(self):
        bad = self.token().replace(" %s " % AUDIT, " AUDIT=%s " % AUDIT, 1)
        self.assertIn("AUDIT=", bad)
        parsed = controller.parse_approval(bad)
        self.assertNotEqual(parsed["audit_id"], AUDIT)
        self.prepare()
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(bad)
        self.assertIn("audit", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_token_with_APPROVE_audit_prefix_is_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(
                self.token().replace("APPROVE-EXECUTION", "APPROVE-%s" % AUDIT, 1))

    def test_token_with_wrong_field_count_is_rejected(self):
        for bad in (self.token() + " EXTRA",
                    " ".join(self.token().split(" ")[:5]),
                    " ".join(self.token().split(" ")[:3])):
            with self.assertRaises(controller.ControllerError):
                controller.parse_approval(bad)


# ------------------------------------------------------------------ binding
class TestApprovalBinding(PreparationCase):

    def setUp(self):
        PreparationCase.setUp(self)
        self.prepare()

    def test_wrong_audit_rejected(self):
        other = "L1-A18"
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(self.token(audit=other))
        self.assertIn("AWAITING_APPROVAL", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))

    def test_wrong_phase_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(self.token(phase="RUN-B"))
        self.assertIn("AWAITING_APPROVAL", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_wrong_plan_hash_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(self.token(plan_sha="a" * 64))
        self.assertIn("plan", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))

    def test_wrong_target_hash_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(self.token(target_sha="b" * 64))
        self.assertIn("target", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))

    def test_plan_drift_after_prepare_rejected(self):
        token = self.token()
        with io.open(self.plan_path, "a", encoding="utf-8") as fh:
            fh.write("\n")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(token)
        self.assertIn("plan changed after preparation", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_target_drift_after_prepare_rejected(self):
        token = self.token()
        with io.open(self.target, "ab") as fh:
            fh.write(b"drift\n")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(token)
        self.assertIn("target changed after preparation", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_replayed_approval_rejected(self):
        """A recorded approval is spent, and cannot be spent again.

        Two independent controls refuse the second use, and the test insists
        on both. Replaying it immediately is stopped by the state gate, since
        the phase is APPROVED and no longer at the gate. Replaying it after
        the phase has somehow returned to AWAITING_APPROVAL — a re-preparation,
        a restored state file — reaches the replay gate itself, which is the
        one that must hold when the state gate no longer does.
        """
        token = self.token()
        self.record(token)
        self.assertEqual(self.state(), "APPROVED")
        self.assertEqual(len(controller._recorded_approvals()), 1)

        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(token)
        self.assertIn("AWAITING_APPROVAL", str(ctx.exception))
        self.assertEqual(len(controller._recorded_approvals()), 1)

        progress = controller._load_progress()
        progress["audits"][AUDIT][PHASE]["state"] = "AWAITING_APPROVAL"
        controller._save_progress(progress)

        with self.assertRaises(controller.ControllerError) as ctx:
            self.record(token)
        self.assertIn("replay", str(ctx.exception).lower())
        self.assertEqual(len(controller._recorded_approvals()), 1)
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_replay_gate_sees_the_recorded_approval(self):
        self.record(self.token())
        recorded = controller._recorded_approvals()
        self.assertEqual(len(recorded), 1)
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_not_replayed(controller.parse_approval(self.token()))
        self.assertIn("replay", str(ctx.exception).lower())


# ------------------------------------------------------- idempotent restart
class TestIdempotentRecovery(PreparationCase):

    def _rewind_to(self, target_state):
        """Put the phase back into an intermediate prepared state.

        This stands in for a crash between two transitions. The binding stays
        exactly as preparation wrote it; only the state label moves back, which
        is what a process killed mid-sequence would have left behind.
        """
        progress = controller._load_progress()
        node = progress["audits"][AUDIT][PHASE]
        node["state"] = target_state
        controller._save_progress(progress)

    def test_prepare_execution_same_binding_is_idempotent(self):
        self.prepare()
        first = len(self.journal())
        code, out = self.prepare()
        self.assertEqual(code, 0)
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertEqual(len(self.journal()), first,
                         "a second identical preparation wrote a transition")
        self.assertEqual(json.loads(out.split("\n\n")[0])["transitions"], [])
        self.assertFalse(os.path.exists(controller.APPROVALS_PATH))

    def test_prepare_execution_different_binding_fails(self):
        self.prepare()
        self.write_plan(_plan_document(target_path=self.target,
                                       target_sha=self.target_sha,
                                       scope="a different plan"))
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare()
        self.assertIn("PREPARATION_BINDING_MISMATCH", str(ctx.exception))
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_resume_from_planning(self):
        self.prepare()
        self._rewind_to("PLANNING")
        before = len(self.journal())
        self.prepare()
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        added = [(r["from_state"], r["to_state"])
                 for r in self.journal()[before:]]
        self.assertEqual(added, [("PLANNING", "PLAN_READY"),
                                 ("PLAN_READY", "AWAITING_APPROVAL")])

    def test_resume_from_plan_ready(self):
        self.prepare()
        self._rewind_to("PLAN_READY")
        before = len(self.journal())
        self.prepare()
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        added = [(r["from_state"], r["to_state"])
                 for r in self.journal()[before:]]
        self.assertEqual(added, [("PLAN_READY", "AWAITING_APPROVAL")])

    def test_resume_from_awaiting_approval(self):
        self.prepare()
        before = len(self.journal())
        self.prepare()
        self.assertEqual(self.state(), "AWAITING_APPROVAL")
        self.assertEqual(len(self.journal()), before)

    def test_resume_with_no_recorded_binding_is_refused(self):
        self.prepare()
        progress = controller._load_progress()
        node = progress["audits"][AUDIT][PHASE]
        for field in controller.BINDING_FIELDS:
            node.pop(field, None)
        controller._save_progress(progress)
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare()
        self.assertIn("no binding was recorded", str(ctx.exception))


# ---------------------------------------------------------------- locking
class TestOneLawfulWriter(PreparationCase):

    def test_concurrent_prepare_has_one_lawful_writer(self):
        held = locking.ControllerLock().acquire()
        try:
            with self.assertRaises(locking.LockError):
                self.prepare()
        finally:
            held.release()
        self.assertFalse(os.path.exists(controller.PROGRESS_PATH))
        self.assertEqual(self.state(), "NOT_STARTED")
        code, _ = self.prepare()
        self.assertEqual(code, 0)
        self.assertEqual(self.state(), "AWAITING_APPROVAL")


# ------------------------------------------------------------- path safety
class TestPathSafety(PreparationCase):

    def test_plan_path_traversal_rejected(self):
        traversal = os.path.join(self.results_dir, "..", PHASE, "plan.json")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(plan=traversal)
        self.assertIn("parent-directory", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")
        self.assertFalse(os.path.exists(controller.PROGRESS_PATH))

    def test_target_path_traversal_rejected(self):
        traversal = os.path.join(SANDBOX, "..", "prepare", "target.bin")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(target=traversal)
        self.assertIn("parent-directory", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_plan_symlink_rejected(self):
        real = os.path.join(SANDBOX, "elsewhere.json")
        shutil.copyfile(self.plan_path, real)
        os.unlink(self.plan_path)
        os.symlink(real, self.plan_path)
        try:
            with self.assertRaises(controller.ControllerError) as ctx:
                self.prepare()
            self.assertIn("symlink", str(ctx.exception))
            self.assertEqual(self.state(), "NOT_STARTED")
        finally:
            os.unlink(self.plan_path)

    def test_target_symlink_rejected(self):
        link = os.path.join(SANDBOX, "target-link.bin")
        os.symlink(self.target, link)
        self.write_plan(_plan_document(target_path=link,
                                       target_sha=self.target_sha))
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(target=link)
        self.assertIn("symlink", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_plan_outside_the_controller_owned_location_rejected(self):
        stray = os.path.join(SANDBOX, "stray-plan.json")
        shutil.copyfile(self.plan_path, stray)
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(plan=stray)
        self.assertIn("controller-owned plan", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_target_disagreeing_with_the_plan_rejected(self):
        other = os.path.join(SANDBOX, "other.bin")
        with io.open(other, "wb") as fh:
            fh.write(b"a different file\n")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(target=other)
        self.assertIn("not the target the plan declares", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_target_identity_drift_before_prepare_rejected(self):
        with io.open(self.target, "ab") as fh:
            fh.write(b"changed before preparation\n")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare()
        self.assertIn("target identity does not match", str(ctx.exception))
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_plan_naming_a_sibling_package_is_rejected(self):
        """A plan bound to another Level-1 package may not run in this one."""
        parent = os.path.dirname(path_policy.LEVEL1_ROOT)
        sibling = os.path.join(parent, "sibling_level1_package")
        os.makedirs(os.path.join(sibling, "automation"), exist_ok=True)
        with io.open(os.path.join(sibling, "paths.json"), "w",
                     encoding="utf-8") as fh:
            fh.write('{"schema": "wpno.level1.paths/2", "project_root": "..",'
                     ' "discovery_root": "..", "level1_root": "."}\n')
        try:
            self.assertIn(path_policy.normalize(sibling),
                          controller._sibling_package_roots())
            document = _plan_document(target_path=self.target,
                                      target_sha=self.target_sha)
            document["static_analysis"] = os.path.join(sibling, "references",
                                                       "thing.zip")
            self.write_plan(document)
            with self.assertRaises(controller.ControllerError) as ctx:
                self.prepare()
            self.assertIn("another Level-1 audit package", str(ctx.exception))
            self.assertEqual(self.state(), "NOT_STARTED")
        finally:
            shutil.rmtree(sibling, ignore_errors=True)


    def test_a_name_that_merely_starts_like_a_sibling_is_not_a_match(self):
        """`_Audits` is a prefix of `_Audits_R3`; only whole names count."""
        self.assertTrue(controller._names_directory("/a/b/pkg/x", "/a/b/pkg"))
        self.assertTrue(controller._names_directory('"/a/b/pkg"', "/a/b/pkg"))
        self.assertTrue(controller._names_directory("/a/b/pkg", "/a/b/pkg"))
        self.assertFalse(controller._names_directory("/a/b/pkg_R3/x", "/a/b/pkg"))
        self.assertFalse(controller._names_directory("/a/b/pkgx", "/a/b/pkg"))


# ------------------------------------------------------------ state layer
class TestStateLayer(PreparationCase):

    def test_state_write_is_atomic(self):
        self.prepare()
        with io.open(controller.PROGRESS_PATH, encoding="utf-8") as fh:
            original = fh.read()

        def refuse(src, dst):
            raise OSError("replace refused by the test")

        progress = controller._load_progress()
        progress["audits"][AUDIT][PHASE]["state"] = "PLANNING"
        saved = controller.os.replace
        controller.os.replace = refuse
        try:
            with self.assertRaises(OSError):
                controller._save_progress(progress)
        finally:
            controller.os.replace = saved

        with io.open(controller.PROGRESS_PATH, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original,
                             "a failed write changed the state file")
        debris = [n for n in os.listdir(controller.STATE_DIR)
                  if n.startswith("progress.json.tmp")]
        self.assertEqual(debris, [], "a temporary state file survived")
        self.assertEqual(self.state(), "AWAITING_APPROVAL")

    def test_state_file_is_always_complete_json(self):
        self.prepare()
        with io.open(controller.PROGRESS_PATH, encoding="utf-8") as fh:
            self.assertIn("audits", json.loads(fh.read()))

    def test_transition_journal_is_append_only(self):
        self.prepare()
        with io.open(controller.TRANSITIONS_PATH, "rb") as fh:
            first = fh.read()
        self.assertEqual(len(self.journal()), 3)
        self.record(self.token())
        with io.open(controller.TRANSITIONS_PATH, "rb") as fh:
            second = fh.read()
        self.assertTrue(second.startswith(first),
                        "earlier journal bytes were rewritten")
        self.assertGreater(len(second), len(first))
        self.assertEqual(len(self.journal()), 4)
        self.assertEqual(self.journal()[-1]["to_state"], "APPROVED")
        self.assertEqual(self.journal()[-1]["route"], "record-approval")


# --------------------------------------------- controls that must not move
class TestUnchangedControls(PreparationCase):

    def test_run_b_isolation_unchanged(self):
        leak = {"common_rules": "r", "audit_specification": "s",
                "target_identity": "t", "target_sha256": "0" * 64,
                "minimal_discovery_evidence": {"findings": ["a RUN-A finding"]},
                "independent_oracle_material": "o", "run_phase": "RUN-B"}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(leak)

        pointer = dict(leak)
        pointer["minimal_discovery_evidence"] = {
            "note": "see results/L1-A31/RUN-A/verdict.json"}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(pointer)

        clean = dict(leak)
        clean["minimal_discovery_evidence"] = {"note": "no conclusions here"}
        self.assertTrue(audit_context.assert_run_b_isolated(clean))

    def test_comparison_sequencing_unchanged(self):
        self.assertEqual(state_machine.phase_order(2),
                         ("RUN-A", "RUN-B", "COMPARISON"))
        self.assertEqual(state_machine.next_run_phase(2, []), "RUN-A")
        self.assertEqual(state_machine.next_run_phase(2, ["RUN-A"]), "RUN-B")
        self.assertEqual(
            state_machine.next_run_phase(2, ["RUN-A", "RUN-B"]), "COMPARISON")
        for impossible in (["RUN-B"], ["COMPARISON"], ["RUN-B", "COMPARISON"],
                           ["RUN-A", "COMPARISON"]):
            with self.assertRaises(state_machine.StateError):
                state_machine.next_run_phase(2, impossible)

    def _plan_for(self, phase):
        """Write a well-formed plan at the controller-owned path for a phase."""
        directory = os.path.join(path_policy.LEVEL1_ROOT, "results", AUDIT,
                                 phase, "attempt-1")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "plan.json")
        document = _plan_document(phase=phase, target_path=self.target,
                                  target_sha=self.target_sha)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        return path

    def test_comparison_cannot_be_prepared_before_run_a(self):
        plan = self._plan_for("COMPARISON")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(phase="COMPARISON", plan=plan)
        self.assertIn("next phase", str(ctx.exception))
        self.assertEqual(self.state(phase="COMPARISON"), "NOT_STARTED")
        self.assertFalse(os.path.exists(controller.PROGRESS_PATH))

    def test_run_b_cannot_be_prepared_before_run_a(self):
        plan = self._plan_for("RUN-B")
        with self.assertRaises(controller.ControllerError) as ctx:
            self.prepare(phase="RUN-B", plan=plan)
        self.assertIn("next phase", str(ctx.exception))
        self.assertEqual(self.state(phase="RUN-B"), "NOT_STARTED")

    def test_forbidden_operation_in_a_plan_is_still_refused(self):
        document = _plan_document(target_path=self.target,
                                  target_sha=self.target_sha)
        document["steps"][1]["operation"] = "ARBITRARY_SHELL"
        self.write_plan(document)
        with self.assertRaises(operation_catalog.ForbiddenOperation):
            self.prepare()
        self.assertEqual(self.state(), "NOT_STARTED")

    def test_no_bypass_option_was_introduced(self):
        rendered = controller.build_parser().format_help()
        for forbidden in policy.FORBIDDEN_CLI_OPTIONS:
            self.assertNotIn(forbidden, rendered)
        self.assertIn("prepare-execution", rendered)


# ------------------------------------------------- reproduction, R3 and R4
def _write_replica(root, package_source, plan_document, plan_name="plan.json",
                   attempt_dir=None):
    """Build a throwaway one-package replica around a control-plane source."""
    os.makedirs(root, exist_ok=True)
    project = os.path.join(root, "project_root")
    discovery = os.path.join(root, "discovery_root")
    package = os.path.join(root, "package")
    for d in (project, discovery, package):
        os.makedirs(d, exist_ok=True)
    shutil.copytree(os.path.join(package_source, "automation"),
                    os.path.join(package, "automation"))
    with io.open(os.path.join(package, "paths.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"schema": "wpno.level1.paths/2",
                   "project_root": "../project_root",
                   "discovery_root": "../discovery_root",
                   "level1_root": "."}, fh, indent=2)
        fh.write("\n")
    shutil.copyfile(
        os.path.join(path_policy.LEVEL1_ROOT, "audit_registry.json"),
        os.path.join(package, "audit_registry.json"))

    target = os.path.join(package, "work", "target.bin")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with io.open(target, "wb") as fh:
        fh.write(b"reproduction target\n")
    target_sha = hashing.sha256_file(target)

    document = plan_document(target, target_sha)
    results = os.path.join(package, "results", AUDIT, PHASE)
    if attempt_dir:
        results = os.path.join(results, attempt_dir)
    os.makedirs(results, exist_ok=True)
    plan_path = os.path.join(results, plan_name)
    raw = json.dumps(document, indent=2, sort_keys=True) + "\n"
    with io.open(plan_path, "w", encoding="utf-8") as fh:
        fh.write(raw)
    return {"package": package, "plan_path": plan_path,
            "plan_sha256": hashing.sha256_text(raw),
            "target_path": target, "target_sha256": target_sha}


def _run_controller(package, argv, timeout=120):
    """Invoke a replica's controller as its own process.

    A subprocess, not an import: the R3 fixture and the R4 package both define
    a module named `automation`, and only one of them can be the imported one.
    The argv is a list, there is no shell in the call path, the interpreter is
    named absolutely, the environment is the controller's own allowlist and the
    timeout is bounded.
    """
    env = policy.base_environment()
    env["PYTHONPATH"] = package
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(  # noqa: S603 - argv list, no shell
        [policy.EXECUTABLES["python3"], "-m", "automation.controller"] + argv,
        shell=False, capture_output=True, timeout=timeout, env=env,
        cwd=package, check=False)


class TestBlockerReproduction(unittest.TestCase):
    """The defect against R3, and its absence against R4."""

    def setUp(self):
        _require_replica()
        self.root = os.path.join(SANDBOX, "reproduction")
        if os.path.isdir(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_r3_blocker_reproduction_fails_on_unmodified_R3_copy(self):
        replica = _write_replica(
            os.path.join(self.root, "r3"), FIXTURE_ROOT,
            lambda t, s: _plan_document(target_path=t, target_sha=s))
        package = replica["package"]

        self.assertEqual(
            [], [n for n in os.listdir(package)
                 if n == "state" and os.path.exists(
                     os.path.join(package, "state", "progress.json"))])

        token = ("APPROVE-EXECUTION %s RUN=%s PLAN-SHA256=%s "
                 "TARGET-SHA256=%s RUN-ONCE"
                 % (AUDIT, PHASE, replica["plan_sha256"],
                    replica["target_sha256"]))

        # The R3 package has no route to AWAITING_APPROVAL at all.
        help_text = _run_controller(package, ["--help"]).stdout.decode(
            "utf-8", "replace")
        self.assertNotIn("prepare-execution", help_text,
                         "the R3 fixture is not the unmodified R3 controller")

        result = _run_controller(package, ["record-approval", "--token", token])
        self.assertNotEqual(result.returncode, 0)
        stderr = result.stderr.decode("utf-8", "replace")
        self.assertIn("StateError", stderr)
        self.assertIn("invalid transition NOT_STARTED ->", stderr)
        # The destination state is reported as `[REDACTED:BIC]`: the word
        # APPROVED is eight capitals and the redactor's bank-identifier
        # pattern matches any such token. That behaviour belongs to the
        # confidentiality control, is unchanged in R4 by design, and is
        # recorded as an open item rather than quietly edited here. The
        # transition it names is unambiguous either way.
        self.assertIn("[REDACTED:BIC]", stderr)

        self.assertFalse(os.path.exists(
            os.path.join(package, "state", "progress.json")))
        self.assertFalse(os.path.exists(
            os.path.join(package, "state", "approvals.jsonl")))

    def test_r4_blocker_reproduction_succeeds_through_AWAITING_APPROVAL(self):
        replica = _write_replica(
            os.path.join(self.root, "r4"), path_policy.LEVEL1_ROOT,
            lambda t, s: _plan_document(target_path=t, target_sha=s),
            attempt_dir="attempt-1")
        package = replica["package"]

        prepared = _run_controller(package, [
            "prepare-execution", "--audit-id", AUDIT, "--run-phase", PHASE,
            "--plan-path", replica["plan_path"],
            "--target-path", replica["target_path"]])
        stdout = prepared.stdout.decode("utf-8", "replace")
        self.assertEqual(prepared.returncode, 0,
                         prepared.stderr.decode("utf-8", "replace"))

        report = json.loads(stdout.split("\n\n")[0])
        self.assertEqual(report["state"], "AWAITING_APPROVAL")
        self.assertFalse(report["approval_recorded"])
        self.assertEqual(report["operations_executed"], 0)

        token = [ln.strip() for ln in stdout.splitlines() if ln.strip()][-1]
        self.assertEqual(len(token.split(" ")), 6)

        self.assertFalse(os.path.exists(
            os.path.join(package, "state", "approvals.jsonl")))

        with io.open(os.path.join(package, "state", "progress.json"),
                     encoding="utf-8") as fh:
            self.assertEqual(
                json.load(fh)["audits"][AUDIT][PHASE]["state"],
                "AWAITING_APPROVAL")

        approved = _run_controller(package, ["record-approval", "--token", token])
        self.assertEqual(approved.returncode, 0,
                         approved.stderr.decode("utf-8", "replace"))
        with io.open(os.path.join(package, "state", "progress.json"),
                     encoding="utf-8") as fh:
            self.assertEqual(
                json.load(fh)["audits"][AUDIT][PHASE]["state"], "APPROVED")
        self.assertTrue(os.path.exists(
            os.path.join(package, "state", "approvals.jsonl")))

        replayed = _run_controller(package, ["record-approval", "--token", token])
        self.assertNotEqual(replayed.returncode, 0)
        self.assertIn("AWAITING_APPROVAL",
                      replayed.stderr.decode("utf-8", "replace"))
        with io.open(os.path.join(package, "state", "approvals.jsonl"),
                     encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
        self.assertEqual(len(lines), 1, "a replay was recorded")


if __name__ == "__main__":
    unittest.main()
