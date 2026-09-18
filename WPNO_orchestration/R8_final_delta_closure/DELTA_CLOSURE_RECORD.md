# R8 final delta closure — record

    MODE:            R8_FINAL_DELTA_CLOSURE_NO_REPEAT_NO_R9
    EVIDENCE MODEL:  ATTEMPT_8_BASE_PLUS_FRESH_DELTA_CLOSURE
    RESULT:          VERIFICATION_PASS_PRE_FREEZE_R8_FINAL
    R9 CREATED:      NO

## What was carried forward, and what was measured again

    CARRIED FORWARD  29 items  1-22, 24-27, 31, 32, 33
    FRESH DELTA       6 items  23, 28, 29, 30, 34, 35
    TOTAL            35 items, each exactly once, none twice

Nothing attempt 8 durably completed was rerun. The controller suite, the
package suite, static safety, the rehearsals, plan generation and the
predecessor manifests were NOT re-executed. Their results were verified as
hash-bound stored output — the suite's own captured stderr, the package-suite
runner's own JSON, the static review's own report — never from a summary
quoting itself.

Carry-forward required six conditions per item, recorded in
`ATTEMPT_8_DURABLE_ITEM_MATRIX.json`. Condition 6, that no relevant dependency
changed, was answered once and in the strongest available form: the whole R8
tree, all 1362 paths, compared against the inventory attempt 8 took at its end
on type, size, SHA-256, symlink target, mode, uid, gid and mtime_ns — 0
differing. A per-item dependency list would have been weaker, because it could
omit a dependency nobody thought of.

## The defect that ended attempt 8, and how it was made impossible

Attempt 8's predicate asked for `IN_PROCESS_HANDLER_INVOCATIONS`; the record
holds `R8_IN_PROCESS_HANDLER_INVOCATIONS`. The name was a guess and the failure
arrived as a `KeyError` that killed the process rather than as a verdict that
could be recorded.

Two things were built before a single Codex attempt was spent:

`VERIFIER_SCHEMA_MAP.json` — 175 fields, every key any predicate names, opened
and listed from the real bytes with its type and a sample. Both required
prefixed keys proved present. `UNRESOLVED_KEY_LOOKUPS: 0`. No fallbacks and no
unprefixed aliases: a fallback lets a wrong name succeed by finding something
else.

`DELTA_VERIFIER_SELFTEST.json` — 14 cases, all passing, 42/42 predicates:

    correct prefixed key accepted                          PASS
    missing key rejected                                   PASS
    attempt 8's exact unprefixed name rejected             PASS
    wrong type rejected (str, bool, and a non-object)      PASS
    168 against expected 169 rejected                      PASS
    169 against expected 169 accepted                      PASS
    no uncontrolled exception escapes any predicate        PASS
    every predicate run once against a valid fixture       PASS

The lookup helper raises one controlled `SchemaError`, which the runner turns
into a recorded INVALID verdict. A `KeyError` can no longer end a run.

## Item 23, remeasured from three independent derivations

    reconciliation record        R8_IN_PROCESS_HANDLER_INVOCATIONS   169
                                 R8_UNIQUE_IN_PROCESS_PLAN_STEPS     169
                                 R8_TOTAL_PLAN_STEPS                 311
                                 UNEXPLAINED_COUNT_DIFFERENCE          0
    its own 311 step rows        unique in-process steps             169
                                 invocations summed                  169
                                 rows not executed                     0
    rehearsal aggregate          invocations 169 · steps 169
                                 note-only 0 · without evidence 0
                                 hollow phases none
    43 per-phase records summed  invocations 169 · steps 169
                                 note-only 0 · without evidence 0
                                 none HOLLOW
    the 43 plan files + the
    operation catalogue          in-process steps                    169

Two records produced by one build agreeing proves less than three derivations
agreeing. Per STEP across all 43 phases: every in-process step executed, and
none carries the note `performed by the worker`.

## Two defects found in the freeze tools, both repaired, neither in R8

**The validator failed the package's own static-safety standard.** The 43-file
review carried forward from attempt 8 cannot cover the freeze-plan builder and
validator, because neither existed when it ran. Running it over them raised
four findings against the validator's `subprocess` call: `shell`, `timeout`,
`env` and `cwd` all unstated. The call now states all four. The standard was
not relaxed for the tool that exists to uphold it. Re-run: 45 files reviewed,
**0 findings**.

**The builder refused to bind a legitimately empty file.** Four of attempt 8's
installed artefacts are the captured stderr of commands that wrote nothing to
stderr. The zero-byte refusal exists to catch a truncated artefact, and for a
control-plane file it is right; for a clean run's own evidence it is wrong. The
guard was narrowed, not removed: a zero-byte artefact is admitted only inside
the installed verification directory and only when that directory's own
manifest declares its digest to be the SHA-256 of the empty string. Emptiness
attested, not merely observed. Truncate any other bound artefact and the build
still stops.

Both are disclosed in `FREEZE_TOOL_REPAIR_RECORD.json`, with the versions the
independent verifier actually saw preserved unaltered under
`superseded_by_static_safety_repair/`.

## What R8 gained, and what it did not

    manifest-covered paths changed          0
    paths removed                           0
    new paths                              86, every one inside
                                            verification_codex_final_pre_freeze_attempt_5/
                                            or build/freeze_plan_attempt_2/
    __pycache__ created inside R8           0
    build manifest                         724/724 valid, 6dfd1af6…5b945a

Both directories are excluded from the build manifest by a named
path-component rule in `build/build_r8_build_manifest.py`, which is why writing
there does not invalidate the manifest and why the plan binds their contents by
digest instead.

Attempt 1's freeze plan and builder are preserved byte-for-byte and were not
overwritten.

## Limit of one measurement, stated rather than glossed

Codex's own item-35 writer inspection could enumerate only 1 pid: its sandbox
restricts `/proc`. It reported that honestly. The broader measurement is mine,
taken outside the sandbox — 27 pid tables readable, 117 not, all of the latter
owned by other uids and unreadable without privilege, **0 processes holding a
writable descriptor below R8**. Neither measurement alone covers the machine;
together they cover what is observable without privilege, and the full
pre/post inventory is what closes the gap after the fact.
