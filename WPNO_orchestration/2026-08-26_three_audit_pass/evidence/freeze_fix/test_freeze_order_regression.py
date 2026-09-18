"""Freeze ordering: the regression that made R5 fail its own control manifest.

R5 froze successfully, reported `frozen: true`, exited zero, and produced a
package whose CONTROL_MANIFEST failed on exactly one entry - MODE. The manifest
recorded the pre-freeze `GENERATED_UNVERIFIED` digest because it was generated
by hashing the control plane from disk, and MODE was published afterwards.

Nothing caught it. The freeze tests that existed exercised the driver's
refusals and asserted that no artefact was written; none of them ran the
success path to completion and then checked the manifest it produced. A test
that never lets the thing finish cannot see what the finished thing looks like.

So the load-bearing test here is the first one: run the real controller freeze
route against a real isolated package and verify the resulting manifest from
disk, the same question `sha256sum -c` asks. Everything after it holds a
refusal in place.

The fixture is small and synthetic rather than a copy of a real package,
because the freeze route does not care how big the package is - it cares that
the predecessor baseline members exist and hash as declared, that the bound
artefacts are present, and that state is initialised. A fixture that supplies
those exercises the same code the real freeze runs.

One thing is deliberately not tested here. R5's consumed freeze token is
one-time and is preserved only as a digest in R5's ledger; the token grammar
is deterministic, so reconstructing it from the plan and package digests would
put the raw token back into a source file. The refusal is therefore tested by
its two independent mechanisms - a plan digest that does not match, and a plan
whose revision is not this package's - neither of which needs the token text.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import unittest

from automation import freeze, path_policy

ROOT = path_policy.LEVEL1_ROOT
REVISION = getattr(freeze, "PACKAGE_REVISION", None) or freeze.R5_REVISION
PLATFORM = getattr(freeze, "PACKAGE_PLATFORM", None) or freeze.R5_PLATFORM
PREDECESSOR_REL = freeze.PREDECESSOR_BASELINE_REL
LINEAGE_DIR = PREDECESSOR_REL.split(os.sep)[1]
LINEAGE_MANIFEST_REL = "lineage/%s_MANIFEST.sha256" % LINEAGE_DIR

SANDBOX = os.path.join(ROOT, "work", "_freeze_order_regression")
FREEZE_ARTEFACTS = ("BASELINE_MANIFEST.json", "CONTROL_MANIFEST.sha256",
                    os.path.join("state", "PACKAGE_VERIFIED.json"))


def _sha_file(path):
    return freeze.sha256_file(path)


def _run(pkg, argv, driver=None):
    """Invoke the controller inside the fixture, in a fresh interpreter.

    A fresh process each time because `path_policy` resolves the package root
    once at import; a reload inside one interpreter would leave the previous
    fixture's root bound in half the modules.
    """
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "en_US.UTF-8",
           "PYTHONPATH": pkg, "HOME": os.environ.get("HOME", "/home/ubuntu")}
    if driver is None:
        command = [sys.executable, "-m", "automation.controller"] + argv
    else:
        command = [sys.executable, driver] + argv
    return subprocess.run(command, cwd=pkg, env=env, capture_output=True,
                          text=True)


# The harness for the publication-failure cases. It patches the one function
# every artefact write goes through, so a failure can be placed at an exact
# step without touching the filesystem's permissions.
FAIL_AT_DRIVER = '''
import sys
from automation import controller

stop_after = int(sys.argv[1])
original = controller._freeze_write
calls = {"n": 0}

def failing(path, text):
    calls["n"] += 1
    if calls["n"] > stop_after:
        raise IOError("simulated publication failure at write %d" % calls["n"])
    return original(path, text)

controller._freeze_write = failing
raise SystemExit(controller.main(sys.argv[2:]))
'''


class FreezeFixture(object):
    """An isolated package the real freeze route will accept."""

    def __init__(self, base):
        self.base = base
        self.pkg = os.path.join(base, "pkg")
        self.project = os.path.join(base, "project_root")
        self.discovery = os.path.join(base, "discovery_root")

    def build(self):
        if os.path.isdir(self.base):
            shutil.rmtree(self.base)
        for d in (self.pkg, self.project, self.discovery):
            os.makedirs(d)

        shutil.copytree(os.path.join(ROOT, "automation"),
                        os.path.join(self.pkg, "automation"))
        shutil.rmtree(os.path.join(self.pkg, "automation", "package_tests"),
                      ignore_errors=True)
        for name in ("bindings", "prompts", "discovery_reconciliation"):
            source = os.path.join(ROOT, name)
            if os.path.isdir(source):
                shutil.copytree(source, os.path.join(self.pkg, name))
        for name in ("audit_registry.json", "AGENTS.md", "00_COMMON_RULES.md"):
            source = os.path.join(ROOT, name)
            if os.path.isfile(source):
                shutil.copy2(source, os.path.join(self.pkg, name))
        for dirpath, dirnames, _ in os.walk(self.pkg):
            for name in list(dirnames):
                if name == "__pycache__":
                    shutil.rmtree(os.path.join(dirpath, name), ignore_errors=True)
                    dirnames.remove(name)

        with io.open(os.path.join(self.pkg, "paths.json"), "w",
                     encoding="utf-8") as fh:
            json.dump({"schema": "wpno.level1.paths/2",
                       "note": "Isolated freeze-order regression fixture.",
                       "project_root": "../project_root",
                       "discovery_root": "../discovery_root",
                       "level1_root": "."}, fh, indent=2, sort_keys=True)
            fh.write("\n")
        for name in ("state", "results", "evidence", "work", "logs"):
            os.makedirs(os.path.join(self.pkg, name))

        project_files, discovery_files = [], []
        for i in range(3):
            rel = "src_%d.txt" % i
            full = os.path.join(self.project, rel)
            with io.open(full, "w", encoding="utf-8") as fh:
                fh.write("audited project source %d\n" % i)
            project_files.append({"path": rel, "sha256": _sha_file(full),
                                  "state": "FILE"})
        for i in range(2):
            rel = "disc_%d.txt" % i
            full = os.path.join(self.discovery, rel)
            with io.open(full, "w", encoding="utf-8") as fh:
                fh.write("discovery member %d\n" % i)
            discovery_files.append({"path": rel, "sha256": _sha_file(full)})

        lineage = os.path.join(self.pkg, os.path.dirname(PREDECESSOR_REL))
        os.makedirs(lineage)
        baseline = {"schema": "wpno.level1.baseline-manifest/1",
                    "scope": {"audited_sources": "fixture",
                              "discovery": "fixture"},
                    "project_files": project_files,
                    "discovery_files": discovery_files}
        self.predecessor = os.path.join(self.pkg, PREDECESSOR_REL)
        with io.open(self.predecessor, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(baseline, indent=2, sort_keys=True,
                                ensure_ascii=False) + "\n")
        with io.open(os.path.join(lineage, "MODE"), "w", encoding="utf-8") as fh:
            fh.write("FROZEN\n")

        self.lineage_manifest = os.path.join(self.pkg,
                                             *LINEAGE_MANIFEST_REL.split("/"))
        rows = []
        for dirpath, dirnames, filenames in os.walk(lineage):
            dirnames.sort()
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rows.append((_sha_file(full),
                             os.path.relpath(full, os.path.dirname(lineage))))
        with io.open(self.lineage_manifest, "w", encoding="utf-8") as fh:
            fh.write("".join("%s  %s\n" % r
                             for r in sorted(rows, key=lambda x: x[1])))

        with io.open(self.mode_path, "w", encoding="utf-8") as fh:
            fh.write("GENERATED_UNVERIFIED\n")
        return self

    @property
    def mode_path(self):
        return os.path.join(self.pkg, "MODE")

    def mode(self):
        with io.open(self.mode_path, encoding="utf-8") as fh:
            return fh.read().strip()

    def init_revision(self):
        result = _run(self.pkg, ["init-revision", "--revision", REVISION,
                                 "--predecessor", "PRED",
                                 "--predecessor-root", "/nonexistent",
                                 "--lineage", os.path.dirname(PREDECESSOR_REL),
                                 "--platform", PLATFORM])
        if result.returncode != 0:
            raise AssertionError("fixture init-revision failed: %s%s"
                                 % (result.stdout, result.stderr))
        return self

    def plan(self, attempt=2, directory="build/freeze_plan", **override):
        baseline, _ = freeze.build_baseline_from_predecessor(
            self.pkg, _sha_file(self.predecessor))
        preview = freeze.sha256_text(freeze.serialize_baseline(baseline))
        plan = {
            "schema": "wpno.level1.freeze-plan/2",
            "revision": REVISION,
            "platform": PLATFORM,
            "attempt_number": attempt,
            "package_sha256": _sha_file(self.lineage_manifest),
            "verification_result_sha256": _sha_file(self.predecessor),
            "baseline_preview_sha256": preview,
            "expected_project_baseline_count": len(baseline["project_files"]),
            "expected_discovery_baseline_count": len(baseline["discovery_files"]),
            "bound_artifacts": {
                LINEAGE_MANIFEST_REL: _sha_file(self.lineage_manifest),
                PREDECESSOR_REL.replace(os.sep, "/"): _sha_file(self.predecessor),
            },
            "predecessor_baseline_manifest_sha256": _sha_file(self.predecessor),
            "predecessor_baseline_manifest_path":
                PREDECESSOR_REL.replace(os.sep, "/"),
            "independence_limitation": "FIXTURE",
        }
        plan.update(override)
        os.makedirs(os.path.join(self.pkg, *directory.split("/")), exist_ok=True)
        rel = "%s/FREEZE_PLAN.json" % directory
        raw = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        with io.open(os.path.join(self.pkg, *rel.split("/")), "w",
                     encoding="utf-8") as fh:
            fh.write(raw)
        return rel, freeze.sha256_text(raw), plan

    def token(self, plan, plan_sha256):
        return freeze.token_for(plan["package_sha256"],
                                plan["verification_result_sha256"], plan_sha256)

    def freeze_now(self, rel, token, stop_after=None):
        if stop_after is None:
            return _run(self.pkg, ["freeze-level1", "--token", token,
                                   "--plan", rel])
        driver = os.path.join(self.pkg, "_fail_at.py")
        with io.open(driver, "w", encoding="utf-8") as fh:
            fh.write(FAIL_AT_DRIVER)
        return _run(self.pkg, [str(stop_after), "freeze-level1",
                               "--token", token, "--plan", rel], driver=driver)

    def ledger(self):
        path = os.path.join(self.pkg, "state", "freeze_attempts.jsonl")
        if not os.path.exists(path):
            return []
        with io.open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def artefacts_present(self):
        return [rel for rel in FREEZE_ARTEFACTS
                if os.path.exists(os.path.join(self.pkg, rel))]


def _fixture(name):
    return FreezeFixture(os.path.join(SANDBOX, name)).build()


class FrozenPackageVerifiesAgainstItsOwnManifest(unittest.TestCase):
    """The load-bearing case. R5 failed exactly this and reported success."""

    @classmethod
    def setUpClass(cls):
        cls.fx = _fixture("success").init_revision()
        rel, plan_sha, plan = cls.fx.plan()
        cls.result = cls.fx.freeze_now(rel, cls.fx.token(plan, plan_sha))
        cls.check = subprocess.run(
            ["sha256sum", "-c", "CONTROL_MANIFEST.sha256"],
            cwd=cls.fx.pkg, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.fx.base, ignore_errors=True)

    def test_the_freeze_route_completed(self):
        self.assertEqual(self.result.returncode, 0,
                         self.result.stdout + self.result.stderr)
        self.assertTrue(json.loads(self.result.stdout)["frozen"])

    def test_sha256sum_c_reports_no_failure(self):
        """The external check, byte for byte the one a human would run."""
        self.assertEqual(self.check.returncode, 0, self.check.stderr)
        failed = [l for l in self.check.stdout.splitlines()
                  if not l.endswith(": OK")]
        self.assertEqual(failed, [], "manifest entries failed: %r" % failed)

    def test_every_entry_is_ok_and_none_failed(self):
        report = json.loads(self.result.stdout)["control_manifest_verified_from_disk"]
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["missing"], 0)
        self.assertEqual(report["unlisted"], 0)
        self.assertEqual(report["ok"], report["entries"])
        self.assertGreater(report["entries"], 0)

    def test_the_mode_entry_is_present_and_ok(self):
        """The single entry R5 got wrong."""
        report = freeze.verify_manifest_from_disk(self.fx.pkg)
        self.assertTrue(report["mode_entry_present"])
        self.assertTrue(report["mode_entry_ok"])
        self.assertEqual(self.fx.mode(), "FROZEN")

    def test_the_manifest_records_the_frozen_mode_not_the_pre_freeze_one(self):
        with io.open(os.path.join(self.fx.pkg, "CONTROL_MANIFEST.sha256"),
                     encoding="utf-8") as handle:
            entries = freeze.parse_manifest(handle.read())
        self.assertEqual(entries["MODE"], freeze.sha256_text("FROZEN\n"))
        self.assertNotEqual(entries["MODE"],
                            freeze.sha256_text("GENERATED_UNVERIFIED\n"))

    def test_the_manifest_does_not_record_itself(self):
        with io.open(os.path.join(self.fx.pkg, "CONTROL_MANIFEST.sha256"),
                     encoding="utf-8") as handle:
            entries = freeze.parse_manifest(handle.read())
        self.assertNotIn("CONTROL_MANIFEST.sha256", entries)

    def test_the_ledger_records_exactly_one_successful_attempt(self):
        outcomes = [r["outcome"] for r in self.fx.ledger()]
        self.assertEqual(outcomes.count("FROZEN"), 1, outcomes)

    def test_mode_was_published_last(self):
        with io.open(os.path.join(self.fx.pkg, "state",
                                  "PACKAGE_VERIFIED.json"),
                     encoding="utf-8") as handle:
            verified = json.load(handle)
        self.assertEqual(verified["publication_order"][-1], "MODE")
        self.assertEqual(verified["manifest_generation"],
                         "FINAL_STATE_STAGED_BYTES")


class PreFreezeModeCannotSatisfyTheFinalManifest(unittest.TestCase):
    """The defect stated directly: the old digest must not verify."""

    def setUp(self):
        self.fx = _fixture("prefreeze").init_revision()

    def tearDown(self):
        shutil.rmtree(self.fx.base, ignore_errors=True)

    def test_restoring_the_pre_freeze_mode_breaks_the_manifest(self):
        rel, plan_sha, plan = self.fx.plan()
        self.assertEqual(
            self.fx.freeze_now(rel, self.fx.token(plan, plan_sha)).returncode, 0)
        with io.open(self.fx.mode_path, "w", encoding="utf-8") as fh:
            fh.write("GENERATED_UNVERIFIED\n")
        report = freeze.verify_manifest_from_disk(self.fx.pkg)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(report["failed"][0]["path"], "MODE")
        self.assertFalse(report["mode_entry_ok"])

    def test_the_final_state_manifest_refuses_to_hash_mode_from_disk(self):
        """Staged bytes win over disk. This is the repair, isolated."""
        staged = {"MODE": "FROZEN\n"}
        manifest = freeze.final_state_manifest(self.fx.pkg, staged)
        self.assertEqual(manifest["MODE"], freeze.sha256_text("FROZEN\n"))
        self.assertEqual(self.fx.mode(), "GENERATED_UNVERIFIED")


class PublicationFailure(unittest.TestCase):
    """A freeze that stops part way must not leave a package claiming FROZEN."""

    def setUp(self):
        self.fx = _fixture("partial").init_revision()

    def tearDown(self):
        shutil.rmtree(self.fx.base, ignore_errors=True)

    def _fail_after(self, writes):
        rel, plan_sha, plan = self.fx.plan()
        return self.fx.freeze_now(rel, self.fx.token(plan, plan_sha),
                                  stop_after=writes)

    def test_failure_before_mode_leaves_the_package_unfrozen(self):
        """Three artefacts written, MODE not reached."""
        result = self._fail_after(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.fx.mode(), "GENERATED_UNVERIFIED")

    def test_failure_before_mode_records_no_success(self):
        self._fail_after(3)
        outcomes = [r["outcome"] for r in self.fx.ledger()]
        self.assertNotIn("FROZEN", outcomes)
        self.assertIn("PUBLISH_STARTED", outcomes)
        self.assertIn("FAILED_DURING_PUBLICATION", outcomes)

    def test_failure_at_the_first_write_leaves_no_artefact(self):
        result = self._fail_after(0)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.fx.artefacts_present(), [])
        self.assertEqual(self.fx.mode(), "GENERATED_UNVERIFIED")

    def test_a_stopped_freeze_cannot_be_resumed_under_the_same_approval(self):
        """Crash before MODE, then retry with the same plan and token.

        The retry is refused on the artefacts the stopped attempt already
        published, which is a stricter guard than the replay ledger and fires
        before it. What matters is the pair of facts underneath: the package
        never reaches FROZEN, and no second attempt can quietly finish what
        the first one started. A package in this state is dead and belongs to
        a successor revision, not to a resumed freeze.
        """
        rel, plan_sha, plan = self.fx.plan()
        token = self.fx.token(plan, plan_sha)
        self.assertNotEqual(
            self.fx.freeze_now(rel, token, stop_after=3).returncode, 0)
        retry = self.fx.freeze_now(rel, token)
        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("FREEZE_ARTEFACT_PRESENT", retry.stdout + retry.stderr)
        self.assertEqual(self.fx.mode(), "GENERATED_UNVERIFIED")
        self.assertNotIn("FROZEN", [r["outcome"] for r in self.fx.ledger()])


class RefusalsBeforeAnyWrite(unittest.TestCase):
    """Every refusal must happen before the write stage, and leave no trace."""

    def setUp(self):
        self.fx = _fixture("refusal").init_revision()

    def tearDown(self):
        shutil.rmtree(self.fx.base, ignore_errors=True)

    def _refused(self, result):
        self.assertNotEqual(result.returncode, 0,
                            "the freeze was accepted: %s" % result.stdout)
        self.assertEqual(self.fx.artefacts_present(), [])
        self.assertEqual(self.fx.mode(), "GENERATED_UNVERIFIED")
        return result.stdout + result.stderr

    def test_wrong_plan_hash_is_refused(self):
        rel, plan_sha, plan = self.fx.plan()
        wrong = self.fx.token(plan, "0" * 64)
        self.assertIn("FREEZE_PLAN_MISMATCH",
                      self._refused(self.fx.freeze_now(rel, wrong)))

    def test_wrong_package_hash_is_refused(self):
        rel, plan_sha, plan = self.fx.plan()
        wrong = freeze.token_for("1" * 64, plan["verification_result_sha256"],
                                 plan_sha)
        self.assertIn("FREEZE_PACKAGE_MISMATCH",
                      self._refused(self.fx.freeze_now(rel, wrong)))

    def test_wrong_verification_hash_is_refused(self):
        rel, plan_sha, plan = self.fx.plan()
        wrong = freeze.token_for(plan["package_sha256"], "2" * 64, plan_sha)
        self.assertIn("FREEZE_VERIFICATION_MISMATCH",
                      self._refused(self.fx.freeze_now(rel, wrong)))

    def test_a_plan_for_another_revision_is_refused(self):
        """A predecessor's freeze plan cannot authorise this package.

        The mechanism that stops R5's spent approval reaching R6, tested
        without reconstructing the token text: the plan itself names the wrong
        revision and is refused on its shape.
        """
        rel, plan_sha, plan = self.fx.plan(revision="R5-PREDECESSOR")
        output = self._refused(
            self.fx.freeze_now(rel, self.fx.token(plan, plan_sha)))
        self.assertIn("FREEZE_REVISION_MISMATCH", output)

    def test_a_started_phase_is_refused(self):
        rel, plan_sha, plan = self.fx.plan()
        progress_path = os.path.join(self.fx.pkg, "state", "progress.json")
        with io.open(progress_path, encoding="utf-8") as handle:
            progress = json.load(handle)
        first = sorted(progress["audits"])[0]
        phase = sorted(progress["audits"][first])[0]
        progress["audits"][first][phase]["state"] = "AWAITING_APPROVAL"
        with io.open(progress_path, "w", encoding="utf-8") as fh:
            json.dump(progress, fh)
        self.assertIn("FREEZE_PHASE_ALREADY_STARTED",
                      self._refused(self.fx.freeze_now(
                          rel, self.fx.token(plan, plan_sha))))

    def test_attempt_one_is_refused(self):
        rel, plan_sha, plan = self.fx.plan(attempt=1)
        self.assertIn("ATTEMPT_1",
                      self._refused(self.fx.freeze_now(
                          rel, self.fx.token(plan, plan_sha))))


class AlreadyFrozenAndReplay(unittest.TestCase):

    def setUp(self):
        self.fx = _fixture("replay").init_revision()
        rel, plan_sha, plan = self.fx.plan()
        self.token_used = self.fx.token(plan, plan_sha)
        self.rel = rel
        self.assertEqual(self.fx.freeze_now(rel, self.token_used).returncode, 0)

    def tearDown(self):
        shutil.rmtree(self.fx.base, ignore_errors=True)

    def test_the_same_token_is_refused_a_second_time(self):
        """Refused on MODE, which is checked before the plan is even read.

        The replay ledger is the second line and is tested directly in
        `ReplayLedger` below; here the package is already frozen, so the
        refusal arrives earlier. Both are refusals and neither writes.
        """
        again = self.fx.freeze_now(self.rel, self.token_used)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("FREEZE_ALREADY_DONE", again.stdout + again.stderr)
        self.assertEqual(len([r for r in self.fx.ledger()
                              if r["outcome"] == "FROZEN"]), 1)

    def test_a_frozen_package_refuses_a_further_freeze(self):
        rel, plan_sha, plan = self.fx.plan(attempt=3,
                                           directory="build/freeze_plan_3")
        again = self.fx.freeze_now(rel, self.fx.token(plan, plan_sha))
        self.assertNotEqual(again.returncode, 0)
        output = again.stdout + again.stderr
        self.assertTrue("ALREADY_DONE" in output or "ARTEFACT_PRESENT" in output,
                        output)

    def test_the_frozen_package_still_verifies(self):
        report = freeze.verify_manifest_from_disk(self.fx.pkg)
        self.assertEqual(report["failed_count"], 0)
        self.assertTrue(report["mode_entry_ok"])


class ReplayLedger(unittest.TestCase):
    """The replay guard itself, separated from the already-frozen guard.

    In a completed freeze the package refuses on MODE long before the ledger
    is consulted, so the ledger's own two refusals - same token, and same
    attempt number under a different token - would otherwise never be reached
    by a test that goes through the driver.
    """

    def setUp(self):
        self.fx = _fixture("ledger").init_revision()
        self.ledger_path = os.path.join(self.fx.pkg, "state",
                                        "freeze_attempts.jsonl")
        _, self.plan_sha, self.plan = self.fx.plan()
        self.token_used = self.fx.token(self.plan, self.plan_sha)
        freeze.append_attempt(self.ledger_path, self.token_used, self.plan,
                              self.plan_sha, "FROZEN", "2026-08-26T00:00:00Z")

    def tearDown(self):
        shutil.rmtree(self.fx.base, ignore_errors=True)

    def test_the_same_token_is_refused(self):
        with self.assertRaises(freeze.FreezeError) as caught:
            freeze.assert_not_replayed(self.token_used, self.plan,
                                       self.ledger_path)
        self.assertIn("FREEZE_TOKEN_REPLAY", str(caught.exception))

    def test_the_same_attempt_under_a_new_token_is_refused(self):
        """A fresh token for a spent attempt number is still a replay."""
        other = freeze.token_for(self.plan["package_sha256"],
                                 self.plan["verification_result_sha256"],
                                 "3" * 64)
        with self.assertRaises(freeze.FreezeError) as caught:
            freeze.assert_not_replayed(other, self.plan, self.ledger_path)
        self.assertIn("FREEZE_ATTEMPT_REPLAY", str(caught.exception))

    def test_a_later_attempt_is_permitted(self):
        later = dict(self.plan, attempt_number=self.plan["attempt_number"] + 1)
        other = freeze.token_for(later["package_sha256"],
                                 later["verification_result_sha256"], "4" * 64)
        self.assertTrue(
            freeze.assert_not_replayed(other, later, self.ledger_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
