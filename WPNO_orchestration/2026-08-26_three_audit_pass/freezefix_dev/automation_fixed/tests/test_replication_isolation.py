"""RUN-B isolation.

Covers self-test case 38: RUN-B may not see RUN-A's conclusions.

The point of a second run is a second opinion. A RUN-B that has seen RUN-A's
verdict produces agreement, and agreement obtained that way carries no
information at all.

The VF-003 regressions are in `TestReplicationContext`. The predecessor package
searched a serialised copy of the whole context for the forbidden names, and
`RUN-A` is one of them, so the legitimate value of `run_phase` tripped the guard
and every valid RUN-A context was refused. The guard here inspects keys and
result paths. It does not inspect the phase label, because the phase label is
what both runs are told about themselves.
"""

import os
import unittest

from automation import audit_context, path_policy, policy, state_machine


class TestForbiddenKeys(unittest.TestCase):
    def test_forbidden_key_list_covers_the_conclusion_surface(self):
        for key in ("findings", "verdict", "self_critique", "disproof",
                    "expected_conclusion"):
            self.assertIn(key, policy.RUN_B_FORBIDDEN_KEYS)

    def test_clean_context_passes(self):
        context = {
            "common_rules": "…",
            "audit_specification": "…",
            "target_identity": "/x/y.py",
            "target_sha256": "0" * 64,
            "minimal_discovery_evidence": {"note": "…"},
            "independent_oracle_material": {"vectors": []},
            "run_phase": "RUN-B",
        }
        self.assertTrue(audit_context.assert_run_b_isolated(context))

    def test_each_forbidden_key_is_caught_at_top_level(self):
        for key in policy.RUN_B_FORBIDDEN_KEYS:
            context = {"run_phase": "RUN-B", key: "leaked"}
            with self.assertRaises(audit_context.ContextError):
                audit_context.assert_run_b_isolated(context)

    def test_forbidden_key_is_caught_when_nested(self):
        context = {"run_phase": "RUN-B",
                   "minimal_discovery_evidence": {
                       "notes": [{"verdict": "PASS"}]}}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(context)

    def test_forbidden_key_is_caught_deep_in_a_list(self):
        context = {"run_phase": "RUN-B",
                   "independent_oracle_material": [
                       [{"inner": {"expected_conclusion": "valid"}}]]}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(context)


class TestPhaseLabelIsNotALeak(unittest.TestCase):
    """VF-003 — the run label is metadata, and metadata is not a conclusion."""

    def test_run_phase_value_run_a_is_accepted(self):
        context = {"run_phase": "RUN-A",
                   "minimal_discovery_evidence": {"note": "nothing"}}
        self.assertTrue(audit_context.assert_run_b_isolated(context))

    def test_forbidden_name_as_a_value_is_not_a_violation(self):
        for value in ("RUN-A", "the verdict is not in here",
                      "findings are discussed in prose"):
            context = {"run_phase": "RUN-B",
                       "minimal_discovery_evidence": {"excerpt": value}}
            self.assertTrue(audit_context.assert_run_b_isolated(context))

    def test_forbidden_name_as_a_key_is_still_a_violation(self):
        context = {"run_phase": "RUN-B",
                   "minimal_discovery_evidence": {"RUN-A": "leaked"}}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(context)

    def test_a_pointer_to_another_phase_result_is_a_violation(self):
        for pointer in ("results/L1-A18/RUN-A/verdict.json",
                        "/somewhere/evidence/L1-A31/RUN-A/commands.jsonl",
                        "please read results/L1-A34/RUN-A first"):
            context = {"run_phase": "RUN-B",
                       "minimal_discovery_evidence": {"hint": pointer}}
            with self.assertRaises(audit_context.ContextError) as ctx:
                audit_context.assert_run_b_isolated(context)
            self.assertIn("result path", str(ctx.exception))

    def test_the_two_checks_are_separately_callable(self):
        keyed = {"verdict": "PASS"}
        pathed = {"hint": "results/L1-A19/RUN-A/verdict.json"}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_no_forbidden_keys(keyed)
        self.assertTrue(audit_context.assert_no_other_phase_result_paths(keyed))
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_no_other_phase_result_paths(pathed)
        self.assertTrue(audit_context.assert_no_forbidden_keys(pathed))

    def test_control_plane_documents_may_name_their_own_output_paths(self):
        """The specification's OUTPUT FILES section is not a leak."""
        context = {
            "common_rules": "phase paths are results/L1-A31/RUN-A/ and so on",
            "audit_specification": "results/L1-A31/RUN-A/verdict.json",
            "minimal_discovery_evidence": {},
            "run_phase": "RUN-B",
        }
        self.assertTrue(audit_context.assert_run_b_isolated(context))


