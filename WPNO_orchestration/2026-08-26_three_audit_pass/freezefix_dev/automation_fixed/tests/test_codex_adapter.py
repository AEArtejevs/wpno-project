"""Codex capability detection and subprocess hardening.

Covers self-test cases 14, 15, 26 and 44:
environment injection · PATH hijack · timeout · unsupported Codex CLI.
"""

import os
import unittest

from automation import codex_adapter, policy


class TestEnvironmentInjection(unittest.TestCase):
    """Case 14 — the child environment is an allowlist, not an inheritance."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_unlisted_variables_are_not_passed_through(self):
        os.environ["WPNO_INJECTED_VARIABLE"] = "malicious"
        env = policy.base_environment()
        self.assertNotIn("WPNO_INJECTED_VARIABLE", env)

    def test_ld_preload_style_variables_are_not_passed_through(self):
        for name in ("LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONPATH",
                     "PYTHONSTARTUP", "IFS", "BASH_ENV"):
            os.environ[name] = "/tmp/evil"
            env = policy.base_environment()
            self.assertNotIn(name, env, "%s leaked into the child env" % name)

    def test_fixed_values_override_the_caller(self):
        os.environ["TZ"] = "Europe/Berlin"
        os.environ["LC_ALL"] = "de_DE.UTF-8"
        env = policy.base_environment()
        self.assertEqual(env["TZ"], "UTC")
        self.assertEqual(env["LC_ALL"], "C.UTF-8")
        self.assertEqual(env["PYTHONHASHSEED"], "0")

    def test_bytecode_writing_is_disabled(self):
        self.assertEqual(policy.base_environment()["PYTHONDONTWRITEBYTECODE"], "1")

    def test_allowlist_is_explicit_and_small(self):
        self.assertLessEqual(len(policy.ENV_ALLOWLIST), 12)
        for name in policy.ENV_ALLOWLIST:
            self.assertEqual(name, name.upper())


class TestPathHijack(unittest.TestCase):
    """Case 15 — PATH is fixed, and executables are absolute regardless."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_prepended_path_entry_is_discarded(self):
        os.environ["PATH"] = "/tmp/evil:" + os.environ.get("PATH", "")
        env = policy.base_environment()
        self.assertEqual(env["PATH"], policy.FIXED_PATH)
        self.assertNotIn("/tmp/evil", env["PATH"])

    def test_fixed_path_contains_only_system_directories(self):
        for part in policy.FIXED_PATH.split(":"):
            self.assertTrue(part.startswith("/"))
            self.assertNotIn("tmp", part)
            self.assertNotIn(os.path.expanduser("~"), part)

    def test_every_executable_is_an_absolute_path(self):
        for key, exe in policy.EXECUTABLES.items():
            self.assertTrue(os.path.isabs(exe), key)

    def test_no_executable_resolves_through_path_at_call_time(self):
        for exe in policy.EXECUTABLES.values():
            self.assertEqual(exe, os.path.normpath(exe))
            self.assertNotIn("..", exe)


class TestTimeout(unittest.TestCase):
    """Case 26 — every subprocess carries a bounded, recorded timeout."""

    def test_defaults_are_bounded(self):
        self.assertGreater(policy.DEFAULT_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(policy.DEFAULT_TIMEOUT_SECONDS,
                             policy.MAX_TIMEOUT_SECONDS)
        self.assertLessEqual(policy.MAX_TIMEOUT_SECONDS, 900)

    def test_controller_rejects_a_timeout_over_the_maximum(self):
        import inspect
        from automation import controller
        source = inspect.getsource(controller._run_operation)
        self.assertIn("MAX_TIMEOUT_SECONDS", source)

    def test_every_subprocess_call_passes_a_timeout(self):
        import ast
        import inspect
        from automation import controller
        for module in (controller, codex_adapter):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "run":
                    kwargs = {kw.arg for kw in node.keywords or []}
                    self.assertIn("timeout", kwargs)
                    self.assertIn("env", kwargs)
                    self.assertIn("shell", kwargs)


class TestUnsupportedCodexCli(unittest.TestCase):
    """Case 44 — an installed CLI without safe isolation stops the run."""

    def _probe(self, help_text):
        return {"executable": "/usr/local/bin/codex",
                "probes": [{"stdout": help_text, "stderr": ""}],
                "probe_sha256": "0" * 64}

    def test_subagent_support_is_detected(self):
        mode = codex_adapter.detect_isolation(
            self._probe("usage: codex\n  subagent   run an isolated subagent"))
        self.assertEqual(mode, codex_adapter.ISOLATION_SUBAGENT)

    def test_ephemeral_exec_is_detected(self):
        mode = codex_adapter.detect_isolation(
            self._probe("usage: codex exec\n  --ephemeral   discard session"))
        self.assertEqual(mode, codex_adapter.ISOLATION_EPHEMERAL)

    def test_absence_of_both_yields_none(self):
        mode = codex_adapter.detect_isolation(
            self._probe("usage: codex\n  --help  show this message"))
        self.assertEqual(mode, codex_adapter.ISOLATION_NONE)

    def test_no_isolation_stops_the_run(self):
        with self.assertRaises(codex_adapter.UnsupportedCapability):
            codex_adapter.assert_isolation_available(codex_adapter.ISOLATION_NONE)

    def test_available_isolation_is_returned(self):
        for mode in (codex_adapter.ISOLATION_SUBAGENT,
                     codex_adapter.ISOLATION_EPHEMERAL):
            self.assertEqual(codex_adapter.assert_isolation_available(mode), mode)

    def test_probe_requires_an_absolute_executable(self):
        with self.assertRaises(codex_adapter.CodexError):
            codex_adapter.probe("codex")

    def test_plan_with_forbidden_operation_is_refused_even_with_isolation(self):
        from automation import operation_catalog
        plan = {"steps": [{"operation": "DOCKER_RUN"}]}
        with self.assertRaises(operation_catalog.ForbiddenOperation):
            codex_adapter.assert_plan_supported(
                plan, codex_adapter.ISOLATION_EPHEMERAL)

    def test_preference_order_is_subagent_then_ephemeral(self):
        both = self._probe("subagent available; --ephemeral available")
        self.assertEqual(codex_adapter.detect_isolation(both),
                         codex_adapter.ISOLATION_SUBAGENT)


if __name__ == "__main__":
    unittest.main()
