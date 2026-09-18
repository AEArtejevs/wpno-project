"""Counter-tests for the in-process operation executor.

These exist because the defect they cover was invisible for exactly the
reason CLAUDE.md section 10 names: a tool that silently does something other
than what was meant reports success. The controller skipped every in-process
step, called the result "executed", and nothing anywhere contradicted it.

So the tests below are written to fail if the skip ever comes back. The
central one is `test_controller_branch_is_not_a_no_op`: it reads the
controller's own execute path and refuses a bare `continue` in the
IN_PROCESS branch. The rest prove that each operation really reads bytes,
that assertions are enforced rather than accepted, and that the safety
switches a plan asks for are honoured rather than trusted.
"""

import ast
import hashlib
import json
import os
import unittest

from automation import in_process_ops, operation_catalog

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
CONTROLLER = os.path.join(ROOT, "automation", "controller.py")
REHEARSAL = os.path.join(ROOT, "build", "rehearse_candidate_plans.py")


class EveryCataloguedOperationIsImplemented(unittest.TestCase):

    def test_no_catalogued_operation_lacks_a_handler(self):
        missing = set(operation_catalog.IN_PROCESS) - set(in_process_ops.HANDLERS)
        self.assertEqual(missing, set(),
                         "IN_PROCESS operations with no implementation: %s"
                         % sorted(missing))

    def test_no_handler_is_outside_the_catalogue(self):
        extra = set(in_process_ops.HANDLERS) - set(operation_catalog.IN_PROCESS)
        self.assertEqual(extra, set())

    def test_an_unimplemented_operation_is_refused_not_skipped(self):
        with self.assertRaises(in_process_ops.InProcessError):
            in_process_ops.perform("NOT_A_REAL_OPERATION", {})


