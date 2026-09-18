# Independent pre-freeze verification of R8 — attempt 5 (write-isolated, final)

You are an independent verifier. Measure; do not trust this prompt's numbers.
Check every claim against bytes on disk. Where a claim and the bytes disagree,
the bytes win and it is a finding.

## What this attempt is

Attempt 4's substantive checks passed. Attempt 4 was nevertheless superseded on
procedure: it wrote inside the package it was verifying. It removed and
restored the write bits of 723 manifest-covered files, and the controller
suite reopened and rewrote

    verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt

The final bytes matched, so the manifest still verified. Matching final bytes
is not the claim "no write occurred". Attempt 5 exists to make that second
claim true and provable.

Attempt 4 is NOT evidence for you. Its outputs may be read for comparison
only. Re-measure everything yourself. If your measurement differs from
attempt 4's, yours is the one that counts and the difference is a finding
worth stating.

This is VERIFICATION ONLY. You may not repair, edit, delete, move, rename,
regenerate or reformat anything in R8, and you may not change any test. If you
find ANY defect, inconsistency, missing evidence, package mutation, manifest
mismatch, test failure, unenforced control, or defect in the verification
itself: STOP, record it, and finish. Do not repair it, do not work around it,
do not re-run to see whether it clears.

## The two roots, and which one each check uses

    ORIGINAL = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8
    CLONE    = /home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/test_clone/08.18.26_Level1_Audits_R8
    OUT      = /home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/codex_output

ORIGINAL is the package being frozen. It is READ-ONLY to you. It is not
read-only by permission bits — nothing has touched its modes — it is read-only
because the sandbox you run under denies every write outside your workspace
root. Do not try to route around that. If a write outside OUT is refused,
record it as a finding; do not retry it another way.

CLONE was produced with `cp -a` before you started and was proved
byte-identical and metadata-identical to ORIGINAL: same 1362 paths, same 961
file contents, same modes, same uid/gid, same mtimes to the nanosecond, zero
differences. Confirm that record yourself at
`/home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/original_inventory/COMPARE_ORIGINAL_VS_CLONE_INITIAL.json`.
Because the two were identical when the clone was made, a measurement taken in
CLONE is a measurement of ORIGINAL's bytes at that moment.

**Every check that only reads runs against ORIGINAL.**

**Every check that writes runs in CLONE.** There are exactly three, and they
are named in items 18, 19 and 20. You must not attempt them against ORIGINAL.
Item 20's script refuses an `--out-dir` outside its own package by design, so
running it against ORIGINAL would necessarily write into ORIGINAL; run it in
CLONE.

State, for every item, which root you measured.

## Hard rules

- Write ONLY inside OUT. Nothing anywhere else except CLONE, which is
  disposable and may receive test-generated output.
- No network. No git. No installation. No package repair. No live audit phase.
  Do not apply the migration. Do not freeze. Do not create a token. Do not
  create `08.18.26_Level1_Audits_R9`.
- `/usr/bin/python3` for everything. `PYTHONDONTWRITEBYTECODE=1` is already
  exported and `PYTHONPYCACHEPREFIX`, `TMPDIR`, `TEMP`, `TMP`, `PYTEST_ADDOPTS`
  and `COVERAGE_FILE` are already redirected out of both packages. Do not
  unset them. No `.pyc` inside either root.
- Run the suites with `python -m unittest` directly. Do NOT use
  `build/run_test_suites.py`; it writes into `build/`.
- Do not modify anything in R4, R5, R6 or R7. Read them only.

## Predecessor roots

    R7 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7
    R6 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6
    R5 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    R4 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4

## The manifest this attempt verifies

    6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a

with 724 entries. Confirm that digest and that count yourself before you begin.
An earlier manifest `796fd130…` is SUPERSEDED; attempt 3 passed against it and
its result is therefore not evidence about the current bytes.

## Where things actually live — read this before writing a check

Structural facts, given so your checks address the right bytes. The values are
still yours to measure.

- Phase state is in `state/progress.json`, under
  `audits[<AUDIT>][<PHASE>]["state"]`. There is no `state/phase_status.json`.
- Transition records are in `state/transitions.jsonl`. Each row has a `route`
  key. There is no `event` key.
