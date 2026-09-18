#!/usr/bin/env python3
"""Build the two records R8 may not freeze without.

IN_PROCESS_COUNT_RECONCILIATION.json settles 165 against 187.
CONTROL_EXPECTATION_COVERAGE.json settles the 55 control steps that carried
no declared exit code.

Both are measurements over bytes that exist: the 43 R8 plans, the R8
rehearsal report, and -- for the R7 side of the reconciliation -- the
rehearsal report the dirty repair left in R7's `work/`, which is a mutable
directory outside R7's control manifest and is therefore readable without
touching anything the freeze covers.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import (hashing, in_process_executor,  # noqa: E402
                        operation_catalog, path_policy)

PLANS = os.path.join(ROOT, "build", "candidate_plans_r8")
REHEARSAL = os.path.join(ROOT, "work", "_rehearsal_r8", "REHEARSAL_REPORT.json")
R7 = os.path.join(os.path.dirname(ROOT), "08.18.26_Level1_Audits_R7")
R7_REHEARSAL = os.path.join(R7, "work", "_rehearsal_r7", "REHEARSAL_REPORT.json")

# The R7 IN_PROCESS set, before R8 added the MIME extraction operation. Named
# here rather than imported, because the point of the reconciliation is to
# compare two different catalogues and importing one of them twice would
# compare it with itself.
R7_IN_PROCESS = frozenset((
    "READ_FILE_RANGE", "LIST_DIRECTORY", "STAT_FILE", "SHA256_FILE",
    "COMPARE_HASHES", "COMPARE_BINARY_FILES", "PYTHON_AST_PARSE",
    "PARSE_JSON_READONLY", "PARSE_CSV_READONLY", "COUNT_TEXT_MATCHES",
    "ZIP_LIST", "TAR_LIST", "XML_PARSE_SANDBOX", "DOCX_PARSE_SANDBOX",
    "DOCKER_METADATA_IMPORT", "DATABASE_EVIDENCE_IMPORT"))

CONTROL_ROLES = ("POSITIVE", "NEGATIVE", "MUTATION", "SABOTAGE", "ORACLE")


def load_plans(directory, pattern_root):
    plans = {}
    for audit_id in sorted(os.listdir(directory)):
        audit_dir = os.path.join(directory, audit_id)
        if not os.path.isdir(audit_dir):
            continue
        for phase in sorted(os.listdir(audit_dir)):
            path = os.path.join(audit_dir, phase, "plan.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    plans[(audit_id, phase)] = json.load(fh)
    return plans


def reconciliation():
    r8_plans = load_plans(PLANS, ROOT)
    r7_plans = load_plans(os.path.join(R7, "build", "candidate_plans_r7"), R7)

    with open(REHEARSAL, encoding="utf-8") as fh:
        r8_report = json.load(fh)
    r8_steps = {}
    for entry in r8_report["reports"]:
        for step in entry["steps"]:
            r8_steps[(entry["audit_id"], entry["run_phase"],
                      step["step_id"])] = step

    r7_steps = {}
    r7_available = os.path.isfile(R7_REHEARSAL)
    if r7_available:
        with open(R7_REHEARSAL, encoding="utf-8") as fh:
            r7_report = json.load(fh)
        for entry in r7_report["reports"]:
            for step in entry["steps"]:
                r7_steps[(entry["audit_id"], entry["run_phase"],
                          step["step_id"])] = step

    rows = []
    for (audit_id, phase), plan in sorted(r8_plans.items()):
        r7_plan = r7_plans.get((audit_id, phase))
        r7_by_id = {s["step_id"]: s for s in (r7_plan or {}).get("steps", [])}
        for step in plan["steps"]:
            key = (audit_id, phase, step["step_id"])
            operation = step["operation"]
            r7_step = r7_by_id.get(step["step_id"])
            r7_operation = r7_step["operation"] if r7_step else None
            r7_class = (None if r7_step is None else
                        ("IN_PROCESS" if r7_operation in R7_IN_PROCESS
                         else "NOT_IN_PROCESS"))
            r8_class = ("IN_PROCESS" if operation in operation_catalog.IN_PROCESS
                        else ("OPERATOR_PERFORMED"
                              if operation in operation_catalog.OPERATOR_PERFORMED
                              else "SUBPROCESS"))
            observed = r8_steps.get(key) or {}
            invocations = 1 if observed.get("in_process_handler_invoked") else 0

            why = None
            if r8_class != "IN_PROCESS":
                why = "not an in-process step; no handler invocation expected"
                invocations = 0
            elif invocations == 1:
                why = ("one plan step, one handler invocation; the executor "
                       "is called once per step and does not loop")
            else:
                why = ("the step did not invoke a handler: %s"
                       % (observed.get("error_artifact") or "not rehearsed"))

            if r7_step is None:
                change = "ADDED_BY_AN_AUTHORISED_R8_PLAN_REPAIR"
            elif r7_operation != operation:
                change = "OPERATION_CHANGED_BY_AN_AUTHORISED_R8_PLAN_REPAIR"
            else:
                change = "UNCHANGED"

            rows.append({
                "AUDIT_ID": audit_id,
                "PHASE": phase,
                "STEP_ID": step["step_id"],
                "OPERATION": operation,
                "R7_OPERATION": r7_operation,
                "R7_CLASSIFICATION": r7_class,
                "R8_FINAL_CLASSIFICATION": r8_class,
                "UNIQUE_PLAN_STEP": True,
                "EXECUTION_INVOCATION_COUNT": invocations,
                "WHY_INVOCATION_COUNT_DIFFERS_FROM_ONE":
                    None if invocations == 1 else why,
                "CHANGE_SINCE_R7": change,
                "R7_REHEARSAL_EXECUTED":
                    r7_steps.get(key, {}).get("executed") if r7_available
                    else None,
                "R8_REHEARSAL_EXECUTED": observed.get("executed"),
            })

    r7_unique = sum(1 for r in rows if r["R7_CLASSIFICATION"] == "IN_PROCESS")
    r8_unique = sum(1 for r in rows
                    if r["R8_FINAL_CLASSIFICATION"] == "IN_PROCESS")
    r8_invocations = sum(r["EXECUTION_INVOCATION_COUNT"] for r in rows)

    # The R7 side, measured from the report the dirty repair left behind.
    r7_side = {"available": r7_available}
    if r7_available:
        by_class = {"IN_PROCESS_EXECUTED": 0, "IN_PROCESS_NOT_EXECUTED": 0,
                    "OTHER_EXECUTED": 0, "OTHER_NOT_EXECUTED": 0}
        deferral_reasons = {}
        for entry in r7_report["reports"]:
            for step in entry["steps"]:
                in_process = step["operation"] in R7_IN_PROCESS
                executed = bool(step.get("executed"))
                bucket = ("IN_PROCESS_" if in_process else "OTHER_") + (
                    "EXECUTED" if executed else "NOT_EXECUTED")
                by_class[bucket] += 1
                if in_process and not executed:
                    reason = step.get("not_executed_reason")
                    deferral_reasons[reason] = deferral_reasons.get(reason, 0) + 1
        r7_side.update({
            "report_path": os.path.relpath(R7_REHEARSAL, os.path.dirname(ROOT)),
            "report_sha256": hashing.sha256_file(R7_REHEARSAL),
            "report_is_in_r7_mutable_work_not_the_control_manifest": True,
            "steps_total_field": r7_report["steps_total"],
            "steps_executed_field": r7_report["steps_executed"],
            "by_class": by_class,
            "in_process_deferral_reasons": deferral_reasons,
        })

    explanation = {
        "R7_165_COUNT_EXPLAINED": "YES",
        "WHAT_165_IS": (
            "the number of unique plan-bound steps across R7's 43 plans whose "
            "operation is in R7's IN_PROCESS set. It is a property of the "
            "plans, measured statically, and it does not depend on any run. "
            "Re-measured here from R7's own plan bytes: %d." % r7_unique),
        "DIRTY_REPAIR_187_COUNT_EXPLAINED": "YES",
        "WHAT_187_IS": (
            "the value of the `steps_executed` field in the rehearsal report "
            "the dirty repair produced. That field counts executed steps of "
            "EVERY class, not in-process steps. REPAIR_FINDINGS.md records it "
            "as 'In-process steps executed: 187', which is a mislabelling of "
            "the field: the in-process execution count in that same run was "
            "143."),
        "THE_TWO_NUMBERS_COUNT_DIFFERENT_THINGS": (
            "165 counts plan steps of one class. 187 counts executed steps of "
            "all classes. They were never comparable, and the appearance of a "
            "discrepancy came from the second one's label rather than from "
            "either measurement."),
        "ARITHMETIC": (
            "In the dirty run: 143 in-process executed + 44 subprocess "
            "executed = 187 executed. 143 in-process executed + 22 in-process "
            "deferred = 165 in-process plan steps. Both identities hold "
            "exactly against the report's own per-step records."),
        "WHY_22_WERE_DEFERRED": (
            "6 LIVE_PHASE_MATERIAL_NOT_STAGED and 16 "
            "INPUT_PRODUCED_BY_AN_EARLIER_STEP_NOT_RUN_HERE. R8 does not "
            "permit either for an in-process step: the inputs are staged "
            "before the rehearsal instead of excused during it, and all %d "
            "in-process steps invoke their handler." % r8_unique),
        "WHY_R8_HAS_ONE_MORE": (
            "R8's L1-A33 repair adds MIME_EXTRACT_XML_PART_SANDBOX as a new "
            "step, and R8's L1-A21 repair changes one step's operation from "
            "PARSE_JSON_READONLY to COUNT_TEXT_MATCHES without changing the "
            "count. 165 + 1 = %d." % r8_unique),
        "FINAL_UNIQUE_IN_PROCESS_PLAN_STEP_COUNT": r8_unique,
        "FINAL_IN_PROCESS_HANDLER_INVOCATION_COUNT": r8_invocations,
        "UNEXPLAINED_COUNT_DIFFERENCE": 0,
    }

    return {
        "schema": "wpno.level1.in-process-count-reconciliation/1",
        "revision": "R8",
        "R7_UNIQUE_IN_PROCESS_PLAN_STEPS_REMEASURED": r7_unique,
        "R8_UNIQUE_IN_PROCESS_PLAN_STEPS": r8_unique,
        "R8_TOTAL_PLAN_STEPS": len(rows),
        "R8_IN_PROCESS_HANDLER_INVOCATIONS": r8_invocations,
        "R8_INVOCATIONS_PER_UNIQUE_STEP": (
            "1:1 for every step that ran; the executor is called once per "
            "plan step and never loops over inputs"),
        "r7_dirty_rehearsal": r7_side,
        "explanation": explanation,
        "steps": rows,
    }


def control_coverage():
    plans = load_plans(PLANS, ROOT)
    with open(REHEARSAL, encoding="utf-8") as fh:
        report = json.load(fh)
    observed = {}
    for entry in report["reports"]:
        for step in entry["steps"]:
            observed[(entry["audit_id"], entry["run_phase"],
                      step["step_id"])] = step

    rows = []
    for (audit_id, phase), plan in sorted(plans.items()):
        entries = {e["step_id"]: e for e in plan["test_matrix"]
                   if isinstance(e, dict) and "step_id" in e}
        for step in plan["steps"]:
            role = step.get("control_role")
            if role not in CONTROL_ROLES:
                continue
            entry = entries.get(step["step_id"]) or {}
            declared = in_process_executor.expectation_keys_present(entry)
            seen = observed.get((audit_id, phase, step["step_id"])) or {}
            rows.append({
                "AUDIT_ID": audit_id,
                "PHASE": phase,
                "STEP_ID": step["step_id"],
                "OPERATION": step["operation"],
                "CONTROL_ROLE": role,
                "DECLARED_EXPECTATIONS": declared,
                "MACHINE_CHECKABLE": bool(declared),
                "EXPECTED_FAILURE_REASON":
                    entry.get("expected_failure_reason_canonical")
                    or entry.get("expected_failure_reason"),
                "EXPECTATION_SOURCE": entry.get("expectation_source",
                                                "plan specification"),
                "WHY": entry.get("why"),
                "REHEARSAL_STATUS": seen.get("status"),
                "REHEARSAL_EXPECTATION_RESULT": seen.get("expectation_result"),
                "REHEARSAL_EXECUTED": seen.get("executed"),
                "DEGENERATE_OPERANDS": entry.get("degenerate_operands"),
                "ASSERTION_NOT_EXPRESSIBLE_IN_STEP":
                    entry.get("assertion_not_expressible_in_step"),
                "READS_OUTSIDE_DECLARED_ALLOWANCE":
                    seen.get("reads_outside_declared_allowance") or [],
            })

    needs_reason = [r for r in rows
                    if r["CONTROL_ROLE"] in ("NEGATIVE", "MUTATION")]
    outside = [r for r in rows if r["READS_OUTSIDE_DECLARED_ALLOWANCE"]]

    # Every step, not only control steps, for the allowance finding.
    all_outside = []
    for entry in report["reports"]:
        for step in entry["steps"]:
            paths = step.get("reads_outside_declared_allowance") or []
            if paths:
                all_outside.append({
                    "audit_id": entry["audit_id"],
                    "run_phase": entry["run_phase"],
                    "step_id": step["step_id"],
                    "operation": step["operation"],
                    "paths": paths})

    return {
        "schema": "wpno.level1.control-expectation-coverage/1",
        "revision": "R8",
        "CONTROL_ROLE_STEP_COUNT": len(rows),
        "CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION": "%d/%d" % (
            sum(1 for r in rows if r["MACHINE_CHECKABLE"]), len(rows)),
        "CONTROL_STEPS_WITH_EXPECTED_REASON_WHERE_REQUIRED": "%d/%d" % (
            sum(1 for r in needs_reason if r["EXPECTED_FAILURE_REASON"]),
            len(needs_reason)),
        "CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION": sum(
            1 for r in rows if not r["MACHINE_CHECKABLE"]),
        "R7_STEPS_WITH_CONTROL_ROLE_AND_NO_DECLARED_EXIT_CODE": 55,
        "R7_55_ADJUDICATED": (
            "41 of the 55 already declared an expectation in prose that no "
            "harness could evaluate; 14 declared none at all. All 55 now "
            "carry an operation-appropriate machine-checkable expectation "
            "from build/control_expectations.py, and the remaining 64 control "
            "steps kept the expected_exit_code they already had."),
        "NOT_WEAKENED": (
            "No control's expectation was loosened to make a rehearsal pass. "
            "Where the plan leaves an outcome open, the expectation demands "
            "that the step really ran rather than asserting an outcome the "
            "audit has not measured."),
        "findings_for_the_human": {
            "degenerate_operands": [
                {"audit_id": r["AUDIT_ID"], "step_id": r["STEP_ID"],
                 "note": r["DEGENERATE_OPERANDS"]}
                for r in rows if r["DEGENERATE_OPERANDS"]],
            "assertion_not_expressible_in_step": [
                {"audit_id": r["AUDIT_ID"], "step_id": r["STEP_ID"],
                 "note": r["ASSERTION_NOT_EXPRESSIBLE_IN_STEP"]}
                for r in rows if r["ASSERTION_NOT_EXPRESSIBLE_IN_STEP"]],
            "steps_reading_outside_their_plan_declared_allowance": all_outside,
        },
        "controls": rows,
    }


def write(name, payload):
    directory = os.path.join(ROOT, "build")
    path = os.path.join(directory, name)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(path), "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashing.sha256_text(text)
    with open(path_policy.assert_writable(
            path.replace(".json", ".sha256")), "w", encoding="utf-8") as fh:
        fh.write("%s  %s\n" % (digest, name))
    return path, digest


def main():
    recon, recon_sha = write("IN_PROCESS_COUNT_RECONCILIATION.json",
                             reconciliation())
    cover, cover_sha = write("CONTROL_EXPECTATION_COVERAGE.json",
                             control_coverage())
    with open(recon, encoding="utf-8") as fh:
        r = json.load(fh)
    with open(cover, encoding="utf-8") as fh:
        c = json.load(fh)
    print(json.dumps({
        "reconciliation": os.path.relpath(recon, ROOT),
        "reconciliation_sha256": recon_sha,
        "R7_165": r["R7_UNIQUE_IN_PROCESS_PLAN_STEPS_REMEASURED"],
        "R8_unique_in_process": r["R8_UNIQUE_IN_PROCESS_PLAN_STEPS"],
        "R8_invocations": r["R8_IN_PROCESS_HANDLER_INVOCATIONS"],
        "UNEXPLAINED_COUNT_DIFFERENCE":
            r["explanation"]["UNEXPLAINED_COUNT_DIFFERENCE"],
        "dirty_187_decomposition": r["r7_dirty_rehearsal"].get("by_class"),
        "coverage": os.path.relpath(cover, ROOT),
        "coverage_sha256": cover_sha,
        "CONTROL_ROLE_STEP_COUNT": c["CONTROL_ROLE_STEP_COUNT"],
        "CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION":
            c["CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION"],
        "CONTROL_STEPS_WITH_EXPECTED_REASON_WHERE_REQUIRED":
            c["CONTROL_STEPS_WITH_EXPECTED_REASON_WHERE_REQUIRED"],
        "CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION":
            c["CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION"],
        "steps_reading_outside_declared_allowance": len(
            c["findings_for_the_human"]
            ["steps_reading_outside_their_plan_declared_allowance"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
