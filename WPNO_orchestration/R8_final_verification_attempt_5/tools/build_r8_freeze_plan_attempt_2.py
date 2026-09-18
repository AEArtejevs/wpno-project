#!/usr/bin/env python3
"""Build R8 freeze plan attempt 2 and print the token a human must supply.

Why this builder lives outside the package
------------------------------------------
Attempt 1's builder sat at `build/freeze_plan_attempt_1/` inside R8, and
writing its plan wrote into R8. Attempt 5's governing condition is that no
attempt-5 operation writes into R8 at all, proved by a full pre/post inventory
over every path, mode and mtime. A builder that wrote its plan into the package
would break that condition before the plan existed.

So this builder lives under ATTEMPT5_ROOT and writes the plan under
ATTEMPT5_ROOT. It does not call `automation.path_policy.assert_writable`,
which by design admits writes only below LEVEL1_ROOT: routing the plan through
it would mean writing into the package, which is the thing forbidden here. That
omission is deliberate and stated rather than silent.

What that costs, and what it does not
-------------------------------------
`automation.controller.cmd_freeze_level1` resolves its plan with
`freeze.confined_path(root, args.plan or FREEZE_PLAN_REL)`, and `confined_path`
refuses an absolute path and refuses any path that escapes the package root. So
the freeze route cannot read a plan from outside R8.

That is not a defect in the plan and does not weaken the token. The token binds
the plan by the SHA-256 of its exact bytes. Those bytes are identical wherever
the file sits. A human who accepts this gate copies the plan file, unmodified,
to the path this plan declares in `plan_install_path`, and the freeze route
then finds it and computes the same digest the token names. Installing it is a
human act after the gate, which is where it belongs; §2 of the project rules
reserves the commit to the human.

Bindings that cannot live in `bound_artifacts`
----------------------------------------------
`freeze.assert_bound_artifacts_match_disk` requires every key of
`bound_artifacts` to be a relative path confined under the package root. The
attempt-5 verification artefacts and every attempt-5 tool sit outside R8 by
construction, so they cannot go there without moving them into R8, which is
forbidden. They are bound in `external_bound_artifacts` instead: same digests,
same completeness, validated by `validate_freeze_plan_attempt_2.py` rather than
by `freeze.assert_plan_matches_disk`.

The binding that matters most is not weakened by this. The token's third field
is the plan digest and its second is
`verification_result_sha256` -- the digest of the attempt-5
`VERIFICATION_RESULT.json`. `freeze.assert_token_binds_plan` checks both. A
token cannot authorise this package unless it names this verification.

Architecture otherwise follows attempt 1 exactly: same schema
`wpno.level1.freeze-plan/2`, same shape check in `automation.freeze`, same
token grammar, same refusal to issue a token itself. This script issues no
token. It prints the exact token the freeze route will demand.
"""

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
A5_ROOT = os.path.dirname(HERE)

ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
CLONE = os.path.join(A5_ROOT, "test_clone", "08.18.26_Level1_Audits_R8")

# Import the automation package from the CLONE, not from ROOT. The two are
# proved byte-identical in the attempt-5 inventory comparison. Importing from
# the clone means no import of R8 can leave a __pycache__ inside R8 even if the
# bytecode redirect were to fail. Every root passed to those functions is still
# ROOT: the plan describes the original package, not the copy.
sys.path.insert(0, CLONE)

from automation import freeze, hashing  # noqa: E402

ATTEMPT = 2
PLAN_DIR = os.path.join(A5_ROOT, "freeze_output",
                        "freeze_plan_attempt_%d" % ATTEMPT)
PLAN_NAME = "FREEZE_PLAN_R8_ATTEMPT_%d.json" % ATTEMPT
PLAN_PATH = os.path.join(PLAN_DIR, PLAN_NAME)

# Where a human must install this plan before the freeze route can read it.
PLAN_INSTALL_REL = os.path.join("build", "freeze_plan_attempt_%d" % ATTEMPT,
                                PLAN_NAME)

