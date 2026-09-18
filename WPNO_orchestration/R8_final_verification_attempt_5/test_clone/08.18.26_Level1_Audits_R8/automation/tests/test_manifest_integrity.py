"""Package and JSON integrity.

Covers self-test cases 31, 32, 41 and 42:
malformed JSON · extra JSON property · duplicate audit ID · missing prompt.
"""

import json
import os
import re
import unittest

from automation import audit_context, path_policy, policy, schema_validation


class TestMalformedJson(unittest.TestCase):
    """Case 31 — malformed JSON is an error, never a partial parse."""

    def test_broken_json_raises(self):
        for bad in ('{"a": }', '{"a": 1,}', "{'a': 1}", "", "not json"):
            with self.assertRaises(Exception):
                schema_validation.parse_strict(bad)

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.parse_strict('{"a": 1, "a": 2}')

    def test_every_package_json_parses(self):
        for rel in ("audit_registry.json", "paths.json"):
            path = os.path.join(path_policy.LEVEL1_ROOT, rel)
            with open(path, encoding="utf-8") as fh:
                schema_validation.parse_strict(fh.read())


class TestExtraProperty(unittest.TestCase):
    """Case 32 — an unexpected property is a defect, not a courtesy."""

    def test_extra_property_is_rejected(self):
        schema = schema_validation.load_schema("approval.schema.json")
        doc = {"audit_id": "L1-A18", "run_phase": "RUN-A",
               "plan_sha256": "0" * 64, "target_sha256": "1" * 64,
               "recorded_at": 1.0}
        self.assertTrue(schema_validation.validate(doc, schema))
        doc["extra"] = "surprise"
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate(doc, schema)

    def test_missing_required_property_is_rejected(self):
        schema = schema_validation.load_schema("approval.schema.json")
        doc = {"audit_id": "L1-A18", "run_phase": "RUN-A",
               "plan_sha256": "0" * 64, "target_sha256": "1" * 64}
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate(doc, schema)

    def test_boolean_is_not_an_integer(self):
        schema = {"type": "integer"}
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate(True, schema)

    def test_unsupported_schema_keyword_is_an_error(self):
        with self.assertRaises(schema_validation.SchemaError):
            schema_validation.validate({}, {"type": "object", "oneOf": []})


class TestRegistryIntegrity(unittest.TestCase):
    """Cases 41 and 42 — no duplicate id, no missing prompt or binding."""

    def setUp(self):
        self.registry = audit_context.load_registry()

    def test_registry_validates_against_its_schema(self):
        self.assertTrue(schema_validation.validate_named(
            self.registry, "audit_registry.schema.json"))

    def test_exactly_35_entries(self):
        self.assertEqual(len(self.registry["audits"]), 35)

    def test_audit_ids_are_unique(self):
        ids = [a["audit_id"] for a in self.registry["audits"]]
        self.assertEqual(len(ids), len(set(ids)))
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        self.assertEqual(duplicates, [])

    def test_audit_ids_match_the_expected_scheme(self):
        for entry in self.registry["audits"]:
            self.assertRegex(entry["audit_id"], r"^L1-A(0[1-9]|[12][0-9]|3[0-5])$")

    def test_ap_identifiers_are_not_reused(self):
        for entry in self.registry["audits"]:
            self.assertFalse(entry["audit_id"].startswith("AP-"))

    def test_every_prompt_file_exists(self):
        missing = []
        for entry in self.registry["audits"]:
            path = os.path.join(path_policy.LEVEL1_ROOT, entry["prompt_file"])
            if not os.path.exists(path):
                missing.append(entry["audit_id"])
        self.assertEqual(missing, [])

    def test_every_binding_file_exists_and_validates(self):
        for entry in self.registry["audits"]:
            path = os.path.join(path_policy.LEVEL1_ROOT, entry["binding_file"])
            self.assertTrue(os.path.exists(path), entry["audit_id"])
            with open(path, encoding="utf-8") as fh:
                binding = schema_validation.parse_strict(fh.read())
            schema_validation.validate_named(binding, "binding.schema.json")
            self.assertEqual(binding["audit_id"], entry["audit_id"])

    def test_prompt_and_binding_counts_are_35(self):
        prompts = [f for f in os.listdir(
            os.path.join(path_policy.LEVEL1_ROOT, "prompts")) if f.endswith(".md")]
        bindings = [f for f in os.listdir(
            os.path.join(path_policy.LEVEL1_ROOT, "bindings"))
            if f.endswith(".binding.json")]
        self.assertEqual(len(prompts), 35)
        self.assertEqual(len(bindings), 35)


class TestBindingAgreement(unittest.TestCase):
    """A binding that disagrees with the registry is a silent contradiction."""

    def setUp(self):
        self.registry = audit_context.load_registry()

    def test_binding_agrees_with_registry_on_risk_order_and_replications(self):
        for entry in self.registry["audits"]:
            binding = audit_context.load_binding(entry["audit_id"])
            self.assertEqual(binding.get("risk"), entry["risk"],
                             entry["audit_id"])
            self.assertEqual(binding.get("execution_order"),
                             entry["execution_order"], entry["audit_id"])
            self.assertEqual(binding.get("replications"),
                             entry["replications"], entry["audit_id"])

    def test_only_the_four_declared_audits_are_replicated_in_bindings(self):
        replicated = set()
        for entry in self.registry["audits"]:
            binding = audit_context.load_binding(entry["audit_id"])
            if binding.get("replications") == 2:
                replicated.add(entry["audit_id"])
        self.assertEqual(replicated, set(policy.CRITICAL_REPLICATED_AUDITS))


