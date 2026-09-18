# Attempt 7 — disposition

    CODEX STATUS:   VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL
    STOPPED AT:     item 13
    CLASSIFICATION: VERIFIER_HARNESS_DEFECT
    NOT:            R8_INTERNAL_PREFREEZE_DEFECT

Attempt 7 is preserved unchanged under `attempt_7/`.

## Item 9 is fixed

The content-based rule worked: item 9 no longer stops the run. That repair
stands and is not revisited.

## What stopped attempt 7

    VERIFICATION_DEFECT: item 13 measurement assumed every test_matrix entry
    had a direct key step_id and raised KeyError('step_id')

Codex's own words. This is a crash in the verifier's scratch code, not a
measurement of R8. Its cause is a structural fact the instructions asserted
too narrowly. The prompt said:

    "A step's expectation lives in the plan's `test_matrix`, in the entry
     whose `step_id` equals the step's."

True of the entries that have one. Measured across all 43 plans:

    test_matrix entries        295
      carrying `step_id`       185
      carrying `check_id`       84   (34 of them PLAN_BINDING)
      carrying neither          26   (free-form prose keys, e.g.
                                      `compared`, `refusal`, `independence`)

So `entry["step_id"]` raises on 110 of 295 entries. The instruction described
the majority case as though it were the only case.

## The second defect, which turned one crash into a total loss

Attempt 7 measured items 1–12 and then lost them. The prompt said to write the
five output files LAST, so every result lived only in the process's memory
until the end. When item 13 raised, twelve completed measurements went with it
and were reported as "Measurement process aborted before durable result
capture" — recorded as `pass: false`, which is not what was measured. Attempt 6
had measured several of the same items and passed them.

A measurement that is not durable is not evidence, and an instruction that
holds results in memory until the end guarantees that any late failure erases
the early work.

## The repairs for attempt 8

1. **State the structure as it is.** The `test_matrix` heterogeneity above goes
   into "Where things actually live", with the counts, and with the direction
   to use `.get()` and to skip entries that carry no identifier rather than
   indexing them.

2. **Record each item durably as it completes.** Append one JSON object per
   item to `OUT/ITEM_RESULTS.jsonl` the moment that item finishes, before
   starting the next. A later stop then leaves the earlier measurements intact
   and honestly labelled, and the final files are assembled from that file
   rather than from memory.

3. **Separate a crash in the verifier's own scratch code from an adverse
   measurement.** The two are not the same thing and attempt 7 treated them
   alike:

     - A measurement that COMPLETES and returns an adverse result is a finding.
       STOP. Do not re-run it, do not adjust it, do not see whether it clears.
     - A crash in the verifier's own throwaway code — a KeyError, a TypeError,
       a bad path in a scratch script — measures nothing about R8 in either
       direction. Fix that code, re-run THAT measurement, and record the crash,
       the fix and both runs.

   This is not a relaxation. It removes a typo's power to decide an audit
   outcome, while leaving intact the rule that matters: an adverse result that
   was actually measured is never re-rolled.

## Attempt accounting

    MAX_FRESH_CODEX_ATTEMPTS_IN_THIS_INVOCATION = 3
    used after attempt 7                        = 2

    root cause "item 9 exclusion rule is path-based"   1 repair, resolved
    root cause "instructions misstate test_matrix
      shape, and results are not durable"              1 repair, first

The two root causes are distinct. Neither has survived two repairs. R8 is not
modified.