- A step's expectation lives in the plan's `test_matrix`, in the entry whose
  `step_id` equals the step's. The vocabulary is wider than exit codes:
  `expected_exit_code`, `expected_status`, `expected_count`,
  `expected_minimum_count`, `expected_hash_relation`, `expected_boolean`,
  `expected_difference_count`, `expected_failure_reason_canonical`,
  `expected_parse_result`, `expected_validation_result`. The authoritative list
  is `automation.in_process_executor.EXPECTATION_KEYS` and
  `expectation_keys_present(entry)` is the function that reads it. Use them.
- R8's predecessor disclosure is nested under the `r7` key of
  `lineage/R8_LINEAGE.json`, not at the top level.
- R4 predates `state/REVISION.json` and is reachable as `lineage/R4_EXECUTION`
  inside R5. `automation.package_tests.generation_root` handles this; use it
  rather than reimplementing the walk.
- Importing R8's `automation` package requires its root on `sys.path`. Import
  from CLONE when you need to import, so no `__pycache__` can land in
  ORIGINAL even if the bytecode redirect were to fail. The two trees'
  `automation/` are byte-identical, and you are re-proving that in item 32.

## Verify these thirty-four items

Items 1 to 31 are attempt 4's, re-measured. Items 32 to 34 are new and are
what attempt 4 could not show.

1.  R4's `CONTROL_MANIFEST.sha256` verifies with 0 mismatching.
2.  R5's control manifest has exactly ONE mismatching entry and it is `MODE`.
    More than one, or a different path, is a finding.
3.  R6's control manifest verifies with 0 mismatching.
4.  R7's control manifest verifies: 15804 entries, 0 mismatching.
5.  R8 carries R7's post-freeze incident record under
    `lineage/R7_POST_FREEZE_INCIDENT/`; its `INCIDENT_MANIFEST.sha256`
    verifies; and `lineage/R8_LINEAGE.json` has
    `r7.continuous_post_freeze_immutability == false` and
    `r7.current_bytes_restored_to_frozen_manifest == true`. R8 must nowhere
    claim R7 was continuously immutable after its freeze.
6.  R8 contains no directory `lineage/R6_EXECUTION` and no full copy of any
    predecessor package, and `generation_root` resolves all of R4, R5, R6, R7
    and R8.
7.  No active R8 file shares an inode with an active R7 file.
8.  `in_process_executor.execute` is called from BOTH `automation/controller.py`
    and `build/rehearse_candidate_plans.py`.
9.  No LIVE code path writes a note instead of performing an in-process
    operation.

    Find every occurrence of the string "performed by the worker" in every
    `.py` under R8, then classify each. An occurrence is NOT a finding when:

      - it is inside a docstring or comment that quotes the defect
        (`automation/in_process_ops.py`, `automation/in_process_executor.py`,
        `automation/controller.py`); or
      - any path SEGMENT of the file is `fixtures` or `lineage`, at any depth.
        Use a segment test, not a prefix test: the self-test replica duplicates
        the package, so the same fixture appears both at
        `automation/tests/fixtures/...` and at
        `verification/selftest_runtime/automation/tests/fixtures/...`. For any
        file excluded by this rule, show it is inert rather than assuming it:
        confirm no module imports it, and that it is referenced only as a
        directory of read-only fixture data; or
      - it is in `automation/migration.py`, where the string is the value a
        guard refuses, or in `automation/package_tests/test_r8_migration.py`,
        where that guard is tested.

    A finding is an executable statement on a live controller or rehearsal path
    that assigns that note as a step's outcome instead of performing the
    operation. Report your classification of every occurrence found.
10. Every operation in `operation_catalog.IN_PROCESS` has a handler in
    `in_process_ops.HANDLERS` and a schema in
    `in_process_executor.ARGUMENT_SCHEMA`; the three sets are equal.
11. L1-A16's novelty measurement and its controls. Passes when a, b and c hold.

    a. In `build/candidate_plans_r8/L1-A16/RUN-A/plan.json`, step
       `prove_cases_are_novel` has operation `PROVE_SET_NOVELTY`,
       `reference_root` `/home/ubuntu/project/WPNO/ap18/korpus_docx` (not
       `ap18`), and `expected_reference_entry_count` 7.
    b. That plan has exactly three FURTHER steps whose operation is
       `PROVE_SET_NOVELTY` and whose `control_role` is POSITIVE or NEGATIVE.
    c. In `work/_rehearsal_r8/REHEARSAL_REPORT.json`, every step of
       L1-A16/RUN-A whose operation is `PROVE_SET_NOVELTY` has `status`
       EXECUTED and `expectation_result` AS_EXPECTED. There are FOUR such
       steps: the measurement from (a) and the three controls from (b). Four
       AS_EXPECTED results is the expected outcome, not an excess.
