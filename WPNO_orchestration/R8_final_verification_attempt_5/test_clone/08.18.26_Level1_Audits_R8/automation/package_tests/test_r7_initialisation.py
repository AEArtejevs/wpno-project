"""R7 revision initialisation, lineage, and the R6 failure it carries forward.

Three things have to hold at once for R7's active state to mean anything, and
they are the same three that held for R5 and R6.

The predecessor must be intact, because R6 is the historical evidence this
revision supersedes — including one sealed attempt that failed, which is the
whole reason R7 exists. An R6 that changed during the build would make the
lineage a claim rather than a record.

The active state must be empty, because a revision that inherits a sealed
verdict has not re-run anything. It has copied a conclusion.

And no R6 approval may authorise an R7 phase.

R7 adds a fourth. The R6 attempt that failed must still be there, exactly as
R6 wrote it, with the three wrong parameters legible in its plan. R7's claim
is that those parameters were wrong and are now right; that claim is only
checkable if the wrong ones survive.
"""

import json
import os
import unittest

from automation import attempts, hashing, path_policy, policy, state_machine
from automation.package_tests import (compact_lineage_record,
                                      generation_root,
                                      inherited_lineage_root)

ROOT = path_policy.LEVEL1_ROOT
STATE = os.path.join(ROOT, "state")
LINEAGE = os.path.join(ROOT, "lineage")
R6_ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6"

# R8 retarget. These constants pointed inside R8's own `lineage/`, because R7
# carried a complete physical copy of R6 there. R8 carries a hash-bound
# reference instead -- 555 MiB duplicated to answer a question a digest
# already answers -- so the same bytes are reached through the predecessor's
# lineage tree, resolved and digest-checked by `inherited_lineage_root`.
#
# Every assertion below is unchanged and is made against the same bytes. What
# changed is where those bytes live, and that the path is now verified before
# it is read rather than assumed because it is local.
INHERITED_LINEAGE = inherited_lineage_root()
R6_COPY = os.path.join(INHERITED_LINEAGE, "R6_EXECUTION")
R6_MANIFEST = os.path.join(INHERITED_LINEAGE, "R6_EXECUTION_MANIFEST.sha256")

R6_SEALED_ERROR = {
    "evidence/L1-A31/RUN-A/EVIDENCE_MANIFEST.sha256":
        "4a185eefb4f4221419a6cc7e53c2fe9b59c721c2def2bbb26864752013c1a85e",
    "evidence/L1-A31/RUN-A/SEAL.json":
        "fcfeb8947fdb9c2bf01e6d0007a7adddbf4f5ec5138a78580e2dead622323edc",
    "results/L1-A31/RUN-A/plan.json":
        "794a7d588112ad4a68ee594378611ad196f71f7c05b7fc1c71c6d0baa4ea7be8",
}


def load_state(name):
    with open(os.path.join(STATE, name), encoding="utf-8") as handle:
        return json.load(handle)


class PredecessorIsIntact(unittest.TestCase):

    def test_the_sibling_r6_is_not_a_symlink(self):
        self.assertTrue(os.path.isdir(R6_ROOT))
        self.assertFalse(os.path.islink(R6_ROOT))

    def test_the_lineage_copy_is_byte_identical_to_r6(self):
        """Compared through the manifest, not by trusting the copy."""
        rows = {}
        with open(R6_MANIFEST, encoding="utf-8") as handle:
            for line in handle:
                digest, relative = line.rstrip("\n").split("  ", 1)
                rows[relative] = digest
        self.assertEqual(len(rows), 15153)
        source_count = sum(len(files) for _, _, files in os.walk(R6_ROOT))
        self.assertEqual(source_count, len(rows),
                         "the copy enumerates a different number of files "
                         "than R6 contains")
        differences = []
        for relative, digest in rows.items():
            copied = os.path.join(R6_COPY, relative)
            original = os.path.join(R6_ROOT, relative)
            if not os.path.isfile(copied):
                differences.append((relative, "MISSING"))
            elif hashing.sha256_file(copied) != digest:
                differences.append((relative, "COPY_CHANGED"))
            elif hashing.sha256_file(original) != digest:
                differences.append((relative, "PREDECESSOR_CHANGED"))
        self.assertEqual(differences, [])

    def test_nothing_in_the_copy_is_absent_from_r6(self):
        extra = []
        for dirpath, _, filenames in os.walk(R6_COPY):
            for name in filenames:
                full = os.path.join(dirpath, name)
                relative = os.path.relpath(full, R6_COPY)
                if not os.path.isfile(os.path.join(R6_ROOT, relative)):
                    extra.append(relative)
        self.assertEqual(extra, [],
                         "the lineage copy contains files R6 does not have")


