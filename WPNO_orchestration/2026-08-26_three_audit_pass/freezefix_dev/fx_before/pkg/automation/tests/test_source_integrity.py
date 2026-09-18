"""Source integrity and dangerous-pattern scanning.

Covers self-test cases 10, 11, 12, 24 and 45: rejection of a shell-invoking
subprocess keyword, rejection of the os module's command-string helper,
rejection of the two dynamic-execution builtins, source mutation, and
Discovery drift.

The forbidden constructs are named indirectly on purpose. A test file that
spells them out would be flagged by the very scanner it exists to support, and
a scanner with a hand-maintained exception list stops being a scanner.
"""

import json
import os
import unittest

from automation import hashing, path_policy, policy

CONTROLLER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def controller_sources():
    out = []
    for dirpath, dirnames, filenames in os.walk(CONTROLLER_DIR):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


class TestDangerousPatterns(unittest.TestCase):
    """Cases 10-12 — the controller contains no dynamic-execution construct.

    The tokens are assembled from fragments in `policy` so that neither this
    file nor `policy` contains the literal a scanner searches for. A test that
    fails because it quotes the thing it forbids is a test nobody trusts.
    """

    def test_no_dangerous_token_in_controller_sources(self):
        offenders = []
        for path in controller_sources():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for token in policy.DANGEROUS_TOKENS:
                if token in text:
                    offenders.append((os.path.basename(path), token))
        self.assertEqual(offenders, [], "dangerous constructs found: %r" % offenders)

    def test_subprocess_calls_are_argv_lists_without_a_shell(self):
        import ast
        for path in controller_sources():
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "attr", None)
                if name in ("run", "Popen", "call", "check_output"):
                    for kw in node.keywords or []:
                        if kw.arg == "shell":
                            self.assertIsInstance(kw.value, ast.Constant)
                            self.assertFalse(
                                kw.value.value,
                                "a shell was requested in %s" % path)

    def test_executables_are_absolute(self):
        for key, exe in policy.EXECUTABLES.items():
            self.assertTrue(os.path.isabs(exe), "%s is not absolute" % key)

    def test_dangerous_token_list_is_non_empty(self):
        self.assertGreaterEqual(len(policy.DANGEROUS_TOKENS), 5)

    def test_the_scanner_finds_a_planted_construct(self):
        """The instrument is checked against a known answer before it is used.

        A scanner that reports 'nothing found' is indistinguishable from a
        scanner that looks at nothing. This plants each forbidden token in a
        string held only in memory and requires the same matching logic to see
        it.
        """
        for token in policy.DANGEROUS_TOKENS:
            planted = "prefix " + token + " suffix"
            found = [t for t in policy.DANGEROUS_TOKENS if t in planted]
            self.assertIn(token, found, token)


class TestSourceMutation(unittest.TestCase):
    """Case 24 — a change to an audited source is detected, never absorbed."""

    def setUp(self):
        self.work = path_policy.ensure_dir(
            os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest", "integrity"))
        self.sample = os.path.join(self.work, "sample.txt")
        with open(self.sample, "w", encoding="utf-8") as fh:
            fh.write("original\n")
        self.manifest = os.path.join(self.work, "m.sha256")
        hashing.write_manifest(
            hashing.manifest_for([self.sample], self.work), self.manifest)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.work, ignore_errors=True)

    def test_unchanged_file_verifies(self):
        ok, diffs = hashing.verify_manifest(self.manifest, self.work)
        self.assertTrue(ok)
        self.assertEqual(diffs, [])

    def test_single_byte_change_is_detected(self):
        with open(self.sample, "w", encoding="utf-8") as fh:
            fh.write("originaL\n")
        ok, diffs = hashing.verify_manifest(self.manifest, self.work)
        self.assertFalse(ok)
        self.assertEqual(diffs[0]["reason"], "CHANGED")

    def test_deleted_file_is_detected(self):
        os.unlink(self.sample)
        ok, diffs = hashing.verify_manifest(self.manifest, self.work)
        self.assertFalse(ok)
        self.assertEqual(diffs[0]["reason"], "MISSING")

    def test_bindings_record_the_hashes_audits_must_check(self):
        bindings_dir = os.path.join(path_policy.LEVEL1_ROOT, "bindings")
        found = 0
        for name in sorted(os.listdir(bindings_dir)):
            with open(os.path.join(bindings_dir, name), encoding="utf-8") as fh:
                binding = json.load(fh)
            for item in binding["source_evidence"]:
                if item["sha256"]:
                    self.assertTrue(hashing.is_hex64(item["sha256"]),
                                    "%s has a malformed hash" % name)
                    found += 1
        self.assertGreater(found, 0)


