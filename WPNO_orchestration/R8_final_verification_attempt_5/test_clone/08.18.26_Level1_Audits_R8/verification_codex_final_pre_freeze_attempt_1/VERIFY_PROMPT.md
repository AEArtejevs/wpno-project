# Independent pre-freeze verification of R8

You are an independent verifier. Measure; do not trust this prompt's numbers.
Every claim below must be checked against bytes on disk. Where a claim and the
bytes disagree, the bytes win and it is a finding.

## Hard rules

- Write ONLY inside `verification_codex_final_pre_freeze_attempt_1/`.
- Do not modify any file anywhere else, in R8 or in R4/R5/R6/R7.
- No network. No git. Do not copy the package. Do not apply the migration.
- Do not execute any live audit phase. Do not freeze anything.
- Do not create a directory named `..._R9`.
- Use `/usr/bin/python3`. Set `PYTHONDONTWRITEBYTECODE=1`. Create no `.pyc`.

## Roots

    R8 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8   (you are here)
    R7 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7
    R6 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6
    R5 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    R4 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4

## Verify these thirty items

1.  R4 `CONTROL_MANIFEST.sha256` verifies with 0 mismatching.
2.  R5's control manifest has exactly ONE mismatching entry and it is `MODE`
    (recorded digest is that of `GENERATED_UNVERIFIED`, on-disk reads
    `FROZEN`). More than one mismatch, or a different path, is a finding.
3.  R6's control manifest verifies with 0 mismatching.
4.  R7's control manifest verifies: 15804 entries, 0 mismatching.
5.  R8 discloses R7's post-freeze modification incident and does NOT claim R7
    had continuous post-freeze immutability. See `lineage/R8_LINEAGE.json` and
    `lineage/R7_POST_FREEZE_INCIDENT/`. Verify that incident manifest.
6.  R8's lineage is compact: R8 contains no directory `lineage/R6_EXECUTION`
    and no full copy of a predecessor package, yet the chain R4→R5→R6→R7→R8
    is resolvable. `automation/package_tests/__init__.py` has the resolver.
7.  No active R8 file shares an inode with an active R7 file (compare
    `st_ino`/`st_dev` for files present in both trees by relative path).
8.  There is ONE in-process executor and both the live controller and the
    rehearsal harness call it. Grep for `in_process_executor.execute` in
    `automation/controller.py` and `build/rehearse_candidate_plans.py`.
9.  No live code path still writes a note instead of performing an in-process
    operation. Occurrences of "performed by the worker" outside docstrings,
    outside `lineage/`, and outside `automation/tests/fixtures/` are findings.
10. Every operation in `operation_catalog.IN_PROCESS` has a handler in
    `automation/in_process_ops.HANDLERS` and a schema in
    `in_process_executor.ARGUMENT_SCHEMA`. `in_process_executor.self_check()`
    reports it; verify the three sets independently as well.
11. L1-A16 repair: `build/candidate_plans_r8/L1-A16/RUN-A/plan.json` step
    `prove_cases_are_novel` uses `PROVE_SET_NOVELTY` against
    `/home/ubuntu/project/WPNO/ap18/korpus_docx` (7 entries), NOT against
    `ap18`, and NOT `COMPARE_HASHES` on two directories. Three novelty
    controls exist and all executed in the rehearsal with AS_EXPECTED.
12. Every finding recorded in
    `/home/ubuntu/project/WPNO_orchestration/R8_in_process_execution_repair/R8_STATUS_AND_FINDINGS.md`
    is resolved: no `COMPARE_HASHES` step in any of the 43 plans has
    `left == right` WITHOUT an `expected_sha256`; no step reads outside its
    plan's declared `allowed_reads`.
13. L1-A21: step `negative_control_export_is_not_another_project` uses
    `COUNT_TEXT_MATCHES` with `word_boundary` true and expects count 0.
14. L1-A33: `references/REF-11-563203462.xml` still begins with
    `MIME-Version:` and its sha256 is unchanged from R7's copy; the plan
    extracts the part into `work/` and parses the extraction.
15. Every control-role step (POSITIVE/NEGATIVE/MUTATION/ORACLE/SABOTAGE) in
    all 43 plans carries at least one machine-checkable expectation.
    `build/CONTROL_EXPECTATION_COVERAGE.json` claims 122/122 and 0
    unenforced; re-derive both from the plans.
16. Migration: `build/migration_plan_r7_to_r8/MIGRATION_PLAN.json` lists
    exactly L1-A31 RUN-A and RUN-B as migratable, excludes L1-A31 COMPARISON
    with reason EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT, and
    records `applied_before_freeze: false`.
17. R7's L1-A31 COMPARISON is genuinely EXECUTED, unsealed, with zero evidence
    files. Measure it in R7.
18. Controller suite passes. Run it in `verification/selftest_runtime`.
19. Package suite passes. Run it at the R8 root.
20. `build/r8_static_safety_review.py` reports 0 findings.
21. 43/43 plans exist, schema-valid, no missing/duplicate/unknown.
22. 43/43 rehearsals PASS_READY in `work/_rehearsal_r8/REHEARSAL_REPORT.json`.
23. No required in-process step lacks evidence
    (`REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` is 0) and
    `NOTE_ONLY_IN_PROCESS_STEPS` is 0.
24. No phase produced zero evidence (`HOLLOW_PHASES` is empty).
25. R8 active state is 43/43 NOT_STARTED across 35 audits.
26. R8 has 0 approvals, 0 files under `results/`, 0 files under `evidence/`,
    and no raw approval token anywhere in `state/`.
27. `build/R8_BUILD_MANIFEST.sha256` verifies: every entry present and
    matching; no duplicates; no malformed lines; and every in-scope physical
    file is listed (the builder's own `in_scope` defines scope).
28. The freeze mechanism is self-consistent: `automation/freeze.py`
    `PACKAGE_REVISION` is R8, its `PREDECESSOR_BASELINE_REL` resolves inside
    R8, and `freeze.build_baseline_from_predecessor` runs.
29. No `08.18.26_Level1_Audits_R9` exists beside the package.
30. No live R8 phase has been executed: `state/transitions.jsonl` contains
    only the `init-revision` transition.

## Output

Write `verification_codex_final_pre_freeze_attempt_1/VERIFICATION_RESULT.json`:

```json
{
  "schema": "wpno.level1.codex-verification/1",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL",
  "verified_utc": "<UTC>",
  "items": [
    {"id": 1, "claim": "...", "measured": "...", "pass": true}
  ],
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when all 30 items
pass and `unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL` with every finding stated.

Also write `VERIFICATION_NOTES.md` with what you actually ran.

Do not report an item as passing on the strength of this prompt. If you did
not measure it, mark it `"pass": false` and say so.
