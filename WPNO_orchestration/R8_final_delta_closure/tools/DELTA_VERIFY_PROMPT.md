# R8 final delta closure — independent verification

You are an independent verifier. Measure; do not trust this prompt's numbers.
Where a claim here and the bytes disagree, the bytes win and it is a finding.

## What this is, and why it is a delta and not a repeat

Attempt 8 measured 35 items and recorded each one durably, as it was made, in
`ITEM_RESULTS.jsonl`. Twenty-nine of them passed on measurement, including all
three suites. It stopped at item 23 because its own scratch predicate looked
up `IN_PROCESS_HANDLER_INVOCATIONS` in a record that holds
`R8_IN_PROCESS_HANDLER_INVOCATIONS`. The lookup was a guess; the guess was
wrong; the predicate completed and returned an adverse verdict, so the run
stopped. The four figures it had already read were correct.

The human has classified that as a defect in the verifier and has authorised
one delta closure. **You are explicitly forbidden from repeating work attempt 8
durably completed.** Do not rerun the controller suite, the package suite,
static safety, the rehearsals, plan generation, predecessor manifests, or the
reference and readiness checks. Their results are carried forward from
hash-bound stored output, and you verify that binding rather than the work.

## The two roots

    ORIGINAL = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8
    CLONE    = /home/ubuntu/project/WPNO/.r8_verify_clone_attempt_8_676767
    BASE     = /home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_8
    OUT      = /home/ubuntu/project/WPNO_orchestration/R8_final_delta_closure/codex_output
    WORKSPACE= /home/ubuntu/project/WPNO_orchestration/R8_final_delta_closure

ORIGINAL is READ-ONLY to you, enforced by the sandbox, not by permission bits.
CLONE exists so that importing R8's `automation` package cannot leave a
`__pycache__` inside ORIGINAL; it is proved byte-identical, and you re-prove
that. Nothing in this closure needs to write to either package.

Write ONLY inside OUT.

## The delta set, fixed and finite

    CARRIED FORWARD (do NOT remeasure): items 1-22, 24-27, 31, 32, 33
    DELTA (measure these): items 23, 28, 29, 30, 34, 35

Item 23 failed on a verifier predicate. Items 28, 29, 30, 34 and 35 were never
measured — NOT VERIFIED, which is not FAILED.

## Hard rules

- No network. No git. No installation. No write to R8. No R9. No live audit
  phase. Do not apply the migration. Do not freeze. **Do not compute the real
  freeze token.**
- `/usr/bin/python3`. `PYTHONDONTWRITEBYTECODE=1` and the temp/cache redirects
  are already exported. Do not unset them.
- Record each item to `OUT/ITEM_RESULTS.jsonl` the moment it finishes, before
  starting the next. Assemble the final files from that, never from memory.
- Log every command to `OUT/COMMAND_LOG.jsonl` as you go.
- Every measurement uses an absolute canonical path. For a before/after pair
  record requested path, resolved absolute path, owning root, both mtime_ns and
  both SHA-256. `after_mtime_ns < before_mtime_ns` is INVALID EVIDENCE, not a
  pass.
- **Never index a JSON object with a key you have not first proved present.**
  `WORKSPACE/VERIFIER_SCHEMA_MAP.json` lists every key any predicate names,
  with its real type and a sample, measured from the bytes. Read it. If you
  need a key it does not carry, add your own proof before you use it. There are
  no fallbacks and no unprefixed aliases — a fallback lets a wrong name succeed
  by finding something else.
- A crash in your own scratch code measures nothing. Fix it, rerun that
  measurement, and record the traceback, the fix and both runs. An adverse
  result from a predicate that COMPLETED is a finding: stop.

## Verify these, in this order

### A. The base is still the base

A1. ORIGINAL's `MODE` is `GENERATED_UNVERIFIED`.
A2. `build/R8_BUILD_MANIFEST.sha256` verifies: 724 entries, every path present
    and matching, no duplicates, no malformed lines. Its own digest is
    `6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a`.
A3. ORIGINAL is byte- and metadata-identical to the inventory attempt 8 took at
    its end, `BASE/original_inventory/INVENTORY_FINAL.json` — all 1362 paths on
    type, size, SHA-256, symlink target, mode, uid, gid and mtime_ns. If it is
    not, stop with `STOP_R8_CHANGED_AFTER_ATTEMPT_8` and repair nothing.
A4. `state/progress.json` holds 35 audits and 43 phase records, all
    `NOT_STARTED`; `state/approvals.jsonl` is empty; `results/` and `evidence/`
    hold no files.
A5. The migration packet is valid, bound and unconsumed:
    `MIGRATION_PLAN.sha256` equals the plan's own digest, its
    `route_module_sha256` equals the digest of `automation/migration.py`,
    `applied_before_freeze` is false, and `state/migrations.jsonl` is absent or
    empty.

