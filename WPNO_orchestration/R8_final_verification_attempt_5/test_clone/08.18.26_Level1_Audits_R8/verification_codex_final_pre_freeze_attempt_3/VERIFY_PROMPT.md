# Independent pre-freeze verification of R8 — attempt 3

You are an independent verifier. Measure; do not trust this prompt's numbers.
Check every claim against bytes on disk. Where a claim and the bytes disagree,
the bytes win and it is a finding.

## Why there is an attempt 3

Attempt 1 ran the suites and the static-safety review with their default
outputs, which write into `build/`, and then correctly reported the manifest
mismatch it had caused itself. That was a real process finding and it is
fixed: the review now takes `--out-dir`, and the rules below keep every write
inside your own directory.

Attempt 2 passed 28 of 30. Both remaining failures were in the shape of its
own checks rather than in the package, and both items are restated below so
that attempt 3 measures what the item is about:

  * item 9 excluded `automation/tests/fixtures/`, but the self-test replica
    duplicates the package, so the same fixture also sits under
    `verification/selftest_runtime/automation/tests/fixtures/` and the
    exclusion missed it. The rule is now a path-SEGMENT rule.
  * item 11 measured every value correctly -- the operation, the corpus, the
    entry count, four steps all AS_EXPECTED -- and still recorded a failure.
    What it should compare is now stated explicitly.

Attempts 1 and 2 are preserved beside this one. Do not assume either was
right: re-measure everything yourself.

## Hard rules — output confinement

- Write ONLY inside `verification_codex_final_pre_freeze_attempt_3/`.
- Run the test suites with `python -m unittest` directly (writes nothing), NOT
  with `build/run_test_suites.py` (which writes into `build/`).
- Run static safety as:
  `/usr/bin/python3 -B build/r8_static_safety_review.py --out-dir
   verification_codex_final_pre_freeze_attempt_3/static`
- Do not modify any file elsewhere in R8, or anything in R4/R5/R6/R7.
- No network. No git. Do not apply the migration. Do not freeze. Do not run a
  live audit phase. Do not create `..._R9`.
- `/usr/bin/python3`, `PYTHONDONTWRITEBYTECODE=1`, no `.pyc`.
- If you cause a write outside your directory anyway, say so plainly and
  record it as a finding. Do not attempt to revert it.

## Roots

    R8 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8   (you are here)
    R7 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7
    R6 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6
    R5 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    R4 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4

## Where things actually live — read this before writing a check

These are structural facts about this package. They are given so your checks
address the right bytes; the values are still yours to measure.

- Phase state is in `state/progress.json`, under `audits[<AUDIT>][<PHASE>]
  ["state"]`. There is no `state/phase_status.json`.
- Transition records are in `state/transitions.jsonl`. Each row has a `route`
  key. There is no `event` key.
- A step's expectation lives in the plan's `test_matrix`, in the entry whose
  `step_id` equals the step's. The vocabulary is wider than exit codes:
  `expected_exit_code`, `expected_status`, `expected_count`,
  `expected_minimum_count`, `expected_hash_relation`, `expected_boolean`,
  `expected_difference_count`, `expected_failure_reason_canonical`,
  `expected_parse_result`, `expected_validation_result`. The authoritative
  list is `automation.in_process_executor.EXPECTATION_KEYS`, and
  `expectation_keys_present(entry)` is the function that reads it. Use them.
- R8's predecessor disclosure is nested under the `r7` key of
  `lineage/R8_LINEAGE.json`, not at the top level.
- R4 predates `state/REVISION.json` and is reachable as
  `lineage/R4_EXECUTION` inside R5. `automation.package_tests.generation_root`
  handles this; use it rather than reimplementing the walk.

## Verify these thirty items

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
8.  `in_process_executor.execute` is called from BOTH
    `automation/controller.py` and `build/rehearse_candidate_plans.py`.
9.  No LIVE code path writes a note instead of performing an in-process
    operation.

    Find every occurrence of the string "performed by the worker" in every
    `.py` under R8, then classify each. An occurrence is NOT a finding when:

      - it is inside a docstring or comment that quotes the defect
        (`automation/in_process_ops.py`, `automation/in_process_executor.py`,
        `automation/controller.py`); or
      - any path SEGMENT of the file is `fixtures` or `lineage`, at any
        depth. Use a segment test, not a prefix test: the self-test replica
        duplicates the package, so the same fixture appears both at
        `automation/tests/fixtures/...` and at
        `verification/selftest_runtime/automation/tests/fixtures/...`.
        For any file excluded by this rule, show it is inert rather than
        assuming it: confirm no module imports it, and that it is referenced
        only as a directory of read-only fixture data; or
      - it is in `automation/migration.py`, where the string is the value a
        guard refuses, or in `automation/package_tests/test_r8_migration.py`,
        where that guard is tested.

    A finding is an executable statement on a live controller or rehearsal
    path that assigns that note as a step's outcome instead of performing the
    operation. Report your classification of every occurrence found.
