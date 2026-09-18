"""R5 revision initialisation and lineage.

Three things have to be true at once for the R5 active state to mean anything.

The predecessor must be intact, because R4 is the historical evidence this
revision supersedes and an R4 that changed during the build would make the
lineage a claim rather than a record.

The active state must be empty, because a revision that inherits a sealed
verdict has not re-run anything — it has copied a conclusion.

And no R4 approval may authorise an R5 phase. An approval token is bound to a
plan; a token carried across revisions would approve a plan nobody read.
"""

import json
import os
import unittest

from automation import path_policy, state_machine

STATE = os.path.join(path_policy.LEVEL1_ROOT, "state")
LINEAGE = os.path.join(path_policy.LEVEL1_ROOT, "lineage")
R4_ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4"

R4_EXPECTED = {
    "CONTROL_MANIFEST.sha256":
        "4b9d44f256975f7211dc37dbd382d8c3737b02abd1211fec3ea1fe78a1f1cb9f",
    "BASELINE_MANIFEST.json":
        "0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d",
    "state/PACKAGE_VERIFIED.json":
        "52254365d8bdb53688ab0e0c9752db29a7f856018baf005d76b4cdf99f6b5caf",
}

REQUIRED_NOT_STARTED = ("L1-A18", "L1-A31", "L1-A34")


