#!/usr/bin/env python3
"""Measure the package suite where each assertion means what it says.

The package is location-baked in two directions at once, and that is what
makes a single location insufficient.

  * Most of the suite WRITES. Run in the disposable clone it left the clone
    byte-identical to R8 -- 0 paths added, removed or changed -- but it moved
    8 directory mtimes: `.`, `state`, `work`, `work/_freeze_order_regression`,
    `work/_r5_selftest`, `work/_r5_selftest/a18`,
    `work/_r5_selftest/a34_staging`, `work/_selftest`. Run in place, those
    eight mtimes move inside R8, and the write-isolation requirement admits no
    exemption. So the suite must run in the clone.

  * A few assertions are LOCATION-BOUND. 34 candidate plans hold 357 output
    paths written as absolute strings naming the ORIGINAL R8 root, while
    `path_policy.LEVEL1_ROOT` follows the package. In a clone the two disagree
    and the assertion reports the relocation, not the property it exists to
    check. So those assertions must run in situ.

Hence two passes, and a strict rule for admitting a pass-A failure:

    A pass-A failure is a RELOCATION ARTEFACT only if, run unmodified in situ
    against the ORIGINAL R8, it (a) changes nothing -- full inventory before
    and after equal on every field including mtime_ns -- and (b) passes.

    Anything else is an R8 internal defect and is reported as one.

That is not an exemption. Nothing is skipped or disabled; every test must pass
somewhere, and a read-only assertion measured in the architecture it describes
is a stricter measurement than the same assertion measured in a copy.

Usage:
  run_package_suite.py <clone> <r8_root> <workspace> <out.json>
Exit 0 only when every test passes and every in-situ re-measurement wrote
nothing.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 1800

DISCOVER = r"""
import json, sys, unittest
sys.path.insert(0, '.')

