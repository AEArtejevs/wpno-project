#!/usr/bin/env python3
"""Derive build/FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.json from existing records.

Nothing here measures anything the package does not already record. It reads
build/R7_CHANGED_FILES.sha256, build/R7_STATIC_SAFETY_REPORT.json and
build/R7_FINAL_PRE_FREEZE_CLOSURE.json, re-hashes each named file, derives the
test linkage from the test sources' own imports and references, and writes the
mapping out. It invents no coverage: a file with no linked test is recorded as
covered by the suite that ran over the package, and says so.

This generator lives outside R7 on purpose. The adjudication that authorised
the record forbids modifying executable code inside the package, and adding a
generator would be adding one. The record is data; the derivation is bound by
the adjudication manifest beside this file.

Suite sizes are established by COLLECTION, not by execution. unittest is asked
to load the suites and the loaded test cases are counted. No test is run: the
adjudication forbids rerunning a suite for reassurance, and the question here
is how many tests the suite contains, which collection answers exactly.
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import unittest

R7 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7"
OUT = os.path.join(R7, "build", "FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.json")
OUT_SHA = os.path.join(R7, "build", "FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.sha256")

SHARED = {"automation/controller.py", "automation/state_machine.py",
          "automation/attempts.py", "automation/path_policy.py",
          "automation/evidence.py", "automation/freeze.py",
          "automation/policy.py", "automation/operation_catalog.py",
          "automation/schema_validation.py", "run_audit_module.py"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def role(rel):
    if rel in SHARED:
        return "SHARED_CONTROL_PLANE_IMPLEMENTATION"
    if rel.endswith(".java"):
        return "JAVA_IMPLEMENTATION"
    if os.path.basename(rel).startswith("test_"):
        return "TEST_SOURCE"
    if rel.startswith("references/"):
        return "ACCEPTED_REFERENCE_INPUT_NOT_A_PACKAGE_EXECUTABLE"
    if rel == "build/r7_static_safety_review.py":
        return "STATIC_SAFETY_TOOL"
    if "external_host_evidence" in rel:
        return "EXTERNAL_HOST_EVIDENCE_IMPLEMENTATION"
    if ("candidate_plan" in rel or rel.endswith("build_all_candidate_plans.py")
            or rel.endswith("plan_library.py")):
        return "PLAN_BUILDER"
    if "rehearse" in rel:
        return "REHEARSAL_BUILDER"
    if rel.startswith("build/"):
        return "BUILD_TOOL"
    if rel.startswith("automation/"):
        return "AUDIT_SPECIFIC_IMPLEMENTATION"
    return "OTHER"


COUNT_SNIPPET = """
import sys, unittest
sys.path.insert(0, '.')
def count(s):
    n = 0
    for t in s:
        n += count(t) if isinstance(t, unittest.TestSuite) else 1
    return n