# The attempt-5 verification, outside R8.
CODEX_OUT = os.path.join(A5_ROOT, "codex_output")
VERIFICATION_RESULT = os.path.join(CODEX_OUT, "VERIFICATION_RESULT.json")
VERIFICATION_MANIFEST = os.path.join(CODEX_OUT, "VERIFICATION_MANIFEST.sha256")
VERIFICATION_NOTES = os.path.join(CODEX_OUT, "VERIFICATION_NOTES.md")

TOOL_INVENTORY = os.path.join(A5_ROOT, "TOOL_INVENTORY.json")

COVERAGE = "build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json"

# Attempt 1's builder, read as the derivation source for the bound list. Its
# stale constants are removed below and the removal is asserted, not assumed.
ATTEMPT_1_BUILDER_REL = os.path.join(
    "build", "freeze_plan_attempt_1", "build_r8_freeze_plan.py")
ATTEMPT_1_STALE_VERIFICATION_DIR = "verification_codex_final_pre_freeze_attempt_3"


def rel_sha(relative):
    path = os.path.join(ROOT, relative)
    if not os.path.isfile(path):
        raise SystemExit("bound artefact is absent: %s" % relative)
    if os.path.islink(path):
        raise SystemExit("bound artefact is a symlink: %s" % relative)
    if os.path.getsize(path) == 0:
        raise SystemExit("bound artefact is zero bytes: %s" % relative)
    return hashing.sha256_file(path)


def abs_sha(path):
    if not os.path.isfile(path):
        raise SystemExit("external bound artefact is absent: %s" % path)
    if os.path.islink(path):
        raise SystemExit("external bound artefact is a symlink: %s" % path)
    if os.path.getsize(path) == 0:
        raise SystemExit("external bound artefact is zero bytes: %s" % path)
    return hashing.sha256_file(path)


