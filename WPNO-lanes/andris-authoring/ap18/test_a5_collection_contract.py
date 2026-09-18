#!/usr/bin/env python3
"""Standard-library contract checks for AP18 pytest discoverability."""

import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "ap18" / "AP18_test_injection.py"
FILTER = ROOT / "ap18" / "AP18_eingangsfilter.py"
PYTEST_INI = ROOT / "pytest.ini"


class A5CollectionContractTests(unittest.TestCase):
    def test_pytest_configuration_includes_ap18_target(self):
        config = PYTEST_INI.read_text(encoding="utf-8")
        testpaths = re.search(r"^testpaths\s*=\s*(.+)$", config, re.MULTILINE)
        patterns = re.search(r"^python_files\s*=\s*(.+)$", config, re.MULTILINE)
        self.assertIsNotNone(testpaths)
        self.assertIn("ap18", testpaths.group(1).split())
        self.assertIsNotNone(patterns)
        self.assertIn("AP18_test_*.py", patterns.group(1).split())

    def test_target_has_collectable_tests_and_real_assert_statements(self):
        tree = ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))
        tests = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        self.assertGreaterEqual(len(tests), 3)
        self.assertGreaterEqual(len(assertions), 6)

    def test_import_does_not_require_pdf_dependency(self):
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(TARGET.parent)!r}); "
            "import AP18_test_injection; print('IMPORTED')"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("IMPORTED", result.stdout.strip())

    def test_unittest_executes_the_collectable_ap18_tests(self):
        code = (
            "import sys, unittest; "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            "suite = unittest.defaultTestLoader.loadTestsFromName("
            "'ap18.AP18_test_injection'); "
            "result = unittest.TextTestRunner(verbosity=1).run(suite); "
            "raise SystemExit(0 if result.wasSuccessful() else 1)"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertRegex(result.stderr, r"Ran\s+[3-9]\d*\s+tests?")

    def test_deliberate_filter_weakening_fails_the_ap18_suite(self):
        source = FILTER.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(FILTER))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "anweisungen_finden"
        )
        lines = source.splitlines(keepends=True)
        mutated_source = "".join(
            lines[:function.lineno - 1]
            + ["def anweisungen_finden(text):\n", "    return []\n"]
            + lines[function.end_lineno:]
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / TARGET.name).write_text(
                TARGET.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (directory / FILTER.name).write_text(
                mutated_source, encoding="utf-8"
            )
            code = (
                "import sys, unittest; "
                f"sys.path.insert(0, {tmp!r}); "
                "suite = unittest.defaultTestLoader.loadTestsFromName("
                "'AP18_test_injection.TestAP18Injection'); "
                "result = unittest.TextTestRunner(verbosity=1).run(suite); "
                "raise SystemExit(0 if result.wasSuccessful() else 1)"
            )
            results = [
                subprocess.run(
                    [sys.executable, *flags, "-I", "-B", "-c", code],
                    cwd=directory,
                    env={"PATH": os.environ.get("PATH", "")},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                for flags in ([], ["-O"])
            ]
        for result in results:
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("FAILED (failures=", result.stderr)
            self.assertIn("test_versteckte_anweisung_wird_blockiert", result.stderr)


if __name__ == "__main__":
    unittest.main()