12. In all 43 plans: no `COMPARE_HASHES` step has `left == right` without an
    `expected_sha256`; and no rehearsal step recorded a non-empty
    `reads_outside_declared_allowance`. Report the count of steps carrying that
    key and the count that were non-empty.
13. L1-A21 `negative_control_export_is_not_another_project` uses
    `COUNT_TEXT_MATCHES`, `word_boundary` true, expected count 0.
14. `references/REF-11-563203462.xml` still begins `MIME-Version:` and has the
    same sha256 as R7's copy; L1-A33 extracts the part into `work/` and parses
    the extraction, not the reference.
15. Every control-role step (POSITIVE/NEGATIVE/MUTATION/ORACLE/SABOTAGE) in all
    43 plans carries at least one expectation from `EXPECTATION_KEYS`.
    Re-derive the count and the unenforced list yourself and compare with
    `build/CONTROL_EXPECTATION_COVERAGE.json`. Report both your count and the
    record's.
16. `build/migration_plan_r7_to_r8/MIGRATION_PLAN.json`: `migratable_attempts`
    is exactly L1-A31 RUN-A and RUN-B; `excluded_attempts` is exactly L1-A31
    COMPARISON with reason
    `EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`;
    `applied_before_freeze` is false; and its `route_module_sha256` equals the
    digest of `automation/migration.py`.
17. In R7, L1-A31 COMPARISON is EXECUTED, has no SEAL.json, and has zero
    evidence files.
18. **CLONE.** Controller suite passes with 0 failures, 0 errors, 0 skips. Run
    `/usr/bin/python3 -B -m unittest discover -s . -t .` inside
    `CLONE/verification/selftest_runtime`. Report the number of tests run.
19. **CLONE.** Package suite passes with 0 failures, 0 errors, 0 skips. Run
    `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .`
    at the CLONE root. Report the number of tests run.
20. **CLONE.** Static safety reports 0 findings and `clean` true. Run
    `/usr/bin/python3 -B build/r8_static_safety_review.py --out-dir
     <CLONE>/build/_attempt5_static` from the CLONE root, then copy the two
    output files into OUT. The script refuses an out-dir outside its own
    package; that refusal is by design and is why this item runs in CLONE.
21. 43/43 plans exist and the coverage manifest reports 0 missing, 0 duplicate,
    0 unknown.
22. `work/_rehearsal_r8/REHEARSAL_REPORT.json` reports 43 of 43 phases
    PASS_READY.
23. That report has `REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` 0 and
    `NOTE_ONLY_IN_PROCESS_STEPS` 0, and
    `IN_PROCESS_HANDLER_INVOCATIONS == IN_PROCESS_STEP_COUNT`. Report both
    numbers.
24. That report has `HOLLOW_PHASES` empty and `LIVE_STATE_UNCHANGED` true.
25. `state/progress.json` holds 35 audits and 43 phase records, and every one is
    `NOT_STARTED`.
26. `state/approvals.jsonl` is empty; `results/` and `evidence/` contain zero
    files; and no approval token text (`APPROVE-EXECUTION`, `RUN-ONCE`) appears
    anywhere under `state/`.
27. `build/R8_BUILD_MANIFEST.sha256` verifies: every entry present and
    matching, no duplicates, no malformed lines, and the set of listed paths
    equals the set of physical files for which the builder's own `in_scope`
    returns true.
28. `automation/freeze.py` has `PACKAGE_REVISION` "R8", its
    `PREDECESSOR_BASELINE_REL` resolves to a file inside R8 whose digest equals
    `lineage/R8_LINEAGE.json`'s `r7.baseline_manifest_sha256`, and
    `freeze.build_baseline_from_predecessor(R8)` returns without raising.
    Import from CLONE and pass CLONE as the root; the two are proved identical.
