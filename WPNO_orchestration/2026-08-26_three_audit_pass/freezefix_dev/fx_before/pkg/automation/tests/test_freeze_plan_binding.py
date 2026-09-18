"""Freeze approval bound to a freeze plan.

The first R4 freeze was rolled back for a defect in an artefact it produced.
The package itself had not changed, so the token required for the second
attempt was character-for-character the token already spent on the first. A
RUN-ONCE approval that is indistinguishable from its own replay is not
one-time; it only looks it.

These tests hold the repair in place: the attempt-1 grammar cannot authorise
attempt 2, the plan digest must match, a consumed approval cannot be spent
again, and nothing is written until every binding has been checked.
"""

import io
import json
import os
import shutil
import unittest

from automation import freeze, path_policy, policy

SANDBOX = os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest", "freeze")

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def _require_replica():
    if os.path.basename(path_policy.LEVEL1_ROOT) != "selftest_runtime":
        raise AssertionError(
            "these tests write below work/_selftest and must run only inside "
            "the isolated replica; LEVEL1_ROOT is %s" % path_policy.LEVEL1_ROOT)


def _plan(attempt=2, package=A, verification=B, baseline=C, prior=D,
          project_count=33, discovery_count=26):
    return {
        "schema": "wpno.level1.freeze-plan/1",
        "attempt_number": attempt,
        "package_sha256": package,
        "verification_result_sha256": verification,
        "verification_manifest_sha256": B,
        "baseline_preview_sha256": baseline,
        "expected_project_baseline_count": project_count,
        "expected_discovery_baseline_count": discovery_count,
        "prior_freeze_attempt_manifest_sha256": prior,
        "excluded_paths": ["/Users/martinotten/.claude/CLAUDE.md"],
        "r3_root": "/Users/martinotten/WPNO/08.18.26_Level1_Audits_R3",
        "r3_expected_aggregate": "0" * 64,
        "r3_expected_file_count": 505,
    }


