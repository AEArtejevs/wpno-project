#!/usr/bin/env python3
"""Check attempt 8's headline results against its own STORED OUTPUT.

Not against its summary. A summary that quotes itself proves nothing, and the
`281` literal that outlived the suite it described is the reason this file
exists. Each figure below is read from the artefact the run actually produced
-- the suite's captured stderr, the package-suite runner's JSON, the static
review's own report -- and only then compared with what the item record claims.

Where a figure has no stored artefact of its own, the item record IS the
artefact: it was written at the moment of measurement, its digest is in
attempt 8's manifest, and that manifest verifies. That is stated per figure
rather than blurred.

Usage: verify_base_evidence.py <attempt8_root> <r8> <out.json>
"""

import json
import os
import re
import sys



# Attempt 8 recorded `measured` two ways: items 1-8 and 10-17 as a
# semicolon-separated `key=value` STRING, items 9 and 18-35 as an OBJECT. A
# reader that assumes one shape raises on the other -- which is the shape of
# the defect that ended attempt 8, in a different place. Both are handled, and
# a key that is absent returns a sentinel rather than raising, so a missing
# figure is reported as a failed check instead of a crash.

ABSENT = object()


def field(measured, key):
    """Read `key` out of an attempt-8 `measured` value of either shape."""
    if isinstance(measured, dict):
        return measured.get(key, ABSENT)
    if isinstance(measured, str):
        for part in measured.split(";"):
            name, sep, value = part.partition("=")
            if sep and name.strip() == key:
                return parse(value.strip())
        return ABSENT
    return ABSENT


