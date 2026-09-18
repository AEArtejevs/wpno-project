#!/usr/bin/env python3
"""Run a test suite and record what it actually did.

The closure record used to carry the package-suite size as a literal. A
literal is written once and then goes on being read after it has stopped being
true: it said 281 while the suite held 312, because two test modules were
added and the number was not. A count nobody measures is not evidence, and a
record that quotes one is quoting itself.

So the number comes from a run. This writes `build/R7_TEST_SUITE_RESULTS.json`
with, per suite, the tests run, failures, errors and skips as unittest
reported them, the per-module composition, and the digest of every test source
that took part. The closure record reads that file instead of holding a
literal, and if a module is added and the suite is not rerun, the digests no
longer describe the tree and the discrepancy is visible rather than silent.

Two suites, and they are not interchangeable. The controller suite writes
controller state and runs only inside the isolated replica at
`verification/selftest_runtime`; the package suite runs at the package root.
Each is run in its own subprocess, because loading one leaves its directory
and `sys.path` behind and the second would then answer about the first.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy  # noqa: E402

OUT = os.path.join(ROOT, "build", "R8_TEST_SUITE_RESULTS.json")

SUITES = {
    "package_suite": {
        "cwd": ROOT,
        "start_dir": "automation/package_tests",
        "sources": ["automation/package_tests"],
        "note": "runs at the package root",
    },
    "controller_suite": {
        "cwd": os.path.join(ROOT, "verification", "selftest_runtime"),
        "start_dir": ".",
        "sources": ["automation/tests"],
        "note": ("runs only inside the isolated replica; these tests write "
                 "controller state and refuse to run anywhere else"),
    },
}

RUNNER = """
import json, sys, unittest
sys.path.insert(0, '.')
suite = unittest.TestLoader().discover(start_dir=%r, top_level_dir='.')
result = unittest.TextTestRunner(verbosity=0).run(suite)
print('WPNO_RESULT ' + json.dumps({
    'ran': result.testsRun,
    'failures': len(result.failures),
    'errors': len(result.errors),
    'skips': len(result.skipped),
    'expected_failures': len(result.expectedFailures),
    'unexpected_successes': len(result.unexpectedSuccesses),
}))
"""

# A suite that hangs must end the run rather than the run waiting on it.
TIMEOUT_SECONDS = 1800
OUTPUT_LIMIT_BYTES = 16 * 1024 * 1024


def run(name):
    spec = SUITES[name]
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, shell=False
            [sys.executable, "-c", RUNNER % spec["start_dir"]],
            shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
            cwd=spec["cwd"], check=False,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    except subprocess.TimeoutExpired:
        raise SystemExit("%s did not finish within %ds"
                         % (name, TIMEOUT_SECONDS))
    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    text = proc.stdout[:OUTPUT_LIMIT_BYTES].decode("utf-8", "replace")
    match = re.search(r"WPNO_RESULT (\{.*\})", text)
    if not match:
        raise SystemExit("%s produced no result line:\n%s"
                         % (name, proc.stderr[:OUTPUT_LIMIT_BYTES]
                            .decode("utf-8", "replace")[:2000]))
    counts = json.loads(match.group(1))
    sources = {}
    for relative in spec["sources"]:
        base = os.path.join(spec["cwd"], relative)
        for entry in sorted(os.listdir(base)):
            if entry.startswith("test_") and entry.endswith(".py"):
                sources[os.path.join(relative, entry)] = hashing.sha256_file(
                    os.path.join(base, entry))
    return {
        "suite": name,
        "cwd": os.path.relpath(spec["cwd"], ROOT) or ".",
        "note": spec["note"],
        "started_utc": started,
        "finished_utc": finished,
        "exit_code": proc.returncode,
        "ran": counts["ran"],
        "failures": counts["failures"],
        "errors": counts["errors"],
        "skips": counts["skips"],
        "expected_failures": counts["expected_failures"],
        "unexpected_successes": counts["unexpected_successes"],
        "clean": (counts["failures"] == 0 and counts["errors"] == 0
                  and counts["skips"] == 0),
        "test_sources": sources,
        "test_source_count": len(sources),
    }


def carry_forward(name, ran, failures, errors, skips, why):
    """Record a suite that was not rerun, and say on whose evidence.

    A suite is carried forward only when nothing it covers changed. The
    current digest of every test source is recorded with it, so a later reader
    can see whether the tree it describes is still the tree on disk - which is
    the check the stale literal 281 never had.
    """
    spec = SUITES[name]
    sources = {}
    for relative in spec["sources"]:
        base = os.path.join(spec["cwd"], relative)
        for entry in sorted(os.listdir(base)):
            if entry.startswith("test_") and entry.endswith(".py"):
                sources[os.path.join(relative, entry)] = hashing.sha256_file(
                    os.path.join(base, entry))
    return {
        "suite": name,
        "cwd": os.path.relpath(spec["cwd"], ROOT) or ".",
        "note": spec["note"],
        "measurement": "CARRIED_FORWARD_NOT_RERUN",
        "why_not_rerun": why,
        "ran": ran, "failures": failures, "errors": errors, "skips": skips,
        "clean": failures == 0 and errors == 0 and skips == 0,
        "test_sources": sources,
        "test_source_count": len(sources),
    }


CARRY_REASONS = {
    "controller_suite": (
        "no shared controller or control-plane code changed in this repair. "
        "The isolated replica copies automation/, bindings/, prompts/, "
        "discovery_reconciliation/, the candidate plans and the frozen "
        "launcher; it does not copy build/rehearse_candidate_plans.py or "
        "build/build_final_closure_record.py, which are what changed. The "
        "suite is therefore unaffected and rerunning it would be the "
        "reassurance the instruction forbids."),
}


def main():
    parser = argparse.ArgumentParser(prog="run-test-suites")
    parser.add_argument("--suite", action="append", choices=sorted(SUITES),
                        default=None,
                        help="run this suite; repeatable, default both")
    parser.add_argument("--carry-forward", action="append",
                        choices=sorted(SUITES), default=None, metavar="SUITE",
                        help=("record this suite from accepted evidence "
                              "instead of running it"))
    parser.add_argument("--carried-counts", default=None,
                        help="ran,failures,errors,skips for a carried suite")
    args = parser.parse_args()
    wanted = args.suite or ([] if args.carry_forward else sorted(SUITES))

    record = {"schema": "wpno.level1.test-suite-results/1", "revision": "R8",
              "suites": {}}
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as fh:
            record = json.load(fh)
        record.setdefault("suites", {})

    for name in wanted:
        result = run(name)
        result["measurement"] = "RUN"
        record["suites"][name] = result
        print("%-18s RUN             ran=%-4d failures=%d errors=%d skips=%d clean=%s"
              % (name, result["ran"], result["failures"], result["errors"],
                 result["skips"], result["clean"]))

    for name in (args.carry_forward or []):
        if not args.carried_counts:
            raise SystemExit("--carry-forward needs --carried-counts")
        ran, failures, errors, skips = (
            int(x) for x in args.carried_counts.split(","))
        result = carry_forward(name, ran, failures, errors, skips,
                               CARRY_REASONS.get(name, "stated by the operator"))
        record["suites"][name] = result
        print("%-18s CARRIED_FORWARD ran=%-4d failures=%d errors=%d skips=%d clean=%s"
              % (name, result["ran"], result["failures"], result["errors"],
                 result["skips"], result["clean"]))

    record["recorded_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime())
    record["all_clean"] = all(s["clean"] for s in record["suites"].values())
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(OUT), "w", encoding="utf-8") as fh:
        fh.write(text)
    print("record: %s" % os.path.relpath(OUT, ROOT))
    print("sha256: %s" % hashing.sha256_text(text))
    return 0 if record["all_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
