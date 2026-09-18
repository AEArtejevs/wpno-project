# J1 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner after recorded transfer: Andris
- Writing agent: Codex
- R9 finding: `L1-A22-RUN-A-F01`
- Result: `SUCCESS`

## Red evidence

- Default Mac pytest collection: exit 0, seven tests collected, golden program absent.
- Explicit collection of `anonymization/golden/payload_scan_golden_test.py`:
  exit 5, zero tests collected.
- Ubuntu `/usr/bin/python3 -m pytest`: unavailable because pytest is not installed
  for the system interpreter. No package was installed.

## Change

- Added `anonymization/test_payload_golden.py` as a conventional pytest wrapper.
- The wrapper stages the byte-identical canonical scanner with the existing
  synthetic golden party-name fixture; production party-name data is not changed.
- The wrapper runs the standalone golden program and includes an allow-all
  mutation control.

## Proof

- Focused Mac run: 2 passed.
- Default Mac collection: 9 tests collected, including both J1 tests.
- Focused Ubuntu run through the already-existing read-only pytest launcher:
  2 passed.
- Default Ubuntu collection: 9 tests collected, including both J1 tests.
- Ubuntu lane regression: 9 passed.
- Independent allow-all mutation of `blocked = len(hits) > 0` to
  `blocked = False`: the positive golden pytest test failed, with all 202
  synthetic PII payloads reported as leaks.
- Syntax compile: passed.
- Ordinary baseline comparison: only
  `anonymization/test_payload_golden.py` was added.
- R9 evidence verification after the change: `ok=true`, `tampered=[]`,
  `sealed=63`, `intact=63`.

## Hashes

- Baseline `anonymization/test_payload_golden.py`: absent.
- Final `anonymization/test_payload_golden.py` SHA-256:
  `3871001831150acbca05b87c81435f5158b8bf79638e8d274496e8b3f0bdd1c8`.
- Canonical scanner remained unchanged at:
  `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b`.
- `pytest.ini` remained unchanged at:
  `3259aae6b1feea94c78ee30440a63e82f2e4d5a4caa5a291820307c83323f227`.

## Limitations

- This is remediation evidence, not a rewritten R9 verdict.
- Ubuntu testing used the already-present frozen-style pytest launcher and
  existing WPNO orchestrator site-packages. No dependency was installed.
