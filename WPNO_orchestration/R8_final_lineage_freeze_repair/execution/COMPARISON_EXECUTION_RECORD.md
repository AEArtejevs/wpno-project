# L1-A31 COMPARISON — indexes published, phase executed

    GATE:      HUMAN_GATE: REVIEWER_VERDICT
    STATE:     L1-A31/COMPARISON = EXECUTED, attempt-1 = OPEN (unsealed)
    APPROVAL:  recorded once, token spent
    MODE:      FROZEN — control manifest 914/914, unlisted 0, missing 0

## The two indexes

Published through `automation.attempts.write_attempt_index`, the controller's
own publisher, under the controller lock, driven by R8's own
`state/progress.json`. Derived, not copied: a copy of R7's index would have
carried R7's attempt identifiers into R8's evidence.

    evidence/L1-A31/RUN-A/ATTEMPT_INDEX.json  412bf564…  SEALED, accepted 1
    evidence/L1-A31/RUN-B/ATTEMPT_INDEX.json  b7cfb1cc…  SEALED, accepted 1

Both land under `evidence/`, a runtime directory the frozen control manifest
deliberately excludes. Measured after: exactly two paths added, nothing
removed, nothing changed, nothing outside `evidence/`. The frozen manifest
verified before and after.

## The execution

    record-approval    state APPROVED, 1 approval row, token spent
    execute-approved   3 planned / 3 executed / 0 failed / 0 skipped /
                       0 deferred / 3 evidence records
    target             023541aa… before and after — unchanged by the run

Each evidence record carries its stdout and stderr digests and the note
`IN_PROCESS_NO_SUBPROCESS: performed by the controller with the standard
library; no process was launched` — the repaired wording. Not one record
carries the note the frozen R7 controller wrote instead of working.

## What the run measured, and what it did not

This is the part a verdict has to rest on, so it is stated plainly.

The three steps produced:

    collect_accepted_attempts  PARSE_JSON_READONLY  state/progress.json
      -> path, sha256 0250b50b…, shape "object", top-level keys
         ["audits", "halt_critical"]
    compare_run_a_seal         SHA256_FILE
      -> RUN-A ATTEMPT_INDEX.json, sha256 412bf564…, 681 bytes
    compare_run_b_seal         SHA256_FILE
      -> RUN-B ATTEMPT_INDEX.json, sha256 b7cfb1cc…, 681 bytes

The plan's `test_matrix` says COMPARISON compares:

    chain path validation outcome
    CMS signature outcome
    key-usage conformance determination
    validation time used
    anchor identity

**None of those five appears in the evidence.** The steps bound the phase to
the two attempt indexes and to the progress file by digest; they did not read,
extract or compare the two runs' substantive findings. The first step's stated
purpose is "Read the accepted attempt pointer and the full attempt history for
RUN-A and RUN-B", and its artefact records the file's shape and key names, not
those pointers or that history.

Every step reported `NO_MACHINE_CHECKABLE_EXPECTATION`: the plan declares no
expectation any of them could fail. So the run cannot have detected a
disagreement between RUN-A and RUN-B, and its clean result is not evidence that
none exists. The `disagreement` entry — "a disagreement between the two methods
is a finding in its own right and is never resolved by preferring the run that
matches expectation" — was not exercised.

What the phase did establish: both runs have an accepted, usable, sealed
attempt, and the comparison is bound by digest to exactly which attempts those
were. That satisfies the `refusal` and `superseded_attempts` entries. It does
not satisfy `compared`.

## One thing I did and then undid

Six `__pycache__` files appeared under `automation/` during this session: one
of my own commands ran without `PYTHONDONTWRITEBYTECODE`. They were generated
bytecode, `control_plane_files` skips `__pycache__` by design, and the frozen
manifest verified throughout — but they were my artefact and did not belong in
a frozen package, so they were removed. Verified structurally afterwards:
914 entries, 0 failed, 0 missing, **0 unlisted**, MODE entry present and
correct.

## The verdict is not mine

`finalize-current --verdict` records the Reviewer's verdict and seals the
attempt. CLAUDE.md section 2 reserves every Freigabe des Berufsträgers to the
human, and the verdict decides whether the phase becomes SEALED and terminal or
is routed to RETRYABLE_INTERNAL_ERROR, BLOCKED_FOR_EXTERNAL_MATERIAL or
HALT_CRITICAL. The attempt stays OPEN until you give one.

    VERDICTS         PASS · PASS_WITH_WARNINGS · FAIL · BLOCKED ·
                     UNVERIFIED · ERROR · CONTAMINATED
    CLASSIFICATIONS  SUBSTANTIVE_AUDIT_RESULT · INTERNAL_REPAIRABLE_DEFECT ·
                     MISSING_EXTERNAL_REFERENCE_OR_OPERATOR_INPUT ·
                     CONTROL_PLANE_INTEGRITY_FAILURE ·
                     INDEPENDENT_METHOD_MATERIAL_MISSING

    python3 -m automation.controller finalize-current \
      --audit-id L1-A31 --run-phase COMPARISON --verdict <VERDICT>

Given that the five substantive dimensions were not measured, `PASS` would
assert more than the evidence carries. That is an observation about the
evidence, not a recommendation about the verdict.
