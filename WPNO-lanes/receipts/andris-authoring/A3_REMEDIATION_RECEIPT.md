# A3 Remediation Receipt — AP18 Impossible and Zero-Citation Handling

Date: 2026-09-01  
Lane: `/home/ubuntu/project/WPNO-lanes/andris-authoring`  
Finding: `L1-A13-RUN-A-F01`

## Scope

This remediation changed only the isolated AP18 authoring copy and its new focused test. The live WPNO source, baseline mirror, R9 controller, references, and sealed evidence were not modified.

## Reproduced defects

Before the fix:

- `IIII ZR 1/20` was classified as possible and allowed as unresolved.
- `14 StR 1/20` was classified as possible and allowed as unresolved.
- Seven punctuation, repeated-space, non-breaking-space, and line-break controls all escaped blocking.
- A text with zero citations reported that all BGH citations were verified.

The red phase produced nine assertion failures while the known-valid control remained green.

## Fix

- Restrict Roman civil-senate identifiers to canonical `I` through `XIII`, with the existing optional lowercase suffix.
- Restrict numeric criminal-senate identifiers to `1` through `6` for `StR` and `StB`; reject numeric identifiers for other BGH registers.
- Add an explicit zero-citation result: `KEINE AKTENZEICHEN GEFUNDEN — NICHTS GEPRUEFT`.
- Condense comments without changing behavior so the edited production file complies with the project rule requiring files under 500 lines.

## Source binding

- Starting source SHA-256: `f5eb5a9cbeb37cada9186ba305b9a307ea40e3012ca0e2e6dd0b2560f4352d74`
- Final source SHA-256: `3ac100df6b9fd6f0f428bb1ac4ba16dc1d5eb503767b853cdef80e6f61ad2ad5`
- Focused test SHA-256: `48d3921ba1c35b325a887d978f8ca89d7eb64a8a3264cf132dd05d292f045d15`
- Final line counts: source 468; focused test 114.

## Validation

- Six focused A3 tests passed.
- Thirteen combined A1–A3 tests passed under normal Python.
- The same thirteen tests passed under `python3 -O`.
- Valid `IV ZR 1/20`, `6 StR 1/20`, and the declared-present `I ZR 130/25` control remain allowed.
- All seven formatting variants for the two impossible forms are blocked with exit 1 and a semantic blocking report.
- A broad-Roman-numeral mutation reproduced the old false allowance and was detected.
- A zero-citation-success mutation reproduced the old misleading report and was detected.
- AST parsing passed. No trailing whitespace or secret-pattern match was found.

The historical `AP18_referenzpruefung_test.py` still depends on an external `zip` executable absent from the audited Ubuntu runtime. No package was installed. The new focused controls use only the Python standard library and do not replace the still-unavailable wider legacy run.

## Integrity and result

Post-change R9 verification returned `ok: true`, `tampered: []`, and 63 intact records out of 63 sealed attempts. Test-generated Python cache files were removed from the isolated lane.

Result: `COMPLETED_WITH_RUNTIME_LIMITATION`.

This is remediation evidence, not an R9 verdict. A fresh R10 audit must validate the changed target before any production-path PASS claim.
