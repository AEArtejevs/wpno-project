"""R5 freeze mechanism repair: baseline, validator, driver.

Three blockers stopped freeze attempt 1, and these tests hold each repair in
place.

A. The baseline was built from absolute paths embedded in the bindings. Those
   are the Mac's paths. On Ubuntu every one of them resolves outside
   PROJECT_ROOT, so all 34 were excluded and `project_files` came out empty. A
   freeze on that preview would have sealed a BASELINE_MANIFEST attesting to
   nothing while looking complete. Membership now comes from the predecessor's
   verified baseline and every member is re-hashed from the real Ubuntu file.

B. The validator named four R4-only files and refused an R5 plan before
   comparing a single digest. It is now driven by the plan's own
   `bound_artifacts`.

C. There was no freeze driver at all. `controller freeze-level1` is it, and it
   verifies everything before it writes anything.

The driver's refusals are exercised against the live package on purpose: every
one of them must happen before the write stage, so a refusal test that touched
the real package would be a defect the test would catch. Each such test asserts
afterwards that no freeze artefact exists and MODE is unchanged.
"""

import io
import json
import os
import shutil
import unittest

from automation import controller, freeze, hashing, path_policy, policy

ROOT = path_policy.LEVEL1_ROOT
SANDBOX = os.path.join(ROOT, "work", "_freeze_selftest")

R4_BASELINE_SHA = "0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d"
EXPECTED_PROJECT = 33
EXPECTED_DISCOVERY = 26

FREEZE_ARTEFACTS = ("CONTROL_MANIFEST.sha256", "BASELINE_MANIFEST.json",
                    os.path.join("state", "PACKAGE_VERIFIED.json"))


def _predecessor():
    path = os.path.join(ROOT, freeze.PREDECESSOR_BASELINE_REL)
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


class BaselineFromPredecessor(unittest.TestCase):
    """Blocker A."""

    def setUp(self):
        self.baseline, self.provenance = freeze.build_baseline_from_predecessor(
            ROOT, R4_BASELINE_SHA)

    def test_the_ubuntu_baseline_is_not_empty(self):
        """The defect that stopped attempt 1: zero project files."""
        self.assertEqual(len(self.baseline["project_files"]), EXPECTED_PROJECT)
        self.assertEqual(len(self.baseline["discovery_files"]),
                         EXPECTED_DISCOVERY)

    def test_membership_comes_from_the_verified_predecessor_baseline(self):
        self.assertEqual(self.provenance["membership_source"],
                         "PREDECESSOR_VERIFIED_BASELINE")
        self.assertEqual(self.provenance["predecessor_baseline_sha256"],
                         R4_BASELINE_SHA)

    def test_no_mac_absolute_path_is_required_on_ubuntu(self):
        """Every recorded path is relative and none is a /Users path."""
        for key in ("project_files", "discovery_files"):
            for record in self.baseline[key]:
                self.assertFalse(os.path.isabs(record["path"]), record["path"])
                self.assertNotIn("/Users/", record["path"])

    def test_every_member_equals_the_predecessor_digest(self):
        old = _predecessor()
        for key in ("project_files", "discovery_files"):
            expected = {r["path"]: r["sha256"] for r in old[key]}
            actual = {r["path"]: r["sha256"] for r in self.baseline[key]}
            self.assertEqual(actual, expected, key)

    def test_nothing_was_added_or_dropped(self):
        self.assertEqual(self.provenance["members_added_beyond_predecessor"], 0)
        self.assertEqual(self.provenance["members_dropped"], 0)

    def test_an_unrelated_ubuntu_file_is_not_silently_added(self):
        """PROJECT_ROOT holds far more files than the baseline names."""
        project = self.provenance["project_root"]
        on_disk = sum(len(files) for _, _, files in os.walk(project))
        self.assertGreater(on_disk, EXPECTED_PROJECT * 5)
        self.assertEqual(len(self.baseline["project_files"]), EXPECTED_PROJECT)

    def test_a_drifting_predecessor_baseline_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.build_baseline_from_predecessor(ROOT, "f" * 64)
        self.assertIn("PREDECESSOR_BASELINE_DRIFT", str(ctx.exception))

    def test_serialization_is_deterministic(self):
        again, _ = freeze.build_baseline_from_predecessor(ROOT, R4_BASELINE_SHA)
        self.assertEqual(freeze.serialize_baseline(self.baseline),
                         freeze.serialize_baseline(again))


