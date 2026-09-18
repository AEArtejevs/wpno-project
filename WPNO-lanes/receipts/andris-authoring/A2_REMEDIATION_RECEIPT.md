# A2 Remediation Receipt — AP17 Citation Blocking

Date: 2026-09-01  
Lane: `/home/ubuntu/project/WPNO-lanes/andris-authoring`  
Scope: isolated remediation copy only; the live WPNO source and sealed R9 package were not modified.

## Findings addressed

- `L1-A05-RUN-A-F01`: the known-bad citation `VII ZR 100/12` was accepted.
- `L1-A05-RUN-A-F02`: unresolved citations did not block release.
- `L1-A06-RUN-A-F01`: the known-bad positive control was accepted.

## Root cause

`AP18_referenzpruefung.aktenzeichen_finden()` returns `(docket, context)` tuples. AP17 compared those tuples directly with string-key reference maps, causing declared present and declared absent citations to be treated as unresolved. AP17 then explicitly allowed unresolved citations to continue.

## Change

- Normalize finder output to the docket string before reference-map lookup.
- Treat every unresolved citation as blocking pending evidence.
- Preserve the separate A1 missing/malformed-config handling.

No package, dependency, user configuration, controller, audit evidence, or unrelated source file was changed.

## Source binding

- A2 input source SHA-256 (after A1): `aaebbc54bfeeacf81f221c9c2904b3ccc1028d87a2608c0e6220350edf332cfd`
- A2 output source SHA-256: `d77c09816055638ff560cbc080626881b1663ecea6f1293315ef52738bd9bdf1`
- A1 regression test SHA-256: `7d4bad5b2b80072aaea604eacc7b782443acef5c4b7c020008fcfd71d3d20472`
- A2 focused test SHA-256: `6ac29f34a781de9a1b554fecb165f2264e84ea4516065e11df0b890361a17472`

## Test evidence

- Red phase: three focused tests failed before the source fix.
- Green phase: seven combined A1+A2 tests passed under normal Python.
- Optimized mode: the same seven tests passed under `python3 -O`.
- Positive control: the declared-present citation `I ZR 130/25` is allowed.
- Negative control: declared-absent `VII ZR 100/12` is blocked with non-zero exit.
- Unknown control: an unlisted citation is blocked with non-zero exit.
- Mutation 1: restoring the tuple-shape mismatch was detected by the test suite.
- Mutation 2: disabling the unresolved-citation block was detected by the test suite.
- AST parsing passed; changed files are below 500 lines; no trailing whitespace or secret-pattern match was found.

The broader legacy scripts `WPNO_versionsvergleich_test.py` and `AP18_referenzpruefung_test.py` cannot start on the audited server runtime because the external `zip` executable is absent. The server also lacks `pytest`. No package was installed. These are recorded runtime limitations, not A2 passes or failures.

## Integrity and status

After testing, `automation.controller verify-evidence` returned `ok: true`; all 63 sealed R9 attempts were intact with zero reported difference. Test-generated `__pycache__` content was removed from the isolated lane.

Result: `COMPLETED_WITH_RUNTIME_LIMITATION`.

This receipt records remediation evidence only. It is not an R9 audit verdict. A fresh R10 audit is required before any production-path PASS claim.