class TestReplicationContext(unittest.TestCase):
    def test_run_b_context_carries_only_permitted_material(self):
        context = audit_context.replication_context(
            "L1-A18", "RUN-B", "/x/payload_scan.py", "0" * 64,
            {"note": "minimal"}, {"vectors": ["synthetic"]})
        self.assertEqual(context["run_phase"], "RUN-B")
        self.assertNotIn("findings", context)
        self.assertNotIn("verdict", context)
        allowed = {"common_rules", "audit_specification", "target_identity",
                   "target_sha256", "minimal_discovery_evidence",
                   "independent_oracle_material", "run_phase"}
        self.assertEqual(set(context), allowed)

    def test_run_a_context_is_built_without_error(self):
        context = audit_context.replication_context(
            "L1-A18", "RUN-A", "/x/payload_scan.py", "0" * 64,
            {"note": "minimal"}, {"vectors": ["synthetic"]})
        self.assertEqual(context["run_phase"], "RUN-A")

    def test_run_a_and_run_b_receive_the_same_key_set(self):
        a = audit_context.replication_context(
            "L1-A18", "RUN-A", "/x", "0" * 64, {}, {})
        b = audit_context.replication_context(
            "L1-A18", "RUN-B", "/x", "0" * 64, {}, {})
        self.assertEqual(set(a), set(b))

    def test_the_two_phases_differ_only_in_the_phase_label(self):
        a = audit_context.replication_context(
            "L1-A31", "RUN-A", "/x", "0" * 64, {"n": 1}, {"o": 2})
        b = audit_context.replication_context(
            "L1-A31", "RUN-B", "/x", "0" * 64, {"n": 1}, {"o": 2})
        differing = sorted(k for k in a if a[k] != b[k])
        self.assertEqual(differing, ["run_phase"])

    def test_the_declared_key_set_is_the_one_delivered(self):
        context = audit_context.replication_context(
            "L1-A19", "RUN-A", "/x", "0" * 64, {}, {})
        self.assertEqual(set(context), set(audit_context.REPLICATION_KEYS))

    def test_every_replicated_audit_can_build_both_phases(self):
        for aid in policy.CRITICAL_REPLICATED_AUDITS:
            for phase in ("RUN-A", "RUN-B"):
                context = audit_context.replication_context(
                    aid, phase, "/x", "0" * 64, {}, {})
                self.assertEqual(context["run_phase"], phase)

    def test_comparison_is_not_built_by_replication_context(self):
        with self.assertRaises(audit_context.ContextError):
            audit_context.replication_context(
                "L1-A18", "COMPARISON", "/x", "0" * 64, {}, {})

    def test_unknown_phase_is_rejected(self):
        with self.assertRaises(audit_context.ContextError):
            audit_context.replication_context(
                "L1-A18", "RUN-Z", "/x", "0" * 64, {}, {})

    def test_comparison_context_is_the_only_place_both_runs_meet(self):
        merged = audit_context.comparison_context(
            "L1-A18", {"verdict": "PASS"}, {"verdict": "FAIL"})
        self.assertIn("run_a", merged)
        self.assertIn("run_b", merged)
        self.assertIn("disagreement", merged["instruction"].lower())

    def test_comparison_instruction_forbids_an_automatic_pass(self):
        merged = audit_context.comparison_context("L1-A18", {}, {})
        self.assertIn("never becomes PASS automatically", merged["instruction"])


class TestReplicatedAuditSet(unittest.TestCase):
    def test_exactly_four_audits_are_replicated(self):
        self.assertEqual(set(policy.CRITICAL_REPLICATED_AUDITS),
                         {"L1-A18", "L1-A19", "L1-A31", "L1-A34"})

    def test_registry_matches_the_replicated_set(self):
        registry = audit_context.load_registry()
        replicated = {a["audit_id"] for a in registry["audits"]
                      if a["replications"] == 2}
        self.assertEqual(replicated, set(policy.CRITICAL_REPLICATED_AUDITS))

    def test_replicated_audits_use_three_phases(self):
        self.assertEqual(policy.RUN_PHASES_REPLICATED,
                         ("RUN-A", "RUN-B", "COMPARISON"))
        self.assertEqual(
            state_machine.next_run_phase(2, ["RUN-A", "RUN-B"]), "COMPARISON")

    def test_every_replicated_prompt_states_the_isolation_rule(self):
        for aid in policy.CRITICAL_REPLICATED_AUDITS:
            path = os.path.join(path_policy.LEVEL1_ROOT, "prompts", "%s.md" % aid)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("RUN-B", text)
            self.assertIn("independent methods", text)
            self.assertIn("replications = 2", text)

    def test_every_replicated_prompt_states_the_four_replication_rules(self):
        """VF-006 — the four requirements are stated, not merely implied."""
        for aid in policy.CRITICAL_REPLICATED_AUDITS:
            path = os.path.join(path_policy.LEVEL1_ROOT, "prompts", "%s.md" % aid)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("independent methods", text, aid)
            self.assertIn("no RUN-A conclusion or result material", text, aid)
            self.assertIn("only after both runs are sealed", text, aid)
            self.assertIn("never becomes PASS automatically", text, aid)


class TestReviewerIsolation(unittest.TestCase):
    """The Reviewer must not be told what the Planner expected."""

    def _payload(self):
        return {k: "value" for k in audit_context.REVIEWER_KEYS}

    def test_clean_reviewer_payload_is_accepted(self):
        context = audit_context.reviewer_context(self._payload())
        self.assertEqual(set(context), set(audit_context.REVIEWER_KEYS))

    def test_planner_conclusion_is_refused(self):
        for key in audit_context.REVIEWER_FORBIDDEN_KEYS:
            payload = self._payload()
            payload[key] = "PASS"
            with self.assertRaises(audit_context.ContextError):
                audit_context.reviewer_context(payload)


if __name__ == "__main__":
    unittest.main()
