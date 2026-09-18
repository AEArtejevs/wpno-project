# A4 Remediation Receipt — AP18 Structural Citation Classification and Counting

Date: 2026-09-01  
Lane: `/home/ubuntu/project/WPNO-lanes/andris-authoring`  
Finding: `L1-A14-RUN-A-F01`

## Scope and oracle

The remediation used the sealed L1-A14 source-bound rule: an explicit issuing court followed within the same OOXML paragraph and within 80 characters by a decision date, dash, and docket. Identity is normalized court/date/docket. The live WPNO source, R9 package, baseline mirror, references, and sealed evidence remained read-only.

## Red reproduction

Before the A4 change, three focused controls failed:

- bare docket-like strings were counted as citations;
- court/date and docket split across paragraphs or beyond the 80-character boundary were counted;
- two distinct court/date/docket identities sharing one docket collapsed to one result.

The structured foreign-court positive control already behaved correctly.

## Fix

- Add the exact source-bound structural court/date/docket matcher.
- Deduplicate by normalized court/date/docket identity, not docket alone.
- Count only complete structural identities in the `gefunden`, `davon BGH`, and `uebrige` metrics.
- Preserve broad docket scanning as a separate safety signal: impossible BGH forms still block, while other incomplete docket mentions are explicitly listed as `NICHT ALS ENTSCHEIDUNGSZITAT GEZAEHLT` and excluded from citation totals.
- Preserve AP17's existing broad finder interface for the separately remediated A2 send-blocking path.

## Source binding

- A4 input source SHA-256 (after A3): `3ac100df6b9fd6f0f428bb1ac4ba16dc1d5eb503767b853cdef80e6f61ad2ad5`
- A4 output source SHA-256: `fd665e38687f14fe53ba45e9a9b8c3461ed7198a9bbd006d4718001ae84b647d`
- Updated A3 regression test SHA-256: `3223d789b5ee0986c68e422bd93b3a7b8cf6493ebcf7e7487e2459ef566d0406`
- A4 focused test SHA-256: `a93d0647b80190af2ef096807525952fa27409e850ea26a24f300314fab13b3d`
- Final line counts: source 463; A3 test 114; A4 test 109.

## Validation

- Five focused A4 tests passed, including a deliberate broad-scanner mutation.
- Eighteen combined A1–A4 tests passed under normal Python.
- The same eighteen tests passed under `python3 -O`.
- AST parsing passed. No trailing whitespace or secret-pattern match was found.
- Ordinary cumulative AP18 diff against the read-only lane baseline was reviewed.

The isolated candidate processed the exact real REF-06 input at SHA-256 `9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc48722675` and emitted only redacted aggregate validation data to the operator:

- structural unique identities: 64;
- BGH unique identities: 52;
- other-court unique identities: 12;
- `IX ZR 170/18`, `IX ZR 49/13`, and `IX ZR 78/20` were each classified as incomplete/non-structural and excluded from the BGH total;
- process exit 0 and no traceback.

These values match the accepted sealed L1-A14 oracle. This isolated agreement is remediation evidence only; it does not rewrite R9 or establish productive execution-path identity.

The historical `AP18_referenzpruefung_test.py` remains unable to start because the external `zip` executable is absent on the server. No package was installed.

## Integrity and result

Post-change R9 verification returned 63 intact records out of 63 sealed attempts, `ok: true`, and no tampering. Test-generated Python cache files were removed.

Result: `COMPLETED_WITH_RUNTIME_LIMITATION`.

A fresh R10 audit is required before a production-path PASS claim.
