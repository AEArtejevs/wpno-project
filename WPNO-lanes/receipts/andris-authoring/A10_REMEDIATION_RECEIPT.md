# A10 Remediation Receipt — Canonical AP18/AP16/AP17 Gate

- Scope: isolated Andris remediation lane only.
- Findings addressed: productive-path limitations in L1-A01, L1-A02, and
  `L1-A17-RUN-A-F01`.
- Input-filter input SHA-256: `623ae5b3392340360aabf408476dd6ff7a324b063407f6ec48e8e0ef23a99807`.
- Input-filter output SHA-256: `2d098cc9109fa832e7885bf157d8135fd773ceb0b17a143ff493fe3acb6e1957`.
- Canonical gate SHA-256: `60aa1d6bfe08f4a38dff3ec2176fcca52d05e35bc18e0cf43d3e8c15aaffe1ba`.
- Gate test SHA-256: `d9220ba0715c20482785f296874ce654e0111a5ba472b9fd716d3786cdaa281d`.

## Red baseline

No `scripts/wpno_document_gate.py` existed in the isolated lane. The AP18
input filter also returned zero for `PRUEFEN`, so an operator launcher relying
only on its process status could not fail closed on review-required input.

## Minimal change

- AP18 gained an opt-in `--fail-on-review` flag. Existing direct CLI behavior
  is unchanged unless the flag is supplied.
- The new canonical launcher validates every input path and keeps AP18 and AP17
  SQLite files separate.
- It verifies immutable hashes for the AP18 input filter, AP16 verifier, AP17
  output guard, AP18 reference classifier, and AP18 reference data.
- It runs AP18 input filtering first, AP16 semantic verification second, and
  AP17 output guarding with AP18 full reference classification third.
- It stops immediately and returns the non-zero child result at every gate.
- Existing report files are never overwritten.

The launcher requires a final DOCX whose Word fields/TOC have already been
updated. It does not invoke Word, deploy, start a service, access credentials,
or perform network activity.

## Validation

- Focused A10 suite: 5/5 passed under normal and optimized Python.
- Clean pipeline control passed in the required AP18 -> AP16 -> AP17 order.
- AP18 `PRUEFEN` stopped before AP16/AP17.
- AP16 semantic failure stopped before AP17.
- AP17 rejection propagated after AP16 passed.
- Component-hash mutation failed before any gate executed.
- Four launcher mutations were killed independently: review flag removal,
  AP16 stop removal, AP17 stop removal, and hash-check removal.
- Cumulative authoring suite: 38/38 passed under normal and optimized Python.
- Cumulative AP18 suite: 10/10 passed under normal and optimized Python.
- Cumulative launcher suite: 5/5 passed under normal and optimized Python.
- Syntax compilation passed; every changed file remains under 500 lines.

## Integrity and activation boundary

- Live AP18 filter remained
  `a9ba953f66c03a552dff654f842b7648ab28cad5d2116d03764938d844bc5f92`.
- Baseline AP18 filter remained the same hash.
- R9 post-change verification: 63 sealed attempts, 63 intact, zero tampered.
- This receipt proves an isolated candidate operator path. Copying it into the
  real project and using it productively remain morning human approval gates.

Outcome: A10 complete in the isolated remediation lane; no production
activation was performed.