class TheControllerBranchActuallyRuns(unittest.TestCase):
    """The regression guard. A skipped step must never read as an executed one."""

    def _in_process_branch(self, tree):
        """Find the branch in the execute loop, not the guard in _run_operation.

        The first version of this helper returned the first `if` mentioning
        IN_PROCESS anywhere in the file. That is the guard inside
        `_run_operation`, which only raises, so the test failed against a
        correctly repaired controller. It was the same mistake the repair is
        about: a search that quietly matched something other than what was
        meant. The branch is now located inside the execute route by name.
        """
        target = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef)
                    and node.name == "cmd_execute_approved"):
                target = node
                break
        if target is None:
            return None
        for node in ast.walk(target):
            if isinstance(node, ast.If) and "IN_PROCESS" in ast.dump(node.test):
                return node
        return None

    def test_controller_branch_is_not_a_no_op(self):
        with open(CONTROLLER, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        branch = self._in_process_branch(tree)
        self.assertIsNotNone(branch, "the IN_PROCESS branch has disappeared")
        calls = [node for node in ast.walk(branch) if isinstance(node, ast.Call)]
        names = set()
        for call in calls:
            if isinstance(call.func, ast.Name):
                names.add(call.func.id)
            elif isinstance(call.func, ast.Attribute):
                names.add(call.func.attr)
        self.assertIn(
            "_run_in_process_operation", names,
            "the IN_PROCESS branch does not perform the operation; a branch "
            "that only appends a note and continues is the defect this test "
            "exists to catch")

    def test_the_guard_rejects_the_original_defective_branch(self):
        """The sabotage proof. A guard that cannot fail has proved nothing.

        CLAUDE.md section 6: a test that changed nothing has shown nothing,
        and a sabotage must be demonstrated effective or the test is void.
        So the defect is reconstructed here verbatim -- the branch exactly as
        it stood before the repair -- and the same predicate is applied. If
        this test ever passes the reconstruction, the guard above is
        decoration.
        """
        defective = (
            "def cmd_execute_approved(args):\n"
            "    outcomes = []\n"
            "    for step in plan['steps']:\n"
            "        if step['operation'] in operation_catalog.IN_PROCESS:\n"
            "            outcomes.append({'operation': step['operation'],\n"
            "                             'note': 'in-process; performed by "
            "the worker'})\n"
            "            continue\n"
        )
        branch = self._in_process_branch(ast.parse(defective))
        self.assertIsNotNone(branch, "the reconstruction did not compile")
        names = set()
        for call in ast.walk(branch):
            if isinstance(call, ast.Call):
                if isinstance(call.func, ast.Name):
                    names.add(call.func.id)
                elif isinstance(call.func, ast.Attribute):
                    names.add(call.func.attr)
        self.assertNotIn(
            "_run_in_process_operation", names,
            "the reconstructed defect was not recognised as defective, so "
            "the guard on the real controller does not discriminate")

    def test_controller_records_evidence_for_in_process_steps(self):
        with open(CONTROLLER, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index("def _run_in_process_operation")
        body = source[start:start + 4000]
        self.assertIn("recorder.record_operation", body,
                      "an in-process operation must be recorded as evidence")

    def test_rehearsal_does_not_mark_an_unexecuted_step_ok(self):
        """executed False together with ok True is the combination that lied."""
        with open(REHEARSAL, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        branch = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and "IN_PROCESS" in ast.dump(node.test):
                branch = node
                break
        self.assertIsNotNone(branch)
        names = {call.func.attr for call in ast.walk(branch)
                 if isinstance(call, ast.Call)
                 and isinstance(call.func, ast.Attribute)}
        self.assertIn("perform", names,
                      "the rehearsal must really perform in-process steps")


class OperationsReadRealBytes(unittest.TestCase):

    def test_sha256_file_matches_an_independently_computed_digest(self):
        code, result = in_process_ops.perform("SHA256_FILE", {"path": CONTROLLER})
        self.assertEqual(code, 0)
        with open(CONTROLLER, "rb") as handle:
            expected = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(result["sha256"], expected)

    def test_python_ast_parse_finds_a_function_that_is_really_there(self):
        code, result = in_process_ops.perform("PYTHON_AST_PARSE",
                                              {"path": CONTROLLER})
        self.assertEqual(code, 0)
        self.assertIn("_run_in_process_operation", result["functions"])
        self.assertFalse(result["imported_module_was_executed"])

    def test_stat_file_reports_a_real_size(self):
        code, result = in_process_ops.perform("STAT_FILE", {"path": CONTROLLER})
        self.assertEqual(code, 0)
        self.assertEqual(result["size_bytes"], os.path.getsize(CONTROLLER))

    def test_read_file_range_returns_the_requested_bytes(self):
        code, result = in_process_ops.perform(
            "READ_FILE_RANGE", {"path": CONTROLLER, "start": 0, "length": 16})
        self.assertEqual(code, 0)
        self.assertEqual(result["returned_bytes"], 16)
        with open(CONTROLLER, "rb") as handle:
            head = handle.read(16)
        self.assertEqual(result["sha256_of_range"],
                         hashlib.sha256(head).hexdigest())


class AssertionsAreEnforcedNotAccepted(unittest.TestCase):
    """A parameter that is accepted and ignored reads as a check that happened."""

    def test_expected_sha256_mismatch_fails(self):
        code, result = in_process_ops.perform(
            "SHA256_FILE", {"path": CONTROLLER, "expected_sha256": "0" * 64})
        self.assertEqual(code, 1)
        self.assertTrue(result["failed"])
        self.assertIn("mismatch", result["reason"])

    def test_expected_sha256_match_passes(self):
        with open(CONTROLLER, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        code, _ = in_process_ops.perform(
            "SHA256_FILE", {"path": CONTROLLER, "expected_sha256": digest})
        self.assertEqual(code, 0)

    def test_expect_contains_that_is_absent_fails(self):
        target = os.path.join(HERE, "_fixture_expect.json")
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"present": "yes"}, handle)
        try:
            code, result = in_process_ops.perform(
                "PARSE_JSON_READONLY",
                {"path": target, "expect_contains": "definitely_not_here"})
            self.assertEqual(code, 1)
            self.assertIn("expect_contains", result["reason"])
        finally:
            os.remove(target)

    def test_expect_absent_that_is_present_fails(self):
        target = os.path.join(HERE, "_fixture_absent.json")
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"present": "sentinel_value"}, handle)
        try:
            code, result = in_process_ops.perform(
                "PARSE_JSON_READONLY",
                {"path": target, "expect_absent": "sentinel_value"})
            self.assertEqual(code, 1)
            self.assertIn("expect_absent", result["reason"])
        finally:
            os.remove(target)