### B. The carried-forward evidence is sound

B1. `BASE/codex_output/VERIFICATION_MANIFEST.sha256` verifies: every listed
    file present and matching. Report the entry count.
B2. `WORKSPACE/ATTEMPT_8_DURABLE_ITEM_MATRIX.json` — check it yourself. For
    every item marked `CARRY_FORWARD_ALLOWED`, confirm all six conditions hold
    and that its record holds an actual measured value rather than a sentence
    saying one was taken. Confirm the delta set is exactly {23, 28, 29, 30, 34,
    35} and that no item is both carried forward and remeasured.
B3. The headline figures, read from the STORED OUTPUT of the run that produced
    them, not from any summary:

      - controller suite: `BASE/codex_output/CONTROLLER_SUITE.stderr.txt` —
        503 tests, trailing `OK`
      - package suite: `BASE/codex_output/PACKAGE_SUITE.json` — 361 run,
        `EFFECTIVE_PASSED` 361, `EFFECTIVE_FAILURES` 0, errors 0, skips 0,
        `SUITE_CLEAN` true, and the one clone failure classified
        `RELOCATION_ARTEFACT_RESOLVED_IN_SITU` having written nothing
      - static safety:
        `BASE/codex_output/static_safety_outputs/R8_STATIC_SAFETY_REPORT.json`
        — `finding_count` 0, `clean` true, `unpermitted_changes` empty

    Do NOT rerun any of the three. Verify instead that each file's digest
    matches attempt 8's manifest, and that the executables that produced them
    are unchanged in ORIGINAL today.
B4. `WORKSPACE/BASE_EVIDENCE_VERIFICATION.json` — read it and confirm its
    conclusions against the same stored files.

### C. Item 23, remeasured in full

Not two aggregates being equal. The record, the aggregate, the per-phase
records and the plans must all say the same thing, and each must be derived
from its own bytes.

C1. `build/IN_PROCESS_COUNT_RECONCILIATION.json`:
    `R8_IN_PROCESS_HANDLER_INVOCATIONS` = 169 and
    `R8_UNIQUE_IN_PROCESS_PLAN_STEPS` = 169. **These exact prefixed names.**
    `R8_TOTAL_PLAN_STEPS` = 311.
C2. Re-derive both numbers from that record's own 311 `steps` rows: the rows
    whose `R8_FINAL_CLASSIFICATION` is `IN_PROCESS` and whose
    `UNIQUE_PLAN_STEP` is true must number 169, and their
    `EXECUTION_INVOCATION_COUNT` must sum to 169.
C3. Every such row has `R8_REHEARSAL_EXECUTED` true.
C4. `explanation.UNEXPLAINED_COUNT_DIFFERENCE` is 0.
C5. `work/_rehearsal_r8/REHEARSAL_REPORT.json` aggregates:
    `IN_PROCESS_HANDLER_INVOCATIONS` 169, `IN_PROCESS_STEP_COUNT` 169,
    `NOTE_ONLY_IN_PROCESS_STEPS` 0,
    `REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` 0, `HOLLOW_PHASES` empty.
C6. The 43 per-phase records sum to those aggregates: invocations 169, step
    count 169, note-only 0, without-evidence 0, and no record has `HOLLOW`
    true. An aggregate can conceal one skipped step; the sum cannot.
C7. Derive the in-process step set a THIRD time, from the 43 plan files and
    `automation.operation_catalog.IN_PROCESS`: 169 steps. Two records produced
    by one build agreeing proves less than three independent derivations
    agreeing.
C8. Every operation in `operation_catalog.IN_PROCESS` has a handler in
    `in_process_ops.HANDLERS`.
C9. Per STEP across all 43 rehearsal records: every step whose operation is
    in-process has `executed` true, and none carries a note containing
    `performed by the worker`.

Item 23 passes only if C1 through C9 all hold, with zero unexplained
difference.

### D. Item 28 — the freeze mechanism can produce the plan and the token

D1. `automation/freeze.py` has `PACKAGE_REVISION` "R8" and `PACKAGE_PLATFORM`
    "UBUNTU".
D2. Its `PREDECESSOR_BASELINE_REL` resolves to a file inside R8 whose digest
    equals `lineage/R8_LINEAGE.json`'s `r7.baseline_manifest_sha256`.
D3. `freeze.build_baseline_from_predecessor(CLONE)` returns without raising,
    and both baseline member counts are greater than zero. Report them.
D4. `freeze.token_for` composes a well-formed token and
    `freeze.parse_freeze_token` round-trips it — called with THREE DUMMY
    64-hex digests of your own choosing, for instance the SHA-256 of "a", "b"
    and "c". Confirm five whitespace-separated fields and no trailing newline.
    **You must not compute the real token.** Producing it would be a finding
    against this attempt.