10. Every operation in `operation_catalog.IN_PROCESS` has a handler in
    `in_process_ops.HANDLERS` and a schema in
    `in_process_executor.ARGUMENT_SCHEMA`; the three sets are equal.
11. L1-A16's novelty measurement and its controls. The item passes when a,
    b and c all hold.

    a. In `build/candidate_plans_r8/L1-A16/RUN-A/plan.json`, step
       `prove_cases_are_novel` has operation `PROVE_SET_NOVELTY`,
       `reference_root` `/home/ubuntu/project/WPNO/ap18/korpus_docx` (not
       `ap18`), and `expected_reference_entry_count` 7.
    b. That plan has exactly three FURTHER steps whose operation is
       `PROVE_SET_NOVELTY` and whose `control_role` is POSITIVE or NEGATIVE.
    c. In `work/_rehearsal_r8/REHEARSAL_REPORT.json`, every step of
       L1-A16/RUN-A whose operation is `PROVE_SET_NOVELTY` has `status`
       EXECUTED and `expectation_result` AS_EXPECTED. There are FOUR such
       steps: the measurement from (a) and the three controls from (b).
       Four AS_EXPECTED results is the expected outcome, not an excess.
12. In all 43 plans: no `COMPARE_HASHES` step has `left == right` without an
    `expected_sha256`; and no rehearsal step recorded a non-empty
    `reads_outside_declared_allowance`.
13. L1-A21 `negative_control_export_is_not_another_project` uses
    `COUNT_TEXT_MATCHES`, `word_boundary` true, expected count 0.
14. `references/REF-11-563203462.xml` still begins `MIME-Version:` and has the
    same sha256 as R7's copy; L1-A33 extracts the part into `work/` and parses
    the extraction, not the reference.
15. Every control-role step (POSITIVE/NEGATIVE/MUTATION/ORACLE/SABOTAGE) in
    all 43 plans carries at least one expectation from `EXPECTATION_KEYS`.
    Re-derive the count and the unenforced list yourself and compare with
    `build/CONTROL_EXPECTATION_COVERAGE.json`.
16. `build/migration_plan_r7_to_r8/MIGRATION_PLAN.json`: `migratable_attempts`
    is exactly L1-A31 RUN-A and RUN-B; `excluded_attempts` is exactly L1-A31
    COMPARISON with reason
    `EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`;
    `applied_before_freeze` is false; and its `route_module_sha256` equals the
    digest of `automation/migration.py`.
17. In R7, L1-A31 COMPARISON is EXECUTED, has no SEAL.json, and has zero
    evidence files.
18. Controller suite passes with 0 failures, 0 errors, 0 skips. Run
    `/usr/bin/python3 -B -m unittest discover -s . -t .` inside
    `verification/selftest_runtime`.
19. Package suite passes with 0 failures, 0 errors, 0 skips. Run
    `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .`
    at the R8 root.
20. Static safety reports 0 findings and `clean` true, run with `--out-dir`
    into your directory as specified above.
21. 43/43 plans exist and the coverage manifest reports 0 missing, 0
    duplicate, 0 unknown.
22. `work/_rehearsal_r8/REHEARSAL_REPORT.json` reports 43 of 43 phases
    PASS_READY.
23. That report has `REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` 0 and
    `NOTE_ONLY_IN_PROCESS_STEPS` 0, and
    `IN_PROCESS_HANDLER_INVOCATIONS == IN_PROCESS_STEP_COUNT`.
24. That report has `HOLLOW_PHASES` empty and `LIVE_STATE_UNCHANGED` true.
25. `state/progress.json` holds 35 audits and 43 phase records, and every one
    is `NOT_STARTED`.
26. `state/approvals.jsonl` is empty; `results/` and `evidence/` contain zero
    files; and no approval token text (`APPROVE-EXECUTION`, `RUN-ONCE`)
    appears anywhere under `state/`.
27. `build/R8_BUILD_MANIFEST.sha256` verifies: every entry present and
    matching, no duplicates, no malformed lines, and the set of listed paths
    equals the set of physical files for which the builder's own `in_scope`
    returns true.
28. `automation/freeze.py` has `PACKAGE_REVISION` "R8", its
    `PREDECESSOR_BASELINE_REL` resolves to a file inside R8 whose digest
    equals `lineage/R8_LINEAGE.json`'s `r7.baseline_manifest_sha256`, and
    `freeze.build_baseline_from_predecessor(R8)` returns without raising.
29. No `08.18.26_Level1_Audits_R9` exists beside the package.
30. `state/transitions.jsonl` contains exactly one row and its `route` is
    `init-revision`.

## Output

Write `verification_codex_final_pre_freeze_attempt_3/VERIFICATION_RESULT.json`:

```json
{
  "schema": "wpno.level1.codex-verification/1",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL",
  "verified_utc": "<UTC>",
  "items": [{"id": 1, "claim": "...", "measured": "...", "pass": true}],
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when all 30 pass and
`unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`, with every finding stated.

Also write `VERIFICATION_NOTES.md` describing what you actually ran.

Do not mark an item passing on the strength of this prompt. If you did not
measure it, mark it `"pass": false` and say so.
