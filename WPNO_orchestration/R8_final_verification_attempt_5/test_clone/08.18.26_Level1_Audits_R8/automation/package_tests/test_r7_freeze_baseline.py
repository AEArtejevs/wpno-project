"""The freeze mechanism's outputs, asserted rather than assumed.

`automation.freeze` refuses a baseline count below one, with the reason
written into the error: a baseline of zero files attests to nothing. Nothing
tested that refusal, and nothing tested that the builder actually produces a
populated baseline on this machine. Both are asserted here.

The independent pre-freeze verification looked for exactly this and did not
find it. It was right that it was missing.

Nothing here freezes anything. `final_state_manifest` is a pure function: it
is given the bytes a freeze would publish and returns the manifest that freeze
would write, without writing one. That is what makes it testable before the
event rather than after.
"""

import copy
import json
import os
import unittest

from automation import freeze, hashing, path_policy, policy

ROOT = path_policy.LEVEL1_ROOT

# What the predecessor baseline declares, and what a populated baseline on this
# machine therefore has to contain.
EXPECTED_PROJECT_MEMBERS = 33
EXPECTED_DISCOVERY_MEMBERS = 26


class BaselineIsNonEmpty(unittest.TestCase):
    def setUp(self):
        expected = hashing.sha256_file(
            os.path.join(ROOT, freeze.PREDECESSOR_BASELINE_REL))
        self.baseline, self.provenance = freeze.build_baseline_from_predecessor(
            ROOT, expected)

    def test_the_baseline_builds_at_all(self):
        self.assertIn("project_files", self.baseline)
        self.assertIn("discovery_files", self.baseline)

    def test_the_project_baseline_is_not_empty(self):
        self.assertGreater(len(self.baseline["project_files"]), 0,
                           "a baseline of zero files attests to nothing")
        self.assertEqual(len(self.baseline["project_files"]),
                         EXPECTED_PROJECT_MEMBERS)
        self.assertEqual(self.provenance["project_members"],
                         EXPECTED_PROJECT_MEMBERS)

    def test_the_discovery_baseline_is_not_empty(self):
        self.assertGreater(len(self.baseline["discovery_files"]), 0,
                           "a baseline of zero files attests to nothing")
        self.assertEqual(len(self.baseline["discovery_files"]),
                         EXPECTED_DISCOVERY_MEMBERS)
        self.assertEqual(self.provenance["discovery_members"],
                         EXPECTED_DISCOVERY_MEMBERS)

    def test_every_member_was_rehashed_here_and_matched(self):
        self.assertTrue(self.provenance["every_member_rehashed_on_ubuntu"])
        self.assertTrue(
            self.provenance["every_member_equals_predecessor_digest"])
        self.assertEqual(self.provenance["members_added_beyond_predecessor"], 0)
        self.assertEqual(self.provenance["members_dropped"], 0)

    def test_membership_comes_from_the_predecessor_baseline(self):
        self.assertEqual(self.provenance["membership_source"],
                         "PREDECESSOR_VERIFIED_BASELINE")

    def test_the_baseline_serialises_deterministically(self):
        first = freeze.serialize_baseline(self.baseline)
        second = freeze.serialize_baseline(self.baseline)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)


class ZeroBaselineIsRefused(unittest.TestCase):
    """The counter-proof: the shape check must reject what it says it rejects."""

    def plan(self, **overrides):
        base = {
            "schema": "wpno.level1.freeze-plan/2",
            "revision": freeze.PACKAGE_REVISION,
            "platform": freeze.PACKAGE_PLATFORM,
            "attempt_number": 1,
            "package_sha256": "a" * 64,
            "verification_result_sha256": "b" * 64,
            "baseline_preview_sha256": "c" * 64,
            "expected_project_baseline_count": EXPECTED_PROJECT_MEMBERS,
            "expected_discovery_baseline_count": EXPECTED_DISCOVERY_MEMBERS,
            "bound_artifacts": {},
            "predecessor_baseline_manifest_sha256": "d" * 64,
            "predecessor_baseline_manifest_path":
                freeze.PREDECESSOR_BASELINE_REL,
        }
        base.update(overrides)
        return base

    def test_a_well_formed_plan_is_accepted(self):
        self.assertTrue(freeze.assert_package_plan_shape(self.plan()))

    def test_a_zero_project_baseline_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as caught:
            freeze.assert_package_plan_shape(
                self.plan(expected_project_baseline_count=0))
        self.assertIn("attests to nothing", str(caught.exception))

    def test_a_zero_discovery_baseline_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as caught:
            freeze.assert_package_plan_shape(
                self.plan(expected_discovery_baseline_count=0))
        self.assertIn("attests to nothing", str(caught.exception))

    def test_a_negative_baseline_is_refused(self):
        with self.assertRaises(freeze.FreezeError):
            freeze.assert_package_plan_shape(
                self.plan(expected_project_baseline_count=-1))

    def test_a_boolean_is_not_a_count(self):
        """True == 1 in Python, and a boolean count is not a measurement."""
        with self.assertRaises(freeze.FreezeError):
            freeze.assert_package_plan_shape(
                self.plan(expected_project_baseline_count=True))

    def test_a_plan_for_another_revision_is_refused(self):
        with self.assertRaises(freeze.FreezeError):
            freeze.assert_package_plan_shape(self.plan(revision="R6"))