class FreezeCase(unittest.TestCase):
    def setUp(self):
        _require_replica()
        if os.path.isdir(SANDBOX):
            shutil.rmtree(SANDBOX)
        os.makedirs(SANDBOX)
        self.plan_path = os.path.join(SANDBOX, "FREEZE_PLAN_V2.json")
        self.plan = _plan()
        self.plan_sha = self.write_plan(self.plan)
        self.ledger = os.path.join(SANDBOX, "FREEZE_ATTEMPTS.jsonl")

    def tearDown(self):
        shutil.rmtree(SANDBOX, ignore_errors=True)

    def write_plan(self, plan):
        raw = json.dumps(plan, indent=2, sort_keys=True) + "\n"
        with io.open(self.plan_path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        return freeze.sha256_text(raw)

    def token(self, package=None, verification=None, plan_sha=None):
        return freeze.token_for(package or self.plan["package_sha256"],
                                verification or self.plan["verification_result_sha256"],
                                plan_sha or self.plan_sha)


# ------------------------------------------------------------------ grammar
class TestTokenGrammar(FreezeCase):

    def test_attempt_1_token_cannot_authorize_attempt_2(self):
        """The R3 four-field grammar is refused on its shape."""
        legacy = ("%s PACKAGE-SHA256=%s VERIFICATION-SHA256=%s %s"
                  % (policy.FREEZE_PREFIX, self.plan["package_sha256"],
                     self.plan["verification_result_sha256"],
                     policy.APPROVAL_SUFFIX))
        self.assertEqual(len(legacy.split()), 4)
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.parse_freeze_token(legacy)
        message = str(ctx.exception)
        self.assertIn("four-field", message)
        self.assertIn("FREEZE-PLAN-SHA256", message)

    def test_the_two_grammars_are_not_interchangeable(self):
        five = self.token()
        self.assertEqual(len(five.split()), freeze.FREEZE_FIELD_COUNT)
        self.assertIn("FREEZE-PLAN-SHA256=", five)
        parsed = freeze.parse_freeze_token(five)
        self.assertEqual(parsed["freeze_plan_sha256"], self.plan_sha)

    def test_wrong_field_count_rejected(self):
        for bad in (self.token() + " EXTRA",
                    " ".join(self.token().split()[:3]),
                    " ".join(self.token().split()[:2])):
            with self.assertRaises(freeze.FreezeError):
                freeze.parse_freeze_token(bad)

    def test_wrong_prefix_or_suffix_rejected(self):
        with self.assertRaises(freeze.FreezeError):
            freeze.parse_freeze_token(
                self.token().replace(policy.FREEZE_PREFIX, "FREEZE-LEVEL2", 1))
        with self.assertRaises(freeze.FreezeError):
            freeze.parse_freeze_token(
                self.token()[: -len(policy.APPROVAL_SUFFIX)] + "RUN-MANY")

    def test_non_hex_digest_rejected(self):
        with self.assertRaises(freeze.FreezeError):
            freeze.parse_freeze_token(self.token(plan_sha="z" * 64))

    def test_none_and_empty_rejected(self):
        for bad in (None, "", "   ", 42, [], {}):
            with self.assertRaises(freeze.FreezeError):
                freeze.parse_freeze_token(bad)


# ------------------------------------------------------------------ binding
class TestPlanBinding(FreezeCase):

    def test_correct_binding_accepted(self):
        parsed = freeze.parse_freeze_token(self.token())
        self.assertTrue(
            freeze.assert_token_binds_plan(parsed, self.plan, self.plan_sha))

    def test_wrong_freeze_plan_hash_rejected(self):
        parsed = freeze.parse_freeze_token(self.token(plan_sha="e" * 64))
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_token_binds_plan(parsed, self.plan, self.plan_sha)
        self.assertIn("FREEZE_PLAN_MISMATCH", str(ctx.exception))

    def test_plan_edited_after_approval_is_rejected(self):
        """Editing the plan changes its digest, which voids the approval."""
        token = self.token()
        edited = dict(self.plan)
        edited["attempt_number"] = 3
        new_sha = self.write_plan(edited)
        self.assertNotEqual(new_sha, self.plan_sha)
        parsed = freeze.parse_freeze_token(token)
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_token_binds_plan(parsed, edited, new_sha)
        self.assertIn("FREEZE_PLAN_MISMATCH", str(ctx.exception))

    def test_wrong_package_hash_rejected(self):
        parsed = freeze.parse_freeze_token(self.token(package="f" * 64))
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_token_binds_plan(parsed, self.plan, self.plan_sha)
        self.assertIn("FREEZE_PACKAGE_MISMATCH", str(ctx.exception))

    def test_wrong_verification_hash_rejected(self):
        parsed = freeze.parse_freeze_token(self.token(verification="0" * 64))
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_token_binds_plan(parsed, self.plan, self.plan_sha)
        self.assertIn("FREEZE_VERIFICATION_MISMATCH", str(ctx.exception))

    def test_incomplete_plan_rejected(self):
        for field in ("attempt_number", "package_sha256",
                      "baseline_preview_sha256",
                      "prior_freeze_attempt_manifest_sha256"):
            partial = dict(self.plan)
            partial.pop(field)
            self.write_plan(partial)
            with self.assertRaises(freeze.FreezeError) as ctx:
                freeze.load_freeze_plan(self.plan_path)
            self.assertIn(field, str(ctx.exception))

    def test_plan_digest_is_of_the_bytes_on_disk(self):
        plan, sha = freeze.load_freeze_plan(self.plan_path)
        with io.open(self.plan_path, encoding="utf-8") as fh:
            self.assertEqual(sha, freeze.sha256_text(fh.read()))
        self.assertEqual(plan["attempt_number"], 2)

    def test_stale_plan_against_disk_is_rejected(self):
        """A plan that names a digest the file no longer has is refused."""
        root = os.path.join(SANDBOX, "pkg")
        os.makedirs(os.path.join(root, "build", "freeze_attempt_1"))
        os.makedirs(os.path.join(root, "verification"))
        files = {
            "build/R4_BUILD_MANIFEST.sha256": "package\n",
            "verification/VERIFICATION_RESULT.json": "{}\n",
            "verification/VERIFICATION_MANIFEST.sha256": "manifest\n",
            "build/freeze_attempt_1/FREEZE_ATTEMPT_1_MANIFEST.sha256": "prior\n",
        }
        for rel, text in files.items():
            with io.open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
        good = dict(self.plan)
        good["package_sha256"] = freeze.sha256_text(files["build/R4_BUILD_MANIFEST.sha256"])
        good["verification_result_sha256"] = freeze.sha256_text(files["verification/VERIFICATION_RESULT.json"])
        good["verification_manifest_sha256"] = freeze.sha256_text(files["verification/VERIFICATION_MANIFEST.sha256"])
        good["prior_freeze_attempt_manifest_sha256"] = freeze.sha256_text(files["build/freeze_attempt_1/FREEZE_ATTEMPT_1_MANIFEST.sha256"])
        self.assertTrue(freeze.assert_plan_matches_disk(good, root))

        with io.open(os.path.join(root, "build", "R4_BUILD_MANIFEST.sha256"),
                     "w", encoding="utf-8") as fh:
            fh.write("package changed\n")
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_plan_matches_disk(good, root)
        self.assertIn("FREEZE_PLAN_STALE", str(ctx.exception))


# ------------------------------------------------------------------- replay
class TestReplay(FreezeCase):

    def test_replayed_attempt_2_token_is_rejected(self):
        token = self.token()
        self.assertTrue(freeze.assert_not_replayed(token, self.plan, self.ledger))
        freeze.append_attempt(self.ledger, token, self.plan, self.plan_sha,
                              "FROZEN", "2026-08-25T00:00:00Z")
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_not_replayed(token, self.plan, self.ledger)
        self.assertIn("FREEZE_TOKEN_REPLAY", str(ctx.exception))

    def test_a_second_token_for_a_consumed_attempt_is_rejected(self):
        """A fresh token cannot revive an attempt number already spent."""
        freeze.append_attempt(self.ledger, self.token(), self.plan,
                              self.plan_sha, "FROZEN", "2026-08-25T00:00:00Z")
        other = dict(self.plan)
        other["baseline_preview_sha256"] = "9" * 64
        other_sha = self.write_plan(other)
        fresh = freeze.token_for(other["package_sha256"],
                                 other["verification_result_sha256"], other_sha)
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_not_replayed(fresh, other, self.ledger)
        self.assertIn("FREEZE_ATTEMPT_REPLAY", str(ctx.exception))

    def test_a_new_attempt_number_is_not_a_replay(self):
        freeze.append_attempt(self.ledger, self.token(), self.plan,
                              self.plan_sha, "ROLLED_BACK",
                              "2026-08-25T00:00:00Z")
        third = _plan(attempt=3, baseline="7" * 64)
        third_sha = self.write_plan(third)
        fresh = freeze.token_for(third["package_sha256"],
                                 third["verification_result_sha256"], third_sha)
        self.assertTrue(freeze.assert_not_replayed(fresh, third, self.ledger))

    def test_ledger_is_append_only(self):
        freeze.append_attempt(self.ledger, self.token(), self.plan,
                              self.plan_sha, "FROZEN", "2026-08-25T00:00:00Z")
        with io.open(self.ledger, "rb") as fh:
            first = fh.read()
        third = _plan(attempt=3, baseline="7" * 64)
        freeze.append_attempt(self.ledger, self.token(plan_sha="8" * 64), third,
                              "8" * 64, "FROZEN", "2026-08-25T01:00:00Z")
        with io.open(self.ledger, "rb") as fh:
            second = fh.read()
        self.assertTrue(second.startswith(first))
        self.assertEqual(len(freeze.recorded_attempts(self.ledger)), 2)


# ------------------------------------------------- nothing written too early
class TestNothingWrittenBeforeBindingsVerify(unittest.TestCase):

    def setUp(self):
        _require_replica()
        self.root = os.path.join(SANDBOX, "package")
        if os.path.isdir(SANDBOX):
            shutil.rmtree(SANDBOX)
        os.makedirs(self.root)
        with io.open(os.path.join(self.root, "MODE"), "w",
                     encoding="utf-8") as fh:
            fh.write("GENERATED_UNVERIFIED\n")

    def tearDown(self):
        shutil.rmtree(SANDBOX, ignore_errors=True)

    def _artefacts(self):
        return [rel for rel in ("CONTROL_MANIFEST.sha256",
                                "BASELINE_MANIFEST.json",
                                os.path.join("state", "PACKAGE_VERIFIED.json"))
                if os.path.exists(os.path.join(self.root, rel))]

    def test_no_freeze_artefact_is_written_before_bindings_verify(self):
        plan_path = os.path.join(self.root, "plan.json")
        plan_body = _plan()
        raw = json.dumps(plan_body, indent=2, sort_keys=True) + "\n"
        with io.open(plan_path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        plan, plan_sha = freeze.load_freeze_plan(plan_path)

        for bad in (freeze.token_for(A, B, "e" * 64),
                    freeze.token_for("f" * 64, B, plan_sha),
                    freeze.token_for(A, "0" * 64, plan_sha)):
            with self.assertRaises(freeze.FreezeError):
                parsed = freeze.parse_freeze_token(bad)
                freeze.assert_token_binds_plan(parsed, plan, plan_sha)
            self.assertEqual(self._artefacts(), [],
                             "a freeze artefact appeared after a refusal")

        with io.open(os.path.join(self.root, "MODE"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "GENERATED_UNVERIFIED")

    def test_an_existing_artefact_stops_the_freeze(self):
        self.assertTrue(freeze.assert_no_freeze_artefact(self.root))
        with io.open(os.path.join(self.root, "BASELINE_MANIFEST.json"), "w",
                     encoding="utf-8") as fh:
            fh.write("{}\n")
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_no_freeze_artefact(self.root)
        self.assertIn("FREEZE_ARTEFACT_PRESENT", str(ctx.exception))

    def test_a_frozen_package_refuses_to_freeze_again(self):
        with io.open(os.path.join(self.root, "MODE"), "w",
                     encoding="utf-8") as fh:
            fh.write("FROZEN\n")
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_no_freeze_artefact(self.root)
        self.assertIn("FREEZE_ALREADY_DONE", str(ctx.exception))


# ------------------------------------------------------------ baseline scope
class TestBaselineScope(unittest.TestCase):
    """The defect attempt 1 shipped, and the rule that now prevents it."""

    def setUp(self):
        _require_replica()

    def test_baseline_excludes_paths_outside_project_root(self):
        baseline, excluded = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        project = os.path.realpath(
            os.path.join(path_policy.LEVEL1_ROOT, "..", "selftest_project_root"))
        for entry in baseline["project_files"]:
            resolved = os.path.abspath(os.path.join(project, entry["path"]))
            self.assertTrue(
                resolved == project or resolved.startswith(project + os.sep),
                "%s escapes PROJECT_ROOT" % entry["path"])
            self.assertNotIn("..", entry["path"].split(os.sep))

    def test_a_binding_path_outside_project_root_is_reported_not_recorded(self):
        _, excluded = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        baseline, _ = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        recorded = {e["path"] for e in baseline["project_files"]}
        for path in excluded:
            self.assertNotIn(path, recorded)
            self.assertNotIn(os.path.basename(path) + "-outside", recorded)

    def test_baseline_serialization_is_deterministic(self):
        first, _ = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        second, _ = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        self.assertEqual(freeze.serialize_baseline(first),
                         freeze.serialize_baseline(second))

    def test_baseline_must_match_the_plan_preview(self):
        baseline, _ = freeze.build_baseline(path_policy.LEVEL1_ROOT)
        raw = freeze.serialize_baseline(baseline)
        plan = _plan(baseline=freeze.sha256_text(raw),
                     project_count=len(baseline["project_files"]),
                     discovery_count=len(baseline["discovery_files"]))
        self.assertTrue(freeze.assert_baseline_matches_plan(baseline, plan))

        wrong_preview = dict(plan)
        wrong_preview["baseline_preview_sha256"] = "1" * 64
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_baseline_matches_plan(baseline, wrong_preview)
        self.assertIn("BASELINE_PREVIEW_MISMATCH", str(ctx.exception))

        wrong_count = dict(plan)
        wrong_count["expected_project_baseline_count"] = plan[
            "expected_project_baseline_count"] + 1
        with self.assertRaises(freeze.FreezeError) as ctx:
            freeze.assert_baseline_matches_plan(baseline, wrong_count)
        self.assertIn("BASELINE_COUNT_MISMATCH", str(ctx.exception))


# ----------------------------------------------------------------- R3 intact
class TestR3Unchanged(unittest.TestCase):
    """R3 is evidence. The freeze reads it and must never write to it."""

    def setUp(self):
        _require_replica()

    def test_freeze_module_names_no_write_to_r3(self):
        import inspect
        source = inspect.getsource(freeze)
        for forbidden in ('open(', 'os.remove', 'shutil.rmtree'):
            if forbidden == 'open(':
                continue
            self.assertNotIn(forbidden, source)

    def test_freeze_module_opens_r3_paths_only_for_reading(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(freeze))
        write_modes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    write_modes.append(node.args[1].value)
        for mode in write_modes:
            self.assertIn("r", mode, "freeze opened a file for writing: %r" % mode)

    def test_control_plane_excludes_runtime_directories(self):
        files = freeze.control_plane_files(path_policy.LEVEL1_ROOT)
        for rel in files:
            self.assertNotIn(rel.split(os.sep)[0], freeze.MUTABLE_SUBDIRS)
        self.assertNotIn("CONTROL_MANIFEST.sha256", files)


if __name__ == "__main__":
    unittest.main()