D5. `state/freeze_attempts.jsonl` records no consumed attempt.

### E. Items 29, 30, 34, 35

E1. Item 29 — no `08.18.26_Level1_Audits_R9` exists beside the package.
E2. Item 30 — `state/transitions.jsonl` holds exactly one row and its `route`
    is `init-revision`.
E3. Item 34 — read `WORKSPACE/TOOL_INVENTORY.json`. Every row's file exists and
    its SHA-256 matches disk. `UNIDENTIFIED_TOOLS` is 0. The inventory
    distinguishes the instructions, the runner, each helper, the schema map,
    the self-test, the durable item matrix, the freeze-plan builder, the plan
    wrapper or an explicit `NOT_USED`, `automation/freeze.py`, the exact
    token-generation function source, and every executable used to create or
    validate freeze artefacts. `VERIFICATION_RESULT.json` and the attempt-8
    records are RESULTS; if any is labelled a verifier that is a finding.
E4. Item 35 — from `/proc/<pid>/fd` and `/proc/<pid>/fdinfo/<fd>`, not from
    `pgrep -f`, confirm no process other than your own holds a writable
    descriptor below ORIGINAL. Report how many pids you could inspect and how
    many you could not, and why. Kill nothing.

### F. The self-test that let this attempt run

F1. Read `WORKSPACE/selftest/DELTA_VERIFIER_SELFTEST.json` and
    `WORKSPACE/tools/selftest_delta_verifier.py`. Confirm the self-test proves,
    by running and not by assertion: the correct prefixed keys accepted; a
    missing key rejected; **attempt 8's exact unprefixed key name rejected**; a
    wrong type rejected; 168 against 169 rejected; 169 against 169 accepted; no
    uncontrolled exception escaping any predicate; and every predicate
    evaluated once against a schema-valid fixture.
F2. `DELTA_VERIFIER_SELF_TEST` is `PASS`, `UNRESOLVED_KEY_LOOKUPS` is 0, and
    `PREDICATES_TESTED` is n/n.

### G. Coverage and closure

G1. Carried-forward items plus delta items equal the complete set 1..35 exactly
    once each, with none missing and none counted twice.
G2. No item remains FAILED, NOT COMPLETED, or resting on evidence you could not
    verify.
G3. ORIGINAL was not written. Full 1362-path inventory before your first
    measurement and after your last: 0 added, 0 removed, 0 contents changed,
    0 mtimes, 0 modes, 0 uid, 0 gid, 0 symlink targets. Exempt nothing.

## Output

`OUT/VERIFICATION_RESULT.json` must contain the COMPLETE item table for all 35
items, not only the delta, and each item must point to its evidence:

```json
{
  "schema": "wpno.level1.codex-verification/2",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL",
  "EVIDENCE_MODEL": "ATTEMPT_8_BASE_PLUS_FRESH_DELTA_CLOSURE",
  "BASE_ATTEMPT": 8,
  "DELTA_ITEMS": [23, 28, 29, 30, 34, 35],
  "CARRIED_FORWARD_ITEMS": [1, 2, "...", 33],
  "verified_utc": "<UTC>",
  "items": [
    {"id": 1, "source": "ATTEMPT_8_DURABLE", "root": "ORIGINAL",
     "claim": "...", "measured": "...",
     "evidence_path": "...", "evidence_sha256": "...", "pass": true},
    {"id": 23, "source": "FRESH_DELTA", "root": "ORIGINAL",
     "claim": "...", "measured": {}, "evidence_path": "...",
     "evidence_sha256": "...", "pass": true}
  ],
  "manifest_sha256_verified": "<the digest you measured>",
  "manifest_entries_verified": 724,
  "package_unchanged_by_this_verification": true,
  "r8_paths_written_during_this_closure": 0,
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

Every one of the 35 items must carry `source` of either `ATTEMPT_8_DURABLE` or
`FRESH_DELTA`, and an `evidence_path` with a digest you verified.

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when all 35 items pass
and `unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`, with every finding stated.

Also write:

- `OUT/ITEM_RESULTS.jsonl` — one line per item, appended as each finishes.
- `OUT/MEASUREMENTS.json` — the raw numbers behind every delta item.
- `OUT/COMMAND_LOG.jsonl` — every command, its root, exit status and UTC time.
- `OUT/VERIFICATION_REPORT.md` — what you ran, which root each ran against,
  what you read versus inferred, what you carried forward and on what binding,
  and anything you could not measure.
- `OUT/VERIFICATION_MANIFEST.sha256` — `sha256  path` for every file you wrote
  into OUT, itself excluded.

The last five are assembled after every measurement is complete and are not
touched again.
