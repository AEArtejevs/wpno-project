# Harness validation, before any Codex attempt

Every measuring tool is checked against a known answer before it is trusted.
These runs were made by Claude to validate the attempt-6 workspace. They are
NOT the independent verification and are not offered as one; Codex remeasures
all of it.

Clone used: a direct sibling of R8, `/home/ubuntu/project/WPNO/.r8_verify_clone_attempt_6_651472`.

| measurement | attempt 5 (clone outside sibling layout) | attempt 6 (sibling clone) | recorded R8 value |
|---|---|---|---|
| controller suite | 503 / 0 / 0 / 0 | 503 / 0 / 0 / 0 | 503 / 0 / 0 / 0 |
| package suite | 343 ran, 1 failure, **47 errors** | 361 ran, 1 failure, **0 errors**, 0 skips | 361 / 0 / 0 / 0 |
| static safety | never ran | 0 findings, report equal to the record on every field except `package_root` and `reviewed_at_utc` | 0 findings |

The 47 errors are gone. The sibling placement was the whole of that defect.

## The one remaining package-suite failure, and why it is a relocation artefact

    FAIL automation.package_tests.test_r7_rehearsal_output_paths
         .OutputsStayInsideTheWorkArea
         .test_no_plan_in_the_package_names_an_unconfined_output

    L1-A01/RUN-A step 'run1' writes outside work/
    ['/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8/work/L1-A01/RUN-A/RUN1/output.docx']

The test computes the permitted work area as `path_policy.LEVEL1_ROOT + "/work"`,
which is location-relative. 34 plan files hold 357 output paths written as
absolute strings naming the ORIGINAL R8 root. In situ the two agree and every
path is confined. In any relocated copy `LEVEL1_ROOT` moves and the baked
strings do not, so the test reports the baked path as unconfined. It is
reporting the relocation, not a plan that writes where it may not.

Measured, not asserted:

- The test method writes nothing. Full 1362-path inventory of the ORIGINAL R8
  before and after running it in situ — type, size, SHA-256, symlink target,
  mode, uid, gid, mtime_ns: **0 added, 0 removed, 0 contents changed,
  0 mtimes changed, 0 modes changed.** Compare record
  `a7459a6360e5ff0ad11c74ce7a86b8e688dbb9565fc787eaeb6efbc05b177935`.
- Run in situ, unmodified, it passes: `Ran 1 test ... OK`.

## Why the clone cannot simply be abandoned for an in-situ run

The package suite as a whole is not read-only. Run in the clone it left the
clone byte-identical to R8 — 0 paths added, 0 removed, 0 contents changed —
but it moved **8 directory mtimes**: `.`, `state`, `work`,
`work/_freeze_order_regression`, `work/_r5_selftest`, `work/_r5_selftest/a18`,
`work/_r5_selftest/a34_staging`, `work/_selftest`. It creates and removes
temporary files there. Run in place those eight mtimes would move inside R8,
and the write-isolation requirement admits no exemption.

So neither location alone can carry the whole suite: the clone cannot host the
location-bound test, and R8 cannot host the writing tests.

## The rule this justifies — and it is not a weakening

A package-suite failure observed in the clone is admitted as a relocation
artefact ONLY when both of these are measured:

1. the failing test method, run unmodified in situ against the ORIGINAL R8,
   changes nothing — full inventory before and after equal on every field
   including `mtime_ns`; and
2. run unmodified in situ, it passes.

If either does not hold, the failure is an R8 internal defect and is treated
as one. A read-only assertion measured in the architecture it describes is a
stricter measurement than the same assertion measured in a copy of it, not a
looser one. No assertion is skipped, disabled, or exempted; every one of the
361 must pass somewhere, and the location is chosen so the assertion means
what it says.
