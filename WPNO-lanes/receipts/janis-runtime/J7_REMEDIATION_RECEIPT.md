# J7 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 finding: `L1-A26-RUN-A-F01`
- Result: `SUCCESS_LANE_PENDING_INTEGRATION`

## Red evidence

The old detector compared only two literal paths. The new four-test detector
suite initially failed entirely because no six-role inventory existed. A
subsequent full-tree check exposed and fixed an internal detector defect that
incorrectly counted immutable audit-package fixtures as source candidates.

## Change

- Added `scripts/payload_scanner_inventory.py` with the exact six audited
  roles: canonical active, active alias, golden test asset, two ALT backups,
  and the historical pre-fix copy.
- Required every active copy and the golden asset; optional backup/historical
  absence is reported explicitly rather than silently ignored.
- Historical differences are reported as intentional non-active differences,
  not treated as active-copy drift.
- Undeclared source-tree scanner copies fail the detector.
- Immutable Level-1 audit packages and cache/control directories are excluded
  from source discovery; `.git` is never traversed.
- Added focused tests for active alias drift, historical-difference reporting,
  undeclared copies, and audit-package exclusion.

## Proof

- Focused Mac J7 suite: 5 passed.
- Focused Ubuntu J7 suite: 5 passed.
- Full Mac lane suite: 31 passed.
- Full Ubuntu lane suite: 31 passed.
- Isolated lane inventory: `ok=true`, six declared roles, zero unexpected.
- Active-alias drift and undeclared-copy mutations both produce exit 1.
- A synthetic full six-file tree reports non-active differences and exits 0.
- Read-only live-tree check now sees exactly the six governed copies and zero
  unexpected source copies. It correctly exits 1 because live WPNO has not yet
  received J5's alias integration; backups/historical copies are reported,
  not failed.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- `scripts/payload_scanner_inventory.py`: baseline absent, final
  `45dbfe1bf04ec46d5dbed426477a78dc10d24bba295fb67efe223ed0c9bfb097`.
- `anonymization/test_payload_scanner_inventory.py`: baseline absent, final
  `3b5dc37f020f9e056aa38cda50e04f075bc4b64d51ea081dfdcb273040d395b9`.

## Limitations

- The isolated lane is green; the untouched live WPNO tree is intentionally
  still pre-integration and therefore reports `ACTIVE_ALIAS_DRIFT` until the
  morning integration gate applies J5/J7 changes.
- This receipt does not alter sealed R9.