def parse(text):
    """`[]`, `['MODE']`, `15804`, `True` -- as written by attempt 8."""
    import ast
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def main():
    a8, r8, out_path = (os.path.realpath(sys.argv[1]),
                        os.path.realpath(sys.argv[2]), sys.argv[3])
    out = os.path.join(a8, "codex_output")
    items = {}
    for line in open(os.path.join(out, "ITEM_RESULTS.jsonl"), encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            items[r["id"]] = r

    checks = []

    def check(name, expected, measured, source, ok=None):
        checks.append({"claim": name, "expected": expected,
                       "measured": measured, "source": source,
                       "PASS": bool(expected == measured if ok is None else ok)})

    # -- unit / controller suite: from the suite's own captured stderr -------
    stderr = open(os.path.join(out, "CONTROLLER_SUITE.stderr.txt"),
                  encoding="utf-8").read()
    m = re.search(r"Ran (\d+) tests?", stderr)
    ran = int(m.group(1)) if m else None
    clean = bool(re.search(r"^OK\s*$", stderr, re.M))
    check("unit tests ran", 503, ran,
          "CONTROLLER_SUITE.stderr.txt (unittest's own summary line)")
    check("unit tests clean (0 failures, 0 errors, 0 skips)", True, clean,
          "CONTROLLER_SUITE.stderr.txt trailing OK")
    check("unit-suite item record agrees",
          {"tests_run": 503, "failures": 0, "errors": 0, "skips": 0},
          {k: field(items[18]["measured"], k) for k in
           ("tests_run", "failures", "errors", "skips")},
          "ITEM_RESULTS.jsonl id=18")

    # -- package suite: from the two-pass runner's own JSON -----------------
    with open(os.path.join(out, "PACKAGE_SUITE.json"), encoding="utf-8") as fh:
        pkg = json.load(fh)
    check("package tests run", 361, pkg["tests_run"], "PACKAGE_SUITE.json")
    check("package tests effective passes", 361, pkg["EFFECTIVE_PASSED"],
          "PACKAGE_SUITE.json")
    check("package tests effective failures", 0, pkg["EFFECTIVE_FAILURES"],
          "PACKAGE_SUITE.json")
    check("package tests errors", 0, pkg["errors"], "PACKAGE_SUITE.json")
    check("package tests skips", 0, pkg["skips"], "PACKAGE_SUITE.json")
    check("package suite clean", True, pkg["SUITE_CLEAN"],
          "PACKAGE_SUITE.json")
    check("package tests unresolved", 0, pkg["tests_unresolved"],
          "PACKAGE_SUITE.json")
    insitu = pkg["pass_b_in_situ"]
    check("the one clone failure was resolved in situ and wrote nothing",
          True,
          all(r["CLASSIFICATION"] == "RELOCATION_ARTEFACT_RESOLVED_IN_SITU"
              and r["in_situ_wrote_nothing"] and r["in_situ_passed"]
              for r in insitu) and len(insitu) == 1,
          "PACKAGE_SUITE.json pass_b_in_situ")
    check("package suite target was the current package",
          True,
          pkg["r8_root"] == r8, "PACKAGE_SUITE.json r8_root")

    # -- static safety: from the review's own report ------------------------
    with open(os.path.join(out, "static_safety_outputs",
                           "R8_STATIC_SAFETY_REPORT.json"),
              encoding="utf-8") as fh:
        safety = json.load(fh)
    check("static safety findings", 0, safety["finding_count"],
          "static_safety_outputs/R8_STATIC_SAFETY_REPORT.json")
    check("static safety clean", True, safety["clean"],
          "static_safety_outputs/R8_STATIC_SAFETY_REPORT.json")
    check("static safety unpermitted changes", [],
          safety["unpermitted_changes"],
          "static_safety_outputs/R8_STATIC_SAFETY_REPORT.json")
    check("static safety predecessor root was the real R7 sibling",
          os.path.join(os.path.dirname(r8), "08.18.26_Level1_Audits_R7"),
          safety["predecessor_root"],
          "static_safety_outputs/R8_STATIC_SAFETY_REPORT.json")
    # the review in the clone must agree with the record in the package,
    # everywhere except where it cannot
    with open(os.path.join(r8, "build", "R8_STATIC_SAFETY_REPORT.json"),
              encoding="utf-8") as fh:
        recorded = json.load(fh)
    differing = sorted(k for k in set(safety) | set(recorded)
                       if safety.get(k) != recorded.get(k))
    check("clone static review equals the package's own record except "
          "package_root and reviewed_at_utc",
          ["package_root", "reviewed_at_utc"], differing,
          "clone report vs build/R8_STATIC_SAFETY_REPORT.json")

    # -- figures whose artefact is the durable item record ------------------
    for item_id, name, want, path in (
            (21, "plans", 43, ("measured", "plans")),
            (22, "rehearsals PASS_READY", 43, ("measured", "reported")),
            (15, "control expectations re-derived", 122,
             ("measured", "rederived_control_count")),
            (15, "control expectations recorded", 122,
             ("measured", "coverage_count")),
            (15, "unenforced controls", 0, ("measured", "coverage_unenforced")),
            (24, "hollow phases", [], ("measured", "HOLLOW_PHASES")),
            (25, "audits", 35, ("measured", "audits")),
            (25, "phases", 43, ("measured", "phases")),
            (26, "approval rows", 0, ("measured", "approval_rows")),
            (26, "result files", 0, ("measured", "result_files")),
            (26, "evidence files", 0, ("measured", "evidence_files")),
            (27, "manifest entries", 724, ("measured", "entries")),
    ):
        value = field(items[item_id]["measured"], path[1])
        check(name, want, None if value is ABSENT else value,
              "ITEM_RESULTS.jsonl id=%d" % item_id)

    check("live phase states", {"NOT_STARTED": 43},
          field(items[25]["measured"], "state_counts"), "ITEM_RESULTS.jsonl id=25")
    check("manifest digest measured by attempt 8 is the current one",
          "6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a",
          field(items[27]["measured"], "manifest_sha256"),
          "ITEM_RESULTS.jsonl id=27")
    check("out-of-allowance reads", [],
          field(items[12]["measured"], "rehearsal_steps_with_outside_reads"),
          "ITEM_RESULTS.jsonl id=12")

    # -- predecessors -------------------------------------------------------
    check("R4 mismatching", [], field(items[1]["measured"], "mismatching_paths"),
          "ITEM_RESULTS.jsonl id=1")
    check("R5 mismatching is MODE only", ["MODE"],
          field(items[2]["measured"], "mismatching_paths"), "ITEM_RESULTS.jsonl id=2")
    check("R6 mismatching", [], field(items[3]["measured"], "mismatching_paths"),
          "ITEM_RESULTS.jsonl id=3")
    check("R7 entries", 15804, field(items[4]["measured"], "entries"),
          "ITEM_RESULTS.jsonl id=4")
    check("R7 mismatching", [], field(items[4]["measured"], "mismatching_paths"),
          "ITEM_RESULTS.jsonl id=4")

    # -- write isolation: from the comparison record itself -----------------
    with open(os.path.join(out, "ORIGINAL_INVENTORY_COMPARE.json"),
              encoding="utf-8") as fh:
        cmp_doc = json.load(fh)
    check("write isolation: original R8 unchanged", True, cmp_doc["EQUAL"],
          "ORIGINAL_INVENTORY_COMPARE.json")
    # `field` is the module-level reader above; a loop variable of that name
    # would shadow it and make it unbound for the rest of this function.
    for delta_field in ("paths_added", "paths_removed", "contents_changed",
                        "mtimes_changed", "modes_changed", "uid_changed",
                        "gid_changed", "symlink_targets_changed"):
        check("write isolation: %s" % delta_field, 0,
              cmp_doc.get(delta_field, "ABSENT"),
              "ORIGINAL_INVENTORY_COMPARE.json")

    # -- in-process figures: recorded, but item 23's predicate failed -------
    m23 = items[23]["measured"]
    check("in-process handler invocations (recorded by attempt 8)", 169,
          field(m23, "IN_PROCESS_HANDLER_INVOCATIONS"), "ITEM_RESULTS.jsonl id=23")
    check("in-process step count (recorded by attempt 8)", 169,
          field(m23, "IN_PROCESS_STEP_COUNT"), "ITEM_RESULTS.jsonl id=23")
    check("note-only steps (recorded by attempt 8)", 0,
          field(m23, "NOTE_ONLY_IN_PROCESS_STEPS"), "ITEM_RESULTS.jsonl id=23")
    check("steps without evidence (recorded by attempt 8)", 0,
          field(m23, "REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE"),
          "ITEM_RESULTS.jsonl id=23")
    checks.append({
        "claim": "item 23 nevertheless carries FAILED_VERIFIER_PREDICATE",
        "expected": "remeasured in the delta, not carried forward",
        "measured": items[23]["pass"],
        "source": "ITEM_RESULTS.jsonl id=23",
        "PASS": items[23]["pass"] is False,
        "note": ("the four figures above are correct on the bytes, but the "
                 "predicate that judged them completed and returned an "
                 "adverse result. A figure recorded beside a failed judgement "
                 "is not a passed item. Item 23 is remeasured in full.")})

    failed = [c for c in checks if not c["PASS"]]
    doc = {"schema": "wpno.r8.delta-base-evidence/1",
           "base_attempt": 8, "checks": checks,
           "checks_total": len(checks),
           "checks_passed": len(checks) - len(failed),
           "failures": failed,
           "BASE_EVIDENCE_VALID": not failed}
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"checks_total": doc["checks_total"],
                      "checks_passed": doc["checks_passed"],
                      "BASE_EVIDENCE_VALID": doc["BASE_EVIDENCE_VALID"]},
                     indent=1))
    for c in failed:
        print("  FAIL", c["claim"], "expected", c["expected"],
              "measured", c["measured"])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
