#!/usr/bin/env python3
"""Build the final R7 freeze plan and print the token a human must supply.

Why this file sits here rather than beside the other build scripts. The final
build manifest is generated once, over the final package bytes, and everything
written into the package afterwards would make it stale. Two families are
therefore created after it and excluded from it by a named rule: the fresh
verifier's output directory and this freeze-plan directory. A builder that
lived inside the manifest could not be changed for this attempt without
invalidating the manifest the attempt exists to bind. So the builder for an
attempt lives with the attempt, and the plan binds the builder by digest along
with everything else.

`build/build_r7_freeze_plan.py` remains in the package and in the manifest. It
is R7's freeze-plan architecture and this builder follows it: the same schema,
the same shape check in `automation.freeze`, the same token grammar, the same
refusal to issue a token itself.

This script issues no token. It prints the exact token the freeze route will
demand, and the freeze route will not accept one this script produced: the
token has to come from a human, typed, and it is one-time.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# Three levels: this file lives at build/freeze_plan_attempt_1/, which is the
# freeze-plan directory the build manifest excludes by design. It belongs
# here rather than in build/ for the same reason the plan it writes does --
# both are created after the manifest exists, so a manifest that covered
# them would be stale the moment either was written. An earlier R8 copy of
# this builder sat one level up with the same three dirnames, which resolved
# ROOT to the directory above the package and made the module unimportable.
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from automation import freeze, hashing, path_policy  # noqa: E402

ATTEMPT = 1
PLAN_PATH = os.path.join(HERE, "FREEZE_PLAN_R8_ATTEMPT_%d.json" % ATTEMPT)

VERIFICATION_DIR = "verification_codex_final_pre_freeze_attempt_3"
VERIFICATION_RESULT = os.path.join(VERIFICATION_DIR,
                                   "VERIFICATION_RESULT.json")
VERIFICATION_MANIFEST = os.path.join(VERIFICATION_DIR,
                                     "VERIFICATION_MANIFEST.sha256")

COVERAGE = "build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json"


def rel_sha(relative):
    path = os.path.join(ROOT, relative)
    if not os.path.isfile(path):
        raise SystemExit("bound artefact is absent: %s" % relative)
    if os.path.islink(path):
        raise SystemExit("bound artefact is a symlink: %s" % relative)
    if os.path.getsize(path) == 0:
        raise SystemExit("bound artefact is zero bytes: %s" % relative)
    return hashing.sha256_file(path)


def candidate_plan_paths():
    """All 43, from the coverage manifest, checked against the registry."""
    with open(os.path.join(ROOT, COVERAGE), encoding="utf-8") as fh:
        coverage = json.load(fh)
    if coverage["CANDIDATE_PLAN_COUNT"] != 43 \
            or coverage["REQUIRED_PLAN_COUNT"] != 43 \
            or coverage["MISSING_PLAN_COUNT"] \
            or coverage["DUPLICATE_PLAN_COUNT"] \
            or coverage["UNKNOWN_PLAN_COUNT"]:
        raise SystemExit(
            "the plan coverage manifest does not report a complete 43-plan "
            "set: %s" % json.dumps({k: coverage[k] for k in (
                "REQUIRED_PLAN_COUNT", "CANDIDATE_PLAN_COUNT",
                "MISSING_PLAN_COUNT", "DUPLICATE_PLAN_COUNT",
                "UNKNOWN_PLAN_COUNT")}))
    return [row["plan_path"] for row in coverage["plans"]]


# Everything the freeze is bound to, by relative path. The freeze route
# re-hashes each of these from disk before it writes anything, so this list is
# the answer to "what exactly is being frozen, and what would void it".
def bound_paths():
    """Everything the freeze binds, and the reason each family is here.

    Rebuilt for R8. R7's list named R7's artefacts -- its build manifest, its
    closure record, its six verification attempts, and the physical
    `lineage/R6_EXECUTION` tree that R8 does not carry. Naming them here would
    have made the builder refuse on the first absent path, which is the
    correct behaviour and the reason the list is rebuilt rather than trimmed.

    The list is derived where it can be. The 43 candidate plans and the 35
    bindings are enumerated, not typed out, so a plan that appeared without
    being bound would be a build failure rather than an omission nobody sees.
    """
    out = [
        # the manifest of the whole control plane
        "build/R8_BUILD_MANIFEST.sha256",

        # the independent verification and what it read
        VERIFICATION_RESULT,
        VERIFICATION_MANIFEST,
        os.path.join(VERIFICATION_DIR, "VERIFY_PROMPT.md"),
        os.path.join(VERIFICATION_DIR, "VERIFICATION_NOTES.md"),

        # the execution-engine repair: the defect R8 exists to fix
        "automation/in_process_executor.py",
        "automation/in_process_ops.py",
        "automation/operation_catalog.py",
        "automation/controller.py",
        "build/rehearse_candidate_plans.py",

        # the migration route, its packet, and the tests that prove both
        "automation/migration.py",
        "build/migration_plan_r7_to_r8/MIGRATION_PLAN.json",
        "build/migration_plan_r7_to_r8/MIGRATION_PLAN.sha256",
        "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-A.json",
        "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-B.json",
        "build/build_migration_plan.py",
        "automation/package_tests/test_r8_migration.py",

        # the measurement records that settle the two open questions
        "build/IN_PROCESS_COUNT_RECONCILIATION.json",
        "build/IN_PROCESS_COUNT_RECONCILIATION.sha256",
        "build/CONTROL_EXPECTATION_COVERAGE.json",
        "build/CONTROL_EXPECTATION_COVERAGE.sha256",
        "build/control_expectations.py",

        # closure, status, tests and static safety
        "build/R8_FINAL_PRE_FREEZE_CLOSURE.json",
        "build/R8_RESUME_STATUS.json",
        "build/R8_TEST_SUITE_RESULTS.json",
        "build/R8_STATIC_SAFETY_REPORT.json",
        "build/run_test_suites.py",
        "build/r8_static_safety_review.py",

        # the plan builders and the coverage manifest
        "build/build_candidate_plans.py",
        "build/build_all_candidate_plans.py",
        "build/candidate_plan_specs.py",
        "build/plan_library.py",
        "build/stage_l1a31_material.py",
        "build/stage_rehearsal_fixtures.py",
        "build/stage_r8_rehearsal_inputs.py",
        COVERAGE,
        "build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.sha256",

        # the compact lineage, the predecessor's baseline, and the incident
        # that R7's own control manifest cannot record
        "lineage/R8_LINEAGE.json",
        "lineage/R8_LINEAGE.sha256",
        "lineage/R7_BASELINE_MANIFEST.json",
        "lineage/R7_POST_FREEZE_INCIDENT/INCIDENT_MANIFEST.sha256",
        "lineage/R7_POST_FREEZE_INCIDENT/R7_RESTORATION_RECORD.json",
        "lineage/R7_POST_FREEZE_INCIDENT/REPAIR_FINDINGS.json",
        "lineage/R7_POST_FREEZE_INCIDENT/DIRTY_R7_MEASUREMENT.json",

        # references, decisions and corpora
        "references/manifest.json",
        "references/REF-01-swift-iban-registry-release-102.txt",
        "references/REF-02-python-stdnum-2.2.zip",
        "references/REF-03_SOURCE_MAP.txt",
        "references/REF-03_MANIFEST.sha256",
        "references/REF-04_idnr.py",
        "references/REF-05_COVERAGE.json",
        "references/REF-06_S01.docx",
        "references/REF-07_MANIFEST.sha256",
        "references/REF-11-563203462.xml",
        "references/REF-11-original-mail-attachment.zip",
        "references/REF-11-vhn-covered-content.xml",
        "references/REF-12/REF-12_MANIFEST.sha256",
        "references/REF-12/REF-12_OPERATOR_PROVENANCE.txt",
        "references/REF-13_all_containers.txt",
        "references/REF-13_REDACTION_MANIFEST.json",
        "references/REF-13_REDACTED_MANIFEST.sha256",
        "references/REF-14_MANIFEST.sha256",
        "references/REF-14_MAC_MANIFEST.sha256",
        "references/REF-14_MAC_REALITY.json",
        "corpora/R5_REF01_COUNTRY_RULES.jsonl",
        "corpora/R5_REF02_IBAN_VECTORS.jsonl",
        "corpora/R7_REF04_IDNR_VECTORS.jsonl",
        "corpora/R7_REF04_IDNR_VECTORS.meta.json",

        # the independent toolchain
        "tools/R5_BOUNCY_CASTLE_PROVENANCE.json",
        "tools/cms_verifier/src/WpnoCmsVerify.java",
        "tools/cms_verifier/classes/WpnoCmsVerify.class",
        "tools/a18_run_b/src/WpnoIbanValidateRunB.java",
        "tools/a19_run_b/src/WpnoIdnrValidateRunB.java",
        "tools/a19_run_b/classes/WpnoIdnrValidateRunB.class",
    ]
    # every binding: these carry the human decisions
    out += ["bindings/L1-A%02d.binding.json" % n for n in range(1, 36)]
    # every candidate plan, enumerated rather than listed
    out += candidate_plan_paths()
    # the rehearsal evidence, which lives under work/ and is therefore
    # outside the build manifest by design. The freeze binds it here so that
    # nothing which the freeze rests on goes uncovered by both.
    out += ["work/_rehearsal_r8/REHEARSAL_REPORT.json",
            "work/_rehearsal_r8/FIXTURE_STAGING_RECORD.json",
            "work/_rehearsal_r8/REHEARSAL_INPUT_SUBSTITUTIONS.json",
            "work/L1-A31/preparation_r8_2026-08-28/STAGING_RECORD.json"]
    # MODE last, so the freeze cannot record a MODE it did not publish
    out += ["MODE"]
    # this builder
    # This builder is inside the excluded freeze-plan directory, so the
    # build manifest does not cover it. The plan binds it by digest instead.
    out += [os.path.relpath(os.path.abspath(__file__), ROOT)]
    seen, ordered = set(), []
    for rel in out:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def main():
    result_path = os.path.join(ROOT, VERIFICATION_RESULT)
    if not os.path.isfile(result_path):
        raise SystemExit("no final verification result at %s"
                         % VERIFICATION_RESULT)
    with open(result_path, encoding="utf-8") as fh:
        verification = json.load(fh)
    status = verification.get("result") or verification.get("status")
    if status != "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL":
        raise SystemExit(
            "the final verification did not pass: %r. A freeze plan is not "
            "created on a failed or partial verification." % (status,))

    bound = bound_paths()
    baseline, provenance = freeze.build_baseline_from_predecessor(
        ROOT, rel_sha(freeze.PREDECESSOR_BASELINE_REL))
    baseline_text = freeze.serialize_baseline(baseline)

    with open(os.path.join(ROOT, "work", "_rehearsal_r8",
                           "REHEARSAL_REPORT.json"), encoding="utf-8") as fh:
        rehearsal = json.load(fh)
    with open(os.path.join(ROOT, "build", "R8_STATIC_SAFETY_REPORT.json"),
              encoding="utf-8") as fh:
        safety = json.load(fh)
    with open(os.path.join(ROOT, COVERAGE), encoding="utf-8") as fh:
        coverage = json.load(fh)
    with open(os.path.join(ROOT, "build", "R8_TEST_SUITE_RESULTS.json"),
              encoding="utf-8") as fh:
        suites = json.load(fh)["suites"]
    with open(os.path.join(ROOT, "build",
                           "CONTROL_EXPECTATION_COVERAGE.json"),
              encoding="utf-8") as fh:
        controls = json.load(fh)
    with open(os.path.join(ROOT, "build",
                           "R8_FINAL_PRE_FREEZE_CLOSURE.json"),
              encoding="utf-8") as fh:
        closure = json.load(fh)
    with open(os.path.join(ROOT, "lineage", "R8_LINEAGE.json"),
              encoding="utf-8") as fh:
        predecessors = json.load(fh)
    with open(os.path.join(ROOT, "build", "migration_plan_r7_to_r8",
                           "MIGRATION_PLAN.json"), encoding="utf-8") as fh:
        migration_plan = json.load(fh)

    # Refuse to build a plan on top of live state that has moved.
    live = closure["active_state"]
    if live["phase_states"] != {"NOT_STARTED": 43}:
        raise SystemExit("live phase state is not 43 NOT_STARTED: %s" % live)
    if live["approvals"] or live["results_files"] or live["evidence_files"]:
        raise SystemExit("live approval, result or evidence present: %s" % live)

    # The migration is prepared, bound, and not applied. Applying it before
    # the freeze would break the 43/43 NOT_STARTED invariant this plan
    # certifies.
    if migration_plan["applied_before_freeze"]:
        raise SystemExit("the migration packet was applied before the freeze")
    consumed_ledger = os.path.join(ROOT, "state", "migrations.jsonl")
    if os.path.exists(consumed_ledger) and os.path.getsize(consumed_ledger):
        raise SystemExit("a migration packet has already been consumed")

    # R8 is the final revision and nothing may exist past it.
    successor = "08.18.26_Level1_Audits_R9"
    if os.path.exists(os.path.join(os.path.dirname(ROOT), successor)):
        raise SystemExit("%s exists; R8 is the final revision" % successor)
    mode = open(os.path.join(ROOT, "MODE"), encoding="utf-8").read().strip()
    if mode != "GENERATED_UNVERIFIED":
        raise SystemExit("MODE is %r, not GENERATED_UNVERIFIED" % mode)

    ledger = os.path.join(ROOT, "state", "freeze_attempts.jsonl")
    consumed = freeze.recorded_attempts(ledger)
    if consumed:
        raise SystemExit("a freeze attempt has already been recorded: %d"
                         % len(consumed))

    plan = {
        "schema": "wpno.level1.freeze-plan/2",
        "revision": freeze.PACKAGE_REVISION,
        "platform": freeze.PACKAGE_PLATFORM,
        "attempt_number": ATTEMPT,
        "attempt_purpose": (
            "First and only freeze attempt for R7, after the Section 8 build "
            "brought the candidate-plan set from 9 of 43 to 43 of 43 and a "
            "fresh independent verification passed. R7 is the final revision; "
            "there is no R8."),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "r7_root": ROOT,

        "package_sha256": rel_sha("build/R8_BUILD_MANIFEST.sha256"),
        "verification_result_sha256": rel_sha(VERIFICATION_RESULT),
        "verification_manifest_sha256": rel_sha(VERIFICATION_MANIFEST),
        "verification_status": status,
        "verification_path": VERIFICATION_DIR,
        "verification_independence": (
            "a fresh Codex process with no build-session context, in the same "
            "local workspace: a different model, a different harness and a "
            "different vendor from the session that built the package, on the "
            "same machine and reading the same disk. It is not an independent "
            "machine and does not claim to be."),
        "verification_attempts": {
            "attempt_1": {"path": VERIFICATION_DIR, "result": status},
        },

        "baseline_preview_sha256": hashing.sha256_text(baseline_text),
        "expected_project_baseline_count": provenance["project_members"],
        "expected_discovery_baseline_count": provenance["discovery_members"],
        "baseline_provenance": provenance,
        "predecessor_baseline_manifest_path": freeze.PREDECESSOR_BASELINE_REL,
        "predecessor_baseline_manifest_sha256":
            rel_sha(freeze.PREDECESSOR_BASELINE_REL),

        "bound_artifacts": {rel: rel_sha(rel) for rel in bound},

        "plan_coverage": {
            "REQUIRED_PLAN_COUNT": coverage["REQUIRED_PLAN_COUNT"],
            "CANDIDATE_PLAN_COUNT": coverage["CANDIDATE_PLAN_COUNT"],
            "phase_totals_by_kind": coverage["phase_totals_by_kind"],
            "NEW_PLANS_BUILT": len(coverage["newly_built"]),
            "EXISTING_PLANS_REUSED": len(coverage["prebuilt_reused"]),
            "manifest": COVERAGE,
        },

        "exact_plan_rehearsal": {
            "phases_refreshed_this_run": rehearsal.get("phases_refreshed_this_run"),
            "phases_carried_forward": rehearsal.get("phases_carried_forward"),
            "carried_forward_rule": rehearsal.get("carried_forward_rule"),
            "phases_rehearsed": rehearsal["phases_rehearsed"],
            "phases_required": rehearsal["phases_required"],
            "all_pass_ready": rehearsal["all_pass_ready"],
            "LIVE_STATE_UNCHANGED": rehearsal["LIVE_STATE_UNCHANGED"],
            "steps_total": rehearsal["steps_total"],
            "steps_executed": rehearsal["steps_executed"],
            "not_executed_reasons": rehearsal["not_executed_reasons"],
            "report": "work/_rehearsal_r8/REHEARSAL_REPORT.json",
            "note": ("the rehearsal runs the candidate plans through the same "
                     "operation_catalog.build_argv the controller calls, with "
                     "the plans' own parameters. R6's readiness fixture built "
                     "its own parameters and passed while the live plan failed "
                     "on three of them."),
            "what_it_does_not_mean": (
                "PASS_READY is a statement about the plan and the harness. No "
                "live audit has run and no audit verdict exists."),
        },

        "tests": {
            "measured_not_declared": (
                "both figures are read from build/R8_TEST_SUITE_RESULTS.json, "
                "which records what unittest reported and the digest of every "
                "test source. An earlier form held them as literals here and "
                "one went stale, reading 281 after the suite had grown to 312."),
            "controller_suite": {k: suites["controller_suite"][k]
                                 for k in ("ran", "failures", "errors", "skips",
                                           "clean", "measurement")},
            "controller_suite_why_not_rerun":
                suites["controller_suite"].get("why_not_rerun"),
            "package_suite": {k: suites["package_suite"][k]
                              for k in ("ran", "failures", "errors", "skips",
                                        "clean", "measurement")},
            "static_safety_findings": safety["finding_count"],
            "static_safety_clean": safety["clean"],
            "unpermitted_changes": safety.get("unpermitted_changes", []),
            "predecessor_unchanged":
                safety["predecessor_unchanged"]["unchanged"],
        },

        "execution_engine_repair": {
            "what_was_wrong": (
                "the frozen R7 controller performed no IN_PROCESS operation. "
                "Its execute path appended the note 'in-process; performed by "
                "the worker' and continued; there was no worker. 165 of 307 "
                "plan steps were skipped silently and twelve phases consisted "
                "entirely of such steps. The pre-freeze rehearsal recorded "
                "executed false and ok true together, so it shared the blind "
                "spot and 43/43 PASS_READY meant less than it appeared to."),
            "shared_executor": "automation/in_process_executor.py",
            "shared_executor_sha256": rel_sha(
                "automation/in_process_executor.py"),
            "both_callers": ["automation/controller.py",
                             "build/rehearse_candidate_plans.py"],
            "in_process_steps": rehearsal["IN_PROCESS_STEP_COUNT"],
            "in_process_handler_invocations":
                rehearsal["IN_PROCESS_HANDLER_INVOCATIONS"],
            "note_only_in_process_steps":
                rehearsal["NOTE_ONLY_IN_PROCESS_STEPS"],
            "required_in_process_steps_without_evidence":
                rehearsal["REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE"],
            "hollow_phases": rehearsal["HOLLOW_PHASES"],
            "count_reconciliation":
                "build/IN_PROCESS_COUNT_RECONCILIATION.json",
            "count_reconciliation_sha256": rel_sha(
                "build/IN_PROCESS_COUNT_RECONCILIATION.json"),
        },

        "control_expectations": {
            "record": "build/CONTROL_EXPECTATION_COVERAGE.json",
            "record_sha256": rel_sha(
                "build/CONTROL_EXPECTATION_COVERAGE.json"),
            "control_role_steps": controls["CONTROL_ROLE_STEP_COUNT"],
            "machine_checkable":
                controls["CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION"],
            "unenforced":
                controls["CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION"],
        },

        "migration": {
            "route": "automation/migration.py",
            "route_sha256": rel_sha("automation/migration.py"),
            "plan": "build/migration_plan_r7_to_r8/MIGRATION_PLAN.json",
            "plan_sha256": rel_sha(
                "build/migration_plan_r7_to_r8/MIGRATION_PLAN.json"),
            "applied_before_freeze": migration_plan["applied_before_freeze"],
            "packet_consumed": False,
            "migratable": ["%s/%s" % (p["source_audit_id"],
                                      p["source_run_phase"])
                           for p in migration_plan["migratable_attempts"]],
            "excluded": {"%s/%s" % (e["audit_id"], e["run_phase"]):
                         e["exclusion_reason"]
                         for e in migration_plan["excluded_attempts"]},
            "post_freeze_resume_sequence":
                migration_plan["post_freeze_resume_sequence"],
        },

        "lineage": {
            "predecessor": "R7",
            "predecessor_root": predecessors["r7"]["root"],
            "inheritance_method": predecessors["inheritance_method"],
            "r7_bytes_not_duplicated":
                predecessors["R7_BYTES_NOT_DUPLICATED"],
            "r7_control_manifest": "%d/%d" % (
                predecessors["r7"]["control_manifest"]["ok"],
                predecessors["r7"]["control_manifest"]["entries"]),
            "r7_continuous_post_freeze_immutability":
                predecessors["r7"]["continuous_post_freeze_immutability"],
            "r7_current_bytes_restored_to_frozen_manifest":
                predecessors["r7"]["current_bytes_restored_to_frozen_manifest"],
            "r7_incident_record": "lineage/R7_POST_FREEZE_INCIDENT",
            "r7_incident_manifest_sha256": rel_sha(
                "lineage/R7_POST_FREEZE_INCIDENT/INCIDENT_MANIFEST.sha256"),
            "r4_unchanged":
                predecessors["predecessors"]["R4"]["snapshot_matches_r7_record"],
            "r5_historical_mode_mismatch_only": (
                predecessors["predecessors"]["R5"]["control_manifest"]
                ["mismatching_paths"] == ["MODE"]),
            "r6_unchanged":
                predecessors["predecessors"]["R6"]["snapshot_matches_r7_record"],
            "integrity_record": "lineage/R8_LINEAGE.json",
            "integrity_record_sha256": rel_sha("lineage/R8_LINEAGE.json"),
        },

        "excluded_paths": {
            "from_the_build_manifest": [
                "__pycache__", "work/", "state/", "results/", "evidence/",
                "logs/", "build/R8_BUILD_MANIFEST.sha256 (itself)",
                "verification_codex_final_pre_freeze_attempt_*/",
                "build/freeze_plan_attempt_*/"],
            "why_the_last_two": (
                "both are created after the manifest is generated. They are "
                "bound here instead, by digest, which is why this plan lists "
                "the verification directory's files and its own builder among "
                "its bound artefacts."),
            "rule": ("matched on a path component, so "
                     "verification_codex_pre_freeze/ and "
                     "build/notes_about_freeze_plan_attempt_1.md are not "
                     "caught"),
        },

        "replay_protection": {
            "attempt_number": ATTEMPT,
            "attempts_consumed": len(consumed),
            "ledger_path": "state/freeze_attempts.jsonl",
            "prior_r4_token_may_authorize": False,
            "prior_r5_token_may_authorize": False,
            "prior_r6_token_may_authorize": False,
            "semantics": "RUN-ONCE",
        },

        # Read from R8's closure record, whose keys differ from R7's: the
        # closure record reports `phase_states` and `audits` rather than
        # `states` and `phase_records`, and counts approvals rather than the
        # byte length of the journal.
        "live_state_at_plan_time": {
            "mode": mode,
            "audits": live["audits"],
            "phase_records": sum(live["phase_states"].values()),
            "states": live["phase_states"],
            "approvals": live["approvals"],
            "results_files": live["results_files"],
            "evidence_files": live["evidence_files"],
            "migration_packet_consumed": False,
        },

        "final_revision": True,
        "successor_permitted": False,
        "successor_absent_on_disk": True,
        "token_grammar": ("FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> "
                          "VERIFICATION-SHA256=<64hex> "
                          "FREEZE-PLAN-SHA256=<64hex> RUN-ONCE"),
    }

    freeze.assert_package_plan_shape(plan)

    path_policy.ensure_dir(HERE)
    raw = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(PLAN_PATH), "w",
              encoding="utf-8") as fh:
        fh.write(raw)

    plan_sha = hashing.sha256_text(raw)

    # The plan must describe the package as it is now. Checked here, and
    # checked again by the freeze route before it writes a byte.
    freeze.assert_plan_matches_disk(plan, ROOT)

    token = freeze.token_for(plan["package_sha256"],
                             plan["verification_result_sha256"], plan_sha)

    print(json.dumps({
        "freeze_plan_path": os.path.relpath(PLAN_PATH, ROOT),
        "freeze_plan_sha256": plan_sha,
        "attempt_number": ATTEMPT,
        "package_sha256": plan["package_sha256"],
        "verification_result_sha256": plan["verification_result_sha256"],
        "verification_manifest_sha256": plan["verification_manifest_sha256"],
        "bound_artifacts": len(plan["bound_artifacts"]),
        "bound_artifacts_all_matched": True,
        "baseline_project_members": plan["expected_project_baseline_count"],
        "baseline_discovery_members": plan["expected_discovery_baseline_count"],
        "token_issued_by_this_script": False,
        "token_recorded": False,
        "token_consumed": False,
        "required_human_token": token,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
