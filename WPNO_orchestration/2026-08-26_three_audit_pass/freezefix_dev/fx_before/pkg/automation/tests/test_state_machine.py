"""State machine and sequencing.

Covers self-test cases 22, 23, 39 and 43:
invalid state transition · concurrent lock · critical finding halt ·
wrong execution order.

`TestPhaseSequencing` carries the VF-005 regressions. The predecessor package
returned the first phase it found missing from the completed set, so
`[RUN-B, COMPARISON]` was accepted as merely "RUN-A still pending" — a history
in which a comparison had already been drawn between one run and nothing.
"""

import json
import os
import unittest

from automation import audit_context, locking, path_policy, policy, state_machine


class TestInvalidTransition(unittest.TestCase):
    """Case 22 — a transition not in the table cannot occur."""

    def test_valid_transitions_are_accepted(self):
        chain = ["NOT_STARTED", "PLANNING", "PLAN_READY", "AWAITING_APPROVAL",
                 "APPROVED", "EXECUTING", "EXECUTED", "REVIEWING", "FINALIZED",
                 "SEALED"]
        for a, b in zip(chain, chain[1:]):
            self.assertEqual(state_machine.transition(a, b), b)

    def test_skipping_approval_is_rejected(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.transition("PLAN_READY", "EXECUTING")

    def test_planning_cannot_jump_to_sealed(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.transition("PLANNING", "SEALED")

    def test_terminal_states_have_no_exit(self):
        for terminal in ("SEALED", "BLOCKED", "ERROR", "CONTAMINATED"):
            self.assertTrue(state_machine.is_terminal(terminal))
            self.assertEqual(state_machine.TRANSITIONS[terminal], ())
            with self.assertRaises(state_machine.StateError):
                state_machine.transition(terminal, "PLANNING")

    def test_unknown_state_is_rejected(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.assert_state("ALMOST_DONE")

    def test_every_state_has_a_transition_entry(self):
        self.assertEqual(set(state_machine.STATES),
                         set(state_machine.TRANSITIONS))


class TestConcurrentLock(unittest.TestCase):
    """Case 23 — two controllers cannot hold the lock at once."""

    def setUp(self):
        self.lock = locking.ControllerLock("selftest")
        if os.path.exists(self.lock.path):
            os.unlink(self.lock.path)

    def tearDown(self):
        if os.path.exists(self.lock.path):
            os.unlink(self.lock.path)

    def test_second_acquire_is_refused(self):
        first = locking.ControllerLock("selftest").acquire()
        try:
            with self.assertRaises(locking.LockError):
                locking.ControllerLock("selftest").acquire()
        finally:
            first.release()

    def test_lock_is_released_and_reacquirable(self):
        with locking.ControllerLock("selftest"):
            self.assertTrue(os.path.exists(self.lock.path))
        self.assertFalse(os.path.exists(self.lock.path))
        locking.ControllerLock("selftest").acquire().release()

    def test_lock_lives_under_level1_state(self):
        expected = os.path.join(path_policy.LEVEL1_ROOT, "state")
        self.assertTrue(self.lock.path.startswith(expected + os.sep))


class TestCriticalHalt(unittest.TestCase):
    """Case 39 — a critical finding halts the sequence until acknowledged."""

    def test_finalized_may_go_to_halt_critical(self):
        self.assertEqual(state_machine.transition("FINALIZED", "HALT_CRITICAL"),
                         "HALT_CRITICAL")

    def test_halt_critical_leads_only_to_sealed(self):
        self.assertEqual(state_machine.TRANSITIONS["HALT_CRITICAL"], ("SEALED",))
        for target in ("PLANNING", "EXECUTING", "FINALIZED"):
            with self.assertRaises(state_machine.StateError):
                state_machine.transition("HALT_CRITICAL", target)

    def test_acknowledgement_prefix_is_defined(self):
        self.assertEqual(policy.ACK_PREFIX, "ACKNOWLEDGE-CRITICAL")


class TestExecutionOrder(unittest.TestCase):
    """Case 43 — the fixed order is exactly the specified one."""

    EXPECTED = [
        "L1-A31", "L1-A34", "L1-A18", "L1-A19", "L1-A17", "L1-A20", "L1-A21",
        "L1-A22", "L1-A05", "L1-A06", "L1-A07", "L1-A08", "L1-A09", "L1-A10",
        "L1-A11", "L1-A12", "L1-A13", "L1-A14", "L1-A15", "L1-A16", "L1-A01",
        "L1-A02", "L1-A03", "L1-A04", "L1-A23", "L1-A24", "L1-A25", "L1-A26",
        "L1-A27", "L1-A28", "L1-A29", "L1-A30", "L1-A32", "L1-A33", "L1-A35",
    ]

    def setUp(self):
        self.registry = audit_context.load_registry()

    def test_order_matches_the_specification_exactly(self):
        ordered = [a["audit_id"] for a in
                   sorted(self.registry["audits"],
                          key=lambda x: x["execution_order"])]
        self.assertEqual(ordered, self.EXPECTED)

    def test_order_values_are_a_unique_dense_sequence(self):
        values = sorted(a["execution_order"] for a in self.registry["audits"])
        self.assertEqual(values, list(range(1, 36)))

    def test_critical_audits_come_first(self):
        first_four = self.EXPECTED[:4]
        self.assertEqual(set(first_four), set(policy.CRITICAL_REPLICATED_AUDITS))


class TestPhaseSequencing(unittest.TestCase):
    def test_single_run_audit_has_one_phase(self):
        self.assertEqual(state_machine.next_run_phase(1, []), "RUN-A")
        self.assertIsNone(state_machine.next_run_phase(1, ["RUN-A"]))

    def test_replicated_audit_follows_a_b_comparison(self):
        self.assertEqual(state_machine.next_run_phase(2, []), "RUN-A")
        self.assertEqual(state_machine.next_run_phase(2, ["RUN-A"]), "RUN-B")
        self.assertEqual(state_machine.next_run_phase(2, ["RUN-A", "RUN-B"]),
                         "COMPARISON")
        self.assertIsNone(state_machine.next_run_phase(
            2, ["RUN-A", "RUN-B", "COMPARISON"]))

    def test_comparison_cannot_start_before_both_runs(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(2, ["RUN-B", "COMPARISON"])


class TestPhasePrefixDiscipline(unittest.TestCase):
    """VF-005 — only the four reachable completed-phase prefixes exist."""

    def test_the_four_valid_prefixes_are_accepted(self):
        for completed, expected in (
            ([], "RUN-A"),
            (["RUN-A"], "RUN-B"),
            (["RUN-A", "RUN-B"], "COMPARISON"),
            (["RUN-A", "RUN-B", "COMPARISON"], None),
        ):
            self.assertEqual(
                state_machine.next_run_phase(2, completed), expected)

    def test_run_b_without_run_a_is_rejected(self):
        with self.assertRaises(state_machine.StateError) as ctx:
            state_machine.next_run_phase(2, ["RUN-B"])
        self.assertIn("RUN-A", str(ctx.exception))

    def test_comparison_alone_is_rejected(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(2, ["COMPARISON"])

    def test_comparison_without_run_b_is_rejected(self):
        with self.assertRaises(state_machine.StateError) as ctx:
            state_machine.next_run_phase(2, ["RUN-A", "COMPARISON"])
        self.assertIn("RUN-B", str(ctx.exception))

    def test_a_duplicate_phase_is_rejected(self):
        with self.assertRaises(state_machine.StateError) as ctx:
            state_machine.next_run_phase(2, ["RUN-A", "RUN-A"])
        self.assertIn("more than once", str(ctx.exception))

    def test_an_unordered_phase_set_is_rejected(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(2, ["RUN-B", "RUN-A"])

    def test_an_unknown_phase_name_is_rejected(self):
        for bad in (["RUN-C"], ["RUN-A", "RUN-Z"], ["run-a"]):
            with self.assertRaises(state_machine.StateError):
                state_machine.next_run_phase(2, bad)

    def test_a_single_run_audit_refuses_replicated_phases(self):
        for bad in (["RUN-B"], ["RUN-A", "RUN-B"], ["COMPARISON"]):
            with self.assertRaises(state_machine.StateError):
                state_machine.next_run_phase(1, bad)

    def test_too_many_completed_phases_is_rejected(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(
                2, ["RUN-A", "RUN-B", "COMPARISON", "RUN-A"])

    def test_an_invalid_replication_count_is_rejected(self):
        for bad in (0, 3, -1, None):
            with self.assertRaises(state_machine.StateError):
                state_machine.next_run_phase(bad, [])

    def test_a_string_is_not_a_phase_sequence(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(2, "RUN-A")

    def test_none_is_not_a_phase_sequence(self):
        with self.assertRaises(state_machine.StateError):
            state_machine.next_run_phase(2, None)

    def test_phase_order_is_fixed_per_replication_count(self):
        self.assertEqual(state_machine.phase_order(1), ("RUN-A",))
        self.assertEqual(state_machine.phase_order(2),
                         ("RUN-A", "RUN-B", "COMPARISON"))

    def test_the_validator_returns_the_completed_list(self):
        self.assertEqual(
            state_machine.assert_valid_completed_phases(2, ["RUN-A"]),
            ["RUN-A"])


if __name__ == "__main__":
    unittest.main()
