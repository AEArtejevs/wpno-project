# Attempt 6 — disposition

    CODEX STATUS:   VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL
    STOPPED AT:     item 9
    CLASSIFICATION: VERIFIER_HARNESS_DEFECT
    NOT:            R8_INTERNAL_PREFREEZE_DEFECT

Attempt 6 is preserved unchanged under `attempt_6/`. Nothing in it was edited
after the Codex process exited.

## What the corrected clone placement fixed

Attempt 5's 47 package-suite errors are gone. The sibling clone resolved
`project_root`, `discovery_root` and the predecessor siblings to the real
architecture. Items 1–8, 27, 31 and 32 passed on measurement. R8 was not
written to: 1362 paths before and after, inventory digest
`e685461c0b24180bf9520d3f5fc453f805a3ea72362b7054ca7e9cbd84747032` both times,
0 added / 0 removed / 0 contents changed / 0 mtimes changed / 0 modes changed —
measured by Codex independently and again by me after its process exited.

Codex's own conclusion: "No R8 defect has been established by this attempt."

## Where the defect is

Item 9 asks for every occurrence of `performed by the worker` under R8 to be
classified, and defines a finding as an executable statement on a live
controller or rehearsal path that assigns that note as a step's outcome
instead of performing the operation. Its exclusion rule was written in terms of
PATHS: three modules named by their top-level relative paths, plus an escape
for any path segment `fixtures` or `lineage`.

Codex found 16 occurrences and classified 5 as findings:

    verification/selftest_runtime/automation/in_process_ops.py:6
    verification/selftest_runtime/automation/in_process_executor.py:6
    verification/selftest_runtime/automation/controller.py:798
    verification/selftest_runtime/automation/migration.py:363
    verification_codex_final_pre_freeze_attempt_1/verify.py:86
    verification_codex_final_pre_freeze_attempt_2/verify.py:120, :124

None is a finding, and the rule as written could not say so:

- The first four are the SELF-TEST REPLICA's copies of four modules whose
  top-level originals Codex had already classified, correctly, as quoted
  docstring text or as the guard that refuses the note. Measured, not assumed —
  each replica file is byte-identical to its original:

      automation/in_process_ops.py        1e39e3e0fa09d884…  = replica
      automation/in_process_executor.py   d4fb45186aa620f0…  = replica
      automation/controller.py            167b5cf6f43bdead…  = replica
      automation/migration.py             65b3db95c3bf9d01…  = replica

  `automation/controller.py:798` sits inside the docstring of
  `_run_in_process_operation`, which quotes the old defective branch in order
  to describe what was repaired. `automation/migration.py:363` is
  `if "performed by the worker" in note:` — a guard that RAISES
  `SOURCE_USED_THE_DEFECTIVE_BRANCH`. It refuses the note; it does not write
  it. The replica's copies are the same bytes and therefore the same text.
  Nothing on a live controller or rehearsal path imports from
  `verification/selftest_runtime/`.

- The last two are EARLIER VERIFIERS' OWN SCRIPTS, which search for the
  phrase. A script that greps for a string is not a statement that assigns it.

The rule anticipated the replica for `fixtures` — it says so in as many words —
but not for the four modules themselves, and it said nothing about verifier
scripts. That is an incomplete instruction, not a defect in R8.

## The repair, and why it is not a weakening

Item 9 is rewritten for attempt 7 to classify by CONTENT rather than by path.
The generalisation that closes this class of gap:

    A file whose SHA-256 equals that of a file already classified as
    not-a-finding inherits that classification, and the digest is recorded.

That is stricter than a path list, not looser: a path list admits a file
because of where it sits; a digest admits it because it is the same bytes,
which is the only reason the classification transfers at all. The definition of
a finding is unchanged, the search is unchanged, and no occurrence is skipped —
every one of the 16 must still be classified and reported.

Two further exclusions are stated explicitly rather than left to be inferred:
a guard that refuses the note, and a verifier script that searches for it.

## Attempt accounting

    MAX_FRESH_CODEX_ATTEMPTS_IN_THIS_INVOCATION = 3
    used after attempt 6                        = 1

    normalised root cause "item 9 exclusion rule is path-based"
    repairs applied to it                       = 1 of 2 permitted

R8 is not modified. The repair is confined to the verification instructions
below FINAL_ROOT.
