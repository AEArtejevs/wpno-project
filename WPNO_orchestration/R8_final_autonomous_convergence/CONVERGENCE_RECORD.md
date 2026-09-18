# R8 final autonomous convergence — record

    MODE:   R8_FINAL_AUTONOMOUS_CONVERGENCE_NO_R9
    STOP:   HUMAN_GATE: THREE_FRESH_CODEX_ATTEMPTS_WITHOUT_PASS
            (section 10, condition E)

    R8 IS FINAL REVISION: YES
    R9 CREATED:           NO
    R8 MODIFIED:          NO
    FREEZE PLAN CREATED:  NO
    TOKEN GENERATED:      NO

## What was done

1. Attempt 5 classified `VERIFICATION_HARNESS_DEFECT`, preserved unchanged.
   Both of its defects recorded in `disposition/ATTEMPT_5_DISPOSITION.md`.
2. The harness was corrected: the disposable clone is now a direct hidden
   sibling of R8 under `/home/ubuntu/project/WPNO/`, so `paths.json`'s
   location-relative roots resolve to the real architecture.
3. Every measuring tool was checked against a known answer before use. The
   write barrier was proved to refuse a write before anything rested on it,
   both arms firing, once per attempt.
4. Three fresh Codex verifications were run — attempts 6, 7 and 8. Each was a
   new process; no `resume`, no `fork`, `CODEX_HOME` untouched, no login or
   logout. Each was waited on by its exact PID; no output file was read as a
   completion signal.
5. Each failure was classified, the smallest proven cause repaired in the
   harness, and a completely fresh attempt launched.

## Attempt outcomes

| # | stopped at | classification | root cause |
|---|---|---|---|
| 6 | item 9 | VERIFIER_HARNESS_DEFECT | item 9's exclusion rule was path-based; it could not dispose of byte-identical replica copies, nor of earlier verifiers' own scripts |
| 7 | item 13 | VERIFIER_HARNESS_DEFECT | instructions described `test_matrix` as though every entry carried `step_id`; 110 of 295 do not. Results were also held in memory, so twelve completed measurements were lost |
| 8 | item 23 | VERIFIER_HARNESS_DEFECT | the verifier's own predicate looked up reconciliation keys that do not exist (the record uses the `R8_` prefix) |

Three distinct root causes, each new, each repaired once, none surviving two
repairs. Condition D does not apply. Condition E does.

## What attempt 8 established on measurement

30 of 35 items passed, including every check the four preceding attempts could
not reach. Full detail in `disposition/ATTEMPT_8_DISPOSITION.md`. In summary:

    controller suite        503 / 0 / 0 / 0
    package suite           361 / 0 / 0 / 0 effective, SUITE_CLEAN
    static safety           0 findings
    build manifest          724 entries, 6dfd1af6…5b945a
    plans                   43/43
    rehearsals              43/43 PASS_READY
    in-process invocations  169 = 169
    note-only               0
    without evidence        0
    hollow phases           0
    controls                122/122, 0 unenforced
    out-of-allowance reads  0
    live state              43/43 NOT_STARTED, 0 approvals / results / evidence
    migration packet        prepared, bound, unconsumed, not applied
    R4 / R5 / R6 / R7       0 / ['MODE'] only / 0 / 0 mismatching
    R9                      absent
    write isolation         1362 paths, 0 changed on every field

NOT VERIFIED, which is not FAILED: items 28, 29, 30, 34, 35.
FAILED on the instrument, not on the bytes: item 23.

## Write isolation across the whole invocation

R8's inventory was taken before the first attempt and after the last, and
between every attempt. Every comparison: `EQUAL: true`, 0 paths added,
0 removed, 0 contents changed, 0 mtimes, 0 modes, 0 uid, 0 gid, 0 symlink
targets, over all 1362 paths.

    pre-first-attempt digest   e685461c0b24180bf9520d3f5fc453f805a3ea72362b7054ca7e9cbd84747032
    post-final-attempt         equal on every compared field

No process other than the verifier's own held a writable descriptor below R8
at any check. The limit of that measurement is recorded rather than assumed:
descriptors of processes owned by another uid are not readable without
privilege, and those pids are counted in every writer-inspection record. The
pre/post inventory is what closes that gap after the fact, and it is clean.

## What was NOT done, and why

Section 12 installs the verification output into R8 only after a genuine PASS.
There was no PASS, so nothing was installed, no freeze plan was built, and no
token exists. `attempt_8/freeze_output/` holds the prepared attempt-2 builder
and its independent validator, unused and unrun.

The prepared builder already repairs attempt 1's three defects — the stale
`verification_codex_final_pre_freeze_attempt_3` constant, the inherited "R7 is
the final revision; there is no R8" sentence, and the `r7_root` key — and binds
`automation/freeze.py`, `automation/policy.py`, the token-generation function's
own source, the validator, and every file of the installed verification
directory by enumeration. It is ready for the attempt that passes.