class FrozenManifestIsSelfConsistent(unittest.TestCase):
    """MODE is published last and the manifest still records FROZEN.

    R5 froze a package that failed its own control manifest on exactly one
    entry: the manifest was hashed from disk before MODE was rewritten, so it
    recorded the pre-freeze digest of a file the same freeze then changed.
    `final_state_manifest` takes the staged bytes instead, which is what makes
    the two consistent without publishing MODE first.
    """

    def setUp(self):
        self.staged = {"MODE": policy.MODE_FROZEN + "\n"}
        self.manifest = freeze.final_state_manifest(ROOT, self.staged)

    def test_mode_is_recorded_as_frozen_not_as_it_is_on_disk(self):
        self.assertIn("MODE", self.manifest)
        self.assertEqual(self.manifest["MODE"],
                         freeze.sha256_text(policy.MODE_FROZEN + "\n"))

    def test_the_on_disk_mode_still_says_generated_unverified(self):
        """Nothing was published; this test froze nothing."""
        with open(os.path.join(ROOT, "MODE"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "GENERATED_UNVERIFIED")

    def test_the_control_manifest_does_not_record_itself(self):
        self.assertNotIn(freeze.CONTROL_MANIFEST_REL, self.manifest)

    def test_no_runtime_directory_is_in_the_control_manifest(self):
        for relative in self.manifest:
            top = relative.split(os.sep)[0]
            self.assertNotIn(top, freeze.MUTABLE_SUBDIRS, relative)

    def test_the_control_manifest_covers_the_control_plane(self):
        """Coverage, asserted by membership rather than by a magnitude.

        This read `assertGreater(len(self.manifest), 1000)`. The number was
        never measured against anything: it was a stand-in for "the manifest
        is not obviously truncated", and it happened to hold in R7 because
        R7's manifest counted 15804 entries, most of them the copied lineage
        tree. R8 does not copy that tree, so the same package with the same
        control plane covered produces 711 entries and the literal fails --
        for a reason that has nothing to do with coverage.

        A count nobody measures is not evidence, and this file's own sibling
        module says so about a different literal. So the assertion is now
        about membership: every executable and every schema in the control
        plane is inside the manifest, which is the property the number was
        standing in for and is the one that would actually break if the
        manifest were truncated.
        """
        self.assertTrue(self.manifest)
        expected = []
        for directory in ("automation", "build"):
            base = os.path.join(ROOT, directory)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for name in filenames:
                    if not name.endswith((".py", ".json", ".sha256")):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
                    if rel in freeze.CONTROL_MANIFEST_REL:
                        continue
                    expected.append(rel)
        self.assertGreater(len(expected), 100)
        missing = [rel for rel in expected if rel not in self.manifest]
        self.assertEqual(missing, [], "control-plane files outside the "
                                      "manifest: %s" % missing[:10])

    def test_the_candidate_plans_are_inside_the_control_manifest(self):
        """Which is why all 43 had to exist before the freeze, not after."""
        planned = [r for r in self.manifest
                   if r.startswith(os.path.join("build", "candidate_plans_r8"))]
        self.assertGreaterEqual(len(planned), 43)

    def test_no_freeze_artefact_exists_yet(self):
        self.assertTrue(freeze.assert_no_freeze_artefact(ROOT))


class TokenBindingAndReplay(unittest.TestCase):
    def test_the_token_binds_three_digests(self):
        token = freeze.token_for("a" * 64, "b" * 64, "c" * 64)
        parsed = freeze.parse_freeze_token(token)
        self.assertEqual(parsed["package_sha256"], "a" * 64)
        self.assertEqual(parsed["verification_sha256"], "b" * 64)
        self.assertEqual(parsed["freeze_plan_sha256"], "c" * 64)

    def test_a_four_field_token_is_refused_on_its_shape(self):
        with self.assertRaises(freeze.FreezeError):
            freeze.parse_freeze_token(
                "FREEZE-LEVEL1 PACKAGE-SHA256=%s VERIFICATION-SHA256=%s "
                "RUN-ONCE" % ("a" * 64, "b" * 64))

    def test_a_token_for_another_plan_is_refused(self):
        plan = {"package_sha256": "a" * 64,
                "verification_result_sha256": "b" * 64}
        parsed = freeze.parse_freeze_token(
            freeze.token_for("a" * 64, "b" * 64, "c" * 64))
        with self.assertRaises(freeze.FreezeError) as caught:
            freeze.assert_token_binds_plan(parsed, plan, "d" * 64)
        self.assertIn("FREEZE_PLAN_MISMATCH", str(caught.exception))

    def test_no_freeze_attempt_has_been_recorded(self):
        ledger = os.path.join(ROOT, "state", "freeze_attempts.jsonl")
        self.assertEqual(freeze.recorded_attempts(ledger), [],
                         "a freeze attempt is already on the ledger")
