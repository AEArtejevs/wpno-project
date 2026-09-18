"""An output is not an input, and the rehearsal must be able to tell them apart.

The harness classified every absolute string in a step's argv as a path the
step reads. A step whose `--out` file did not exist yet therefore looked
unrunnable, and was recorded `LIVE_PHASE_MATERIAL_NOT_STAGED` with its own
destination listed under `absent_inputs`.

Two steps were skipped that way, and they were the two that mattered most:
L1-A19's sabotage controls. CLAUDE.md section 6 is explicit that a sabotage
must be shown to be effective or the test is void, and a control that never
ran shows nothing. The rehearsal reported the phase PASS_READY while the only
steps capable of proving the method was on the measured path had been stepped
over.

These tests hold the distinction in place from both sides. An output need not
pre-exist; a genuine input still must; and an output may not be written
outside the writable work area, because a destination that escapes `work/` is
a plan writing where this package does not permit writing.
"""

import importlib.util
import json
import os
import unittest

from automation import hashing, path_policy

ROOT = path_policy.LEVEL1_ROOT
PLANS = os.path.join(ROOT, "build", "candidate_plans_r8")
REHEARSAL = os.path.join(ROOT, "work", "_rehearsal_r8", "REHEARSAL_REPORT.json")


def harness():
    path = os.path.join(ROOT, "build", "rehearse_candidate_plans.py")
    spec = importlib.util.spec_from_file_location("rehearse_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def work(*parts):
    return os.path.join(ROOT, "work", *parts)


class OutputsAreNotInputs(unittest.TestCase):
    def setUp(self):
        self.h = harness()

    def test_a_value_after_out_is_an_output(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"module": "automation.a19_run_a_cli",
                           "args": ["--vectors", work("in.jsonl"),
                                    "--out", work("does_not_exist_yet.json")]}}
        self.assertIn(work("does_not_exist_yet.json"), self.h.step_outputs(step))
        self.assertNotIn(work("does_not_exist_yet.json"), self.h.step_inputs(step))

    def test_an_out_destination_need_not_pre_exist(self):
        target = work("_selftest", "surely_absent_output.json")
        if os.path.exists(target):
            os.remove(target)
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"module": "automation.a19_run_a_cli",
                           "args": ["--out", target]}}
        self.assertEqual(self.h.missing_inputs(step), [],
                         "an absent destination must not hold a step back")

    def test_a_missing_real_input_is_still_refused(self):
        absent = work("_selftest", "surely_absent_input.jsonl")
        if os.path.exists(absent):
            os.remove(absent)
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"module": "automation.a19_run_a_cli",
                           "args": ["--vectors", absent,
                                    "--out", work("_selftest", "out.json")]}}
        self.assertEqual(self.h.missing_inputs(step), [absent],
                         "a genuine input that is absent must still be caught")

    def test_a_work_dir_value_is_an_output(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"module": "automation.a19_run_b_cli",
                           "args": ["--work-dir", work("L1-A19", "RUN-B")]}}
        self.assertIn(work("L1-A19", "RUN-B"), self.h.step_outputs(step))
        self.assertNotIn(work("L1-A19", "RUN-B"), self.h.step_inputs(step))

    def test_a_named_out_param_is_an_output(self):
        step = {"step_id": "s", "operation": "OPENSSL_VERIFY_CMS",
                "params": {"cms": work("a.p7s"), "out": work("b.bin")}}
        self.assertIn(work("b.bin"), self.h.step_outputs(step))
        self.assertNotIn(work("b.bin"), self.h.step_inputs(step))
        self.assertIn(work("a.p7s"), self.h.step_inputs(step))


class OutputsStayInsideTheWorkArea(unittest.TestCase):
    def setUp(self):
        self.h = harness()

    def test_an_output_under_work_is_confined(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"args": ["--out", work("L1-A19", "RUN-A", "x.json")]}}
        self.assertEqual(self.h.unconfined_outputs(step), [])

    def test_an_output_in_the_control_plane_is_refused(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"args": ["--out", os.path.join(ROOT, "build", "x.json")]}}
        self.assertEqual(self.h.unconfined_outputs(step),
                         [os.path.join(ROOT, "build", "x.json")])

    def test_an_output_outside_the_package_is_refused(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"args": ["--out", "/tmp/escape.json"]}}
        self.assertEqual(self.h.unconfined_outputs(step), ["/tmp/escape.json"])

    def test_an_output_escaping_by_parent_segments_is_refused(self):
        step = {"step_id": "s", "operation": "AUDIT_MODULE_RUN",
                "params": {"args": ["--out", work("..", "build", "x.json")]}}
        self.assertNotEqual(self.h.unconfined_outputs(step), [])

    def test_no_plan_in_the_package_names_an_unconfined_output(self):
        for audit_id in sorted(os.listdir(PLANS)):
            audit_dir = os.path.join(PLANS, audit_id)
            if not os.path.isdir(audit_dir):
                continue
            for phase in sorted(os.listdir(audit_dir)):
                plan_path = os.path.join(audit_dir, phase, "plan.json")
                if not os.path.isfile(plan_path):
                    continue
                for step in load(plan_path)["steps"]:
                    self.assertEqual(
                        self.h.unconfined_outputs(step), [],
                        "%s/%s step %r writes outside work/"
                        % (audit_id, phase, step["step_id"]))


