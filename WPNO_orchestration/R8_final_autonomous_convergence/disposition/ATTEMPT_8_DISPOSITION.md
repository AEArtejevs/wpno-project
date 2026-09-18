# Attempt 8 — disposition

    CODEX STATUS:   VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL
    STOPPED AT:     item 23
    ITEMS PASSED:   30 of 35
    CLASSIFICATION: VERIFIER_HARNESS_DEFECT
    NOT:            R8_INTERNAL_PREFREEZE_DEFECT

Attempt 8 is preserved unchanged under `attempt_8/`.

## Both earlier repairs held

Item 9 passed: 16 occurrences found, every one disposed of by a stated rule.
Item 13 passed: the `test_matrix` heterogeneity no longer raises. Durable
per-item recording worked — `ITEM_RESULTS.jsonl` holds every measurement as it
was made, so nothing was lost this time and no passed item was retroactively
downgraded.

## What attempt 8 measured

Thirty items passed on measurement, among them every one that attempts 5, 6
and 7 could not reach:

    18  controller suite            503 run / 0 failures / 0 errors / 0 skips
    19  package suite               361 effective / 0 failures / 0 errors /
                                    0 skips; SUITE_CLEAN true. One clone
                                    failure, the location-bound plan-path
                                    assertion, re-run unmodified in situ:
                                    passed, and the full 1362-path inventory
                                    equal before and after.
    20  static safety               0 findings, clean true, predecessor_root
                                    resolved to the real R7 sibling
    15  control expectations        122/122 machine-checkable, 0 unenforced,
                                    re-derived and equal to the record
    12  out-of-allowance reads      0
    21  candidate plans             43/43, 0 missing / duplicate / unknown
    22  rehearsals                  43/43 PASS_READY
    24  hollow phases               none; LIVE_STATE_UNCHANGED true
    25  live state                  35 audits, 43 phases, all NOT_STARTED
    26  approvals / results /       0 / 0 / 0, no token text under state/
        evidence
    27  build manifest              724 entries, digest
                                    6dfd1af6…5b945a, 0 malformed,
                                    0 duplicates, 0 mismatches, scope equal
    16  migration packet            RUN-A and RUN-B migratable, COMPARISON
                                    excluded, not applied, unconsumed
     1  R4                          1915 entries, 0 mismatching
     2  R5                          14160 entries, exactly ['MODE']
     3  R6                          14781 entries, 0 mismatching
     4  R7                          15804 entries, 0 mismatching
     5  R7 incident                 disclosed; continuous immutability false,
                                    bytes restored true
    31  manifest fold               e7d3d32e…b97eb before and after
    32  write isolation             1362 paths; 0 written, 0 mtimes, 0 modes,
                                    0 symlink targets, 0 contents, 0 added,
                                    0 removed
    33  instrument live             the clone control file's mtime advanced
                                    1787935556841911690 -> 1787945105532801228,
                                    observed by one absolute canonical path,
                                    bytes still equal to ORIGINAL

## Why it did not pass

**Item 23.** Codex's own scratch predicate looked up reconciliation keys that
do not exist. The record uses the `R8_`-prefixed names:

    R8_IN_PROCESS_HANDLER_INVOCATIONS  = 169
    R8_UNIQUE_IN_PROCESS_PLAN_STEPS    = 169

and the predicate asked for the unprefixed forms. Verified independently
against the bytes: `work/_rehearsal_r8/REHEARSAL_REPORT.json` reports

    REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE  0
    NOTE_ONLY_IN_PROCESS_STEPS                  0
    IN_PROCESS_HANDLER_INVOCATIONS            169
    IN_PROCESS_STEP_COUNT                     169

so item 23's substantive claim holds on the bytes. Codex said so itself: "the
measured R8 values support item 23's substantive claim."

The predicate had COMPLETED when it recorded `pass: false`, and the attempt-8
instruction is explicit that a completed adverse result stands and is not
re-run. Codex obeyed that, correctly. The rule is right; it was the naming
error inside a completed predicate that the rule could not distinguish from a
real adverse measurement.

**Item 28**, reached afterwards, raised `FileNotFoundError` on
`state/freeze_attempts.jsonl`. That file is legitimately absent — no freeze
attempt has been recorded, which is the required state — and the code did not
handle a permitted absence. Confirmed independently: the path does not exist.

Items 28, 29, 30, 34 and 35 are NOT VERIFIED. That is not FAILED.

## R8 was not touched

Measured by me after the Codex process exited, independently of Codex's own
measurement: 1362 paths, `EQUAL: true`, 0 added / 0 removed / 0 contents
changed / 0 mtimes / 0 modes / 0 uid / 0 gid / 0 symlink targets. Compare
record `59aee5f02340c790c631087fbc6f97d88632d543f1dba4bbbcd28666c4780aca`.
No process other than my own held a writable descriptor below R8, before or
after.

Codex's own output manifest verifies: every listed file matches.

## Attempt accounting — the limit is reached

    MAX_FRESH_CODEX_ATTEMPTS_IN_THIS_INVOCATION = 3
    used                                        = 3  (attempts 6, 7, 8)

    root cause 1  item 9 exclusion rule is path-based    1 repair, resolved
    root cause 2  test_matrix shape misstated; results
                  held in memory until the end           1 repair, resolved
    root cause 3  verifier scratch predicate used
                  non-existent key names                 0 repairs, open

Three distinct root causes, each new, each traceable to the verifier and not
to R8. No normalised root cause has survived two tested repairs, so stop
condition D does not apply. Stop condition E does: three fresh final Codex
attempts in this invocation without a PASS.

No freeze plan was created. No token was generated. Nothing was installed into
R8. `attempt_8/freeze_output/` holds the prepared builder and validator,
unused.