class WordBoundaryIsHonoured(unittest.TestCase):
    """CLAUDE.md section 10: `bea` without \\b matched Bearbeitung twelve times."""

    def setUp(self):
        self.target = os.path.join(HERE, "_fixture_boundary.txt")
        with open(self.target, "w", encoding="utf-8") as handle:
            # lowercase on purpose: the match is case-sensitive, so the
            # substrings only exercise the boundary flag if they share the
            # pattern's case.
            handle.write("bea steht allein. bearbeitung und beanstandung nicht.\n")

    def tearDown(self):
        if os.path.exists(self.target):
            os.remove(self.target)

    def test_word_boundary_true_counts_only_the_standalone_word(self):
        code, result = in_process_ops.perform(
            "COUNT_TEXT_MATCHES",
            {"path": self.target, "patterns": ["bea"], "word_boundary": True})
        self.assertEqual(code, 0)
        self.assertEqual(result["matches_per_pattern"]["bea"], 1)

    def test_word_boundary_false_also_counts_the_substrings(self):
        code, result = in_process_ops.perform(
            "COUNT_TEXT_MATCHES",
            {"path": self.target, "patterns": ["bea"], "word_boundary": False})
        self.assertEqual(code, 0)
        self.assertEqual(result["matches_per_pattern"]["bea"], 3)

    def test_the_two_settings_really_differ(self):
        strict = in_process_ops.perform(
            "COUNT_TEXT_MATCHES",
            {"path": self.target, "patterns": ["bea"], "word_boundary": True})[1]
        loose = in_process_ops.perform(
            "COUNT_TEXT_MATCHES",
            {"path": self.target, "patterns": ["bea"], "word_boundary": False})[1]
        self.assertNotEqual(strict["matches_per_pattern"],
                            loose["matches_per_pattern"])


class SandboxSwitchesAreEnforced(unittest.TestCase):
    """A plan that asks for entity resolution off must not be parsed anyway."""

    def _write(self, name, text):
        target = os.path.join(HERE, name)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.addCleanup(lambda: os.path.exists(target) and os.remove(target))
        return target

    def _safe(self, path):
        return {"path": path, "no_network": True,
                "resolve_entities": False, "load_dtd": False}

    def test_plain_xml_parses(self):
        target = self._write("_fixture_plain.xml", "<r><a/><a/></r>")
        code, result = in_process_ops.perform("XML_PARSE_SANDBOX",
                                              self._safe(target))
        self.assertEqual(code, 0)
        self.assertEqual(result["element_count"], 3)

    def test_entity_declaration_is_refused(self):
        target = self._write(
            "_fixture_entity.xml",
            '<!DOCTYPE r [<!ENTITY x "boom">]><r>&x;</r>')
        code, result = in_process_ops.perform("XML_PARSE_SANDBOX",
                                              self._safe(target))
        self.assertEqual(code, 1)
        self.assertIn("entities", result["reason"])

    def test_external_system_reference_is_refused(self):
        target = self._write(
            "_fixture_external.xml",
            '<!DOCTYPE r SYSTEM "http://example.invalid/x.dtd"><r/>')
        code, result = in_process_ops.perform("XML_PARSE_SANDBOX",
                                              self._safe(target))
        self.assertEqual(code, 1)
        self.assertIn("external", result["reason"])

    def test_asking_for_entity_resolution_is_refused(self):
        target = self._write("_fixture_ok.xml", "<r/>")
        params = self._safe(target)
        params["resolve_entities"] = True
        code, result = in_process_ops.perform("XML_PARSE_SANDBOX", params)
        self.assertEqual(code, 1)
        self.assertIn("resolve_entities", result["reason"])

    def test_docker_import_without_no_socket_is_refused(self):
        target = self._write("_fixture_docker.json", "[]")
        code, result = in_process_ops.perform(
            "DOCKER_METADATA_IMPORT", {"export": target, "no_socket": False})
        self.assertEqual(code, 1)
        self.assertIn("no_socket", result["reason"])

    def test_database_import_without_no_connection_is_refused(self):
        target = self._write("_fixture_db.json", "[]")
        code, result = in_process_ops.perform(
            "DATABASE_EVIDENCE_IMPORT",
            {"export": target, "no_connection": False})
        self.assertEqual(code, 1)
        self.assertIn("no_connection", result["reason"])


class FailuresAreMeasurementsNotCrashes(unittest.TestCase):

    def test_a_missing_file_returns_a_reason_rather_than_raising(self):
        code, result = in_process_ops.perform(
            "SHA256_FILE", {"path": os.path.join(ROOT, "no_such_file_here")})
        self.assertEqual(code, 1)
        self.assertTrue(result["failed"])
        self.assertTrue(result["reason"])

    def test_a_path_outside_the_read_roots_is_refused(self):
        code, result = in_process_ops.perform("SHA256_FILE", {"path": "/etc/passwd"})
        self.assertEqual(code, 1)
        self.assertTrue(result["failed"])


if __name__ == "__main__":
    unittest.main()