class SabotageStepsActuallyRan(unittest.TestCase):
    """The two controls must be recorded as executed, not skipped or inferred."""

    def setUp(self):
        self.report = load(REHEARSAL)
        self.run_a = next(r for r in self.report["reports"]
                          if r["audit_id"] == "L1-A19"
                          and r["run_phase"] == "RUN-A")
        self.steps = {s["step_id"]: s for s in self.run_a["steps"]}

    def test_both_sabotage_steps_are_present(self):
        self.assertIn("sabotage_modulus", self.steps)
        self.assertIn("sabotage_repetition_rule", self.steps)

    def test_both_sabotage_steps_executed(self):
        for step_id in ("sabotage_modulus", "sabotage_repetition_rule"):
            step = self.steps[step_id]
            self.assertTrue(step.get("executed"),
                            "%s was not executed: %s"
                            % (step_id, step.get("not_executed_reason")))
            self.assertNotIn("not_executed_reason", step)
            self.assertIsNotNone(step.get("exit_code"),
                                 "%s has no exit code" % step_id)

    def test_neither_was_skipped_for_an_absent_output(self):
        for step_id in ("sabotage_modulus", "sabotage_repetition_rule"):
            self.assertIsNone(self.steps[step_id].get("absent_inputs"))

    def test_the_phase_is_pass_ready_with_them_run(self):
        self.assertTrue(self.run_a["ok"])


class SabotagedResultsDifferAsExpected(unittest.TestCase):
    """A sabotage that changes nothing is a measurement error, not a control."""

    @staticmethod
    def key(record):
        raw = record["raw"]
        return raw if isinstance(raw, str) else "<not-a-string>"

    def outcomes(self, path):
        return {self.key(r): r["actual"]["result"] for r in load(path)["results"]}

    def setUp(self):
        base = os.path.join(ROOT, "work", "L1-A19")
        self.clean_a = self.outcomes(os.path.join(base, "RUN-A",
                                                  "run_a_results.json"))
        self.modulus = self.outcomes(os.path.join(base, "RUN-A",
                                                  "sabotage_modulus.json"))
        self.repetition = self.outcomes(os.path.join(base, "RUN-A",
                                                     "sabotage_repetition.json"))
        self.run_b = self.outcomes(os.path.join(base, "RUN-B",
                                                "run_b_results.json"))

    def test_the_modulus_sabotage_changes_answers(self):
        changed = {k for k, v in self.modulus.items() if self.clean_a[k] != v}
        self.assertGreater(len(changed), 0,
                           "zero changed answers is a measurement error")

    def test_the_repetition_sabotage_changes_answers(self):
        changed = {k for k, v in self.repetition.items() if self.clean_a[k] != v}
        self.assertGreater(len(changed), 0,
                           "zero changed answers is a measurement error")

    def test_the_two_sabotages_break_different_things(self):
        a = {k for k, v in self.modulus.items() if self.clean_a[k] != v}
        b = {k for k, v in self.repetition.items() if self.clean_a[k] != v}
        self.assertNotEqual(a, b)
        self.assertEqual(a & b, set(),
                         "two controls that move the same answers are one control")

    def test_the_unsabotaged_runs_agree_with_each_other(self):
        self.assertEqual(self.clean_a, self.run_b,
                         "the two independent methods must agree input by input")

    def test_each_sabotaged_run_disagrees_with_run_b(self):
        for label, sabotaged in (("modulus", self.modulus),
                                 ("repetition", self.repetition)):
            self.assertNotEqual(
                sabotaged, self.run_b,
                "the %s sabotage left RUN-A agreeing with RUN-B, so the "
                "comparison could not have seen it" % label)
