"""R6 lineage and controller-owned fresh-state regression tests."""

import json
import os
import unittest

from automation import freeze, hashing, path_policy
from automation.package_tests import generation_root


# R7. As with the R5 module: these are R6's facts, asserted at the root where
# R6 was the active revision, which is now `lineage/R6_EXECUTION`.
ROOT = generation_root("R6")
STATE = os.path.join(ROOT, "state")
LINEAGE = os.path.join(ROOT, "lineage")
R5_ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5"
R5_COPY = os.path.join(LINEAGE, "R5_EXECUTION")
R5_MANIFEST = os.path.join(LINEAGE, "R5_EXECUTION_MANIFEST.sha256")

R5_EXPECTED = {
    "BASELINE_MANIFEST.json":
        "0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d",
    "CONTROL_MANIFEST.sha256":
        "55e702a63e074bf34cdbedb441fcdf9ec3db9356e2d58da80d23a2aceea98176",
    "state/PACKAGE_VERIFIED.json":
        "54bda59541ccb9d933c4e16d821d04f3dd353c55150730ebc3953c498b5d6344",
    "MODE":
        "67885f01edc72c2991b2ae9be04afc14a743b79c9d382262620be8ac154fa5fa",
}


def load_state(name):
    with open(os.path.join(STATE, name), encoding="utf-8") as handle:
        return json.load(handle)


class PredecessorLineage(unittest.TestCase):

    def test_r5_checkpoint_hashes_are_unchanged(self):
        for relative, expected in R5_EXPECTED.items():
            self.assertEqual(hashing.sha256_file(os.path.join(R5_ROOT, relative)),
                             expected, relative)

    def test_complete_lineage_manifest_verifies_all_r5_files(self):
        rows = {}
        with open(R5_MANIFEST, encoding="utf-8") as handle:
            for line in handle:
                digest, relative = line.rstrip("\n").split("  ", 1)
                rows[relative] = digest
        self.assertEqual(len(rows), 14439)
        source_count = sum(len(files) for _, _, files in os.walk(R5_ROOT))
        self.assertEqual(source_count, len(rows))
        differences = []
        for relative, digest in rows.items():
            copied = os.path.join(LINEAGE, relative)
            if not os.path.isfile(copied):
                differences.append((relative, "MISSING"))
            elif hashing.sha256_file(copied) != digest:
                differences.append((relative, "CHANGED"))
        self.assertEqual(differences, [])

    def test_r5_is_classified_with_the_proven_root_cause(self):
        path = os.path.join(LINEAGE, "R5_LINEAGE_CLASSIFICATION.json")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(
            record["classification"],
            "SUPERSEDED_INVALID_FREEZE_MODE_MANIFEST_ORDERING")
        self.assertFalse(record["predecessor_mutated_by_r6_build"])

    def test_r5_defect_is_reproduced_inside_lineage(self):
        report = freeze.verify_manifest_from_disk(R5_COPY)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(report["missing_count"], 0)
        self.assertEqual(report["failed"][0]["path"], "MODE")

    def test_r5_runtime_history_is_preserved(self):
        for relative in ("state/freeze_attempts.jsonl",
                         "state/PACKAGE_VERIFIED.json",
                         "verification_claude_3/VERIFICATION_RESULT.json",
                         "build/freeze_plan_attempt_3/FREEZE_PLAN_R5_ATTEMPT_3.json"):
            self.assertTrue(os.path.isfile(os.path.join(R5_COPY, relative)),
                            relative)


