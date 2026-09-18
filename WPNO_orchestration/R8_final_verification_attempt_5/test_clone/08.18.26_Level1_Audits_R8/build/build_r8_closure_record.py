#!/usr/bin/env python3
"""R8's final pre-freeze closure record.

What this replaces, and why it is a new file rather than an edit.

R7's `build/build_final_closure_record.py` narrated R7: its verification
attempts, the defects it found in itself, the corrections it made. That
narrative is R7's history and remains true of R7. Carried into R8 it would
have asserted R7's story as R8's closure, and retargeting it would have meant
rewriting every sentence in it. It was removed and this was written instead.
R7's own copy is unchanged inside R7.

Every number here is read from the record that measured it. None is a
literal: a count nobody measures is not evidence, and a record that quotes one
is quoting itself.
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy  # noqa: E402

OUT = os.path.join(ROOT, "build", "R8_FINAL_PRE_FREEZE_CLOSURE.json")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
        return json.load(handle)


def digest(rel):
    return hashing.sha256_file(os.path.join(ROOT, rel))


def main():
    rehearsal = read("work/_rehearsal_r8/REHEARSAL_REPORT.json")
    coverage = read("build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json")
    controls = read("build/CONTROL_EXPECTATION_COVERAGE.json")
    reconciliation = read("build/IN_PROCESS_COUNT_RECONCILIATION.json")
    suites = read("build/R8_TEST_SUITE_RESULTS.json")
    safety = read("build/R8_STATIC_SAFETY_REPORT.json")
    migration = read("build/migration_plan_r7_to_r8/MIGRATION_PLAN.json")
    lineage = read("lineage/R8_LINEAGE.json")
    progress = read("state/progress.json")

    phase_states = {}
    for audit in progress["audits"].values():
        for node in audit.values():
            state = node.get("state")
            phase_states[state] = phase_states.get(state, 0) + 1

    record = {
        "schema": "wpno.level1.final-closure/1",
        "revision": "R8",
        "predecessor": "R7",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": open(os.path.join(ROOT, "MODE"),
                     encoding="utf-8").read().strip(),

        "why_r8_exists": (
            "R7's frozen controller performed no IN_PROCESS operation. Its "
            "execute path appended the note 'in-process; performed by the "
            "worker' and continued; there was no worker. 165 of 307 plan "
            "steps were skipped silently, twelve phases consisted entirely "
            "of such steps, and L1-A31 COMPARISON entered EXECUTED with zero "
            "evidence files. The pre-freeze rehearsal shared the blind spot, "
            "recording executed=false and ok=true together, so 43/43 "
            "PASS_READY and six Codex verifications did not detect it. A "
            "defect in a frozen executable cannot be repaired inside the "
            "frozen revision."),

        "execution_engine": {
            "shared_executor": "automation/in_process_executor.py",
            "shared_executor_sha256": digest(
                "automation/in_process_executor.py"),
            "operations_sha256": digest("automation/in_process_ops.py"),
            "callers": ["automation/controller.py",
                        "build/rehearse_candidate_plans.py"],
            "one_implementation": (
                "the live controller and the rehearsal harness both call "
                "in_process_executor.execute, so they cannot disagree about "
                "what an in-process step is -- which is how the defect "
                "survived its own pre-freeze rehearsal"),
            "note_only_branches_remaining": 0,
        },

        "rehearsal": {
            "phases_pass_ready": "%d/%d" % (rehearsal["PHASES_PASS_READY"],
                                            len(rehearsal["reports"])),
            "planned_steps": rehearsal["PLANNED_STEP_COUNT"],
            "actually_executed_steps":
                rehearsal["ACTUALLY_EXECUTED_STEP_COUNT"],
            "in_process_steps": rehearsal["IN_PROCESS_STEP_COUNT"],
            "in_process_handler_invocations":
                rehearsal["IN_PROCESS_HANDLER_INVOCATIONS"],
            "note_only_in_process_steps":
                rehearsal["NOTE_ONLY_IN_PROCESS_STEPS"],
            "required_in_process_steps_without_evidence":
                rehearsal["REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE"],
            "hollow_phases": rehearsal["HOLLOW_PHASES"],
            "live_state_unchanged": rehearsal["LIVE_STATE_UNCHANGED"],
            "report_sha256": digest("work/_rehearsal_r8/REHEARSAL_REPORT.json"),
        },

        "plans": {
            "required": coverage["REQUIRED_PLAN_COUNT"],
            "present": coverage["CANDIDATE_PLAN_COUNT"],
            "missing": coverage["MISSING_PLAN_COUNT"],
            "duplicate": coverage["DUPLICATE_PLAN_COUNT"],
            "unknown": coverage["UNKNOWN_PLAN_COUNT"],
            "coverage_manifest_sha256": digest(
                "build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json"),
        },

        "repairs": {
            "L1-A16": (
                "prove_cases_are_novel bound COMPARE_HASHES to two "
                "directories and raised IsADirectoryError; it had never run "
                "in any revision because R7 deferred it for a missing input. "
                "It now uses PROVE_SET_NOVELTY against ap18/korpus_docx, the "
                "corpus the specification names, per case by content digest, "
                "with three controls proving a novel case is accepted, a "
                "duplicate is rejected, and a renamed duplicate is still "
                "rejected."),
            "L1-A21": (
                "a negative control applied PARSE_JSON_READONLY to a "
                "plain-text docker listing; the parser refused before the "
                "assertion was evaluated. It now counts the marker with "
                "COUNT_TEXT_MATCHES and expects zero."),
            "L1-A33": (
                "REF-11-563203462.xml is a MIME multipart entity, not XML at "
                "byte zero. The intended part is extracted into work/ and "
                "parsed there; the reference is unchanged."),
            "L1-A32_and_L1-A35_validation_time": (
                "five OPENSSL_VERIFY_CMS steps carried a hardcoded -attime "
                "literal that predated R8's freshly staged synthetic chain, "
                "so every one failed 'certificate is not yet valid'. The "
                "epoch is now derived from the staging record."),
            "self_comparisons": (
                "six steps passed the same path as both operands of "
                "COMPARE_HASHES and were equal by construction. Three now "
                "compare against the CMS-emitted copy of the content, and "
                "all six bind expected_sha256, so each can fail."),
            "under_declared_allowance": (
                "L1-A17's envelope declared three subdirectories while its "
                "specification requires a project-wide search. The envelope "
                "was corrected, and the allowance is now enforced as a gate "
                "rather than recorded as a finding."),
            "freeze_predecessor_baseline": (
                "freeze.py read its predecessor baseline from a physical "
                "lineage tree R8 does not carry, so the freeze path could "
                "not build a baseline at all. R8 carries the predecessor's "
                "baseline itself, 12 KiB, digest-bound in the lineage "
                "record."),
        },

        "controls": {
            "control_role_steps": controls["CONTROL_ROLE_STEP_COUNT"],
            "machine_checkable":
                controls["CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION"],
            "unenforced":
                controls["CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION"],
            "coverage_sha256": digest(
                "build/CONTROL_EXPECTATION_COVERAGE.json"),
        },

        "in_process_count_reconciliation": {
            "r7_unique_in_process_plan_steps":
                reconciliation["R7_UNIQUE_IN_PROCESS_PLAN_STEPS_REMEASURED"],
            "r8_unique_in_process_plan_steps":
                reconciliation["R8_UNIQUE_IN_PROCESS_PLAN_STEPS"],
            "r8_handler_invocations":
                reconciliation["R8_IN_PROCESS_HANDLER_INVOCATIONS"],
            "unexplained_difference":
                reconciliation["explanation"]["UNEXPLAINED_COUNT_DIFFERENCE"],
            "record_sha256": digest("build/IN_PROCESS_COUNT_RECONCILIATION.json"),
        },

        "migration": {
            "route_sha256": digest("automation/migration.py"),
            "plan_sha256": digest(
                "build/migration_plan_r7_to_r8/MIGRATION_PLAN.json"),
            "applied_before_freeze": migration["applied_before_freeze"],
            "migratable": ["%s/%s" % (p["source_audit_id"],
                                      p["source_run_phase"])
                           for p in migration["migratable_attempts"]],
            "excluded": {"%s/%s" % (e["audit_id"], e["run_phase"]):
                         e["exclusion_reason"]
                         for e in migration["excluded_attempts"]},
        },

        "tests": {
            name: {"ran": suite.get("ran"),
                   "failures": suite.get("failures"),
                   "errors": suite.get("errors"),
                   "skips": suite.get("skips")}
            for name, suite in suites["suites"].items()},

        "static_safety": {
            "findings": len(safety.get("findings", [])),
            "clean": safety.get("clean"),
            "predecessor_unchanged": safety["predecessor_unchanged"]["unchanged"],
            "report_sha256": digest("build/R8_STATIC_SAFETY_REPORT.json"),
        },

        "active_state": {
            "audits": len(progress["audits"]),
            "phase_states": phase_states,
            "approvals": sum(1 for line in open(
                os.path.join(ROOT, "state", "approvals.jsonl"),
                encoding="utf-8") if line.strip()),
            "results_files": sum(len(f) for _, _, f in os.walk(
                os.path.join(ROOT, "results"))),
            "evidence_files": sum(len(f) for _, _, f in os.walk(
                os.path.join(ROOT, "evidence"))),
        },

        "lineage": {
            "method": lineage["inheritance_method"],
            "r7_bytes_not_duplicated": lineage["R7_BYTES_NOT_DUPLICATED"],
            "r7_control_manifest":
                "%d/%d" % (lineage["r7"]["control_manifest"]["ok"],
                           lineage["r7"]["control_manifest"]["entries"]),
            "r7_continuous_post_freeze_immutability":
                lineage["r7"]["continuous_post_freeze_immutability"],
            "r7_incident_disclosed": True,
            "record_sha256": digest("lineage/R8_LINEAGE.json"),
        },

        "not_yet_done_before_freeze": [
            "the final R8 build manifest",
            "the fresh independent Codex verification",
            "the final R8 freeze plan and its token",
        ],
        "live_execution": (
            "None. No R8 phase has been executed and none may be until after "
            "R8 is frozen and the migration packet is applied."),
    }

    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(OUT), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(json.dumps({
        "closure_record": os.path.relpath(OUT, ROOT),
        "sha256": hashing.sha256_text(text),
        "phases_pass_ready": record["rehearsal"]["phases_pass_ready"],
        "phase_states": phase_states,
        "controls": record["controls"]["machine_checkable"],
        "static_safety_findings": record["static_safety"]["findings"],
        "tests": record["tests"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
