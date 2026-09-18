"""Operation catalogue admission.

Covers self-test cases 8, 9, 13, 29 and 30:
unknown operation · arbitrary shell rejection · argument injection ·
network operation denial · Docker socket denial.
"""

import os
import unittest

from automation import operation_catalog, path_policy


class TestUnknownOperation(unittest.TestCase):
    """Case 8 — an operation not in the catalogue cannot be classified or built."""

    def test_unknown_name_raises(self):
        for name in ("RUN_ANYTHING", "", "read_file_range", "SHA256FILE", None):
            with self.assertRaises(operation_catalog.UnknownOperation):
                operation_catalog.classify(name)

    def test_unknown_name_has_no_argv(self):
        with self.assertRaises(operation_catalog.UnknownOperation):
            operation_catalog.build_argv("RUN_ANYTHING", {})

    def test_catalogue_sets_are_disjoint(self):
        auto = set(operation_catalog.AUTOMATIC)
        gated = set(operation_catalog.GATED)
        forbidden = set(operation_catalog.FORBIDDEN)
        self.assertEqual(auto & gated, set())
        self.assertEqual(auto & forbidden, set())
        self.assertEqual(gated & forbidden, set())


class TestArbitraryShellRejected(unittest.TestCase):
    """Case 9 — there is no path from text to a command line."""

    def test_arbitrary_shell_is_forbidden(self):
        self.assertEqual(operation_catalog.classify("ARBITRARY_SHELL"), "FORBIDDEN")
        with self.assertRaises(operation_catalog.ForbiddenOperation):
            operation_catalog.build_argv("ARBITRARY_SHELL", {"command": "ls"})

    def test_every_forbidden_operation_refuses_to_build(self):
        for name in operation_catalog.FORBIDDEN:
            with self.assertRaises(operation_catalog.ForbiddenOperation):
                operation_catalog.build_argv(name, {})

    def test_plan_with_forbidden_operation_is_rejected(self):
        plan = {"steps": [{"operation": "ARBITRARY_SHELL"}]}
        with self.assertRaises(operation_catalog.ForbiddenOperation):
            operation_catalog.validate_plan_operations(plan)

    def test_builders_produce_lists_not_strings(self):
        argv = operation_catalog.build_argv(
            "GIT_STATUS_READONLY", {"repo": path_policy.PROJECT_ROOT})
        self.assertIsInstance(argv, list)
        for element in argv:
            self.assertIsInstance(element, str)
        self.assertTrue(os.path.isabs(argv[0]))


class TestArgumentInjection(unittest.TestCase):
    """Case 13 — shell metacharacters in a parameter cannot become syntax."""

    def test_metacharacters_in_a_path_do_not_split(self):
        nasty = os.path.join(path_policy.LEVEL1_ROOT, "a; rm -rf /; b")
        # The path does not exist and is not inside a readable root as a real
        # file, but the point is that it is never split: it either resolves to
        # one argv element or is rejected outright.
        try:
            argv = operation_catalog.build_argv("FILE_TYPE", {"path": nasty})
        except path_policy.PathPolicyError:
            return
        self.assertIn(nasty, argv)
        self.assertEqual(sum(1 for a in argv if "rm -rf" in a), 1)

    def test_git_rev_must_be_a_single_bare_token(self):
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv(
                "GIT_SHOW_READONLY",
                {"repo": path_policy.PROJECT_ROOT, "rev": "HEAD; echo hi"})

    def test_script_arguments_must_be_strings(self):
        work = path_policy.ensure_dir(
            os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest", "ops"))
        script = os.path.join(work, "s.py")
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv(
                "PYTHON_SCRIPT_RUN_SANDBOX",
                {"script": script, "args": [{"not": "a string"}]})

    def test_sandbox_operations_must_target_work_dir(self):
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv(
                "PYTHON_SCRIPT_RUN_SANDBOX",
                {"script": os.path.join(path_policy.LEVEL1_ROOT, "prompts",
                                        "L1-A01.md")})


class TestNetworkDenied(unittest.TestCase):
    """Case 29 — no network operation exists to be requested."""

    def test_network_operations_are_forbidden(self):
        for name in ("NETWORK_REQUEST", "NETWORK_UPLOAD"):
            self.assertEqual(operation_catalog.classify(name), "FORBIDDEN")
            with self.assertRaises(operation_catalog.ForbiddenOperation):
                operation_catalog.build_argv(name, {"url": "https://example.invalid"})

    def test_no_builder_emits_a_network_tool(self):
        from automation import policy
        for key, exe in policy.EXECUTABLES.items():
            self.assertNotIn(key, ("curl", "wget", "nc", "ssh"))
            self.assertTrue(os.path.isabs(exe))


class TestDockerSocketDenied(unittest.TestCase):
    """Case 30 — Docker is reachable only through an operator-made export."""

    def test_docker_operations_are_forbidden(self):
        for name in ("DOCKER_SOCKET_ACCESS", "DOCKER_BUILD", "DOCKER_RUN",
                     "DOCKER_EXEC"):
            self.assertEqual(operation_catalog.classify(name), "FORBIDDEN")
            with self.assertRaises(operation_catalog.ForbiddenOperation):
                operation_catalog.build_argv(name, {})

    def test_docker_metadata_import_is_in_process_and_gated(self):
        self.assertEqual(operation_catalog.classify("DOCKER_METADATA_IMPORT"),
                         "GATED")
        self.assertIn("DOCKER_METADATA_IMPORT", operation_catalog.IN_PROCESS)
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv("DOCKER_METADATA_IMPORT", {})

    def test_database_evidence_import_never_connects(self):
        self.assertEqual(operation_catalog.classify("DATABASE_EVIDENCE_IMPORT"),
                         "GATED")
        self.assertIn("DATABASE_EVIDENCE_IMPORT", operation_catalog.IN_PROCESS)
        self.assertEqual(operation_catalog.classify("DATABASE_CONNECTION"),
                         "FORBIDDEN")


class TestVerificationSuppressionRejected(unittest.TestCase):
    """A verification command that suppresses verification cannot be built."""

    def test_suppression_flags_are_rejected(self):
        for flag in operation_catalog.SUPPRESSION_FLAGS:
            with self.assertRaises(operation_catalog.ForbiddenOperation):
                operation_catalog._reject_suppression(["/usr/bin/openssl", flag])


class TestClaudeLoadBehaviourIsOperatorDriven(unittest.TestCase):
    """VF-011 — the controller never launches the L1-A24 runtime test."""

    def test_the_operation_is_gated_and_has_no_argv(self):
        self.assertEqual(
            operation_catalog.classify("CLAUDE_LOAD_BEHAVIOUR_TEST"), "GATED")
        with self.assertRaises(operation_catalog.OperationError) as ctx:
            operation_catalog.build_argv("CLAUDE_LOAD_BEHAVIOUR_TEST", {})
        message = str(ctx.exception)
        self.assertIn("operator", message)
        self.assertIn("never writes to the external directory", message)


if __name__ == "__main__":
    unittest.main()
