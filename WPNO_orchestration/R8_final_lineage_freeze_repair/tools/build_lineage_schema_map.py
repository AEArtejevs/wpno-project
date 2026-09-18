#!/usr/bin/env python3
"""Enumerate the real keys of every record the verification reads.

A verifier attempt was lost to `doc["IN_PROCESS_HANDLER_INVOCATIONS"]` on a
record that holds `R8_IN_PROCESS_HANDLER_INVOCATIONS`. The lookup was a guess.
Nothing here is guessed: every key a check will name is opened and listed from
the bytes first, with its type and a sample. No fallbacks, no aliases -- a
fallback lets a wrong name succeed by finding something else.

Usage: build_lineage_schema_map.py <r8> <out.json>
"""

import hashlib
import json
import os
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def sample(value):
    if isinstance(value, (dict, list)):
        return "<%s len %d>" % (type(value).__name__, len(value))
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def main():
    r8, out_path = os.path.realpath(sys.argv[1]), sys.argv[2]
    fields, sources = [], {}

    def scan(rel, keys=None, pointer="$"):
        path = os.path.join(r8, rel)
        sources[rel] = sha256_file(path)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for key in (sorted(doc) if keys is None else keys):
            present = isinstance(doc, dict) and key in doc
            fields.append({
                "SOURCE_FILE": rel, "JSON_PATH": pointer, "KEY_NAME": key,
                "VALUE_TYPE": type(doc[key]).__name__ if present else None,
                "VALUE_PRESENT": present,
                "SAMPLE_VALUE": sample(doc[key]) if present else None})
        return doc

    scan(os.path.join("build", "IN_PROCESS_COUNT_RECONCILIATION.json"))
    scan(os.path.join("work", "_rehearsal_r8", "REHEARSAL_REPORT.json"),
         ["IN_PROCESS_HANDLER_INVOCATIONS", "IN_PROCESS_STEP_COUNT",
          "NOTE_ONLY_IN_PROCESS_STEPS",
          "REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE", "HOLLOW_PHASES",
          "LIVE_STATE_UNCHANGED", "phases_rehearsed", "phases_required",
          "all_pass_ready", "reports"])
    scan(os.path.join("build", "candidate_plans_r8",
                      "PLAN_COVERAGE_MANIFEST.json"),
         ["REQUIRED_PLAN_COUNT", "CANDIDATE_PLAN_COUNT", "MISSING_PLAN_COUNT",
          "DUPLICATE_PLAN_COUNT", "UNKNOWN_PLAN_COUNT", "plans"])
    scan(os.path.join("build", "CONTROL_EXPECTATION_COVERAGE.json"),
         ["CONTROL_ROLE_STEP_COUNT",
          "CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION",
          "CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION"])
    suites = scan(os.path.join("build", "R8_TEST_SUITE_RESULTS.json"),
                  ["schema", "revision", "all_clean", "suites"])
    for name in sorted(suites["suites"]):
        for key in ("ran", "failures", "errors", "skips", "clean",
                    "measurement"):
            present = key in suites["suites"][name]
            fields.append({
                "SOURCE_FILE": "build/R8_TEST_SUITE_RESULTS.json",
                "JSON_PATH": "$.suites.%s" % name, "KEY_NAME": key,
                "VALUE_TYPE": type(suites["suites"][name][key]).__name__
                if present else None,
                "VALUE_PRESENT": present,
                "SAMPLE_VALUE": sample(suites["suites"][name][key])
                if present else None})
    scan(os.path.join("build", "R8_STATIC_SAFETY_REPORT.json"),
         ["reviewed_file_count", "finding_count", "findings", "clean",
          "unpermitted_changes", "predecessor_root", "predecessor_unchanged",
          "r4_unchanged"])
    closure = scan(os.path.join("build", "R8_FINAL_PRE_FREEZE_CLOSURE.json"),
                   ["refused_freeze_attempt_2", "lineage_binding_defect",
                    "tests", "static_safety", "rehearsal", "controls",
                    "live_execution"])
    for key in sorted(closure["lineage_binding_defect"]):
        fields.append({
            "SOURCE_FILE": "build/R8_FINAL_PRE_FREEZE_CLOSURE.json",
            "JSON_PATH": "$.lineage_binding_defect", "KEY_NAME": key,
            "VALUE_TYPE": type(
                closure["lineage_binding_defect"][key]).__name__,
            "VALUE_PRESENT": True,
            "SAMPLE_VALUE": sample(closure["lineage_binding_defect"][key])})
    lineage = scan(os.path.join("lineage", "R8_LINEAGE.json"))
    if isinstance(lineage.get("r7"), dict):
        for key in sorted(lineage["r7"]):
            fields.append({
                "SOURCE_FILE": "lineage/R8_LINEAGE.json", "JSON_PATH": "$.r7",
                "KEY_NAME": key,
                "VALUE_TYPE": type(lineage["r7"][key]).__name__,
                "VALUE_PRESENT": True,
                "SAMPLE_VALUE": sample(lineage["r7"][key])})
    scan(os.path.join("build", "migration_plan_r7_to_r8",
                      "MIGRATION_PLAN.json"),
         ["applied_before_freeze", "route_module_sha256",
          "migratable_attempts", "excluded_attempts",
          "post_freeze_resume_sequence"])

    # the lineage declaration itself, read from the module rather than a file
    sys.path.insert(0, r8)
    from automation import freeze
    declared = freeze.required_predecessor_lineage_artifacts()
    for rel in declared:
        full = os.path.join(r8, rel)
        fields.append({
            "SOURCE_FILE": "automation/freeze.py",
            "JSON_PATH": "PACKAGE_LINEAGE_MODEL.artifacts[*].rel",
            "KEY_NAME": rel,
            "VALUE_TYPE": "path",
            "VALUE_PRESENT": os.path.isfile(full),
            "SAMPLE_VALUE": sha256_file(full) if os.path.isfile(full)
            else None})

    unresolved = [f for f in fields if not f["VALUE_PRESENT"]]
    doc = {"schema": "wpno.r8.lineage-repair-schema-map/1", "r8_root": r8,
           "rule": ("every key a check names appears here with VALUE_PRESENT "
                    "true. No fallback, no alias."),
           "source_digests": sources, "fields": fields,
           "field_count": len(fields),
           "declared_lineage_artifacts": list(declared),
           "UNRESOLVED_KEY_LOOKUPS": len(unresolved),
           "unresolved": unresolved}
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in
                      ("field_count", "declared_lineage_artifacts",
                       "UNRESOLVED_KEY_LOOKUPS")}, indent=1, sort_keys=True))
    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())