class BaselineRefusals(unittest.TestCase):
    """A missing, altered, traversing or symlinked member must raise.

    Built against a private copy of the predecessor baseline and a private
    source tree, so the real baseline and the real sources are never touched.
    """

    def setUp(self):
        self.dir = os.path.join(SANDBOX, "baseline")
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(os.path.join(self.dir, "src"))
        os.makedirs(os.path.join(self.dir, "disc"))
        os.makedirs(os.path.join(self.dir, "pkg", "lineage", "R4_EXECUTION"))
        self.pkg = os.path.join(self.dir, "pkg")
        with io.open(os.path.join(self.pkg, "paths.json"), "w",
                     encoding="utf-8") as fh:
            json.dump({"schema": "wpno.level1.paths/2",
                       "project_root": "../src",
                       "discovery_root": "../disc",
                       "level1_root": "."}, fh)
        self._write("src/kept.txt", "kept\n")
        self._write("disc/found.txt", "found\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, rel, text):
        full = os.path.join(self.dir, rel)
        with io.open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
        return hashing.sha256_text(text)

    def _baseline(self, project, discovery):
        payload = {"schema": "wpno.level1.baseline-manifest/1",
                   "scope": {},
                   "project_files": project,
                   "discovery_files": discovery}
        raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        path = os.path.join(self.pkg, freeze.PREDECESSOR_BASELINE_REL)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        return hashing.sha256_text(raw)

    def _disc(self):
        return [{"path": "found.txt",
                 "sha256": hashing.sha256_text("found\n")}]

    def _run(self, project, discovery=None):
        """discovery defaults to one valid member.

        A baseline with no Discovery members is refused in its own right, so a
        refusal test that left the list empty would pass for the wrong reason.
        """
        if discovery is None:
            discovery = self._disc()
        digest = self._baseline(project, discovery)
        return freeze.build_baseline_from_predecessor(self.pkg, digest)

    def test_the_happy_case_works(self):
        baseline, _ = self._run(
            [{"path": "kept.txt", "sha256": hashing.sha256_text("kept\n"),
              "state": "FILE"}],
            [{"path": "found.txt", "sha256": hashing.sha256_text("found\n")}])
        self.assertEqual(len(baseline["project_files"]), 1)
        self.assertEqual(len(baseline["discovery_files"]), 1)

    def test_a_missing_member_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "gone.txt", "sha256": "a" * 64,
                        "state": "FILE"}],
                      [{"path": "found.txt",
                        "sha256": hashing.sha256_text("found\n")}])
        self.assertIn("STOP_UBUNTU_SOURCE_BASELINE_NOT_EQUIVALENT",
                      str(ctx.exception))

    def test_a_hash_different_member_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "kept.txt", "sha256": "b" * 64,
                        "state": "FILE"}],
                      [{"path": "found.txt",
                        "sha256": hashing.sha256_text("found\n")}])
        self.assertIn("STOP_UBUNTU_SOURCE_BASELINE_NOT_EQUIVALENT",
                      str(ctx.exception))

    def test_path_traversal_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "../pkg/paths.json", "sha256": "c" * 64,
                        "state": "FILE"}])
        self.assertIn("PATH_ESCAPES_ROOT", str(ctx.exception))

    def test_an_absolute_member_path_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "/etc/hostname", "sha256": "c" * 64,
                        "state": "FILE"}])
        self.assertIn("PATH_NOT_RELATIVE", str(ctx.exception))

    def test_symlink_substitution_is_refused(self):
        """A link whose target has the right bytes is still refused."""
        link = os.path.join(self.dir, "src", "link.txt")
        os.symlink(os.path.join(self.dir, "src", "kept.txt"), link)
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "link.txt",
                        "sha256": hashing.sha256_text("kept\n"),
                        "state": "FILE"}])
        self.assertIn("SYMLINK_REFUSED", str(ctx.exception))

    def test_a_non_file_state_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([{"path": "kept.txt",
                        "sha256": hashing.sha256_text("kept\n"),
                        "state": "SYMLINK"}])
        self.assertIn("UNSUPPORTED_BASELINE_STATE", str(ctx.exception))

    def test_a_duplicate_member_is_refused(self):
        record = {"path": "kept.txt", "sha256": hashing.sha256_text("kept\n"),
                  "state": "FILE"}
        with self.assertRaises(freeze.FreezeError) as ctx:
            self._run([record, dict(record)])
        self.assertIn("DUPLICATE_BASELINE_MEMBER", str(ctx.exception))