class R6FailedAttemptIsPreserved(unittest.TestCase):
    """The sealed ERROR is evidence and is carried forward unedited."""

    def test_the_seal_and_manifest_are_the_bytes_r6_wrote(self):
        for relative, expected in R6_SEALED_ERROR.items():
            self.assertEqual(hashing.sha256_file(
                os.path.join(R6_COPY, relative)), expected, relative)

    def test_the_wrong_parameters_are_still_legible_in_the_failed_plan(self):
        """R7's correction is only checkable if the defect survives."""
        with open(os.path.join(R6_COPY, "results", "L1-A31", "RUN-A",
                               "plan.json"), encoding="utf-8") as handle:
            plan = json.load(handle)
        steps = {step["step_id"]: step for step in plan["steps"]}
        self.assertEqual(steps["vhn_chain"]["params"]["purpose"], "smimesign")
        self.assertEqual(
            steps["synthetic_chain_positive"]["params"]["attime"], 1787000000)
        self.assertIn("vhn_leaf_one_byte_mutated.pem",
                      steps["mutated_vhn_leaf"]["params"]["leaf"])

    def test_the_error_output_that_proves_each_defect_is_preserved(self):
        base = os.path.join(R6_COPY, "evidence", "L1-A31", "RUN-A", "stderr")
        def read(name):
            with open(os.path.join(base, name), encoding="utf-8") as handle:
                return handle.read()
        # F1, on the positive control and on the real chain alike.
        self.assertIn("unsuitable certificate purpose",
                      read("L1-A31-RUN-A-E0007.txt"))
        self.assertIn("unsuitable certificate purpose",
                      read("L1-A31-RUN-A-E0009.txt"))
        # F2, the epoch before the control fixture's own notBefore.
        self.assertIn("certificate is not yet valid",
                      read("L1-A31-RUN-A-E0007.txt"))
        # F3, a parse refusal rather than a signature failure.
        self.assertIn("Could not find certificate file",
                      read("L1-A31-RUN-A-E0013.txt"))

    def test_the_lineage_classifies_r6_by_its_proven_root_cause(self):
        with open(os.path.join(INHERITED_LINEAGE,
                               "R6_LINEAGE_CLASSIFICATION.json"),
                  encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(
            record["classification"],
            "SUPERSEDED_AFTER_SEALED_INTERNAL_PLAN_ERROR_AND_NO_ATTEMPT_"
            "RETRY_MODEL")
        self.assertFalse(record["predecessor_mutated_by_r7_build"])
        self.assertFalse(
            record["raw_r6_freeze_token_copied_into_new_active_evidence"])
        self.assertEqual(record["complete_copy_file_count"], 15153)

    def test_the_whole_chain_back_to_r4_is_reachable(self):
        # R8 is the active root now; R7 is reached by crossing to the
        # recorded predecessor, and R6 by descending into R7's own copy.
        # The chain is the assertion, not any one revision's name.
        self.assertEqual(generation_root("R8"), ROOT)
        self.assertEqual(
            generation_root("R7"),
            compact_lineage_record()["r7"]["root"])
        self.assertEqual(generation_root("R6"), R6_COPY)
        self.assertTrue(os.path.isdir(generation_root("R5")))
        self.assertTrue(os.path.isdir(
            os.path.join(generation_root("R5"), "lineage", "R4_EXECUTION")))


class FreshActiveState(unittest.TestCase):

    def test_the_revision_record_is_r8_from_r7(self):
        record = load_state("REVISION.json")
        self.assertEqual(record["revision"], "R8")
        self.assertEqual(record["predecessor"], "R7")
        # R8's lineage is a record, not a copied tree. The record is what the
        # revision points at, and it must be a file that exists.
        self.assertEqual(record["lineage_path"], "lineage/R8_LINEAGE.json")
        self.assertTrue(os.path.isfile(
            os.path.join(ROOT, record["lineage_path"])))
        self.assertEqual(record["predecessor_root"],
                         compact_lineage_record()["r7"]["root"])
        self.assertEqual(record["platform"], "UBUNTU")
        self.assertEqual(record["predecessor_state_disposition"],
                         "HISTORICAL_ONLY_PRESERVED_IN_LINEAGE_NOT_ACTIVE")
        self.assertIn("NONE", record["predecessor_approvals_authority"])

    def test_all_43_phases_are_not_started_without_verdicts(self):
        progress = load_state("progress.json")
        nodes = [node for audit in progress["audits"].values()
                 for node in audit.values()]
        self.assertEqual(len(nodes), 43)
        self.assertEqual(len(progress["audits"]), 35)
        self.assertTrue(all(node["state"] == "NOT_STARTED" for node in nodes))
        self.assertTrue(all("verdict" not in node for node in nodes))

    def test_no_attempt_is_inherited(self):
        """R6's sealed attempt is lineage, not an R7 attempt."""
        progress = load_state("progress.json")
        for audit in progress["audits"].values():
            for node in audit.values():
                self.assertNotIn("attempts", node)
                self.assertIsNone(attempts.current_attempt_number(node))
                self.assertIsNone(attempts.accepted_attempt_number(node))

    def test_no_approval_or_freeze_attempt_is_inherited(self):
        self.assertEqual(
            os.path.getsize(os.path.join(STATE, "approvals.jsonl")), 0)
        self.assertFalse(
            os.path.exists(os.path.join(STATE, "freeze_attempts.jsonl")))

    def test_the_active_evidence_and_results_trees_are_empty(self):
        for tree in ("evidence", "results"):
            self.assertEqual(os.listdir(os.path.join(ROOT, tree)), [], tree)

    def test_controller_initialisation_is_the_only_transition(self):
        with open(os.path.join(STATE, "transitions.jsonl"),
                  encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["route"], "init-revision")
        self.assertEqual(rows[0]["binding"]["revision"], "R8")
        self.assertEqual(rows[0]["binding"]["predecessor"], "R7")
        self.assertEqual(rows[0]["binding"]["phases_initialised"], 43)

    def test_the_state_was_not_hand_written(self):
        """Every phase's presence is accounted for by the journal."""
        record = load_state("REVISION.json")
        self.assertEqual(record["phases_initialised"], 43)
        self.assertEqual(record["mode_at_initialisation"],
                         "GENERATED_UNVERIFIED")


class R8IsTheFinalRevision(unittest.TestCase):
    """The finality rule, stated as a rule rather than as a revision name.

    This class asserted that R7 was final and that no R8 existed. Both were
    true when written; the human authorised R8 on 2026-08-28 after the frozen
    execution-engine defect was measured, and the assertions then failed for
    the one reason a test must never fail -- the thing they named changed
    while the property they protected did not.

    The property is that the package declares exactly one final revision,
    grants itself no budget past it, and that nothing beyond it exists on
    disk. The successor is derived from the declared final revision, so this
    goes on meaning what it means whatever that revision is called.
    """

    def test_the_package_declares_itself_final(self):
        from automation import freeze
        self.assertEqual(policy.FINAL_REVISION, "R8")
        self.assertEqual(policy.MAX_REVISION_ESCALATIONS_AFTER_R8, 0)
        # R7 escalated exactly once, by human authorisation. One, not an
        # open door.
        self.assertEqual(policy.MAX_REVISION_ESCALATIONS_AFTER_R7, 1)
        self.assertEqual(freeze.PACKAGE_REVISION, "R8")
        self.assertEqual(freeze.PACKAGE_PLATFORM, "UBUNTU")

    def test_the_freeze_reads_its_predecessor_baseline_from_its_own_package(self):
        """The rule is "read only your own package", not "read R6".

        R7 satisfied it by carrying a complete copy of R6 and reading the
        baseline out of that. R8 carries the baseline itself -- one 12 KiB
        file, byte-identical to R7's, digest recorded in the lineage record --
        so the rule holds and the 555 MiB copy does not have to.
        """
        from automation import freeze
        self.assertEqual(freeze.PREDECESSOR_BASELINE_REL,
                         os.path.join("lineage",
                                      "R7_BASELINE_MANIFEST.json"))
        resolved = os.path.join(ROOT, freeze.PREDECESSOR_BASELINE_REL)
        self.assertTrue(os.path.isfile(resolved))
        # It must be the predecessor's own baseline, byte for byte, and the
        # digest the lineage record already published is what says so.
        self.assertEqual(
            hashing.sha256_file(resolved),
            compact_lineage_record()["r7"]["baseline_manifest_sha256"])

    def test_no_revision_beyond_the_final_one_was_created(self):
        successor = "R%d" % (int(policy.FINAL_REVISION[1:]) + 1)
        siblings = os.listdir(os.path.dirname(ROOT))
        self.assertNotIn("08.18.26_Level1_Audits_" + successor, siblings,
                         "%s is the final revision" % policy.FINAL_REVISION)
        # And the package it does declare is the one we are running in.
        self.assertIn("08.18.26_Level1_Audits_" + policy.FINAL_REVISION,
                      siblings)

    def test_the_attempt_model_is_present_and_bounded(self):
        self.assertEqual(policy.MAX_ATTEMPTS_PER_PHASE, 3)
        self.assertEqual(policy.MAX_REPAIRS_PER_ROOT_CAUSE, 2)
        self.assertEqual(policy.MAX_DISTINCT_INTERNAL_REPAIRS, 6)
        self.assertIn("RETRYABLE_INTERNAL_ERROR", state_machine.STATES)
        self.assertIn("BLOCKED_FOR_EXTERNAL_MATERIAL", state_machine.STATES)
        for retryable in state_machine.RETRYABLE_AGGREGATE_STATES:
            self.assertNotIn(retryable, state_machine.TERMINAL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