29. No `08.18.26_Level1_Audits_R9` exists beside the package.
30. `state/transitions.jsonl` contains exactly one row and its `route` is
    `init-revision`.
31. Nothing you did changed ORIGINAL. Before your first measurement and after
    your last, compute the SHA-256 of every file under ORIGINAL whose path the
    build manifest names, fold those 724 digests into one digest, and compare
    the two. They must be identical. Report both. If they differ, name every
    path that changed; that is a VERIFICATION_FAIL and you must not attempt to
    restore anything.

32. **Write isolation, stated as a metadata claim and not only a byte claim.**
    Before your first measurement and after your last, record for EVERY path
    under ORIGINAL — all 1362, not only the 724 the manifest covers, and
    directories as well as files — its size, mode, uid, gid, symlink target and
    mtime in nanoseconds. Compare the two records. Report, as measured
    integers:

        R8 paths written              (expect 0)
        R8 mtimes changed             (expect 0)
        R8 modes changed              (expect 0)
        R8 symlink targets changed    (expect 0)
        R8 contents changed           (expect 0)
        R8 paths added                (expect 0)
        R8 paths removed              (expect 0)

    Exempt nothing. In particular do not exempt
    `verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt`,
    the file attempt 4 allowed to be rewritten. Its mtime must be unchanged,
    not merely its bytes.

    `/home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/tools/inventory_r8.py` and
    `/home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/tools/compare_inventories.py` exist and do this. You may
    use them, and if you do you must first read both and satisfy yourself they
    measure what this item says. You may write your own instead. Either way
    say which you did, and hash what you ran.

33. **The rewrite attempt 4 tolerated is real, and the clone catches it.**
    In CLONE, after item 18 has run, compare
    `verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt`
    against the same path in ORIGINAL. Report its CLONE mtime before and after
    the suite, and whether the bytes match ORIGINAL.

    This is the control for item 32. If that file's mtime in CLONE did NOT move
    when the suite ran, then the suite did not do the thing attempt 4 recorded,
    and item 32's zero would be measuring nothing. A zero that cannot
    distinguish "no write happened" from "the instrument is blind" is not a
    pass. State plainly which of the two you observed.

34. **Every verification and freeze tool is identified and hashed by role.**
    Read `/home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/TOOL_INVENTORY.json`. For every row confirm the file
    exists and its SHA-256 matches. Confirm the inventory distinguishes:

      - the verification INSTRUCTIONS (this file);
      - the verification RUNNER (the script that launched you);
      - each verifier HELPER;
      - the freeze-plan BUILDER;
      - the plan RUNNER or wrapper, or an explicit NOT_USED;
      - `automation/freeze.py`;
      - the exact token-generation function source;
      - every executable used to validate the freeze plan.

    `VERIFICATION_RESULT.json` is the RESULT of a verification and is not a
    verifier. If the inventory labels it as one, that is a finding. If any tool
    named there cannot be identified, or any row's digest does not match, stop
    with `VERIFICATION_FAIL_UNIDENTIFIED_TOOL`.

## Output

Write `OUT/VERIFICATION_RESULT.json`:

```json
{
  "schema": "wpno.level1.codex-verification/1",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL",
  "attempt": 5,
  "verified_utc": "<UTC>",
  "items": [
    {"id": 1, "root": "ORIGINAL", "claim": "...", "measured": "...",
     "pass": true}
  ],
  "manifest_sha256_verified": "<the 64-hex digest you measured>",
  "manifest_entries_verified": 724,
  "package_unchanged_by_this_verification": true,
  "r8_paths_written_during_attempt_5": 0,
  "write_isolation_instrument_proven_live": true,
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when all 34 items pass
and `unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`, with every finding stated.

`write_isolation_instrument_proven_live` is true only if item 33 showed the
clone's copy of that file actually moved. If it did not move, item 32's zero is
not evidence and you say so.

Also write `OUT/VERIFICATION_NOTES.md` describing what you actually ran:
the commands, which root each ran against, and what you read versus inferred.

Also write `OUT/VERIFICATION_MANIFEST.sha256` — a plain `sha256  path` listing
of every file you wrote into OUT, excluding that manifest itself.

Do not mark an item passing on the strength of this prompt. If you did not
measure it, mark it `"pass": false` and say so.