def bound_paths():
    """Everything inside R8 that the freeze binds.

    Derived from attempt 1's list rather than retyped, so a transcription slip
    cannot silently drop a binding. Three things are then removed and the
    removal is asserted:

      - the four files of `verification_codex_final_pre_freeze_attempt_3/`,
        whose manifest is superseded and which the human has ruled must not be
        relied on;
      - attempt 1's own builder self-reference, which is attempt 1's tool, not
        this attempt's.

    Nothing else is removed and nothing is added silently: the difference
    between the two lists is computed and recorded in the plan.
    """
    sys.path.insert(0, os.path.join(CLONE, "build", "freeze_plan_attempt_1"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_attempt1_builder",
        os.path.join(CLONE, ATTEMPT_1_BUILDER_REL))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    inherited = list(module.bound_paths())

    removed = [rel for rel in inherited
               if rel.split(os.sep)[0] == ATTEMPT_1_STALE_VERIFICATION_DIR
               or rel == ATTEMPT_1_BUILDER_REL]
    if len(removed) != 5:
        raise SystemExit(
            "expected to remove exactly 5 attempt-1 entries (4 stale "
            "verification files and the attempt-1 builder), removed %d: %r"
            % (len(removed), removed))
    if ATTEMPT_1_BUILDER_REL not in removed:
        raise SystemExit("attempt 1's builder self-reference was not found")

    kept = [rel for rel in inherited if rel not in set(removed)]
    if any(ATTEMPT_1_STALE_VERIFICATION_DIR in rel for rel in kept):
        raise SystemExit("a superseded attempt-3 path survived the removal")
    return kept, inherited, removed


def external_bound_artifacts():
    """Everything outside R8 that this plan binds, by role.

    `freeze.assert_bound_artifacts_match_disk` cannot hold these -- it confines
    every path under the package root. They are bound here with the same
    digests and validated separately.
    """
    with open(TOOL_INVENTORY, encoding="utf-8") as fh:
        inventory = json.load(fh)

    out = {}
    for row in inventory["tools"]:
        if row["PATH"].startswith(ROOT + os.sep):
            continue          # already covered by bound_artifacts
        out[row["PATH"]] = {"role": row["ROLE"], "sha256": row["SHA256"]}

    for role, path in (
            ("ATTEMPT5_VERIFICATION_RESULT", VERIFICATION_RESULT),
            ("ATTEMPT5_VERIFICATION_MANIFEST", VERIFICATION_MANIFEST),
            ("ATTEMPT5_VERIFICATION_NOTES", VERIFICATION_NOTES),
            ("ATTEMPT5_TOOL_INVENTORY", TOOL_INVENTORY),
            ("ATTEMPT5_INVENTORY_PRE",
             os.path.join(A5_ROOT, "original_inventory", "INVENTORY_PRE.json")),
            ("ATTEMPT5_INVENTORY_POST",
             os.path.join(A5_ROOT, "original_inventory",
                          "INVENTORY_POST.json")),
            ("ATTEMPT5_WRITE_ISOLATION_PROOF",
             os.path.join(A5_ROOT, "original_inventory",
                          "COMPARE_PRE_VS_POST.json")),
            ("ATTEMPT5_SANDBOX_PROBE_RECORD",
             os.path.join(A5_ROOT, "logs", "SANDBOX_PROBE_RECORD.json")),
            ("ATTEMPT4_PROCEDURAL_DEFECT_RECORD",
             os.path.join(A5_ROOT, "ATTEMPT_4_PROCEDURAL_DEFECTS.md")),
            ("THIS_BUILDER", os.path.abspath(__file__)),
    ):
        out[path] = {"role": role, "sha256": abs_sha(path)}
    return out


def token_generator_source():
    """The exact bytes of the token-generating function, not of its module."""
    import inspect
    source = inspect.getsource(freeze.token_for)
    return {
        "symbol": "automation.freeze.token_for",
        "source_bytes": len(source.encode("utf-8")),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }


def main():
    if not os.path.isfile(VERIFICATION_RESULT):
        raise SystemExit("no attempt-5 verification result at %s"
                         % VERIFICATION_RESULT)
    with open(VERIFICATION_RESULT, encoding="utf-8") as fh:
        verification = json.load(fh)
    status = verification.get("result") or verification.get("status")
    if status != "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL":
        raise SystemExit(
            "the attempt-5 verification did not pass: %r. A freeze plan is "
            "not created on a failed or partial verification." % (status,))
    if verification.get("overall_pass") is not True:
        raise SystemExit("overall_pass is not true")
    if verification.get("unresolved_findings"):
        raise SystemExit("unresolved findings are present: %r"
                         % verification["unresolved_findings"])
    if verification.get("r8_paths_written_during_attempt_5") != 0:
        raise SystemExit(
            "the verification does not report zero R8 paths written")

    # Write isolation must already be proved before a plan is built on it.
    proof_path = os.path.join(A5_ROOT, "original_inventory",
                              "COMPARE_PRE_VS_POST.json")
    with open(proof_path, encoding="utf-8") as fh:
        proof = json.load(fh)
    if not proof.get("EQUAL"):
        raise SystemExit("R8 changed during attempt 5: %s" % proof_path)

    kept, inherited, removed = bound_paths()

    baseline, provenance = freeze.build_baseline_from_predecessor(
        ROOT, rel_sha(freeze.PREDECESSOR_BASELINE_REL))
    baseline_text = freeze.serialize_baseline(baseline)

    def load(rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return json.load(fh)

    rehearsal = load("work/_rehearsal_r8/REHEARSAL_REPORT.json")
    safety = load("build/R8_STATIC_SAFETY_REPORT.json")
    coverage = load(COVERAGE)
    suites = load("build/R8_TEST_SUITE_RESULTS.json")["suites"]
    controls = load("build/CONTROL_EXPECTATION_COVERAGE.json")
    closure = load("build/R8_FINAL_PRE_FREEZE_CLOSURE.json")
    predecessors = load("lineage/R8_LINEAGE.json")
    migration_plan = load("build/migration_plan_r7_to_r8/MIGRATION_PLAN.json")

    live = closure["active_state"]
    if live["phase_states"] != {"NOT_STARTED": 43}:
        raise SystemExit("live phase state is not 43 NOT_STARTED: %s" % live)
    if live["approvals"] or live["results_files"] or live["evidence_files"]:
        raise SystemExit("live approval, result or evidence present: %s" % live)

    if migration_plan["applied_before_freeze"]:
        raise SystemExit("the migration packet was applied before the freeze")
    consumed_ledger = os.path.join(ROOT, "state", "migrations.jsonl")
    if os.path.exists(consumed_ledger) and os.path.getsize(consumed_ledger):
        raise SystemExit("a migration packet has already been consumed")

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
            "Second freeze attempt for R8. Attempt 1's plan and its token are "
            "superseded and unconsumed: the verification they rested on "
            "(attempt 4) passed every substantive check but wrote inside the "
            "package it was verifying, so its write isolation was never "
            "proved. This plan rests on attempt 5, which ran the same "
            "substantive checks against an untouched R8 under a "
            "kernel-enforced write barrier that was shown to refuse a write "
            "before it was relied on, ran everything that writes in a "
            "disposable byte-identical clone, and proved R8 unchanged across "
            "the whole attempt on every path, mode, uid, gid and mtime. R8 is "
            "the final revision; there is no R9."),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "r8_root": ROOT,

        "package_sha256": rel_sha("build/R8_BUILD_MANIFEST.sha256"),
        "verification_result_sha256": abs_sha(VERIFICATION_RESULT),
        "verification_manifest_sha256": abs_sha(VERIFICATION_MANIFEST),
        "verification_status": status,
        "verification_path": CODEX_OUT,
        "verification_attempt": 5,
        "verification_independence": (
            "a fresh Codex process with no build-session context and no "
            "resumed thread, in the same local workspace: a different model, "
            "a different harness and a different vendor from the session that "
            "built the package, on the same machine and reading the same "
            "disk. It is not an independent machine and does not claim to be. "
            "It ran under a workspace-write sandbox whose root excluded R8, "
            "so it could read the package and could not write it."),
        "verification_attempts": {
            "attempt_5": {"path": CODEX_OUT, "result": status},
        },
        "superseded_attempts": {
            "attempt_4": {
                "path": os.path.join(
                    ROOT, "verification_codex_final_pre_freeze_attempt_4"),
                "classification": ("SUBSTANTIVE_CHECKS_PASS_BUT_PROCEDURAL_"
                                   "WRITE_ISOLATION_NOT_PROVEN"),
                "token_consumed": False,
                "evidence_preserved": True,
            },
            "attempt_3": {
                "path": os.path.join(
                    ROOT, "verification_codex_final_pre_freeze_attempt_3"),
                "classification": "PASSED_AGAINST_A_SUPERSEDED_MANIFEST",
                "not_relied_on": True,
            },
        },

        "baseline_preview_sha256": hashing.sha256_text(baseline_text),
        "expected_project_baseline_count": provenance["project_members"],
        "expected_discovery_baseline_count": provenance["discovery_members"],
        "baseline_provenance": provenance,
        "predecessor_baseline_manifest_path": freeze.PREDECESSOR_BASELINE_REL,
        "predecessor_baseline_manifest_sha256":
            rel_sha(freeze.PREDECESSOR_BASELINE_REL),

        "bound_artifacts": {rel: rel_sha(rel) for rel in kept},
        "bound_artifacts_derivation": {
            "source": "attempt 1's bound_paths(), read from %s"
                      % ATTEMPT_1_BUILDER_REL,
            "source_sha256": rel_sha(ATTEMPT_1_BUILDER_REL),
            "inherited_count": len(inherited),
            "removed": sorted(removed),
            "removed_reason": (
                "the four files of the superseded attempt-3 verification "
                "directory, which the human has ruled must not be relied on, "
                "and attempt 1's own builder self-reference, which is "
                "attempt 1's tool and not this attempt's"),
            "kept_count": len(kept),
            "added_beyond_inherited": [],
        },
        "external_bound_artifacts": external_bound_artifacts(),
        "external_binding_rationale": (
            "freeze.assert_bound_artifacts_match_disk confines every "
            "bound_artifacts key under the package root, so artefacts that "
            "live outside R8 by construction cannot be held there without "
            "moving them into R8 -- which attempt 5 forbids. They are bound "
            "here with the same digests and are validated by "
            "validate_freeze_plan_attempt_2.py."),

        "plan_install_path": PLAN_INSTALL_REL,
        "plan_install_note": (
            "This plan was written outside R8 so that building it wrote "
            "nothing into the package. automation.controller.cmd_freeze_"
            "level1 resolves its plan with freeze.confined_path, which "
            "refuses an absolute path and refuses any path escaping the "
            "package root, so the freeze route can only read a plan from "
            "inside R8. A human who accepts this gate copies this file "
            "unmodified to plan_install_path. The token binds the plan by the "
            "SHA-256 of its bytes, which the copy does not change."),

        "plan_coverage": {
            "REQUIRED_PLAN_COUNT": coverage["REQUIRED_PLAN_COUNT"],
            "CANDIDATE_PLAN_COUNT": coverage["CANDIDATE_PLAN_COUNT"],
            "phase_totals_by_kind": coverage["phase_totals_by_kind"],
            "NEW_PLANS_BUILT": len(coverage["newly_built"]),
            "EXISTING_PLANS_REUSED": len(coverage["prebuilt_reused"]),
            "manifest": COVERAGE,
        },

        "exact_plan_rehearsal": {
            "phases_refreshed_this_run":
                rehearsal.get("phases_refreshed_this_run"),
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
            "not_rerun_by_attempt_5": (
                "the rehearsal was not re-run. Re-running it would have "
                "written into work/ inside R8. Attempt 5 read its report and "
                "re-derived its claims from the 43 plans instead."),
            "what_it_does_not_mean": (
                "PASS_READY is a statement about the plan and the harness. No "
                "live audit has run and no audit verdict exists."),
        },

        "tests": {
            "measured_not_declared": (
                "both figures are read from build/R8_TEST_SUITE_RESULTS.json "
                "and were re-measured by attempt 5 in a disposable clone."),
            "controller_suite": {k: suites["controller_suite"][k]
                                 for k in ("ran", "failures", "errors",
                                           "skips", "clean", "measurement")},
            "package_suite": {k: suites["package_suite"][k]
                              for k in ("ran", "failures", "errors", "skips",
                                        "clean", "measurement")},
            "static_safety_findings": safety["finding_count"],
            "static_safety_clean": safety["clean"],
            "unpermitted_changes": safety.get("unpermitted_changes", []),
            "predecessor_unchanged":
                safety["predecessor_unchanged"]["unchanged"],
            "where_attempt_5_ran_them": (
                "in test_clone/, proved byte-identical and "
                "metadata-identical to R8 before the run. The controller "
                "suite rewrites verification/selftest_runtime/work/_selftest/"
                "unicode_fs_behaviour.txt on every run; in attempt 4 that "
                "write landed inside R8. Here it landed in the clone, and "
                "that it landed at all is the control proving the "
                "zero-writes measurement was not blind."),
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
            "shared_executor_sha256":
                rel_sha("automation/in_process_executor.py"),
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
            "count_reconciliation_sha256":
                rel_sha("build/IN_PROCESS_COUNT_RECONCILIATION.json"),
        },

        "control_expectations": {
            "record": "build/CONTROL_EXPECTATION_COVERAGE.json",
            "record_sha256":
                rel_sha("build/CONTROL_EXPECTATION_COVERAGE.json"),
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

        "write_isolation": {
            "condition": "no attempt-5 operation writes into R8",
            "enforcement": ("codex workspace-write sandbox whose root is "
                            "ATTEMPT5_ROOT; R8 lies outside it and is "
                            "read-only to the verifier at kernel level"),
            "enforcement_proved_effective_before_use":
                "logs/SANDBOX_PROBE_RECORD.json",
            "detection": ("full pre/post inventory of every path under R8 -- "
                          "files and directories -- on size, sha256, mode, "
                          "uid, gid, symlink target and mtime_ns"),
            "inventory_entries": None,
            "r8_paths_written": 0,
            "package_modes_untouched": True,
            "note": ("attempt 4 removed the write bits of 723 manifest-"
                     "covered files and restored them. Mode is package "
                     "metadata and changing it is a write. Attempt 5 changed "
                     "no mode."),
        },

        "excluded_paths": {
            "from_the_build_manifest": [
                "__pycache__", "work/", "state/", "results/", "evidence/",
                "logs/", "build/R8_BUILD_MANIFEST.sha256 (itself)",
                "verification_codex_final_pre_freeze_attempt_*/",
                "build/freeze_plan_attempt_*/"],
            "why_the_last_two": (
                "both are created after the manifest is generated. Attempt "
                "1 bound its own directory's files by digest instead. "
                "Attempt 5 writes neither into the package: its verification "
                "output and its freeze plan both live outside R8 and are "
                "bound in external_bound_artifacts."),
            "rule": ("matched on a path component, so "
                     "verification_codex_pre_freeze/ and "
                     "build/notes_about_freeze_plan_attempt_1.md are not "
                     "caught"),
        },

        "replay_protection": {
            "attempt_number": ATTEMPT,
            "attempts_consumed": len(consumed),
            "ledger_path": "state/freeze_attempts.jsonl",
            "attempt_1_token_consumed": False,
            "attempt_1_token_may_authorize": False,
            "prior_r4_token_may_authorize": False,
            "prior_r5_token_may_authorize": False,
            "prior_r6_token_may_authorize": False,
            "semantics": "RUN-ONCE",
        },

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

        "token_generator": token_generator_source(),
        "final_revision": True,
        "successor_permitted": False,
        "successor_absent_on_disk": True,
        "token_grammar": ("FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> "
                          "VERIFICATION-SHA256=<64hex> "
                          "FREEZE-PLAN-SHA256=<64hex> RUN-ONCE"),
    }

    with open(os.path.join(A5_ROOT, "original_inventory",
                           "INVENTORY_PRE.json"), encoding="utf-8") as fh:
        plan["write_isolation"]["inventory_entries"] = \
            json.load(fh)["entry_count"]

    freeze.assert_package_plan_shape(plan)

    os.makedirs(PLAN_DIR, exist_ok=True)
    raw = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    # Deliberately not routed through path_policy.assert_writable; see the
    # module docstring. The target is outside the package on purpose.
    with open(PLAN_PATH, "w", encoding="utf-8") as fh:
        fh.write(raw)

    plan_sha = hashing.sha256_text(raw)

    # The plan must describe the package as it is now. Checked here against
    # ROOT, and checked again by the freeze route before it writes a byte.
    freeze.assert_plan_matches_disk(plan, ROOT)

    token = freeze.token_for(plan["package_sha256"],
                             plan["verification_result_sha256"], plan_sha)

    print(json.dumps({
        "freeze_plan_path": PLAN_PATH,
        "freeze_plan_install_path": PLAN_INSTALL_REL,
        "freeze_plan_sha256": plan_sha,
        "attempt_number": ATTEMPT,
        "package_sha256": plan["package_sha256"],
        "verification_result_sha256": plan["verification_result_sha256"],
        "verification_manifest_sha256": plan["verification_manifest_sha256"],
        "bound_artifacts": len(plan["bound_artifacts"]),
        "external_bound_artifacts": len(plan["external_bound_artifacts"]),
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
