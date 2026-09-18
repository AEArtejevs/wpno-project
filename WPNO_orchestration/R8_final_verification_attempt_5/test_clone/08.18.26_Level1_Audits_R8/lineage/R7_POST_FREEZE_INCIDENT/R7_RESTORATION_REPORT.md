# R7 post-freeze in-place repair incident — restoration report

**Classification:** `POST_FREEZE_CONTROL_PLANE_MODIFICATION_INCIDENT`
**Date:** 2026-08-28 · **R8 created:** no

## What happened

R7 was frozen at 2026-08-28T09:14:39Z with its control manifest verified at
15804/15804. A defect was then found in the frozen execution engine: the
controller never performed `IN_PROCESS` operations. The human authorised
repairing the execution engine. That repair was implemented **in place inside
frozen R7**, which the authorisation did not cover. The repair should have
been made in a superseding R8 revision.

**R7 must not be described as having uninterrupted post-freeze immutability.**
It was modified after freeze. The final bytes match the frozen manifest again
only because the original bytes were restored from a proven backup.

## What was modified

Manifest-covered files changed in place:

| path | frozen sha256 | dirty sha256 |
|---|---|---|
| `automation/controller.py` | `aff9bc25…991f06` | `e8be79f3…4a5e63` |
| `build/rehearse_candidate_plans.py` | `acfab6ef…219199` | `4b164c6b…9e51f3d` |

New control-plane files created:

| path | sha256 |
|---|---|
| `automation/in_process_ops.py` | `4269ad5e…9f0ea4e` |
| `automation/package_tests/test_r7_in_process_ops.py` | `2f9d06d0…4b9d1aad` |

Manifest-listed files missing: 0. Bytecode attributable to the repair: 0 — all
51 bytecode files under control-plane directories predate the freeze (newest
2026-08-27T07:22:55Z); `PYTHONDONTWRITEBYTECODE=1` was set on every command.
None were removed.

## Preservation

All four dirty files were copied byte-for-byte to
`dirty_repair_files/`, preserving their relative R7 paths, with digests in
`DIRTY_REPAIR_FILES.sha256` and unified diffs in `DIRTY_REPAIR_DIFFS/`. The
substantive findings — the engine defect, the candidate repair, the two plan
defects and the control-expectation weakness — are in `REPAIR_FINDINGS.json`.

## Restoration

The backup at `/home/ubuntu/R7_repair_backup_2026-08-28` was validated before
use: each source file exists, is not a symlink, and **its SHA-256 equals the
digest the frozen control manifest records for that relative path**, and
differs from the repaired copy. Restoration wrote to a temporary sibling,
fsynced, verified the hash, renamed atomically over the dirty file, and
verified the destination hash again. The two new files were removed only after
preservation was hash-verified and their absence from the frozen manifest
confirmed.

No file under `state/`, `results/`, `evidence/`, `work/` or `logs/` was
restored, removed or overwritten.

## Verified final state

```
MODE                          FROZEN   (entry matches frozen manifest)
CONTROL_MANIFEST              15804/15804 OK, 0 failed, 0 missing
Unlisted control-plane source 0
L1-A31 RUN-A                  SEALED / UNVERIFIED / intact (33 files)
L1-A31 RUN-B                  SEALED / UNVERIFIED / intact (5 files)
L1-A31 COMPARISON             EXECUTED / unsealed / 0 evidence files
Other phases started          0
Approvals                     3 records, 3 distinct, no replay
R4 1915/1915 OK · R5 14158/14159 · R6 14781/14781 · 0 files modified today
```

R5's single mismatch is `MODE`, mtime 2026-08-26T17:20:07Z — two days before
this incident, arising because `MODE` is published after the manifest that
lists it. Not caused by and not touched during this incident.

## Consequences

- The incident must be carried into R8 lineage and named in R8's final
  verification.
- R7 is a restored predecessor. No further live execution may occur in it.
- L1-A31 COMPARISON remains EXECUTED and unsealed with zero evidence. It was
  not sealed, and must not be sealed in R7.
- The two plan defects are to be fixed in R8 only.
