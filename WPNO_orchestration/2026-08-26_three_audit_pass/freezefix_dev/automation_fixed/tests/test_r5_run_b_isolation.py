"""RUN-B isolation, R5 remediation of known cause 5.

R4 forbade a RUN-B context from naming `results/<audit>/RUN-A` and
`evidence/<audit>/RUN-A`. It did not forbid `work/<audit>/RUN-A`, which is
where RUN-A's staged material, mutation fixtures and intermediate outputs
actually live. A RUN-B pointed at that directory could reconstruct RUN-A's
reasoning without ever naming a covered path.

The second half of the defect is subtler and is what these tests exist for:
the R4 check was a plain substring test, so it only ever caught the one
spelling someone thought to type. `RUN-A` and `run-a` are the same directory.
So are `RUN-B/../RUN-A`, a backslash separator, a percent-encoded hyphen, an
NFD-decomposed neighbour and a symlink. Each spelling below reaches the same
bytes, and each one is tested.
"""

import os
import shutil
import unicodedata
import unittest

from automation import audit_context, path_policy, policy


def work_run_a(audit_id):
    return os.path.join(path_policy.LEVEL1_ROOT, "work", audit_id, "RUN-A")


class TestWorkTreeIsCovered(unittest.TestCase):
    """The R4 gap itself."""

    def test_work_run_a_is_forbidden_for_every_replicated_audit(self):
        for audit in policy.REPLICATED_AUDIT_IDS_FOR_ISOLATION:
            self.assertIn("work/%s/RUN-A" % audit,
                          policy.RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS,
                          "work tree not covered for %s" % audit)

    def test_results_and_evidence_remain_covered(self):
        for tree in ("results", "evidence"):
            for audit in policy.REPLICATED_AUDIT_IDS_FOR_ISOLATION:
                self.assertIn("%s/%s/RUN-A" % (tree, audit),
                              policy.RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS)

    def test_a_context_naming_the_work_tree_is_refused(self):
        context = {"run_phase": "RUN-B",
                   "independent_oracle_material":
                       {"path": "work/L1-A31/RUN-A/mutations/x.xml"}}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(context)

    def test_the_registry_and_the_guard_cannot_drift(self):
        """Every replicated audit in policy is in the isolation list.

        The R4 gap was a hand-maintained tuple falling behind. This asserts
        the two lists agree rather than trusting that they do.
        """
        for audit in policy.CRITICAL_REPLICATED_AUDITS:
            self.assertIn(audit, policy.REPLICATED_AUDIT_IDS_FOR_ISOLATION)


class TestSpellings(unittest.TestCase):
    """One directory, many names. Every name is refused."""

    def refuse(self, value, why):
        context = {"run_phase": "RUN-B",
                   "immutable_pre_run_packet": {"note": value}}
        with self.assertRaises(audit_context.ContextError, msg=why):
            audit_context.assert_run_b_isolated(context)

    def test_direct_path(self):
        self.refuse("results/L1-A31/RUN-A/verdict.json", "direct path")

    def test_nested_path(self):
        self.refuse("/home/x/pkg/evidence/L1-A34/RUN-A/artifacts/a.txt",
                    "nested path")

    def test_relative_traversal(self):
        self.refuse("results/L1-A31/RUN-B/../RUN-A/verdict.json", "traversal")

    def test_deep_relative_traversal(self):
        self.refuse("work/L1-A18/RUN-B/sub/../../RUN-A/notes.md",
                    "multi-segment traversal")

    def test_case_variants(self):
        for value in ("RESULTS/L1-A31/RUN-A/verdict.json",
                      "results/l1-a31/run-a/verdict.json",
                      "Results/L1-A31/Run-A/verdict.json",
                      "work/L1-A34/run-a/staged.pem"):
            self.refuse(value, "case variant %r" % value)

    def test_backslash_separator(self):
        self.refuse("results\\L1-A31\\RUN-A\\verdict.json", "backslash")

    def test_percent_encoded(self):
        self.refuse("results/L1-A31/RUN%2DA/verdict.json", "percent-encoded")

    def test_unicode_nfc_and_nfd_are_both_refused(self):
        base = "work/L1-A31/RUN-A/staged.pem"
        self.refuse(unicodedata.normalize("NFC", base), "NFC")
        self.refuse(unicodedata.normalize("NFD", base), "NFD")

    def test_a_legitimate_run_b_path_is_still_allowed(self):
        """The guard must not reject the thing it exists to permit."""
        context = {"run_phase": "RUN-B",
                   "immutable_pre_run_packet":
                       {"note": "work/L1-A31/RUN-B/inputs/packet.json"}}
        self.assertTrue(audit_context.assert_run_b_isolated(context))

    def test_the_phase_label_itself_is_not_a_leak(self):
        """R4's predecessor rejected every context for saying 'RUN-A'."""
        context = {"run_phase": "RUN-B",
                   "phase_sequencing": ["RUN-A", "RUN-B", "COMPARISON"]}
        self.assertTrue(audit_context.assert_run_b_isolated(context))