def load(name):
    with open(os.path.join(STATE, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestPredecessorUnchanged(unittest.TestCase):
    def test_r4_checkpoint_hashes_still_match(self):
        from automation import hashing
        for rel, expected in R4_EXPECTED.items():
            actual = hashing.sha256_file(os.path.join(R4_ROOT, rel))
            self.assertEqual(actual, expected, "R4 changed: %s" % rel)

    def test_r4_still_has_its_recorded_file_count(self):
        count = sum(len(files) for _, _, files in os.walk(R4_ROOT))
        self.assertEqual(count, 2238)

    def test_r4_is_not_a_symlink(self):
        self.assertFalse(os.path.islink(R4_ROOT))


class TestLineage(unittest.TestCase):
    def test_the_lineage_copy_is_byte_identical_to_r4(self):
        """Compared through the manifest, not by trusting the copy."""
        from automation import hashing
        manifest = os.path.join(LINEAGE, "R4_EXECUTION_MANIFEST.sha256")
        root = os.path.join(LINEAGE, "R4_EXECUTION")
        expected = hashing.read_manifest(manifest)
        self.assertEqual(len(expected), 2238)
        differences = []
        for rel, digest in expected.items():
            target = os.path.join(root, rel)
            if not os.path.exists(target):
                differences.append((rel, "MISSING"))
            elif hashing.sha256_file(target) != digest:
                differences.append((rel, "CHANGED"))
        self.assertEqual(differences, [])

    def test_the_lineage_is_classified_as_superseded(self):
        with open(os.path.join(LINEAGE, "R4_LINEAGE_CLASSIFICATION.json"),
                  encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertEqual(
            record["classification"],
            "HISTORICAL_R4_EXECUTION_SUPERSEDED_BY_R5_REMEDIATION")
        self.assertFalse(record["r4_mutated_by_r5_build"])

    def test_the_lineage_preserves_the_runtime_history(self):
        """Every runtime file R4 has, the lineage has.

        The expected set is read from R4 rather than typed out here. A typed
        list is a second source of truth, and the first version of this test
        proved the point by asserting a `results/L1-A31/RUN-A/verdict.json`
        that R4 never produced — RUN-A ended ERROR before writing one. The
        lineage was right and the test was wrong.
        """
        root = os.path.join(LINEAGE, "R4_EXECUTION")
        for tree in ("state", "results", "evidence", "work", "logs"):
            expected = set()
            base = os.path.join(R4_ROOT, tree)
            for dirpath, _, files in os.walk(base):
                for name in files:
                    expected.add(os.path.relpath(
                        os.path.join(dirpath, name), R4_ROOT))
            self.assertTrue(expected, "R4 tree %s is empty" % tree)
            missing = [rel for rel in sorted(expected)
                       if not os.path.exists(os.path.join(root, rel))]
            self.assertEqual(missing, [], "lineage is missing %r" % missing[:5])

    def test_the_lineage_preserves_every_seal_and_its_verdict(self):
        root = os.path.join(LINEAGE, "R4_EXECUTION")
        expected = {
            ("L1-A18", "RUN-A"): "BLOCKED",
            ("L1-A31", "RUN-A"): "ERROR",
            ("L1-A31", "RUN-B"): "BLOCKED",
            ("L1-A31", "COMPARISON"): "ERROR",
            ("L1-A34", "RUN-A"): "ERROR",
            ("L1-A34", "RUN-B"): "BLOCKED",
            ("L1-A34", "COMPARISON"): "UNVERIFIED",
        }
        for (audit, phase), verdict in expected.items():
            path = os.path.join(root, "evidence", audit, phase, "SEAL.json")
            self.assertTrue(os.path.exists(path), path)
            with open(path, encoding="utf-8") as fh:
                seal = json.load(fh)
            self.assertEqual(seal["verdict"], verdict, "%s %s" % (audit, phase))

    def test_l1_a18_run_b_and_comparison_were_never_started(self):
        root = os.path.join(LINEAGE, "R4_EXECUTION")
        for phase in ("RUN-B", "COMPARISON"):
            self.assertFalse(
                os.path.exists(os.path.join(root, "evidence", "L1-A18", phase)),
                "L1-A18 %s should have no evidence directory" % phase)

    def test_every_migrated_record_is_byte_equal(self):
        path = os.path.join(LINEAGE, "R4_TO_R5_MIGRATION_INVENTORY.jsonl")
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["equality"], "EQUAL", row["r4_path"])
            self.assertEqual(row["r4_sha256"], row["r5_sha256"])
            self.assertTrue(row["role"])
            self.assertTrue(row["audit_ids"])

    def test_the_migration_covers_the_reuse_list(self):
        path = os.path.join(LINEAGE, "R4_TO_R5_MIGRATION_INVENTORY.jsonl")
        with open(path, encoding="utf-8") as fh:
            paths = [json.loads(l)["r4_path"] for l in fh if l.strip()]
        joined = "\n".join(paths)
        for required in ("references/REF-08", "references/REF-09",
                         "references/REF-11", "references/manifest.json",
                         "MAIL_EML_EVIDENCE", "ZIP_ENTRY_HASH_INVENTORY",
                         "P7S_CMS_PARSE_EVIDENCE", "bindings/L1-A31",
                         "bindings/L1-A34", "bindings/L1-A18"):
            self.assertIn(required, joined, "reuse item missing: %s" % required)


class TestFreshActiveState(unittest.TestCase):
    def test_the_revision_record_names_r5_and_ubuntu(self):
        record = load("REVISION.json")
        self.assertEqual(record["revision"], "R5")
        self.assertEqual(record["predecessor"], "R4")
        self.assertEqual(record["platform"], "UBUNTU")

    def test_r4_approvals_do_not_authorise_r5(self):
        record = load("REVISION.json")
        self.assertIn("HISTORICAL_ONLY",
                      record["predecessor_state_disposition"])
        self.assertIn("NONE", record["predecessor_approvals_authority"])

    def test_the_three_remediated_audits_start_not_started(self):
        progress = load("progress.json")
        for audit in REQUIRED_NOT_STARTED:
            for phase in ("RUN-A", "RUN-B", "COMPARISON"):
                self.assertEqual(
                    progress["audits"][audit][phase]["state"], "NOT_STARTED",
                    "%s %s did not start NOT_STARTED" % (audit, phase))

    def test_every_other_audit_also_starts_not_started(self):
        progress = load("progress.json")
        for audit, phases in progress["audits"].items():
            for phase, node in phases.items():
                self.assertEqual(node["state"], "NOT_STARTED",
                                 "%s %s" % (audit, phase))

    def test_no_verdict_was_carried_over(self):
        progress = load("progress.json")
        for audit, phases in progress["audits"].items():
            for phase, node in phases.items():
                self.assertNotIn("verdict", node, "%s %s" % (audit, phase))

    def test_no_approval_was_carried_over(self):
        path = os.path.join(STATE, "approvals.jsonl")
        self.assertTrue(os.path.exists(path))
        self.assertEqual(os.path.getsize(path), 0)

    def test_the_only_transition_is_the_initialisation_itself(self):
        with open(os.path.join(STATE, "transitions.jsonl"),
                  encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["route"], "init-revision")
        self.assertEqual(rows[0]["to_state"], "NOT_STARTED")

    def test_the_state_was_not_hand_written(self):
        """Initialisation is a controller route and leaves a journal entry."""
        with open(os.path.join(STATE, "transitions.jsonl"),
                  encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        self.assertEqual(rows[0]["audit_id"], "PACKAGE")
        self.assertEqual(rows[0]["binding"]["revision"], "R5")

    def test_not_started_is_a_real_state(self):
        self.assertIn("NOT_STARTED", state_machine.STATES)
        self.assertFalse(state_machine.is_terminal("NOT_STARTED"))


class TestUbuntuNative(unittest.TestCase):
    def test_the_level1_root_is_the_r5_root(self):
        self.assertTrue(path_policy.LEVEL1_ROOT.endswith(
            "08.18.26_Level1_Audits_R5"))

    def test_no_macos_path_is_bound_into_the_new_active_state(self):
        for name in ("progress.json", "REVISION.json"):
            with open(os.path.join(STATE, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("/Users/", text, name)
            self.assertNotIn("/Volumes/", text, name)

    def test_every_bound_executable_exists_on_this_machine(self):
        from automation import policy
        for name, path in policy.EXECUTABLES.items():
            self.assertTrue(os.path.isabs(path), name)
            self.assertTrue(os.path.exists(path),
                            "%s is bound to %s which does not exist here"
                            % (name, path))

    def test_the_historical_evidence_keeps_its_macos_paths(self):
        """Lineage is not rewritten to look Ubuntu-native."""
        path = os.path.join(LINEAGE, "R4_EXECUTION", "state", "progress.json")
        with open(path, encoding="utf-8") as fh:
            self.assertIn("/Users/", fh.read())


if __name__ == "__main__":
    unittest.main()