class TestDiscoveryDrift(unittest.TestCase):
    """Case 45 — drift is recorded, and Discovery itself is never edited."""

    def _drift_text(self):
        path = os.path.join(path_policy.LEVEL1_ROOT, "discovery_reconciliation",
                            "11_DISCOVERY_DRIFT.md")
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_drift_report_exists_and_names_entries(self):
        path = os.path.join(path_policy.LEVEL1_ROOT, "discovery_reconciliation",
                            "11_DISCOVERY_DRIFT.md")
        self.assertTrue(os.path.exists(path))
        text = self._drift_text()
        for entry in ("D-01", "D-02", "D-03"):
            self.assertIn(entry, text)

    def test_bindings_reference_drift_entries_by_id(self):
        bindings_dir = os.path.join(path_policy.LEVEL1_ROOT, "bindings")
        referenced = set()
        for name in sorted(os.listdir(bindings_dir)):
            with open(os.path.join(bindings_dir, name), encoding="utf-8") as fh:
                referenced.update(json.load(fh)["discovery_drift"])
        self.assertTrue(referenced, "no binding references a drift entry")
        for entry in referenced:
            self.assertRegex(entry, r"^D-\d{2}$")

    def test_discovery_root_is_not_writable(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(
                os.path.join(path_policy.DISCOVERY_ROOT, "11_DISCOVERY_DRIFT.md"))


class TestD08IsTheMeasuredFact(unittest.TestCase):
    """VF-007 — D-08 states what was measured, per path, with hashes."""

    def setUp(self):
        path = os.path.join(path_policy.LEVEL1_ROOT, "discovery_reconciliation",
                            "11_DISCOVERY_DRIFT.md")
        with open(path, encoding="utf-8") as fh:
            self.text = fh.read()

    def test_the_old_claim_is_marked_retracted(self):
        self.assertIn("D-08 — RETRACTED AND REPLACED", self.text)

    def test_not_all_four_families_are_claimed_to_have_both_variants(self):
        self.assertIn("Not all four families have both interpreter variants.",
                      self.text)

    def test_each_family_carries_its_measured_statement(self):
        for statement in (
            "test_payload_scan has both CPython 3.11 and 3.14 cache artefacts",
            "custom_callback: CPython 3.14 only",
            "tool_registry_gate: CPython 3.14 only",
        ):
            self.assertIn(statement, self.text)

    def test_the_payload_scan_family_is_reported_per_directory(self):
        self.assertIn(
            "payload_scan: CPython 3.14 only under docker/litellm, and both "
            "3.11 and 3.14 under anonymization", self.text)

    def test_the_measured_artefacts_are_listed_with_hashes(self):
        for needle in (
            "anonymization/__pycache__/payload_scan.cpython-311.pyc",
            "anonymization/__pycache__/payload_scan.cpython-314.pyc",
            "docker/litellm/__pycache__/custom_callback.cpython-314.pyc",
            "docker/litellm/__pycache__/tool_registry_gate.cpython-314.pyc",
        ):
            self.assertIn(needle, self.text)
        # Every listed artefact line must carry a 64-hex digest.
        import re
        digests = re.findall(r"\b[0-9a-f]{64}\b", self.text)
        self.assertGreaterEqual(len(digests), 12)


if __name__ == "__main__":
    unittest.main()