class TestOperatorIntakeConclusions(unittest.TestCase):
    """Migrated operator intake is evidence; its conclusions are not."""

    def test_run_a_conclusion_documents_are_refused(self):
        for value in (
            "work/operator_intake/L1-A31/2026-08-21_PROVENANCE_FINDINGS.json",
            "work/operator_intake/L1-A31/2026-08-21_PROVENANCE_REVIEW.md",
            "work/operator_intake/L1-A31/2026-08-21_P7S_CMS_PARSE_REPORT.md",
            "work/operator_intake/L1-A31/2026-08-21_PROVENANCE_CONCLUSIONS_AFTER_MAIL_ZIP.json",
            "work/operator_intake/L1-A31/comparison_2026-08-24/x.json",
        ):
            context = {"run_phase": "RUN-B",
                       "immutable_pre_run_packet": {"note": value}}
            with self.assertRaises(audit_context.ContextError,
                                   msg="not refused: %s" % value):
                audit_context.assert_run_b_isolated(context)

    def test_factual_intake_evidence_remains_available(self):
        """RUN-B may still be given the hash inventory and parse evidence.

        Forbidding all of operator intake would be simpler and would also make
        an independent RUN-B impossible, because the source hashes are how it
        identifies its target.
        """
        for value in (
            "work/operator_intake/L1-A31/2026-08-21_ZIP_ENTRY_HASH_INVENTORY.jsonl",
            "work/operator_intake/L1-A31/2026-08-21_P7S_CMS_PARSE_EVIDENCE.json",
            "work/operator_intake/L1-A31/official_chain_material_2026-08-24_v2/work/certs/vhn_root.pem",
        ):
            context = {"run_phase": "RUN-B",
                       "immutable_pre_run_packet": {"note": value}}
            self.assertTrue(audit_context.assert_run_b_isolated(context),
                            "wrongly refused: %s" % value)


class TestSymlinkSpelling(unittest.TestCase):
    """A link is a spelling too, and it is only visible on the filesystem."""

    def setUp(self):
        self.base = os.path.join(path_policy.LEVEL1_ROOT, "work",
                                 "L1-A31", "RUN-B", "_isolation_test")
        self.target = work_run_a("L1-A31")
        os.makedirs(self.target, exist_ok=True)
        os.makedirs(self.base, exist_ok=True)
        self.link = os.path.join(self.base, "innocent_name")
        if os.path.lexists(self.link):
            os.unlink(self.link)
        os.symlink(self.target, self.link)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_a_symlink_into_run_a_is_refused(self):
        context = {"run_phase": "RUN-B",
                   "immutable_pre_run_packet": {"note": self.link}}
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(context)


class TestForbiddenReadEnforcement(unittest.TestCase):
    """The filesystem-level rule, not just the context-level one."""

    def test_forbidden_roots_name_all_three_trees(self):
        roots = audit_context.run_b_forbidden_read_roots("L1-A31")
        self.assertEqual(len(roots), 3)
        for tree in ("results", "evidence", "work"):
            self.assertTrue(
                any(os.sep + tree + os.sep in r for r in roots),
                "tree %s missing from forbidden read roots" % tree)

    def test_reading_run_a_is_refused(self):
        os.makedirs(work_run_a("L1-A31"), exist_ok=True)
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_may_read(
                "L1-A31", os.path.join(work_run_a("L1-A31"), "anything.txt"))

    def test_reading_run_a_via_traversal_is_refused(self):
        os.makedirs(work_run_a("L1-A31"), exist_ok=True)
        sneaky = os.path.join(path_policy.LEVEL1_ROOT, "work", "L1-A31",
                              "RUN-B", "..", "RUN-A", "anything.txt")
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_may_read("L1-A31", sneaky)

    def test_reading_run_b_own_work_is_permitted(self):
        own = os.path.join(path_policy.LEVEL1_ROOT, "work", "L1-A31",
                           "RUN-B", "own.txt")
        os.makedirs(os.path.dirname(own), exist_ok=True)
        self.assertTrue(audit_context.assert_run_b_may_read("L1-A31", own))


class TestRunBPacket(unittest.TestCase):
    """The allowlisted packet."""

    def packet(self, **over):
        kwargs = dict(
            audit_id="L1-A31",
            target_path="references/REF-11-vhn.xml.p7s",
            target_sha256="a" * 64,
            immutable_pre_run_packet={"inputs": ["references/REF-08-safe-root-ca-2017.der"]},
            validation_time=1772232925,
            independent_method="BOUNCY_CASTLE_JAVA_CMS_VERIFIER",
            required_controls=["POSITIVE", "NEGATIVE", "MUTATION"],
            run_a_terminal=True,
            run_a_seal_integrity=True,
        )
        kwargs.update(over)
        return audit_context.run_b_context(**kwargs)

    def test_a_clean_packet_is_built(self):
        ctx = self.packet()
        self.assertEqual(set(ctx), set(policy.RUN_B_ALLOWED_KEYS))
        self.assertEqual(ctx["run_phase"], "RUN-B")

    def test_run_a_facts_are_booleans_only(self):
        with self.assertRaises(audit_context.ContextError):
            self.packet(run_a_terminal="SEALED/ERROR")
        with self.assertRaises(audit_context.ContextError):
            self.packet(run_a_seal_integrity="INTACT, verdict was ERROR")

    def test_validation_time_is_required_and_integral(self):
        with self.assertRaises(audit_context.ContextError):
            self.packet(validation_time="2026-02-27T00:00:00Z")

    def test_required_controls_may_not_be_empty(self):
        with self.assertRaises(audit_context.ContextError):
            self.packet(required_controls=[])

    def test_target_sha256_must_be_a_hash(self):
        with self.assertRaises(audit_context.ContextError):
            self.packet(target_sha256="unknown")

    def test_a_run_a_pointer_in_the_packet_is_refused(self):
        with self.assertRaises(audit_context.ContextError):
            self.packet(immutable_pre_run_packet={
                "inputs": ["results/L1-A31/RUN-A/verdict.json"]})

    def test_no_extra_key_can_be_smuggled_in(self):
        ctx = self.packet()
        ctx["findings"] = "…"
        with self.assertRaises(audit_context.ContextError):
            audit_context.assert_run_b_isolated(ctx)


if __name__ == "__main__":
    unittest.main()
