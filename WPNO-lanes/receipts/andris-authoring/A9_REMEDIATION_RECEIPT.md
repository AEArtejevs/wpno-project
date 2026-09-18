# A9 Remediation Receipt — AP16 Semantic Verification

- Scope: isolated Andris remediation lane only.
- Finding addressed: `L1-A02-RUN-A-F01`.
- Verifier input SHA-256: `f1bd18b05010c4607dbb1e2eb15cca89a6d5c9f35099b4937eb75f12b2478720`.
- Verifier output SHA-256: `fe528a72f4b75a377f7735698f33628aa1f26607eb0f8ec62279a570954c2c54`.
- Focused A9 test SHA-256: `d837d1e92bb3fc9651c91e004ff982cde1cda59e23f2b67cff9eec64bd8e9f08`.

## Requirement-contract decision

A9 was not blocked. `AP16_assemble_long_document.py` already defines an
explicit outline JSON input contract. The verifier now accepts that exact
outline through `--outline`; no document text, heading, party, amount, or case
content is hardcoded into the verifier.

## Red baseline

Before the change, eight focused expectations failed: altered body text,
renamed headings, stale TOC display, unresolved relationships, missing outline,
and malformed outline could all avoid a controlled semantic rejection. The
existing unnumbered-Antrag exit check already returned non-zero.

## Minimal change

- The outline schema is validated at the CLI boundary.
- Rubrum, Antrag text/order, heading text/level/order, per-section body text,
  and generated Anlage entries are compared with the supplied outline.
- A displayed TOC must contain every expected heading; empty or stale display
  cannot be called semantically verified.
- Every `r:id` referenced by the document must exist in the document
  relationship part. No relationship is resolved and no network is used.
- Missing or malformed contracts produce a controlled semantic `FAIL`.

The lane's starting verifier already contained pre-existing controlled
non-OOXML handling and non-zero semantic-failure exit behavior. A9 preserved
those safeguards.

## Validation

- Focused A9 suite: 8/8 passed under normal and optimized Python.
- Semantic-gate-bypass mutation: killed with seven failures.
- TOC-check-bypass mutation: killed with one failure.
- Relationship-check-bypass mutation: killed with one isolated failure.
- Cumulative authoring suite: 38/38 passed under normal and optimized Python.
- Cumulative AP18 suite: 10/10 passed under normal and optimized Python.
- Syntax compilation passed; verifier remains under 500 lines at 419.

The existing assembler, v6 template, and source-bound synthetic outline were
also run together in temporary storage. Assembly exited 0. Verification passed
Rubrum, Antraege, headings, section bodies, Anlagen, and relationships, but
correctly exited 1 because the server-produced DOCX has an unpopulated TOC.
This preserves the requirement for a real Word field update before a document
can be declared send-ready.

## Integrity

- Live and baseline verifier copies remained
  `f1bd18b05010c4607dbb1e2eb15cca89a6d5c9f35099b4937eb75f12b2478720`.
- R9 post-change verification: 63 sealed attempts, 63 intact, zero tampered.

Outcome: A9 code remediation complete in the isolated lane; Word TOC runtime
validation remains a separate external morning gate.
