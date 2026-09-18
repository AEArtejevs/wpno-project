# R8 frozen, migrated, and L1-A31 COMPARISON prepared

    R8 MODE                 FROZEN
    FREEZE ATTEMPT          3
    TOKEN                   validated byte-exact, consumed exactly once
    R9                      absent

## The freeze

The token the human returned was 271 bytes, byte-identical to the expected
token, SHA-256 `23776f5a…3f8b1dee`, accepted by `parse_freeze_token` and
`assert_token_binds_plan`. The corrected controller route was invoked once:

    python3 -m automation.controller freeze-level1 --token <token> \
      --plan build/freeze_plan_attempt_3/FREEZE_PLAN_R8_ATTEMPT_3.json

It crossed the write boundary the previous attempt could not reach and
published, MODE last:

    BASELINE_MANIFEST.json      0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d
    CONTROL_MANIFEST.sha256     62deca0b61f2810bf73bbb9b336cb52761e5ab773334e78a4285921aab2fba65
    state/PACKAGE_VERIFIED.json a1d0ddbc433c45cb6354ec11336ef6585e20a66811cf4db6ee3861aa01eeb707
    MODE                        67885f01edc72c2991b2ae9be04afc14a743b79c9d382262620be8ac154fa5fa

Verified independently, not taken from the route's own report: the control
manifest is 914 entries and **914/914 verify from disk**, including under
`/usr/bin/sha256sum -c`, which is the command a human would run. Its MODE entry
is the digest of the frozen bytes, not the pre-freeze ones — the R5 regression
that this ordering exists to prevent. Project baseline 33 members, Discovery
baseline 26, both nonempty.

`state/PACKAGE_VERIFIED.json` records what the repaired gate required:

    predecessor_lineage_artifacts  lineage/R7_BASELINE_MANIFEST.json
                                   lineage/R8_LINEAGE.sha256
    predecessor_lineage_kind       COMPACT_DIRECT_FILE

The ledger holds two rows for attempt 3 — `PUBLISH_STARTED` then `FROZEN` — so
the token was consumed exactly once. Offered a second time it is refused:
`FREEZE_ALREADY_DONE: MODE is FROZEN`, and the only thing that moved was the
lock directory's mtime.

## The migration

Both packets were verified first with `--verify-only`, which writes nothing.
Ten checks each, all ok, including `source_control_manifest 15804/15804`,
`source_execution_was_real` (16 operation records for 16 required steps in
RUN-A, 2 for 2 in RUN-B), `no_approval_token_imported` and
`destination_is_empty`. Then each was applied once.

    L1-A31 RUN-A   35 files   evidence manifest 33/33 verify
                              seal f7a7a4b2…  verdict UNVERIFIED
    L1-A31 RUN-B    7 files   evidence manifest 5/5 verify
                              seal ebedb95c…  verdict UNVERIFIED

Both seals name their own manifests, and both manifest digests equal what the
packets declared before the import. Re-offering either is refused:
`PACKET_ALREADY_CONSUMED`.

## The defective COMPARISON was refused, and the refusal was made to happen

R7's L1-A31 COMPARISON is excluded as
`EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`. An exclusion that
is only declared proves nothing — CLAUDE.md section 6 — so a well-formed
migration packet naming that attempt was constructed, with its self-digest
computed the route's own way, and offered to the live route. It was refused:

    SOURCE_PHASE_NOT_SEALED: L1-A31/COMPARISON is EXECUTED. An unsealed
    attempt has no manifest and no seal, so nothing about it can be verified
    -- which is exactly the condition of the predecessor's COMPARISON attempt,
    executed with zero evidence.

Two earlier offers were also refused, for the wrong reasons — a packet outside
the allowed read roots, and a self-digest computed by a different convention.
Neither would have demonstrated the control, and both are recorded rather than
quietly replaced by the one that did.

`evidence/L1-A31/COMPARISON/` does not exist. Nothing from that attempt entered
R8.

## L1-A31 COMPARISON prepared

The controller refused the candidate plan path outright — it binds only
`results/L1-A31/COMPARISON/attempt-1/plan.json`, "so binding a different one
would approve a plan that is not the plan that runs". The candidate plan was
installed there byte-identically, `47f25f7d…b6e272`, matching both its own
recorded digest and the frozen control manifest's entry for it.

`prepare-execution` then made the three permitted transitions —
NOT_STARTED → PLANNING → PLAN_READY → AWAITING_APPROVAL — approved nothing,
executed nothing, and printed the approval token.

## Final state, measured

    MODE                        FROZEN
    control manifest            914/914 verify
    L1-A31 RUN-A / RUN-B        SEALED / SEALED
    L1-A31 COMPARISON           AWAITING_APPROVAL
    all phases                  40 NOT_STARTED, 2 SEALED, 1 AWAITING_APPROVAL
    approvals                   0 bytes — nothing approved
    operations executed         0
    freeze ledger               PUBLISH_STARTED, FROZEN
    migration ledger            L1-A31/RUN-A, L1-A31/RUN-B — and nothing else
    R7 control manifest         verifies; untouched by the import
    R9                          absent

Neither token is recorded anywhere on disk. Both were printed to the operator
once.
