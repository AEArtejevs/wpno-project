#!/usr/bin/env python3
"""Name every executable and record that takes part, before any of them runs.

An earlier attempt identified `VERIFICATION_RESULT.json` as the verifier. A
result is what a verifier produced; it is never the producer, and a plan that
binds a result while leaving the producer unnamed binds the output of an
unknown process. Every tool is listed here by ROLE with its canonical absolute
path, digest, executable bit, whether the build manifest already covers it,
what it produces, and what will bind it.

`UNIDENTIFIED_TOOLS` must be 0.

Usage: build_tool_inventory.py <workspace> <clone> <r8> <out.json>
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
    covered = set()
    with open(os.path.join(r8, "build", "R8_BUILD_MANIFEST.sha256"),
              encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                covered.add(line.split("  ", 1)[1])
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(r8) + os.sep):
        return False
    return os.path.relpath(real, os.path.realpath(r8)) in covered


def main():
    ws, clone, r8, out_path = (os.path.realpath(sys.argv[1]),
                               os.path.realpath(sys.argv[2]),
                               os.path.realpath(sys.argv[3]), sys.argv[4])
    T, F = os.path.join(ws, "tools"), os.path.join(ws, "freeze_output")
    BOUND = "installed into the R8 verifier directory; bound by the freeze plan"

    spec = [
        ("FINAL_VERIFICATION_INSTRUCTIONS",
         os.path.join(T, "VERIFY_PROMPT_LINEAGE_FINAL.md"),
         "the exact text handed to the fresh Codex process on stdin", BOUND),
        ("VERIFICATION_RUNNER",
         os.path.join(T, "run_lineage_verification.sh"),
         "launches one fresh Codex process and waits on its exact PID", BOUND),
        ("SCHEMA_MAP", os.path.join(ws, "VERIFIER_SCHEMA_MAP.json"),
         "every key any check names, proved present in the real bytes", BOUND),
        ("SCHEMA_MAP_BUILDER",
         os.path.join(T, "build_lineage_schema_map.py"),
         "VERIFIER_SCHEMA_MAP.json", BOUND),
        ("CLONE_BUILDER", os.path.join(T, "make_clone.sh"),
         "the disposable sibling clone", BOUND),
        ("CLONE_PREFLIGHT", os.path.join(T, "preflight_clone.py"),
         "preflight/PREFLIGHT.json", BOUND),
        ("FIXED_TARGET_CHECK", os.path.join(T, "fixed_target_check.py"),
         "the fixed-state check taken before any write", BOUND),
        ("INVENTORY_SCRIPT", os.path.join(T, "inventory_r8.py"),
         "a full path/type/size/sha256/symlink/mode/uid/gid/mtime_ns "
         "inventory of a tree", BOUND),
        ("INVENTORY_COMPARATOR", os.path.join(T, "compare_inventories.py"),
         "the before/after comparison that proves write isolation", BOUND),
        ("ABSOLUTE_PATH_MEASUREMENT_HELPER",
         os.path.join(T, "measure_path.py"),
         "one observation per file carrying requested path, resolved absolute "
         "path and owning root; refuses a backwards mtime", BOUND),
        ("CONCURRENT_WRITER_INSPECTOR", os.path.join(T, "inspect_writers.py"),
         "WRITER_INSPECTION_*.json from /proc/<pid>/fd and fdinfo", BOUND),
        ("TEST_RUNNER", os.path.join(T, "run_package_suite.py"),
         "the two-pass package-suite runner: the suite in the clone, plus "
         "in-situ re-measurement of any location-bound failure with a full "
         "inventory proof that the re-measurement wrote nothing", BOUND),
        ("TOOL_INVENTORY_BUILDER", os.path.abspath(__file__), "this file",
         BOUND),
        ("FREEZE_PLAN_BUILDER",
         os.path.join(F, "build_r8_freeze_plan_attempt_3.py"),
         "build/freeze_plan_attempt_3/FREEZE_PLAN_R8_ATTEMPT_3.json and the "
         "exact token text; issues no token of its own",
         "binds itself into the plan it writes"),
        ("FREEZE_PLAN_VALIDATOR",
         os.path.join(F, "validate_freeze_plan_attempt_3.py"),
         "an independent validation record over the completed plan, and the "
         "token digest by two methods", "bound by the freeze plan"),
        ("LINEAGE_RULE_DECLARATION",
         os.path.join(r8, "automation", "freeze.py"),
         "PACKAGE_LINEAGE_MODEL, required_predecessor_lineage_artifacts and "
         "assert_lineage_bound -- the one source of truth the controller, the "
         "builder and the validator all read",
         "covered by the build manifest; bound by the freeze plan"),
        ("FREEZE_ROUTE", os.path.join(r8, "automation", "controller.py"),
         "the only route permitted to freeze; carries the repaired step-9 gate",
         "covered by the build manifest; bound by the freeze plan"),
        ("LINEAGE_REGRESSION_SUITE",
         os.path.join(r8, "automation", "package_tests",
                      "test_r8_freeze_lineage.py"),
         "the focused lineage tests and the end-to-end run of the actual "
         "cmd_freeze_level1 route in a disposable package",
         "covered by the build manifest; bound by the freeze plan"),
        ("FREEZE_ORDER_REGRESSION_SUITE",
         os.path.join(r8, "automation", "package_tests",
                      "test_freeze_order_regression.py"),
         "the end-to-end freeze-ordering suite, with its fixture no longer "
         "deriving the impossible lineage filename",
         "covered by the build manifest; bound by the freeze plan"),
        ("TOKEN_GRAMMAR_CONSTANTS",
         os.path.join(r8, "automation", "policy.py"),
         "the token prefix and suffix",
         "covered by the build manifest; bound by the freeze plan"),
        ("MIGRATION_ROUTE", os.path.join(r8, "automation", "migration.py"),
         "applies the pre-freeze-bound R7 to R8 packet exactly once",
         "covered by the build manifest; bound by the freeze plan"),
        ("PACKAGE_TEST_RUNNER_IN_PACKAGE",
         os.path.join(r8, "build", "run_test_suites.py"),
         "build/R8_TEST_SUITE_RESULTS.json",
         "covered by the build manifest; bound by the freeze plan"),
        ("STATIC_SAFETY_RUNNER",
         os.path.join(r8, "build", "r8_static_safety_review.py"),
         "build/R8_STATIC_SAFETY_REPORT.json",
         "covered by the build manifest; bound by the freeze plan"),
        ("BUILD_MANIFEST_BUILDER",
         os.path.join(r8, "build", "build_r8_build_manifest.py"),
         "build/R8_BUILD_MANIFEST.sha256",
         "covered by the build manifest; bound by the freeze plan"),
        ("CLOSURE_RECORD_BUILDER",
         os.path.join(r8, "build", "build_r8_closure_record.py"),
         "build/R8_FINAL_PRE_FREEZE_CLOSURE.json",
         "covered by the build manifest; bound by the freeze plan"),
        ("SUPERSEDED_FREEZE_PLAN_BUILDER_ATTEMPT_1",
         os.path.join(r8, "build", "freeze_plan_attempt_1",
                      "build_r8_freeze_plan.py"),
         "attempt 1's builder; preserved unchanged and NOT used here",
         "bound by attempt 1's own plan"),
        ("SUPERSEDED_FREEZE_PLAN_BUILDER_ATTEMPT_2",
         os.path.join(r8, "build", "freeze_plan_attempt_2",
                      "build_r8_freeze_plan_attempt_2.py"),
         "attempt 2's builder; its plan was valid and its token validated "
         "byte-exact, but the controller refused the freeze unconsumed. "
         "Preserved unchanged and NOT used here",
         "bound by attempt 2's own plan, which is superseded"),
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
    from automation import freeze                          # noqa: E402
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
    lineage_source = inspect.getsource(freeze.assert_lineage_bound)
    tools.append({
        "ROLE": "LINEAGE_GATE_FUNCTION_SOURCE",
        "CANONICAL_PATH": "%s/automation/freeze.py::assert_lineage_bound" % r8,
        "SHA256": hashlib.sha256(lineage_source.encode("utf-8")).hexdigest(),
        "EXECUTABLE": False, "MANIFEST_COVERED": True,
        "EXPECTED_OUTPUT": ("the tuple of lineage artefacts it checked, or a "
                            "FreezeError naming the exact failure"),
        "BOUND_BY": ("the freeze plan's predecessor_lineage block and the "
                     "module digest")})
    tools.append({
        "ROLE": "FREEZE_PLAN_WRAPPER", "CANONICAL_PATH": "NOT_USED",
        "SHA256": "NOT_USED", "EXECUTABLE": False, "MANIFEST_COVERED": False,
        "EXPECTED_OUTPUT": ("none. No wrapper stands between the builder and "
                            "the plan; the builder is invoked directly."),
        "BOUND_BY": ("declared NOT_USED in the plan, so its absence is "
                     "recorded rather than merely true")})

    doc = {"schema": "wpno.r8.lineage-repair-tool-inventory/1",
           "workspace": ws, "clone": clone, "r8_root": r8,
           "rule": ("a result is not a verifier. VERIFICATION_RESULT.json "
                    "appears in no producing role here."),
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
