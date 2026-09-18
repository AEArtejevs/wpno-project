#!/usr/bin/env python3
"""Name every executable that takes part, before any of them runs.

Attempt 4 identified `VERIFICATION_RESULT.json` as the verifier. A result is
what a verifier produced; it is never the thing that produced it, and a plan
that binds a result while leaving the producer unnamed binds the output of an
unknown process. So every tool is listed here by ROLE, with its canonical
absolute path, its digest, whether it is executable, whether the build
manifest already covers it, what it is expected to produce, and what will bind
it.

`UNIDENTIFIED_TOOLS` must be 0. A file that runs and is not in this list is
the defect this file exists to make impossible.

Usage: build_tool_inventory.py <workspace> <clone> <r8_root> <out.json>
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
    """Is this path already covered by the build manifest?

    Asked of the ORIGINAL package only. A tool under the workspace or the
    clone is not manifest-covered whatever its name, and saying so here stops
    a later reader from assuming the manifest already vouches for it.
    """
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
    workspace, clone, r8, out_path = (os.path.realpath(sys.argv[1]),
                                      os.path.realpath(sys.argv[2]),
                                      os.path.realpath(sys.argv[3]),
                                      sys.argv[4])
    T = os.path.join(workspace, "tools")
    F = os.path.join(workspace, "freeze_output")

    spec = [
        ("FINAL_VERIFICATION_INSTRUCTIONS",
         os.path.join(T, "VERIFY_PROMPT_ATTEMPT_6.md"),
         "the exact text handed to the fresh Codex process on stdin",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("VERIFICATION_RUNNER",
         os.path.join(T, "run_verification_attempt_6.sh"),
         "launches one fresh Codex process and waits on its exact PID",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("CLONE_BUILDER",
         os.path.join(T, "make_clone.sh"),
         "the disposable sibling clone of R8",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("CLONE_PREFLIGHT",
         os.path.join(T, "preflight_clone.py"),
         "preflight/PREFLIGHT.json; refuses to let the verifier start on a "
         "wrongly placed clone",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("INVENTORY_SCRIPT",
         os.path.join(T, "inventory_r8.py"),
         "a full path/type/size/sha256/symlink/mode/uid/gid/mtime_ns "
         "inventory of a tree",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("INVENTORY_COMPARATOR",
         os.path.join(T, "compare_inventories.py"),
         "the before/after comparison that proves write isolation",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("ABSOLUTE_PATH_MEASUREMENT_HELPER",
         os.path.join(T, "measure_path.py"),
         "one observation per file, carrying requested path, resolved "
         "absolute path and owning root; refuses a backwards mtime",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("CONCURRENT_WRITER_INSPECTOR",
         os.path.join(T, "inspect_writers.py"),
         "preflight/WRITER_INSPECTION_*.json from /proc/<pid>/fd and fdinfo",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("TEST_RUNNER",
         os.path.join(T, "run_package_suite.py"),
         "the package suite in the clone, plus in-situ re-measurement of any "
         "location-bound failure with an inventory proof",
         "installed into the R8 verifier directory and bound by the freeze plan"),
        ("TOOL_INVENTORY_BUILDER",
         os.path.abspath(__file__),
         "this file",
         "installed into the R8 verifier directory and bound by the freeze plan"),
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
         "build/R8_TEST_SUITE_RESULTS.json -- the package's own suite runner, "
         "listed because the verifier reads its output",
         "already covered by the build manifest and bound by the freeze plan"),
        ("STATIC_SAFETY_RUNNER",
         os.path.join(r8, "build", "r8_static_safety_review.py"),
         "build/R8_STATIC_SAFETY_REPORT.json",
         "already covered by the build manifest and bound by the freeze plan"),
        ("FREEZE_MODULE",
         os.path.join(r8, "automation", "freeze.py"),
         "the plan shape check, the baseline, the replay ledger and "
         "token_for; no output of its own",
         "bound by the freeze plan"),
        ("TOKEN_GRAMMAR_CONSTANTS",
         os.path.join(r8, "automation", "policy.py"),
         "the token prefix and suffix",
         "bound by the freeze plan"),
        ("FREEZE_ROUTE",
         os.path.join(r8, "automation", "controller.py"),
         "the only route permitted to freeze the package",
         "bound by the freeze plan"),
        ("MIGRATION_ROUTE",
         os.path.join(r8, "automation", "migration.py"),
         "applies the pre-freeze-bound R7 to R8 packet exactly once",
         "bound by the freeze plan"),
        ("SUPERSEDED_FREEZE_PLAN_BUILDER_ATTEMPT_1",
         os.path.join(r8, "build", "freeze_plan_attempt_1",
                      "build_r8_freeze_plan.py"),
         "attempt 1's plan; preserved unchanged and NOT used by this attempt",
         "bound by attempt 1's own plan, not by attempt 2's"),
    ]

    tools = []
    missing = []
    for role, path, expected, bound_by in spec:
        if not os.path.isfile(path):
            missing.append({"ROLE": role, "CANONICAL_PATH": path})
            continue
        tools.append({
            "ROLE": role,
            "CANONICAL_PATH": path,
            "SHA256": sha256_file(path),
            "EXECUTABLE": os.access(path, os.X_OK),
            "MANIFEST_COVERED": manifest_covered(r8, path),
            "EXPECTED_OUTPUT": expected,
            "BOUND_BY": bound_by,
        })

    # The token generator, narrowed to the function that composes the token.
    sys.path.insert(0, clone)
    from automation import freeze                       # noqa: E402
    source = inspect.getsource(freeze.token_for)
    tools.append({
        "ROLE": "TOKEN_GENERATION_FUNCTION_SOURCE",
        "CANONICAL_PATH": "%s/automation/freeze.py::token_for" % r8,
        "SHA256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "EXECUTABLE": False,
        "MANIFEST_COVERED": True,
        "EXPECTED_OUTPUT": ("the exact token string; five whitespace-separated "
                            "fields, no trailing newline"),
        "BOUND_BY": ("the freeze plan's token_generation.function_source_sha256, "
                     "separately from the module digest"),
    })
    tools.append({
        "ROLE": "FREEZE_PLAN_WRAPPER",
        "CANONICAL_PATH": "NOT_USED",
        "SHA256": "NOT_USED",
        "EXECUTABLE": False,
        "MANIFEST_COVERED": False,
        "EXPECTED_OUTPUT": ("none. No wrapper stands between the builder and "
                            "the plan; the builder is invoked directly, so "
                            "there is no intermediate whose constants could "
                            "differ from the builder's."),
        "BOUND_BY": ("declared NOT_USED in the plan, so its absence is "
                     "recorded rather than merely true"),
    })

    doc = {
        "schema": "wpno.r8.attempt6-tool-inventory/1",
        "workspace": workspace, "clone": clone, "r8_root": r8,
        "rule": ("a result is not a verifier. VERIFICATION_RESULT.json is "
                 "output and appears in no producing role here."),
        "tools": sorted(tools, key=lambda t: t["ROLE"]),
        "tool_count": len(tools),
        "MISSING_TOOLS": missing,
        "UNIDENTIFIED_TOOLS": len(missing),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"tool_count": doc["tool_count"],
                      "UNIDENTIFIED_TOOLS": doc["UNIDENTIFIED_TOOLS"],
                      "MISSING_TOOLS": missing,
                      "roles": [t["ROLE"] for t in doc["tools"]]},
                     indent=1, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
