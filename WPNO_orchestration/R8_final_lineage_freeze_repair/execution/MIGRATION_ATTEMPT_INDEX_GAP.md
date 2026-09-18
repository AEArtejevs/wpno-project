# L1-A31 COMPARISON cannot execute — the migration did not publish the attempt index

    GATE:            HUMAN_GATE: MIGRATION_ATTEMPT_INDEX_MISSING
    CLASSIFICATION:  R8_INTERNAL_POST_FREEZE_GAP
    APPROVAL TOKEN:  VALIDATED BYTE-EXACT, **NOT RECORDED, NOT SPENT**
    EXECUTION:       NOT ATTEMPTED
    R8 STATE:        unchanged — 0 paths added, removed or altered

## What the plan needs

`results/L1-A31/COMPARISON/attempt-1/plan.json` has three steps:

    collect_accepted_attempts  PARSE_JSON_READONLY  state/progress.json
    compare_run_a_seal         SHA256_FILE          evidence/L1-A31/RUN-A/ATTEMPT_INDEX.json
    compare_run_b_seal         SHA256_FILE          evidence/L1-A31/RUN-B/ATTEMPT_INDEX.json

Neither `ATTEMPT_INDEX.json` exists in R8. `evidence/L1-A31/RUN-A/` and
`.../RUN-B/` each contain exactly one entry, `attempt-1/`.

## Measured, not predicted

The three handlers the executor would call were invoked read-only, directly,
against the real paths:

    collect_accepted_attempts   RETURNED
    compare_run_a_seal          RAISED  FileNotFoundError
    compare_run_b_seal          RAISED  FileNotFoundError

R8 was byte-identical before and after that measurement: 0 paths added,
0 removed, 0 contents changed, 0 mtimes changed.

## Where the gap is

`attempts.write_attempt_index` publishes the phase-level index. It is called
from exactly two places in `automation/controller.py` — `cmd_finalize_current`
and `cmd_prepare_retry`. The migration route,
`cmd_import_sealed_predecessor_attempt` → `migration.apply`, calls neither.

So the import brought across the sealed attempt directory — 35 files for
RUN-A, 7 for RUN-B, both manifests verifying, both seals intact — but not the
phase-level index that R7 publishes at

    R7/evidence/L1-A31/RUN-A/ATTEMPT_INDEX.json
    R7/evidence/L1-A31/RUN-B/ATTEMPT_INDEX.json

and that R8's own COMPARISON plan binds by absolute path.

## Why no test and no verification caught it

The rehearsal ran before the migration, when the evidence did not exist, so it
SUBSTITUTED fixtures for exactly these two paths —
`REHEARSAL_INPUT_SUBSTITUTIONS.json` entries 28 and 29 redirect
`evidence/L1-A31/RUN-{A,B}/ATTEMPT_INDEX.json` to
`work/_rehearsal_r8/fixtures/inputs/_sealed_attempts/...`. The rehearsal
reported L1-A31/COMPARISON PASS_READY with 3 of 3 steps executed. It was
truthful about the fixtures and silent about the real paths, because the real
paths could not exist yet.

That is the same shape as the defects this package has already recorded: a
check that passes against a stand-in and is never repeated against the thing
itself.

## Why I stopped instead of executing

The approval token is `RUN-ONCE`. Spending it on an execution that must fail
would consume your authorisation for nothing and drive the phase into a failed
state requiring a retry and a fresh token. Nothing is gained by watching it
fail: the failure is already measured above.

## Why I did not simply write the two files

R8 is FROZEN. The repair belongs in `automation/migration.py`, which the frozen
control manifest covers — editing it would break the freeze, which is exactly
the R7 post-freeze incident R8 carries in its lineage to avoid repeating.

The index files themselves land under `evidence/`, a runtime directory the
frozen manifest deliberately excludes, so publishing them breaks nothing
frozen. But whether to publish them now, and by what route, is a decision about
what the audit record means — not a mechanical step — so it is yours.

## The three options, and my recommendation

**(a) Publish the two indexes through R8's own `attempts.write_attempt_index`,
using R8's own `state/progress.json`, then execute.** This is what the
migration should have done. The index is DERIVED from R8's state by R8's code,
not copied from R7 — a copy would carry R7's attempt identifiers and paths into
R8's evidence. It writes only under `evidence/`, so the frozen control manifest
is untouched and still verifies. The COMPARISON then reads an index that
describes R8's own imported attempts, which is what it is for.

**(b) Repair `automation/migration.py` properly.** Correct, but it changes a
manifest-covered file in a frozen package. That means unfreezing or a new
revision, and R9 is forbidden.

**(c) Leave it and record the phase as blocked.** Honest, but it leaves the
migration's stated purpose — making L1-A31 COMPARISON runnable in R8 — unmet.

I recommend **(a)**, with the defect in `migration.apply` recorded against the
package so the gap is not lost, and with the index generation done through the
controller's own function rather than by hand. If you authorise it, the
existing approval token stays valid: it binds the plan digest and the target
digest, and neither changes.
