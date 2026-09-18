"""Records, schemas and manifest scope: the three that drifted quietly.

Each of these held a defect that broke nothing while it sat there, which is
why none of them was noticed until something went looking.

The binding schema had `additionalProperties: false` and two closures added
fields to two bindings without adding them to the schema. Every binding still
loaded; only a validation run said otherwise, and the only place that runs is
the isolated replica. The schema now names the closure fields, and it is
stricter than before rather than looser: it also refuses a dot-dot segment,
which the original `^/` admitted.

The build-manifest generator had no rule for the two directories created after
a manifest is written - the fresh verifier's output and the freeze plan. With
no rule, the manifest would have been stale the moment the verifier wrote its
first file, and a stale manifest is what the freeze binds. The rule is a
prefix on one path component and nothing wider.

R7_RESUME_STATUS.json named a superseded manifest stamped 074524Z that was
never written. Its digest and entry count matched the file that does exist,
stamped 074734Z, so the content was right and only the name was wrong. A
dangling path gates nothing; it misleads a reader into looking for evidence
under a name it does not have.
"""

import copy
import glob
import importlib.util
import json
import os
import unittest

from automation import hashing, path_policy, schema_validation

ROOT = path_policy.LEVEL1_ROOT
BINDINGS = os.path.join(ROOT, "bindings")
# R8 retarget. The R7-specific tooling that these tests exercise was renamed
# when R8 was built -- `build/resume_r7/build_r7_build_manifest.py` became
# `build/build_r8_build_manifest.py`, and the status validator moved beside
# it -- and R7's own status record is not carried into R8. The subject of
# these tests is the builder and the validator, not the revision whose name
# the files used to carry, so they now read R8's.
STATUS_RECORD = os.path.join(ROOT, "build", "R8_RESUME_STATUS.json")


