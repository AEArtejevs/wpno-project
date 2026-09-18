# Attempt 5 — result: FAILED

    HUMAN_GATE: R8_ATTEMPT_5_FAILED

No freeze plan was created. No token was generated. Nothing was repaired and
nothing was re-run. `freeze_output/` is empty.

---

## What failed

Item 19, the package suite. Required 361 / 0 / 0 / 0. Measured in the
disposable clone:

    343 tests, 1 failure, 47 errors, 0 skips

Codex stopped there, as the instructions required, so items 1–17, 20–30 and 34
were never measured. They are NOT VERIFIED. That is not the same as FAILED and
must not be read as one.

## Where the defect is

The defect is in **attempt 5's own verification instructions**, which I wrote —
not, on this evidence, in R8's bytes.

`automation/path_policy.py` derives its roots at import time from
`paths.json`, and every value there is **relative to the package directory**:

    project_root    ".."
    discovery_root  "../08.18.26_Discovery"
    level1_root     "."

Run from `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8` those resolve to
the real project root, the real discovery root, and the real package. Run from
`ATTEMPT5_ROOT/test_clone/08.18.26_Level1_Audits_R8` the same three lines
resolve to:

    PROJECT_ROOT    ATTEMPT5_ROOT/test_clone          — contains only the clone
    DISCOVERY_ROOT  ATTEMPT5_ROOT/test_clone/08.18.26_Discovery — does not exist
    LEVEL1_ROOT     the clone

and the predecessor packages R4, R5, R6, R7 are not siblings of the clone. That
accounts for the observed error families exactly, in Codex's own words:
"predecessor paths were rejected as outside allowed roots, the clone did not
have predecessor sibling packages under its parent, and baseline construction
reported the project `.gitignore` absent." The single assertion failure was an
absolute ORIGINAL work path in L1-A01/RUN-A `run1` judged outside the CLONE
work root — the same cause.

Item 19 asked for a location-relative package to be exercised from a different
location. The suite reported that faithfully. The instruction was wrong.

Items 20 and 28 were routed to the clone for the same reason and carry the same
defect. Item 20 never ran.

This is a *diagnosis of the failure*, not a re-measurement of it. The suite was
not re-run, in the clone or anywhere else.

## Why the clone was used at all

Because attempt 4's defect was that the controller suite rewrote a
manifest-covered file inside R8. Running the suites in a clone removes that
write. Item 18 shows the approach is not wrong in general: the controller suite
ran in the clone and gave **503 / 0 / 0 / 0**, matching the record exactly. The
controller suite declares its own roots through the replica's own `paths.json`;
the package suite reaches outside the package, and that is the difference.

## What attempt 5 did establish

These were measured and stand on their own.

- **R8 was not written to.** Full inventory of all 1362 paths — 961 files and
  401 directories — before and after, on type, size, SHA-256, symlink target,
  mode, uid, gid and mtime to the nanosecond:

      paths added 0 · paths removed 0 · contents changed 0
      mtimes changed 0 · modes changed 0 · symlink targets changed 0
      uid changed 0 · gid changed 0

  Pre-inventory and post-inventory hash to the same digest:
  `cdb922d08e90b8cd8c7a755be63b5fb64da23a38748c24006140b00ea837fcf7`.
  Codex measured the same independently and its 724-file fold digest was
  `c6f1ce02…d2d21b` before and after, 0 changed paths.

  **This is the condition attempt 4 could not prove, and it now holds.** No
  mode was touched; the file attempt 4 allowed to be rewritten inside R8 was
  not written here, and its mtime did not move.

- The write barrier was shown to refuse a write before it was relied on. Both
  arms fired: inside the workspace root a write succeeded; outside it the
  kernel returned `Read-only file system`.

- Manifest `6dfd1af6…5b945a`, 724 entries, 724/724 valid, before and after —
  measured by me and, independently, by Codex's own parser.

- Controller suite 503 / 0 / 0 / 0.

## A second defect, in attempt 5's execution

Item 33's recorded evidence is wrong even though its conclusion is right.

Codex recorded the control file's "after" state by stat-ing the relative path
`work/_selftest/unicode_fs_behaviour.txt`, which resolved to the clone's
**root-level** `work/_selftest/…` — a different file, untouched since
13:55:19Z — rather than
`verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt`. So the
"after" value it reports, `1787925319844038458`, is earlier than the "before"
value it reports. An mtime that runs backwards should have been caught before
the item was marked passing.

The conclusion happens to be correct: the intended file's mtime in the clone
did move, from `1787935556841911690` (16:45:56Z) to 18:07:42Z, and its bytes
still match ORIGINAL. The control did fire. But the number written into the
result does not show that, and a pass resting on the wrong file is not a pass.

## What is NOT claimed

- R8's substantive pre-freeze state is NOT VERIFIED by attempt 5. 31 of 34
  items were not measured.
- Nothing here says R8 is defective. Nothing here says R8 is sound either.
- Attempt 4's substantive result is not revived by this. It remains superseded
  on procedure.

## Next

The human decides. Attempt 5 is spent; per the standing instruction it is not
re-run, not repaired, and no plan or token follows from it.

If a further attempt is authorised, the instruction that needs correcting is
narrow and now identified: the package suite (item 19), the static-safety run
(item 20) and the freeze-module check (item 28) cannot be executed from a
relocated copy, because the package resolves its project, discovery and
predecessor roots relative to its own directory. A clone placed as a **sibling
of R8** — under `/home/ubuntu/project/WPNO/` — would resolve all three
correctly while still absorbing every test write, and would keep the controller
suite's result unchanged. That is a statement of where the fault lies, not a
request to proceed.