class R6RevisionRecord(unittest.TestCase):
    """What R6 was when it was initialised, still true of its own root."""

    def test_revision_record_is_r6_from_r5(self):
        record = load_state("REVISION.json")
        self.assertEqual(record["revision"], "R6")
        self.assertEqual(record["predecessor"], "R5")
        self.assertEqual(record["lineage_path"], "lineage/R5_EXECUTION")
        self.assertEqual(record["platform"], "UBUNTU")
        self.assertEqual(record["phases_initialised"], 43)
        self.assertEqual(record["audits_initialised"], 35)
        self.assertEqual(record["mode_at_initialisation"],
                         "GENERATED_UNVERIFIED")

    def test_the_journal_begins_with_exactly_one_initialisation(self):
        """R6's history starts once, through the controller, and only there."""
        rows = _transitions()
        self.assertEqual(rows[0]["route"], "init-revision")
        self.assertEqual(rows[0]["binding"]["revision"], "R6")
        self.assertEqual(rows[0]["binding"]["phases_initialised"], 43)
        self.assertEqual(
            [r for r in rows if r["route"] == "init-revision"], [rows[0]])

    def test_r6_was_frozen(self):
        with open(os.path.join(ROOT, "MODE"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "FROZEN\n")


class R6EndedOnASealedInfrastructureError(unittest.TestCase):
    """The exact history R7 exists to supersede, pinned so it cannot drift.

    R7 note. This class replaces four assertions that used to describe a
    freshly initialised revision — 43 phases NOT_STARTED, an empty approvals
    journal, a single transition, MODE GENERATED_UNVERIFIED. Every one of them
    was true of R6 on the day it was built and none of them is true of R6 now,
    because R6 ran. They are R7's assertions today and they live in
    test_r7_initialisation.py, made against the active root.

    What is worth holding here instead is what actually happened to R6, in the
    detail that justifies R7's existence: one phase was prepared, approved,
    executed and sealed with verdict ERROR, and the state machine had nowhere
    to put it afterwards.
    """

    def test_exactly_one_phase_was_ever_prepared(self):
        progress = load_state("progress.json")
        started = {(audit_id, phase): node
                   for audit_id, phases in progress["audits"].items()
                   for phase, node in phases.items()
                   if node["state"] != "NOT_STARTED"}
        self.assertEqual(list(started), [("L1-A31", "RUN-A")])

    def test_that_phase_sealed_an_error_and_the_phase_was_over(self):
        progress = load_state("progress.json")
        node = progress["audits"]["L1-A31"]["RUN-A"]
        self.assertEqual(node["state"], "SEALED")
        self.assertEqual(node["verdict"], "ERROR")
        # R6's own state machine: SEALED had no exit at all, so the phase
        # could not be attempted again. That is the defect, not the ERROR.
        self.assertEqual(
            freeze_lineage_state_machine().TRANSITIONS["SEALED"], ())

    def test_the_sealed_evidence_is_exactly_the_bytes_r6_sealed(self):
        base = os.path.join(ROOT, "evidence", "L1-A31", "RUN-A")
        self.assertEqual(
            hashing.sha256_file(os.path.join(base, "EVIDENCE_MANIFEST.sha256")),
            "4a185eefb4f4221419a6cc7e53c2fe9b59c721c2def2bbb26864752013c1a85e")
        self.assertEqual(
            hashing.sha256_file(os.path.join(base, "SEAL.json")),
            "fcfeb8947fdb9c2bf01e6d0007a7adddbf4f5ec5138a78580e2dead622323edc")

    def test_the_failed_plan_is_preserved_with_its_wrong_parameters(self):
        """The three defects, read from the sealed plan rather than described."""
        path = os.path.join(ROOT, "results", "L1-A31", "RUN-A", "plan.json")
        self.assertEqual(
            hashing.sha256_file(path),
            "794a7d588112ad4a68ee594378611ad196f71f7c05b7fc1c71c6d0baa4ea7be8")
        with open(path, encoding="utf-8") as handle:
            plan = json.load(handle)
        steps = {step["step_id"]: step for step in plan["steps"]}
        # F1: one purpose for two structurally different certificate chains.
        self.assertEqual(steps["vhn_chain"]["params"]["purpose"], "smimesign")
        # F2: the positive control's epoch, six days before its own notBefore.
        self.assertEqual(
            steps["synthetic_chain_positive"]["params"]["attime"], 1787000000)
        # F3: the mutation fixture the plan named.
        self.assertIn("vhn_leaf_one_byte_mutated.pem",
                      steps["mutated_vhn_leaf"]["params"]["leaf"])

    def test_only_one_approval_was_ever_recorded(self):
        path = os.path.join(STATE, "approvals.jsonl")
        with open(path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["audit_id"], "L1-A31")
        self.assertEqual(rows[0]["run_phase"], "RUN-A")

    def test_r6_never_reached_run_b_or_comparison(self):
        progress = load_state("progress.json")
        for phase in ("RUN-B", "COMPARISON"):
            self.assertEqual(
                progress["audits"]["L1-A31"][phase]["state"], "NOT_STARTED")


def _transitions():
    with open(os.path.join(STATE, "transitions.jsonl"),
              encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def freeze_lineage_state_machine():
    """R6's own state_machine module, loaded from R6's own bytes.

    Not this package's. The claim being pinned is about what R6's table said,
    and reading R7's table to make it would prove nothing about R6.
    """
    import importlib.util

    path = os.path.join(ROOT, "automation", "state_machine.py")
    spec = importlib.util.spec_from_file_location("r6_state_machine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main(verbosity=2)