class TestPromptContent(unittest.TestCase):
    """A prompt with a placeholder in it is not a specification."""

    REQUIRED_HEADINGS = (
        "AUDIT ID", "SOURCE GROUP", "SOURCE POINT", "TITLE", "RISK",
        "OBJECTIVE", "WHY THIS MATTERS", "DISCOVERY INPUTS", "TARGET BINDING",
        "TARGET IDENTIFICATION RULE", "PRODUCTION PATH REQUIREMENT",
        "THREAT MODEL", "STATIC ANALYSIS", "RUNTIME TEST MATRIX",
        "POSITIVE CONTROL", "NEGATIVE CONTROL", "MUTATION CONTROL",
        "INDEPENDENT ORACLE", "EDGE CASES", "REGRESSION REQUIREMENTS",
        "ALLOWED OPERATIONS", "GATED OPERATIONS", "FORBIDDEN OPERATIONS",
        "REQUIRED EVIDENCE", "PASS CRITERIA", "PASS_WITH_WARNINGS CRITERIA",
        "FAIL CRITERIA", "BLOCKED CRITERIA", "UNVERIFIED CRITERIA",
        "SELF-CRITIQUE", "DISPROOF ATTEMPT", "OUTPUT FILES", "STOP CONDITIONS",
        "REPLICATION REQUIREMENT",
    )
    FORBIDDEN_PHRASES = ("TODO", "TBD", "FIXME", "probably works",
                         "looks correct", "should work",
                         "assume this is production")

    def _prompts(self):
        base = os.path.join(path_policy.LEVEL1_ROOT, "prompts")
        for name in sorted(os.listdir(base)):
            if name.endswith(".md"):
                with open(os.path.join(base, name), encoding="utf-8") as fh:
                    yield name, fh.read()

    def test_every_prompt_has_every_required_heading(self):
        for name, text in self._prompts():
            headings = set(re.findall(r"^## (.+)$", text, re.M))
            missing = [h for h in self.REQUIRED_HEADINGS if h not in headings]
            self.assertEqual(missing, [], "%s is missing %r" % (name, missing))

    def test_no_prompt_contains_a_placeholder(self):
        for name, text in self._prompts():
            for phrase in self.FORBIDDEN_PHRASES:
                self.assertNotIn(phrase, text, "%s contains %r" % (name, phrase))

    def test_every_prompt_is_utf8(self):
        base = os.path.join(path_policy.LEVEL1_ROOT, "prompts")
        for name in sorted(os.listdir(base)):
            with open(os.path.join(base, name), "rb") as fh:
                fh.read().decode("utf-8")

    def test_every_prompt_references_the_common_rules(self):
        for name, text in self._prompts():
            self.assertIn("00_COMMON_RULES.md", text, name)
            self.assertIn("audit_registry.json", text, name)

    def test_no_prompt_hardcodes_a_user_home_path(self):
        """The package must not name the machine's user. Roots are resolved."""
        for name, text in self._prompts():
            self.assertNotIn("/Users/", text, name)


class TestL1A24WorkingDirectoryIsSatisfiable(unittest.TestCase):
    """VF-011 — the launch directory and the work directory are two places.

    The predecessor prompt required one directory to be simultaneously below the
    audit work directory and outside the project. Since Level-1 lives inside the
    project, no such directory exists, so the audit could never be planned.
    """

    def setUp(self):
        path = os.path.join(path_policy.LEVEL1_ROOT, "prompts", "L1-A24.md")
        with open(path, encoding="utf-8") as fh:
            self.text = fh.read()

    def test_the_two_directories_are_distinguished_explicitly(self):
        self.assertIn(
            "The launch working directory is outside PROJECT_ROOT and is never "
            "inside LEVEL1_ROOT; the audit's work directory is inside "
            "LEVEL1_ROOT and is never the launch working directory.",
            self.text)

    def test_the_external_directory_is_operator_approved_and_not_written_to(self):
        self.assertIn("operator-approved", self.text)
        self.assertIn("No file is written to the external working directory",
                      self.text)

    def test_home_and_tmpdir_are_redirected_into_the_audit_work_directory(self):
        for needle in ("HOME", "TMPDIR",
                       "work/L1-A24/<RUN-ID>/"):
            self.assertIn(needle, self.text)

    def test_the_test_requires_explicit_human_approval(self):
        self.assertIn("explicit human approval", self.text)

    def test_user_claude_configuration_is_not_modified(self):
        self.assertIn("No user Claude configuration is created, modified or "
                      "deleted", self.text)

    def test_no_particular_external_directory_is_hardcoded(self):
        self.assertIn("bound by the operator before execution", self.text)
        self.assertNotIn("/Users/", self.text)


if __name__ == "__main__":
    unittest.main()