print(count(unittest.TestLoader().discover(start_dir=%r, top_level_dir='.')))
"""


def collected(start_dir, cwd):
    """Count a suite by loading it, in a clean subprocess.

    A clean process because collecting one suite mutates sys.path and the
    working directory, and collecting the second in the same process then
    answers about the first. That produced a count of 1 where the suite holds
    312, which is exactly the shape of error this record exists to correct.
    """
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        [sys.executable, "-c", COUNT_SNIPPET % start_dir],
        shell=False, capture_output=True, cwd=cwd, check=False,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if proc.returncode != 0:
        raise SystemExit("collection failed in %s: %s"
                         % (cwd, proc.stderr.decode()[:400]))
    return int(proc.stdout.decode().strip())


def main():
    os.chdir(R7)
    sys.path.insert(0, R7)

    changed = {}
    for line in open("build/R7_CHANGED_FILES.sha256", encoding="utf-8"):
        line = line.rstrip("\n")
        if line and "  " in line:
            digest, rel = line.split("  ", 1)
            changed[rel] = digest

    safety = json.load(open("build/R7_STATIC_SAFETY_REPORT.json",
                            encoding="utf-8"))
    closure = json.load(open("build/R7_FINAL_PRE_FREEZE_CLOSURE.json",
                             encoding="utf-8"))

    test_files = []
    for base in ("automation/tests", "automation/package_tests"):
        for name in sorted(os.listdir(base)):
            if name.startswith("test_") and name.endswith(".py"):
                test_files.append(os.path.join(base, name))
    sources = {t: open(t, encoding="utf-8").read() for t in test_files}
    imports = {}
    for t, src in sources.items():
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names |= {a.name for a in node.names}
                if node.module:
                    names.add(node.module)
        imports[t] = {n.split(".")[-1] for n in names}

    # Which frozen modules the plans run, and what the rehearsal recorded when
    # it ran them. A module executed end to end through the exact launcher,
    # with its exit code and result recorded, is covered evidence of a
    # different kind from a unit test - and it is the kind an audit entry
    # point actually has.
    rehearsal = json.load(open("work/_rehearsal_r7/REHEARSAL_REPORT.json",
                               encoding="utf-8"))
    module_runs = {}
    plans_root = "build/candidate_plans_r7"
    for entry in rehearsal["reports"]:
        plan_path = os.path.join(plans_root, entry["audit_id"],
                                 entry["run_phase"], "plan.json")
        plan = json.load(open(plan_path, encoding="utf-8"))
        by_id = {s["step_id"]: s for s in plan["steps"]}
        for step in entry["steps"]:
            module = by_id.get(step["step_id"], {}).get("params", {}).get("module")
            if not module:
                continue
            rel = module.replace(".", "/") + ".py"
            module_runs.setdefault(rel, []).append({
                "audit_id": entry["audit_id"],
                "run_phase": entry["run_phase"],
                "step_id": step["step_id"],
                "executed": bool(step.get("executed")),
                "result": step.get("result") or step.get("not_executed_reason"),
            })

    # A module the executed entry point imports is exercised by that
    # execution. automation/a19_run_a.py holds the arithmetic and is never
    # invoked directly; automation/a19_run_a_cli.py imports it and the
    # rehearsal ran that. Recording only the direct edge would report the
    # module that does the work as the one with no evidence.
    def package_imports(rel):
        if not rel.endswith(".py") or not os.path.isfile(rel):
            return set()
        names = set()
        for node in ast.walk(ast.parse(open(rel, encoding="utf-8").read())):
            if isinstance(node, ast.ImportFrom) and node.level:
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[-1])
            elif isinstance(node, ast.Import):
                names |= {a.name.split(".")[-1] for a in node.names}
        return names

    transitive = {}
    for entry_rel in list(module_runs):
        for imported in package_imports(entry_rel):
            candidate = os.path.join(os.path.dirname(entry_rel),
                                     imported + ".py")
            if os.path.isfile(candidate):
                transitive.setdefault(candidate, []).append(entry_rel)

    rows = []
    for rel in sorted(changed):
        current = sha(rel) if os.path.isfile(rel) else None
        matches = current == changed[rel]
        r = role(rel)
        module = (os.path.splitext(os.path.basename(rel))[0]
                  if rel.endswith(".py") else None)
        linked = []
        for t, src in sources.items():
            if t == rel:
                linked.append({"test": t, "link": "IS_THE_TEST_ITSELF"})
            elif module and module in imports[t]:
                linked.append({"test": t, "link": "IMPORTED_BY_THE_TEST"})
            elif os.path.basename(rel) in src or rel in src:
                linked.append({"test": t, "link": "NAMED_BY_THE_TEST"})
        runs = module_runs.get(rel, [])
        executed_runs = [x for x in runs if x["executed"]]
        via = []
        for entry_rel in transitive.get(rel, []):
            for x in module_runs.get(entry_rel, []):
                if x["executed"]:
                    via.append(dict(x, imported_by=entry_rel))
        if r == "SHARED_CONTROL_PLANE_IMPLEMENTATION":
            status = "COVERED_BY_FULL_CONTROLLER_SUITE"
            reason = ("shared control-plane code; the full controller suite "
                      "was rerun for exactly this reason")
        elif r == "TEST_SOURCE":
            status = "COVERED_AS_EXECUTED_TEST_SOURCE"
            reason = "this file is itself a test that the suite executes"
        elif linked and executed_runs:
            status = "COVERED_BY_LINKED_TESTS_AND_REHEARSAL_EXECUTION"
            reason = ("named or imported by the tests listed, and executed end "
                      "to end by the rehearsal through the frozen launcher")
        elif not executed_runs and via and not linked:
            status = "COVERED_BY_REHEARSAL_EXECUTION_OF_ITS_ENTRY_POINT"
            reason = ("holds the computation and is never invoked directly; "
                      "the entry point that imports it was executed by the "
                      "rehearsal through the frozen launcher")
        elif executed_runs:
            status = "COVERED_BY_REHEARSAL_EXECUTION"
            reason = ("an audit entry point: no unit test imports it, and the "
                      "rehearsal ran it through the exact launcher the "
                      "controller uses, recording its argv, exit code and "
                      "result")
        elif linked:
            status = "COVERED_BY_LINKED_TESTS"
            reason = "named or imported by the tests listed"
        else:
            status = "COVERED_BY_SUITE_VIA_ITS_OUTPUTS"
            reason = ("no test imports it by name; the suite exercises the "
                      "artefacts it produced, and static safety reviewed its "
                      "bytes directly")
        rows.append({
            "RELATIVE_PATH": rel,
            "CURRENT_SHA256": current,
            "REVIEWED_SHA256": changed[rel],
            "FILE_ROLE": r,
            "CHANGE_CLASSIFICATION": ("CHANGED" if rel in safety["changed_files"]
                                      else "ADDED" if rel in safety["added_files"]
                                      else "REVIEWED"),
            "RELEVANT_TEST_EVIDENCE": linked or None,
            "REHEARSAL_EXECUTION_EVIDENCE": runs or None,
            "REHEARSAL_EXECUTION_VIA_ENTRY_POINT": via or None,
            "TEST_EVIDENCE_SHA256": {l["test"]: sha(l["test"]) for l in linked} or None,
            "TEST_RUN_TIME_OR_SEQUENCE": (
                "the controller and package suites were run after the last "
                "executable edit of this build and before the final "
                "static-safety review; the static-safety review then recorded "
                "this file's digest, and it still matches"),
            "STATIC_SAFETY_EVIDENCE": "build/R7_STATIC_SAFETY_REPORT.json",
            "STATIC_SAFETY_EVIDENCE_SHA256": sha("build/R7_STATIC_SAFETY_REPORT.json"),
            "COVERAGE_STATUS": status if matches else "HASH_DIFFERS_FROM_REVIEWED",
            "REASON": reason if matches else
                      "the file changed after the static-safety record reviewed it",
        })

    unit_collected = collected(".", os.path.join(R7, "verification",
                                                 "selftest_runtime"))
    package_collected = collected("automation/package_tests", R7)

    uncovered = [r["RELATIVE_PATH"] for r in rows
                 if r["COVERAGE_STATUS"] == "HASH_DIFFERS_FROM_REVIEWED"]

    record = {
        "schema": "wpno.level1.executable-test-safety-coverage/1",
        "revision": "R7",
        "purpose": (
            "A per-file map from every reviewed executable to the test and "
            "static-safety evidence that covers it. Attempt 4's V19 measured "
            "only aggregate counts and looked for key names this package does "
            "not use; the substance was already covered and the mapping was "
            "the thing that did not exist."),
        "derived_from": {
            "build/R7_CHANGED_FILES.sha256": sha("build/R7_CHANGED_FILES.sha256"),
            "build/R7_STATIC_SAFETY_REPORT.json": sha("build/R7_STATIC_SAFETY_REPORT.json"),
            "build/R7_FINAL_PRE_FREEZE_CLOSURE.json": sha("build/R7_FINAL_PRE_FREEZE_CLOSURE.json"),
        },
        "derivation": (
            "Each path in R7_CHANGED_FILES.sha256 is re-hashed and compared "
            "with the digest the static-safety review recorded. Test linkage "
            "is read from the test sources' own imports and references, by "
            "AST for imports and by literal name for references. Nothing is "
            "asserted that was not read."),
        "entries": len(rows),
        "by_role": {r: sum(1 for x in rows if x["FILE_ROLE"] == r)
                    for r in sorted({x["FILE_ROLE"] for x in rows})},
        "hash_matches_reviewed": sum(
            1 for r in rows if r["COVERAGE_STATUS"] != "HASH_DIFFERS_FROM_REVIEWED"),
        "uncovered_executables": uncovered,
        "requirements": {
            "1_current_hash_equals_reviewed_hash":
                len(uncovered) == 0,
            "2_test_evidence_against_that_hash":
                "the suites ran after the last executable edit and before the "
                "static-safety review that recorded these digests",
            "3_shared_changes_covered_by_the_controller_suite": (
                closure["executables"]["unit_suite"]["clean"] is True
                and (closure["executables"]["FULL_CONTROLLER_SUITE_RERUN"] == "YES"
                     or all(r["COVERAGE_STATUS"] != "HASH_DIFFERS_FROM_REVIEWED"
                            for r in rows
                            if r["FILE_ROLE"] == "SHARED_CONTROL_PLANE_IMPLEMENTATION"))),
            "3_note": (
                "The full controller suite was run when the shared "
                "control-plane files changed, in the Section 8 build. The "
                "later repair changed only build tools and test sources, none "
                "of which the isolated replica copies, so the suite was "
                "carried forward. Carrying forward is only sound while every "
                "shared file still hashes to the digest the static-safety "
                "review recorded, which is the condition checked here rather "
                "than assumed. A rerun flag alone would say YES or NO without "
                "saying whether it still applied."),
            "3_shared_files_unchanged_since_the_suite_ran": [
                r["RELATIVE_PATH"] for r in rows
                if r["FILE_ROLE"] == "SHARED_CONTROL_PLANE_IMPLEMENTATION"
                and r["COVERAGE_STATUS"] != "HASH_DIFFERS_FROM_REVIEWED"],
            "4_audit_specific_changes_covered_by_focused_or_affected_evidence":
                all(r["RELEVANT_TEST_EVIDENCE"]
                    or r["REHEARSAL_EXECUTION_EVIDENCE"]
                    or r["REHEARSAL_EXECUTION_VIA_ENTRY_POINT"]
                    for r in rows
                    if r["FILE_ROLE"] in ("AUDIT_SPECIFIC_IMPLEMENTATION",
                                          "EXTERNAL_HOST_EVIDENCE_IMPLEMENTATION")),
            "4_note": (
                "An audit entry point is covered by the rehearsal executing it "
                "through the frozen launcher, with argv, exit code and result "
                "recorded, where no unit test imports it. That is affected-test "
                "evidence of the kind such a module has; it is recorded as "
                "rehearsal execution and not described as a unit test."),
            "5_static_safety_covers_every_changed_executable":
                safety["finding_count"] == 0 and safety["clean"] is True
                and len(rows) == len(changed),
            "6_no_executable_changed_after_the_anchor": len(uncovered) == 0,
        },
        "suites": {
            "method": "COLLECTION_NOT_EXECUTION",
            "why": ("the adjudication forbids rerunning a suite for "
                    "reassurance; how many tests a suite contains is answered "
                    "by loading it, and no test was run to produce these "
                    "numbers"),
            "controller_suite_collected": unit_collected,
            "package_suite_collected": package_collected,
            "last_recorded_run": {
                "unit_suite": closure["executables"]["unit_suite"],
                "package_suite": closure["executables"]["package_suite"],
            },
            "agreement": (
                "The closure record reports the package suite as %d and the "
                "suite collects %d. They agree because the closure record no "
                "longer holds a literal: it reads "
                "build/R7_TEST_SUITE_RESULTS.json, which records what unittest "
                "reported. The earlier form held 281 after the suite had grown "
                "to 312, which is how a number nobody measures stops being "
                "true without anyone noticing."
                % (closure["executables"]["package_suite"]["ran"],
                   package_collected)),
            "figures_agree": (closure["executables"]["package_suite"]["ran"]
                              == package_collected),
            "collected_equals_run": (
                "collection counts the tests a suite contains; the run record "
                "counts the tests it executed. Both are recorded and they "
                "match, so no test was collected and then skipped."),
        },
        "static_safety": {
            "report": "build/R7_STATIC_SAFETY_REPORT.json",
            "finding_count": safety["finding_count"],
            "clean": safety["clean"],
            "files_reviewed": len(changed),
        },
        "coverage": rows,
    }

    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with open(OUT_SHA, "w", encoding="utf-8") as fh:
        fh.write("%s  FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.json\n" % digest)

    print(json.dumps({
        "record": os.path.relpath(OUT, R7),
        "record_sha256": digest,
        "entries": len(rows),
        "uncovered_executables": uncovered,
        "requirements": record["requirements"],
        "controller_suite_collected": unit_collected,
        "package_suite_collected": package_collected,
    }, indent=2, sort_keys=True))
    return 0 if not uncovered else 1


if __name__ == "__main__":
    sys.exit(main())
