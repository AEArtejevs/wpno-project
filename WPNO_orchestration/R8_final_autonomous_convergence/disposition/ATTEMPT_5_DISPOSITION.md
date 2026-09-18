# Attempt 5 — disposition

    CLASSIFICATION: VERIFICATION_HARNESS_DEFECT
    NOT:            R8_PACKAGE_DEFECT

`ATTEMPT5_ROOT` is preserved unchanged. Nothing below it was edited, moved or
deleted to write this record. This file is the disposition; it is not a
re-measurement of attempt 5 and it does not re-run anything.

## Defect 1 — the disposable clone was placed outside the required sibling layout

`08.18.26_Level1_Audits_R8/paths.json` is location-relative:

    project_root    ".."
    discovery_root  "../08.18.26_Discovery"
    level1_root     "."

`automation/path_policy.py` resolves those three values at import time against
the directory that holds `paths.json`. A copy of the package therefore carries
its roots with it: move the package and the roots move too.

Attempt 5 placed the clone at

    ATTEMPT5_ROOT/test_clone/08.18.26_Level1_Audits_R8

so the three roots resolved to

    PROJECT_ROOT    ATTEMPT5_ROOT/test_clone                       (holds only the clone)
    DISCOVERY_ROOT  ATTEMPT5_ROOT/test_clone/08.18.26_Discovery    (does not exist)
    LEVEL1_ROOT     the clone

and R4, R5, R6 and R7 were not siblings of the clone, and
`PROJECT_ROOT/.gitignore` did not exist. Item 19 (package suite) reported
343 tests / 1 failure / 47 errors / 0 skips. The error families Codex named —
predecessor paths rejected as outside allowed roots, missing predecessor
sibling packages, absent project `.gitignore` — follow from the placement.
Items 20 and 28 were routed to the same clone and carry the same defect;
item 20 never ran.

The remedy is a placement, not a change to R8: the clone must be a direct
sibling of R8 below `/home/ubuntu/project/WPNO/`, so that `project_root`
resolves to the real project root, Discovery exists at the expected sibling
path, R4–R7 are visible as siblings, and the project `.gitignore` is present —
while every test write is still absorbed by the clone, because
`WRITE_ROOTS = (LEVEL1_ROOT,)` and `LEVEL1_ROOT` is the clone.

## Defect 2 — a relative stat path measured the wrong file (item 33)

Codex recorded the control file's "after" state by stat-ing the relative path

    work/_selftest/unicode_fs_behaviour.txt

which resolved to the clone's root-level `work/_selftest/…` rather than

    verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt

The recorded "after" mtime `1787925319844038458` is therefore EARLIER than the
recorded "before" mtime. An mtime that runs backwards is impossible for a file
that was written between the two observations; it is proof that the two
observations did not address the same file. The item was nevertheless marked
passing.

The remedy is the absolute-path measurement rule now in force: every stat, hash
and comparison records the requested path, its resolved absolute path and the
root it belongs to, and `after_mtime_ns < before_mtime_ns` invalidates the
check instead of passing it.

## What attempt 5 established, and what it did not

Established and carried forward as OBSERVED, not re-derived here:

- R8 was not written to. 1362 paths, pre- and post-inventory digest
  `cdb922d08e90b8cd8c7a755be63b5fb64da23a38748c24006140b00ea837fcf7`,
  0 added / 0 removed / 0 contents changed / 0 mtimes changed.
- Build manifest `6dfd1af6…5b945a`, 724 entries, 724/724 valid.
- Controller suite 503 / 0 / 0 / 0 in the replica.
- The write barrier was shown to refuse a write before it was relied on.

NOT established: R8's substantive pre-freeze state. 31 of 34 items were never
measured. `NOT VERIFIED` is not `FAILED`. Attempt 6 remeasures the full gate
from scratch; nothing above is accepted in place of a fresh measurement.

## Neither defect is recorded inside R8

R8 is not modified to carry these findings. They are harness findings and they
live here.
