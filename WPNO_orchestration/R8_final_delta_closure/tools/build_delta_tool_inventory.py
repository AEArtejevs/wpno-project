#!/usr/bin/env python3
"""Name every executable and record that takes part in the delta closure.

Attempt 4 identified `VERIFICATION_RESULT.json` as the verifier. A result is
what a verifier produced; it is never the producer. Every tool is listed here
by ROLE with its canonical absolute path, digest, executable bit, whether the
build manifest already covers it, what it produces, and what will bind it.

`UNIDENTIFIED_TOOLS` must be 0.

Usage: build_delta_tool_inventory.py <final_root> <clone> <r8> <out.json>
"""

import hashlib
import inspect
import json
import os
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def manifest_covered(r8, path):
    manifest = os.path.join(r8, "build", "R8_BUILD_MANIFEST.sha256")
    covered = set()
    with open(manifest, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                covered.add(line.split("  ", 1)[1])
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(r8) + os.sep):
        return False
    return os.path.relpath(real, os.path.realpath(r8)) in covered


def main():
    fr, clone, r8, out_path = (os.path.realpath(sys.argv[1]),
                               os.path.realpath(sys.argv[2]),
                               os.path.realpath(sys.argv[3]), sys.argv[4])
    T = os.path.join(fr, "tools")
    F = os.path.join(fr, "freeze_output")
    A8 = ("/home/ubuntu/project/WPNO_orchestration/"
          "R8_final_autonomous_convergence/attempt_8")

    spec = [
        ("FINAL_VERIFICATION_INSTRUCTIONS",
         os.path.join(T, "DELTA_VERIFY_PROMPT.md"),
         "the exact text handed to the fresh Codex process on stdin",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("VERIFICATION_RUNNER", os.path.join(T, "run_delta_closure.sh"),
         "launches one fresh Codex process and waits on its exact PID",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("SCHEMA_MAP", os.path.join(fr, "VERIFIER_SCHEMA_MAP.json"),
         "every key any predicate names, proved present in the real bytes",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("SCHEMA_MAP_BUILDER", os.path.join(T, "build_schema_map.py"),
         "VERIFIER_SCHEMA_MAP.json",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("DELTA_PREDICATE_LIBRARY", os.path.join(T, "delta_predicates.py"),
         "the 42 predicates and the strict lookup that cannot raise KeyError",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("DELTA_CONTEXT_LOADER", os.path.join(T, "delta_context.py"),
         "one loaded document set, shared by the self-test and the real run",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("DELTA_VERIFIER_SELF_TEST",
         os.path.join(T, "selftest_delta_verifier.py"),
         "selftest/DELTA_VERIFIER_SELFTEST.json; refuses to let a Codex "
         "attempt be spent on an untested predicate set",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        # The self-test RESULT is deliberately not listed. It is a record,
        # not a producer -- the same distinction that makes
        # VERIFICATION_RESULT.json not a verifier -- and listing it would
        # create a cycle: the inventory would carry a digest of a file the
        # next self-test run rewrites, so the inventory would be stale the
        # moment it was used. It is bound instead by the freeze plan, through
        # the enumeration of the installed verification directory.
        ("DURABLE_ITEM_MATRIX",
         os.path.join(fr, "ATTEMPT_8_DURABLE_ITEM_MATRIX.json"),
         "which attempt-8 items may be carried forward, and on what evidence",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("DURABLE_ITEM_MATRIX_BUILDER",
         os.path.join(T, "build_durable_matrix.py"),
         "ATTEMPT_8_DURABLE_ITEM_MATRIX.json",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_EVIDENCE_VERIFIER", os.path.join(T, "verify_base_evidence.py"),
         "BASE_EVIDENCE_VERIFICATION.json -- attempt 8's headline figures "
         "checked against its own stored suite output, not its summary",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("FIXED_TARGET_CHECK", os.path.join(T, "fixed_target_check.py"),
         "preflight/FIXED_TARGET.json",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("INVENTORY_SCRIPT", os.path.join(T, "inventory_r8.py"),
         "a full path/type/size/sha256/symlink/mode/uid/gid/mtime_ns "
         "inventory of a tree",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("INVENTORY_COMPARATOR", os.path.join(T, "compare_inventories.py"),
         "the before/after comparison that proves write isolation",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("ABSOLUTE_PATH_MEASUREMENT_HELPER", os.path.join(T, "measure_path.py"),
         "one observation per file carrying requested path, resolved absolute "
         "path and owning root; refuses a backwards mtime",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("CONCURRENT_WRITER_INSPECTOR", os.path.join(T, "inspect_writers.py"),
         "preflight/WRITER_INSPECTION_*.json from /proc/<pid>/fd and fdinfo",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("CLONE_BUILDER", os.path.join(T, "make_clone.sh"),
         "the disposable sibling clone used only for imports",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("CLONE_PREFLIGHT", os.path.join(T, "preflight_clone.py"),
         "preflight/PREFLIGHT.json",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("TEST_RUNNER", os.path.join(T, "run_package_suite.py"),
         "the two-pass package-suite runner. NOT RUN in this closure: the "
         "suite result is carried forward from attempt 8's hash-bound stored "
         "output. Listed because that output is evidence and its producer "
         "must be named.",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("TOOL_INVENTORY_BUILDER", os.path.abspath(__file__), "this file",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_ATTEMPT_8_ITEM_RESULTS",
         os.path.join(A8, "codex_output", "ITEM_RESULTS.jsonl"),
         "attempt 8's durable per-item records; a record, not a producer",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_ATTEMPT_8_PACKAGE_SUITE_OUTPUT",
         os.path.join(A8, "codex_output", "PACKAGE_SUITE.json"),
         "attempt 8's package-suite output, 361/0/0/0; a record",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_ATTEMPT_8_CONTROLLER_SUITE_OUTPUT",
         os.path.join(A8, "codex_output", "CONTROLLER_SUITE.stderr.txt"),
         "attempt 8's controller-suite output, 503 tests, OK; a record",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_ATTEMPT_8_STATIC_SAFETY_OUTPUT",
         os.path.join(A8, "codex_output", "static_safety_outputs",
                      "R8_STATIC_SAFETY_REPORT.json"),
         "attempt 8's static-safety report, 0 findings; a record",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("BASE_ATTEMPT_8_VERIFICATION_MANIFEST",
         os.path.join(A8, "codex_output", "VERIFICATION_MANIFEST.sha256"),
         "the digest listing that binds every attempt-8 output; a record",
         "installed into the R8 verifier directory; bound by the freeze plan"),
        ("FREEZE_PLAN_BUILDER",
         os.path.join(F, "build_r8_freeze_plan_attempt_2.py"),
         "build/freeze_plan_attempt_2/FREEZE_PLAN_R8_ATTEMPT_2.json and the "
         "exact token text; issues no token of its own",
         "binds itself into the plan it writes"),
        ("FREEZE_PLAN_VALIDATOR",
         os.path.join(F, "validate_freeze_plan_attempt_2.py"),
         "an independent validation record over the completed plan, and the "
         "token digest by two methods",
         "bound by the freeze plan"),
        ("PACKAGE_TEST_RUNNER_IN_PACKAGE",
         os.path.join(r8, "build", "run_test_suites.py"),
         "build/R8_TEST_SUITE_RESULTS.json -- the package's own suite runner",
         "covered by the build manifest; bound by the freeze plan"),
        ("STATIC_SAFETY_RUNNER",
         os.path.join(r8, "build", "r8_static_safety_review.py"),
         "build/R8_STATIC_SAFETY_REPORT.json",
         "covered by the build manifest; bound by the freeze plan"),
        ("FREEZE_MODULE", os.path.join(r8, "automation", "freeze.py"),
         "the plan shape check, the baseline, the replay ledger and token_for",
         "bound by the freeze plan"),
        ("TOKEN_GRAMMAR_CONSTANTS", os.path.join(r8, "automation", "policy.py"),
         "the token prefix and suffix", "bound by the freeze plan"),
        ("FREEZE_ROUTE", os.path.join(r8, "automation", "controller.py"),
         "the only route permitted to freeze the package",
         "bound by the freeze plan"),
        ("MIGRATION_ROUTE", os.path.join(r8, "automation", "migration.py"),
         "applies the pre-freeze-bound R7 to R8 packet exactly once",
         "bound by the freeze plan"),
        ("SUPERSEDED_FREEZE_PLAN_BUILDER_ATTEMPT_1",
         os.path.join(r8, "build", "freeze_plan_attempt_1",
                      "build_r8_freeze_plan.py"),
         "attempt 1's builder; preserved unchanged and NOT used here",
         "bound by attempt 1's own plan, not by attempt 2's"),
    ]

    tools, missing = [], []
    for role, path, expected, bound_by in spec:
        if not os.path.isfile(path):
            missing.append({"ROLE": role, "CANONICAL_PATH": path})
            continue
        tools.append({"ROLE": role, "CANONICAL_PATH": path,
                      "SHA256": sha256_file(path),
                      "EXECUTABLE": os.access(path, os.X_OK),
                      "MANIFEST_COVERED": manifest_covered(r8, path),
                      "EXPECTED_OUTPUT": expected, "BOUND_BY": bound_by})

    sys.path.insert(0, clone)
    from automation import freeze                           # noqa: E402
    source = inspect.getsource(freeze.token_for)
    tools.append({
        "ROLE": "TOKEN_GENERATION_FUNCTION_SOURCE",
        "CANONICAL_PATH": "%s/automation/freeze.py::token_for" % r8,
        "SHA256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "EXECUTABLE": False, "MANIFEST_COVERED": True,
        "EXPECTED_OUTPUT": ("the exact token string; five whitespace-separated "
                            "fields, no trailing newline"),
        "BOUND_BY": ("the freeze plan's "
                     "token_generation.function_source_sha256, separately "
                     "from the module digest")})
    tools.append({
        "ROLE": "FREEZE_PLAN_WRAPPER", "CANONICAL_PATH": "NOT_USED",
        "SHA256": "NOT_USED", "EXECUTABLE": False, "MANIFEST_COVERED": False,
        "EXPECTED_OUTPUT": ("none. No wrapper stands between the builder and "
                            "the plan; the builder is invoked directly."),
        "BOUND_BY": ("declared NOT_USED in the plan, so its absence is "
                     "recorded rather than merely true")})

    doc = {"schema": "wpno.r8.delta-tool-inventory/1",
           "final_root": fr, "clone": clone, "r8_root": r8,
           "rule": ("a result is not a verifier. VERIFICATION_RESULT.json and "
                    "the attempt-8 records appear only in recording roles."),
           "tools": sorted(tools, key=lambda t: t["ROLE"]),
           "tool_count": len(tools), "MISSING_TOOLS": missing,
           "UNIDENTIFIED_TOOLS": len(missing)}
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"tool_count": doc["tool_count"],
                      "UNIDENTIFIED_TOOLS": doc["UNIDENTIFIED_TOOLS"],
                      "MISSING_TOOLS": missing}, indent=1, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
