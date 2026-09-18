"""Human approval gate.

Covers self-test cases 16-21 and 25:
wrong plan hash · wrong target hash · wrong audit approval ·
wrong run approval · approval replay · missing human approval ·
target change after approval.
"""

import unittest

from automation import controller, policy

A = "0" * 64
B = "1" * 64


def token(audit="L1-A18", run="RUN-A", plan=A, target=B,
          prefix=policy.APPROVAL_PREFIX, suffix=policy.APPROVAL_SUFFIX):
    return "%s %s RUN=%s PLAN-SHA256=%s TARGET-SHA256=%s %s" % (
        prefix, audit, run, plan, target, suffix)


class TestTokenFormat(unittest.TestCase):
    def test_valid_token_parses(self):
        parsed = controller.parse_approval(token())
        self.assertEqual(parsed["audit_id"], "L1-A18")
        self.assertEqual(parsed["run_phase"], "RUN-A")
        self.assertEqual(parsed["plan_sha256"], A)
        self.assertEqual(parsed["target_sha256"], B)

    def test_wrong_prefix_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(prefix="APPROVE"))

    def test_missing_run_once_suffix_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(suffix="RUN-MANY"))

    def test_field_count_is_exact(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token() + " EXTRA")
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(" ".join(token().split()[:5]))

    def test_short_hashes_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(plan="abc"))
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(target="abc"))

    def test_non_hex_hash_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(plan="z" * 64))

    def test_unknown_run_phase_rejected(self):
        with self.assertRaises(controller.ControllerError):
            controller.parse_approval(token(run="RUN-C"))


class TestBinding(unittest.TestCase):
    """Cases 16-19 — each binding is checked separately and named on failure."""

    def setUp(self):
        self.parsed = controller.parse_approval(token())

    def test_correct_binding_accepted(self):
        self.assertTrue(controller.assert_approval_binds(
            self.parsed, "L1-A18", "RUN-A", A, B))

    def test_wrong_plan_hash_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(self.parsed, "L1-A18", "RUN-A",
                                             "2" * 64, B)
        self.assertIn("plan", str(ctx.exception))

    def test_wrong_target_hash_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(self.parsed, "L1-A18", "RUN-A",
                                             A, "3" * 64)
        self.assertIn("target", str(ctx.exception))

    def test_wrong_audit_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(self.parsed, "L1-A19", "RUN-A", A, B)
        self.assertIn("audit", str(ctx.exception))

    def test_wrong_run_phase_rejected(self):
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(self.parsed, "L1-A18", "RUN-B", A, B)
        self.assertIn("run", str(ctx.exception))


class TestReplay(unittest.TestCase):
    """Case 20 — an approval is one-time."""

    def test_replay_of_a_recorded_approval_is_rejected(self):
        parsed = controller.parse_approval(token())
        prior = [{"audit_id": "L1-A18", "run_phase": "RUN-A",
                  "plan_sha256": A, "target_sha256": B,
                  "recorded_at": 1.0}]
        original = controller._recorded_approvals
        controller._recorded_approvals = lambda: prior
        try:
            with self.assertRaises(controller.ControllerError) as ctx:
                controller.assert_not_replayed(parsed)
            self.assertIn("replay", str(ctx.exception).lower())
        finally:
            controller._recorded_approvals = original

    def test_a_different_plan_is_not_a_replay(self):
        parsed = controller.parse_approval(token(plan="4" * 64))
        prior = [{"audit_id": "L1-A18", "run_phase": "RUN-A",
                  "plan_sha256": A, "target_sha256": B, "recorded_at": 1.0}]
        original = controller._recorded_approvals
        controller._recorded_approvals = lambda: prior
        try:
            self.assertTrue(controller.assert_not_replayed(parsed))
        finally:
            controller._recorded_approvals = original


class TestMissingApproval(unittest.TestCase):
    """Case 21 — no approval, no execution, and no flag that changes that."""

    def test_none_and_empty_are_rejected(self):
        for bad in (None, "", "   ", 42, [], {}):
            with self.assertRaises(controller.ControllerError):
                controller.parse_approval(bad)

    def test_no_auto_approve_option_exists(self):
        parser = controller.build_parser()
        rendered = parser.format_help()
        for sub in ("verify-structure", "status", "prepare-next", "show-plan",
                    "prepare-execution", "record-approval", "execute-approved",
                    "finalize-current", "verify-evidence", "consolidate"):
            self.assertIn(sub, rendered)
        for forbidden in policy.FORBIDDEN_CLI_OPTIONS:
            self.assertNotIn(forbidden, rendered)

    def test_controller_source_contains_no_bypass_option(self):
        import inspect
        source = inspect.getsource(controller)
        for forbidden in policy.FORBIDDEN_CLI_OPTIONS:
            self.assertNotIn('"%s"' % forbidden, source)


class TestTargetChangedAfterApproval(unittest.TestCase):
    """Case 25 — a target that changed after approval voids the approval."""

    def test_changed_target_hash_voids_the_binding(self):
        parsed = controller.parse_approval(token())
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(parsed, "L1-A18", "RUN-A", A,
                                             "5" * 64)
        self.assertIn("void", str(ctx.exception).lower())

    def test_changed_plan_voids_the_binding(self):
        parsed = controller.parse_approval(token())
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.assert_approval_binds(parsed, "L1-A18", "RUN-A",
                                             "6" * 64, B)
        self.assertIn("void", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