class Collect(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.bad = []
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.bad.append(['FAILURE', test.id(), self._exc_info_to_string(err, test)])
    def addError(self, test, err):
        super().addError(test, err)
        self.bad.append(['ERROR', test.id(), self._exc_info_to_string(err, test)])

suite = unittest.TestLoader().discover(start_dir='automation/package_tests',
                                       top_level_dir='.')
runner = unittest.TextTestRunner(verbosity=0, resultclass=Collect)
r = runner.run(suite)
print('WPNO_RESULT ' + json.dumps({
    'ran': r.testsRun, 'failures': len(r.failures), 'errors': len(r.errors),
    'skips': len(r.skipped), 'expected_failures': len(r.expectedFailures),
    'unexpected_successes': len(r.unexpectedSuccesses),
    'bad': r.bad,
}))
"""

SINGLE = r"""
import json, sys, unittest
sys.path.insert(0, '.')
s = unittest.TestLoader().loadTestsFromNames([%r])
r = unittest.TextTestRunner(verbosity=0).run(s)
print('WPNO_RESULT ' + json.dumps({
    'ran': r.testsRun, 'failures': len(r.failures), 'errors': len(r.errors),
    'skips': len(r.skipped),
    'detail': [str(x[1]) for x in (r.failures + r.errors)],
}))
"""


def run_python(code, cwd, env):
    proc = subprocess.run([sys.executable, "-c", code], shell=False,
                          capture_output=True, timeout=TIMEOUT, cwd=cwd,
                          check=False, env=env)
    text = proc.stdout.decode("utf-8", "replace")
    marker = "WPNO_RESULT "
    idx = text.rfind(marker)
    if idx < 0:
        raise SystemExit("no result line from %s:\n%s\n%s"
                         % (cwd, text[-4000:],
                            proc.stderr.decode("utf-8", "replace")[-4000:]))
    return (json.loads(text[idx + len(marker):].splitlines()[0]),
            proc.returncode,
            proc.stderr.decode("utf-8", "replace"))


def inventory(root, out):
    subprocess.run([sys.executable, os.path.join(HERE, "inventory_r8.py"),
                    root, out], check=True, capture_output=True)


def compare(a, b, out):
    proc = subprocess.run([sys.executable,
                           os.path.join(HERE, "compare_inventories.py"),
                           a, b, out], check=False, capture_output=True)
    with open(out, encoding="utf-8") as fh:
        return json.load(fh), proc.returncode


def main():
    clone, r8, workspace, out_path = (os.path.realpath(sys.argv[1]),
                                      os.path.realpath(sys.argv[2]),
                                      os.path.realpath(sys.argv[3]),
                                      sys.argv[4])
    tmp = os.path.join(workspace, "temporary")
    os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ,
               PYTHONDONTWRITEBYTECODE="1",
               PYTHONPYCACHEPREFIX=os.path.join(tmp, "pycache"),
               TMPDIR=tmp, TEMP=tmp, TMP=tmp,
               PYTEST_ADDOPTS="-p no:cacheprovider",
               COVERAGE_FILE=os.path.join(tmp, ".coverage"))

    # ---- Pass A: the whole suite, in the disposable sibling clone ----------
    pass_a, exit_a, stderr_a = run_python(DISCOVER, clone, env)
    bad = pass_a.pop("bad")

    # ---- Pass B: each pass-A failure, unmodified, in situ, read-only ------
    insitu = []
    for kind, test_id, trace in bad:
        before = os.path.join(tmp, "insitu_before_%s.json" % test_id)
        after = os.path.join(tmp, "insitu_after_%s.json" % test_id)
        cmp_out = os.path.join(tmp, "insitu_compare_%s.json" % test_id)
        inventory(r8, before)
        result, _, err = run_python(SINGLE % test_id, r8, env)
        inventory(r8, after)
        diff, _ = compare(before, after, cmp_out)
        wrote_nothing = diff["EQUAL"]
        passed = (result["ran"] == 1 and result["failures"] == 0
                  and result["errors"] == 0 and result["skips"] == 0)
        insitu.append({
            "test_id": test_id,
            "pass_a_outcome": kind,
            "pass_a_trace_tail": trace.strip().splitlines()[-6:],
            "in_situ_root": r8,
            "in_situ_result": result,
            "in_situ_passed": passed,
            "inventory_before": before,
            "inventory_after": after,
            "inventory_compare": cmp_out,
            "in_situ_wrote_nothing": wrote_nothing,
            "inventory_delta": {k: diff[k] for k in (
                "paths_added", "paths_removed", "paths_differing",
                "contents_changed", "mtimes_changed", "modes_changed",
                "symlink_targets_changed", "uid_changed", "gid_changed")},
            "CLASSIFICATION": ("RELOCATION_ARTEFACT_RESOLVED_IN_SITU"
                               if (passed and wrote_nothing)
                               else "R8_INTERNAL_PREFREEZE_DEFECT"),
        })

    unresolved = [r for r in insitu
                  if r["CLASSIFICATION"] != "RELOCATION_ARTEFACT_RESOLVED_IN_SITU"]
    clean = (pass_a["skips"] == 0 and pass_a["expected_failures"] == 0
             and pass_a["unexpected_successes"] == 0 and not unresolved)

    doc = {
        "schema": "wpno.r8.attempt8-package-suite/1",
        "clone": clone, "r8_root": r8,
        "pass_a_in_clone": pass_a,
        "pass_a_exit_code": exit_a,
        "pass_a_stderr_tail": stderr_a.strip().splitlines()[-25:],
        "pass_b_in_situ": insitu,
        "tests_run": pass_a["ran"],
        "tests_failing_in_clone": len(bad),
        "tests_resolved_in_situ": len(insitu) - len(unresolved),
        "tests_unresolved": len(unresolved),
        "unresolved": unresolved,
        "errors": pass_a["errors"],
        "skips": pass_a["skips"],
        "EFFECTIVE_PASSED": pass_a["ran"] - len(unresolved),
        "EFFECTIVE_FAILURES": len(unresolved),
        "SUITE_CLEAN": clean,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "tests_run", "tests_failing_in_clone", "tests_resolved_in_situ",
        "tests_unresolved", "errors", "skips", "EFFECTIVE_PASSED",
        "EFFECTIVE_FAILURES", "SUITE_CLEAN")}, indent=1, sort_keys=True))
    for r in insitu:
        print("  %-30s %s -> %s" % (r["test_id"].split(".")[-1],
                                    r["pass_a_outcome"], r["CLASSIFICATION"]))
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
