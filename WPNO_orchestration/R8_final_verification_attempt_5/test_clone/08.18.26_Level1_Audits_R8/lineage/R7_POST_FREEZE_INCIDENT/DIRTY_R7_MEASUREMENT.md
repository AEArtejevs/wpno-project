# Dirty R7 measurement

Classification: `POST_FREEZE_CONTROL_PLANE_MODIFICATION_INCIDENT`
Measured: 2026-08-28T12:24:15Z · MODE on disk: `FROZEN` · frozen at: 2026-08-28T09:14:39Z
Control manifest entries: 15804

## Manifest-listed files changed in place (2)

| path | frozen expected | current dirty | size | mtime | change | backup candidate |
|---|---|---|---|---|---|---|
| `automation/controller.py` | `aff9bc25271e76ed…` | `e8be79f3a1748c91…` | 89103 | 2026-08-28T11:45:37Z | MODIFIED_IN_PLACE_AFTER_FREEZE | `/home/ubuntu/R7_repair_backup_2026-08-28/automation/controller.py` |
| `build/rehearse_candidate_plans.py` | `acfab6efed4d08c5…` | `4b164c6beefd006e…` | 24866 | 2026-08-28T12:02:29Z | MODIFIED_IN_PLACE_AFTER_FREEZE | `/home/ubuntu/R7_repair_backup_2026-08-28/build/rehearse_candidate_plans.py` |

Manifest-listed files missing: **0**

## New control-plane files (2)

| path | sha256 | size | mtime | why attributed to the repair |
|---|---|---|---|---|
| `automation/in_process_ops.py` | `4269ad5e3da4892e…` | 29658 | 2026-08-28T12:05:01Z | absent from the frozen control manifest; created 2026-08-28 during the in-place execution-engine repair; mtime falls after frozen_at_utc |
| `automation/package_tests/test_r7_in_process_ops.py` | `2f9d06d07b676571…` | 15324 | 2026-08-28T11:56:19Z | absent from the frozen control manifest; created 2026-08-28 during the in-place execution-engine repair; mtime falls after frozen_at_utc |

## Bytecode

Measured: 51. Created after the freeze: **0**.

All 51 bytecode files predate frozen_at_utc (newest 2026-08-27T07:22:55Z). None is attributable to the repair; PYTHONDONTWRITEBYTECODE=1 was set on every command. None will be removed. Their absence from the frozen manifest is a pre-existing condition of the freeze, not part of this incident.

## Exclusions

Mutable subdirectories excluded from repair attribution: `state`, `results`, `evidence`, `work`, `logs`, `verification`. A file under these is not classified as a repair file merely because it is absent from the control manifest.