class ValidatorIsRevisionAware(unittest.TestCase):
    """Blocker B."""

    def setUp(self):
        self.dir = os.path.join(SANDBOX, "validator")
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(os.path.join(self.dir, "sub"))
        self.digest = hashing.sha256_text("bound\n")
        with io.open(os.path.join(self.dir, "sub", "a.txt"), "w",
                     encoding="utf-8") as fh:
            fh.write("bound\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_no_required_path_names_an_r4_artefact(self):
        """The four names that made an R5 plan impossible are gone."""
        for name in ("R4_BUILD_MANIFEST.sha256", "VERIFICATION_RESULT.json",
                     "VERIFICATION_MANIFEST.sha256",
                     "FREEZE_ATTEMPT_1_MANIFEST.sha256"):
            self.assertNotIn(name, " ".join(freeze.R5_REQUIRED_PLAN_FIELDS))

    def test_bound_artifacts_are_verified_by_digest(self):
        plan = {"bound_artifacts": {"sub/a.txt": self.digest}}
        self.assertTrue(freeze.assert_plan_matches_disk(plan, self.dir))

    def test_a_stale_bound_digest_is_refused(self):
        plan = {"bound_artifacts": {"sub/a.txt": "a" * 64}}
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_plan_matches_disk(plan, self.dir)
        self.assertIn("FREEZE_PLAN_STALE", str(ctx.exception))

    def test_a_missing_bound_file_is_refused(self):
        plan = {"bound_artifacts": {"sub/nope.txt": "a" * 64}}
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_plan_matches_disk(plan, self.dir)
        self.assertIn("missing file", str(ctx.exception))

    def test_a_bound_path_outside_the_package_is_refused(self):
        plan = {"bound_artifacts": {"../escape.txt": "a" * 64}}
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_plan_matches_disk(plan, self.dir)
        self.assertIn("PATH_ESCAPES_ROOT", str(ctx.exception))

    def test_a_symlinked_bound_path_is_refused(self):
        os.symlink(os.path.join(self.dir, "sub", "a.txt"),
                   os.path.join(self.dir, "link.txt"))
        plan = {"bound_artifacts": {"link.txt": self.digest}}
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_plan_matches_disk(plan, self.dir)
        self.assertIn("SYMLINK_REFUSED", str(ctx.exception))

    def test_duplicate_json_keys_are_refused(self):
        path = os.path.join(self.dir, "dup.json")
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write('{"revision": "R5", "revision": "R4"}\n')
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.load_json_strict(path)
        self.assertIn("DUPLICATE_JSON_KEY", str(ctx.exception))

    def test_the_legacy_r4_plan_route_still_works(self):
        """An R4-era plan with no bound_artifacts keeps its old behaviour."""
        os.makedirs(os.path.join(self.dir, "build", "freeze_attempt_1"))
        os.makedirs(os.path.join(self.dir, "verification"))
        files = {
            "build/R4_BUILD_MANIFEST.sha256": "package\n",
            "verification/VERIFICATION_RESULT.json": "{}\n",
            "verification/VERIFICATION_MANIFEST.sha256": "manifest\n",
            "build/freeze_attempt_1/FREEZE_ATTEMPT_1_MANIFEST.sha256": "prior\n",
        }
        plan = {}
        for rel, text in files.items():
            with io.open(os.path.join(self.dir, rel), "w",
                         encoding="utf-8") as fh:
                fh.write(text)
        plan["package_sha256"] = hashing.sha256_text(files["build/R4_BUILD_MANIFEST.sha256"])
        plan["verification_result_sha256"] = hashing.sha256_text(files["verification/VERIFICATION_RESULT.json"])
        plan["verification_manifest_sha256"] = hashing.sha256_text(files["verification/VERIFICATION_MANIFEST.sha256"])
        plan["prior_freeze_attempt_manifest_sha256"] = hashing.sha256_text(files["build/freeze_attempt_1/FREEZE_ATTEMPT_1_MANIFEST.sha256"])
        self.assertTrue(freeze.assert_plan_matches_disk(plan, self.dir))


class PlanShape(unittest.TestCase):
    """Revision, platform, attempt number and the attempt-1 refusal."""

    def _plan(self, **over):
        plan = {
            "schema": "wpno.level1.freeze-plan/2",
            "revision": "R5",
            "platform": "UBUNTU",
            "attempt_number": 2,
            "package_sha256": "a" * 64,
            "verification_result_sha256": "b" * 64,
            "baseline_preview_sha256": "c" * 64,
            "expected_project_baseline_count": EXPECTED_PROJECT,
            "expected_discovery_baseline_count": EXPECTED_DISCOVERY,
            "bound_artifacts": {"MODE": "d" * 64},
            "predecessor_baseline_manifest_sha256": "e" * 64,
            "predecessor_baseline_manifest_path": freeze.PREDECESSOR_BASELINE_REL,
        }
        plan.update(over)
        return plan

    def test_a_well_formed_plan_is_accepted(self):
        self.assertTrue(freeze.assert_r5_plan_shape(self._plan()))

    def test_attempt_1_is_refused_as_superseded(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(self._plan(attempt_number=1))
        self.assertIn("FREEZE_ATTEMPT_1_SUPERSEDED", str(ctx.exception))

    def test_a_wrong_revision_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(self._plan(revision="R4"))
        self.assertIn("FREEZE_REVISION_MISMATCH", str(ctx.exception))

    def test_a_wrong_platform_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(self._plan(platform="DARWIN"))
        self.assertIn("FREEZE_PLATFORM_MISMATCH", str(ctx.exception))

    def test_a_zero_baseline_count_is_refused(self):
        """The attempt-1 defect, refused at the plan rather than at the write."""
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(
                self._plan(expected_project_baseline_count=0))
        self.assertIn("attests to nothing", str(ctx.exception))

    def test_a_non_integer_attempt_is_refused(self):
        for bad in ("2", 2.0, True, 0, -1):
            with self.assertRaises(freeze.FreezeError):
                freeze.assert_r5_plan_shape(self._plan(attempt_number=bad))

    def test_a_missing_field_is_refused(self):
        plan = self._plan()
        del plan["bound_artifacts"]
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(plan)
        self.assertIn("missing", str(ctx.exception))


class TokenRefusals(unittest.TestCase):
    """R3, R4 and attempt-1 tokens, and replay."""

    def test_the_r3_four_field_token_is_refused(self):
        legacy = ("%s PACKAGE-SHA256=%s VERIFICATION-SHA256=%s %s"
                  % (policy.FREEZE_PREFIX, "a" * 64, "b" * 64,
                     policy.APPROVAL_SUFFIX))
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.parse_freeze_token(legacy)
        self.assertIn("four-field", str(ctx.exception))

    def test_the_attempt_1_token_is_refused_by_the_attempt_1_plan_rule(self):
        """Its plan is attempt 1, and attempt 1 is superseded."""
        attempt_1 = {
            "schema": "wpno.level1.freeze-plan/1", "revision": "R5",
            "platform": "UBUNTU", "attempt_number": 1,
            "package_sha256": "a" * 64, "verification_result_sha256": "b" * 64,
            "baseline_preview_sha256": "c" * 64,
            "expected_project_baseline_count": 1,
            "expected_discovery_baseline_count": 1,
            "bound_artifacts": {"MODE": "d" * 64},
            "predecessor_baseline_manifest_sha256": "e" * 64,
            "predecessor_baseline_manifest_path": "x",
        }
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_r5_plan_shape(attempt_1)
        self.assertIn("SUPERSEDED", str(ctx.exception))

    def test_a_token_for_another_plan_is_refused(self):
        plan = {"package_sha256": "a" * 64,
                "verification_result_sha256": "b" * 64}
        token = freeze.token_for("a" * 64, "b" * 64, "9" * 64)
        parsed = freeze.parse_freeze_token(token)
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_token_binds_plan(parsed, plan, "8" * 64)
        self.assertIn("FREEZE_PLAN_MISMATCH", str(ctx.exception))


class DriverRefusesBeforeWriting(unittest.TestCase):
    """Blocker C. Every refusal must happen before the write stage.

    These run against the live package deliberately: if any of them reached the
    write stage the package would be frozen, and the assertion below would say
    so. MODE and the three freeze artefacts are checked after every case.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "MODE"), encoding="utf-8") as fh:
            self.mode_before = fh.read()

    def tearDown(self):
        with io.open(os.path.join(ROOT, "MODE"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.mode_before,
                             "the driver changed MODE during a refusal")
        for rel in FREEZE_ARTEFACTS:
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel)),
                             "a freeze artefact was written during a refusal")
        self.assertFalse(
            os.path.exists(os.path.join(ROOT, "state",
                                        "freeze_attempts.jsonl")),
            "the token was consumed during a refusal")

    class _Args(object):
        def __init__(self, token, plan=None):
            self.token = token
            self.plan = plan

    def test_the_route_exists(self):
        parser = controller.build_parser()
        args = parser.parse_args(["freeze-level1", "--token", "x"])
        self.assertIs(args.func, controller.cmd_freeze_level1)

    def test_a_malformed_token_is_refused(self):
        with self.assertRaises(freeze.FreezeError):
            controller.cmd_freeze_level1(self._Args("nonsense"))

    def test_an_r3_token_is_refused(self):
        legacy = ("%s PACKAGE-SHA256=%s VERIFICATION-SHA256=%s %s"
                  % (policy.FREEZE_PREFIX, "a" * 64, "b" * 64,
                     policy.APPROVAL_SUFFIX))
        with self.assertRaises(freeze.FreezeError) as ctx:
            controller.cmd_freeze_level1(self._Args(legacy))
        self.assertIn("four-field", str(ctx.exception))

    def test_a_missing_plan_is_refused(self):
        token = freeze.token_for("a" * 64, "b" * 64, "c" * 64)
        with self.assertRaises(controller.ControllerError) as ctx:
            controller.cmd_freeze_level1(
                self._Args(token, "build/does_not_exist.json"))
        self.assertIn("absent", str(ctx.exception))

    def test_a_traversing_plan_path_is_refused(self):
        token = freeze.token_for("a" * 64, "b" * 64, "c" * 64)
        with self.assertRaises(freeze.FreezeError) as ctx:
            controller.cmd_freeze_level1(
                self._Args(token, "../../../etc/passwd"))
        self.assertIn("PATH_ESCAPES_ROOT", str(ctx.exception))

    def test_the_superseded_attempt_1_plan_is_refused(self):
        """The exact artefact from the first attempt, offered again."""
        token = freeze.token_for(
            "593028afd6d9cad08dbffc29e8d82e213d757163ac8264a44c3cdffc0596562d",
            "3059684cfa42b24d66cc5ca9e07da6d2d4f9adecf7e4d79b0968950d77a9dcfe",
            "4fafb1b76f1bd0ea0c3408598b0c7c6ecdc7de57facb389f1303d68edf5653ba")
        with self.assertRaises(freeze.FreezeError) as ctx:
            controller.cmd_freeze_level1(
                self._Args(token,
                           "build/freeze_plan_attempt_1/"
                           "FREEZE_PLAN_R5_ATTEMPT_1.json"))
        self.assertIn("missing", str(ctx.exception).lower())


def tearDownModule():
    shutil.rmtree(SANDBOX, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