def load_module(relative, name):
    path = os.path.join(ROOT, relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BindingSchema(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(BINDINGS, "L1-A01.binding.json"),
                  encoding="utf-8") as fh:
            self.base = json.load(fh)

    def validates(self, document):
        schema_validation.validate_named(document, "binding.schema.json")

    def refuses(self, mutate):
        document = copy.deepcopy(self.base)
        mutate(document)
        with self.assertRaises(schema_validation.ValidationError):
            self.validates(document)

    def test_all_thirty_five_bindings_validate(self):
        paths = sorted(glob.glob(os.path.join(BINDINGS, "*.binding.json")))
        self.assertEqual(len(paths), 35)
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                document = json.load(fh)
            self.validates(document)

    def test_the_closure_fields_the_two_closures_added_are_named(self):
        with open(os.path.join(ROOT, "automation", "schemas",
                               "binding.schema.json"), encoding="utf-8") as fh:
            schema = json.load(fh)
        for field in ("mac_reality_status",
                      "mac_evidence_package_manifest_sha256",
                      "mac_reality_limitations", "referent", "source_mac_path",
                      "expected_sha256", "expected_hash_source",
                      "chain_of_custody", "chain_of_custody_limitation"):
            self.assertIn(field, schema["properties"])

    def test_the_schema_still_refuses_a_field_it_does_not_name(self):
        self.refuses(lambda d: d.update({"a_field_nobody_declared": 1}))

    def test_an_absolute_candidate_path_is_accepted(self):
        document = copy.deepcopy(self.base)
        document["candidate_paths"].insert(0, "/home/operator/thing.py")
        self.validates(document)

    def test_a_package_relative_references_path_is_accepted(self):
        document = copy.deepcopy(self.base)
        document["candidate_paths"].insert(0, "references/REF-12/a.docx")
        self.validates(document)

    def test_a_bare_relative_path_is_refused(self):
        self.refuses(lambda d: d["candidate_paths"].insert(0, "authoring/x.py"))

    def test_a_parent_escaping_path_is_refused(self):
        """The first version of the pattern accepted this one."""
        self.refuses(
            lambda d: d["candidate_paths"].insert(0, "references/../../etc/passwd"))

    def test_a_dot_dot_inside_an_absolute_path_is_refused(self):
        self.refuses(
            lambda d: d["candidate_paths"].insert(0, "/home/../etc/passwd"))

    def test_a_closure_field_with_the_wrong_value_is_refused(self):
        self.refuses(lambda d: d.update({"mac_reality_status": "MAYBE"}))
        self.refuses(lambda d: d.update({"chain_of_custody": "SORT OF"}))
        self.refuses(lambda d: d.update({"expected_sha256": "short"}))

    def test_a_valid_closure_field_set_is_accepted(self):
        document = copy.deepcopy(self.base)
        document.update({"mac_reality_status": "ACCEPTED",
                         "chain_of_custody": "BOUND",
                         "expected_sha256": "0" * 64})
        self.validates(document)


class ManifestExclusionPolicy(unittest.TestCase):
    """The exclusions must be exactly two families and nothing adjacent."""

    def setUp(self):
        self.builder = load_module(
            os.path.join("build", "build_r8_build_manifest.py"),
            "r8_build_manifest_under_test")

    def excluded(self, rel):
        return self.builder.is_post_manifest_artefact(rel)

    def test_the_final_verifier_output_is_excluded(self):
        self.assertTrue(self.excluded(
            "verification_codex_final_pre_freeze_attempt_1/"
            "VERIFICATION_RESULT.json"))
        self.assertTrue(self.excluded(
            "verification_codex_final_pre_freeze_attempt_12/a/b.json"))

    def test_the_freeze_plan_directory_is_excluded(self):
        self.assertTrue(self.excluded(
            "build/freeze_plan_attempt_1/FREEZE_PLAN_R8_ATTEMPT_1.json"))

    def test_the_earlier_verification_directory_is_not_excluded(self):
        """It holds the earlier independent verification and must stay bound."""
        self.assertFalse(self.excluded(
            "verification_codex_pre_freeze/VERIFICATION_RESULT.json"))
        self.assertFalse(self.excluded(
            "verification_codex_pre_freeze/ATTEMPT_HISTORY.md"))

    def test_a_similarly_named_file_is_not_excluded(self):
        self.assertFalse(self.excluded(
            "build/notes_about_freeze_plan_attempt_1.md"))
        self.assertFalse(self.excluded(
            "verification/selftest_runtime/automation/policy.py"))

    def test_candidate_plans_remain_included(self):
        self.assertFalse(self.excluded(
            "build/candidate_plans_r8/L1-A19/RUN-A/plan.json"))
        self.assertFalse(self.excluded(
            "build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json"))

    def test_builders_readiness_references_and_decisions_remain_included(self):
        for rel in ("build/build_all_candidate_plans.py",
                    "build/candidate_plan_specs.py",
                    "build/plan_library.py",
                    "build/all_level1_scope/R7_ALL35_INPUT_READINESS.json",
                    # R8's own records must be inside the manifest too: a
                    # repair nothing covers is a repair nothing can check.
                    "build/IN_PROCESS_COUNT_RECONCILIATION.json",
                    "build/CONTROL_EXPECTATION_COVERAGE.json",
                    "build/control_expectations.py",
                    "automation/in_process_executor.py",
                    "automation/in_process_ops.py",
                    "lineage/R8_LINEAGE.json",
                    "lineage/R7_BASELINE_MANIFEST.json",
                    "references/manifest.json",
                    "references/REF-05_COVERAGE.json",
                    "bindings/L1-A29.binding.json",
                    "automation/external_host_evidence.py"):
            self.assertFalse(self.excluded(rel), rel)

    def test_the_manifest_excludes_itself(self):
        self.assertIn(os.path.join("build", "R8_BUILD_MANIFEST.sha256"),
                      self.builder.EXCLUDED_RELS)

    def test_a_superseded_manifest_is_not_excluded(self):
        """A superseded copy is evidence, and evidence nothing covers is unchecked."""
        self.assertFalse(self.excluded(
            "build/R8_BUILD_MANIFEST.SUPERSEDED_2026-08-27T074734Z.sha256"))

    def test_the_runtime_directories_are_still_excluded(self):
        for top in ("work", "state", "results", "evidence", "logs"):
            self.assertIn(top, self.builder.EXCLUDED_TOP_LEVEL)

    def test_the_walk_refuses_a_symlink(self):
        import inspect
        source = inspect.getsource(self.builder.enumerate_files)
        self.assertIn("islink", source)
        self.assertIn("followlinks=False", source)


class StatusRecordPaths(unittest.TestCase):
    """A status record must not name a path that is not there."""

    def setUp(self):
        self.validator = load_module(
            os.path.join("build", "validate_status_record.py"),
            "r8_status_record_validator")

    def test_the_resume_status_record_names_only_paths_that_exist(self):
        result = self.validator.validate(STATUS_RECORD)
        self.assertTrue(result["ok"],
                        "dangling or mismatched paths: %s"
                        % json.dumps(result["problems"], indent=2))

    def test_the_validator_catches_a_path_that_does_not_exist(self):
        scratch = os.path.join(ROOT, "work", "_selftest",
                               "status_record_counter_proof.json")
        path_policy.ensure_dir(os.path.dirname(scratch))
        with open(path_policy.assert_writable(scratch), "w",
                  encoding="utf-8") as fh:
            json.dump({"some_section": {"report": "build/no_such_file.json"}},
                      fh)
        try:
            result = self.validator.validate(scratch)
            self.assertFalse(result["ok"])
            self.assertEqual(result["problems"][0]["problem"],
                             "NAMED_PATH_DOES_NOT_EXIST")
        finally:
            os.remove(scratch)

    def test_the_validator_catches_a_digest_that_does_not_match(self):
        scratch = os.path.join(ROOT, "work", "_selftest",
                               "status_digest_counter_proof.json")
        path_policy.ensure_dir(os.path.dirname(scratch))
        with open(path_policy.assert_writable(scratch), "w",
                  encoding="utf-8") as fh:
            json.dump({"some_section": {
                "report": "lineage/R8_LINEAGE.sha256",
                "report_sha256": "0" * 64}}, fh)
        try:
            result = self.validator.validate(scratch)
            self.assertFalse(result["ok"])
            self.assertEqual(result["problems"][0]["problem"],
                             "NAMED_PATH_DIGEST_DOES_NOT_MATCH")
        finally:
            os.remove(scratch)

    def test_the_validator_accepts_a_record_whose_paths_resolve(self):
        scratch = os.path.join(ROOT, "work", "_selftest",
                               "status_record_positive.json")
        path_policy.ensure_dir(os.path.dirname(scratch))
        with open(path_policy.assert_writable(scratch), "w",
                  encoding="utf-8") as fh:
            json.dump({"some_section": {
                "report": "lineage/R8_LINEAGE.sha256",
                "report_sha256": hashing.sha256_file(os.path.join(
                    ROOT, "lineage", "R8_LINEAGE.sha256"))}}, fh)
        try:
            self.assertTrue(self.validator.validate(scratch)["ok"])
        finally:
            os.remove(scratch)

    def test_a_historical_key_may_name_a_path_that_is_gone(self):
        """Documenting a correction must not itself fail the check."""
        scratch = os.path.join(ROOT, "work", "_selftest",
                               "status_record_historical.json")
        path_policy.ensure_dir(os.path.dirname(scratch))
        with open(path_policy.assert_writable(scratch), "w",
                  encoding="utf-8") as fh:
            json.dump({"correction": {
                "previously_named": "build/never_written.sha256",
                "corrected_to": "MODE"}}, fh)
        try:
            self.assertTrue(self.validator.validate(scratch)["ok"])
        finally:
            os.remove(scratch)

    def test_the_exemption_does_not_swallow_a_live_binding(self):
        """A key that is not historical must still have to resolve."""
        scratch = os.path.join(ROOT, "work", "_selftest",
                               "status_record_live_binding.json")
        path_policy.ensure_dir(os.path.dirname(scratch))
        with open(path_policy.assert_writable(scratch), "w",
                  encoding="utf-8") as fh:
            json.dump({"correction": {
                "previously_named": "build/never_written.sha256",
                "report": "build/also_never_written.json"}}, fh)
        try:
            result = self.validator.validate(scratch)
            self.assertFalse(result["ok"])
            self.assertEqual([p["value"] for p in result["problems"]],
                             ["build/also_never_written.json"])
        finally:
            os.remove(scratch)
