# REF-12 / L1-A29 targeted closure report

Date: 2026-08-27  
Mode: `TARGETED_REF12_L1_A29_ONLY`

## Outcome

L1-A29 remains blocked. The supplied DOCX is technically valid and its bytes match the stated expected SHA-256, but the required `REF-12_OPERATOR_PROVENANCE.txt` and `REF-12_MANIFEST.sha256` files are absent from the intake directory. The missing records prevent validation of the REF-12 manifest, internal consistency of the operator record, lawful R7 binding, and evidence/plan construction.

No R7 file was changed. The measured readiness therefore remains 31/35.

## Narrow intake validation

- Intake directory physical entries: one regular file, `376_DKB MH.docx` (52,412 bytes).
- Physical DOCX count: exactly one.
- DOCX symlink: no.
- DOCX zero-byte: no.
- `REF-12_OPERATOR_PROVENANCE.txt`: missing.
- `REF-12_MANIFEST.sha256`: missing; validation cannot pass.
- SHA-256 by `sha256sum`: `0b8403982880761b1e2bc31d8c15b756fad0fe12259d55d1611323a4e768b3ca`.
- SHA-256 by Python standard-library streaming `hashlib.sha256`: the same value.
- Expected-value comparison: equal to the expected value stated for this intake.
- File identification: Microsoft Word 2007+.
- OOXML validation: ZIP integrity passed; required `[Content_Types].xml`, `_rels/.rels`, and `word/document.xml` members exist; all XML and relationship parts parsed successfully.
- Document content was not extracted into this report.

## Authoritative specification determination

The active prompt `prompts/L1-A29.md` expressly permits identity from an operator statement (REF-12) or case material. It requires two independent hashing methods, the operator's stated expected value with provenance, positive/negative/mutation controls, and an unchanged target hash. It does not require an older standalone historical hash manifest.

The limitation that no older standalone historical hash manifest was located remains valid. That limitation does not negate a properly documented operator-supplied source-host measurement. In this intake, however, the required on-disk operator provenance record is absent, so its internal consistency cannot be verified and the binding cannot yet be made.

## Focused rehearsal

The approved methods from L1-A27 were used: `sha256sum` and an independent Python standard-library streaming SHA-256 computation.

- Both methods agreed on the source DOCX and equaled the stated expected SHA-256.
- Positive control: both methods produced the standard SHA-256 of the empty file, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Negative control: both methods distinguished an empty file from a one-byte `x` file.
- Mutation control: both methods detected a one-byte mutation in a temporary copy; the mutated hash was `6463413d06265f98b688c12984a7a9bd8b3318271607d7ad140e5edf4ce5685e`.
- Source SHA-256 before and after: unchanged.
- `state/progress.json` SHA-256 before and after: unchanged at `2c69d95eb3b1b35362a2ad7306db85460a552e06a90173d79eebd885e274f8fe`.
- Evidence/plan construction: blocked by the two missing required intake records; no live plan or audit evidence was constructed.

Because the focused rehearsal requirement includes successful evidence/plan construction, the composite `TWO_METHOD_REHEARSAL` result is FAIL even though the two hashing computations and all three controls passed.

## Scope and state

Only REF-12 and authoritative L1-A29 records were read. No full search, unrelated validation, controller suite, package suite, all-audit readiness run, or pre-freeze verification was performed. No shared executable code changed. R7 remains `GENERATED_UNVERIFIED`; it was not frozen, and no live audit phase advanced.

R7 REF12 / L1-A29 TARGETED CLOSURE COMPLETE

REF12_MANIFEST_VALID:
NO

REFERENT_IDENTITY_ESTABLISHED:
NO

REFERENT:
376_DKB MH.docx

EXPECTED_SHA256:
0b8403982880761b1e2bc31d8c15b756fad0fe12259d55d1611323a4e768b3ca

EXPECTED_HASH_PROVENANCE:
PARTIAL

TWO_METHOD_REHEARSAL:
FAIL

POSITIVE_CONTROL:
PASS

NEGATIVE_CONTROL:
PASS

MUTATION_CONTROL:
PASS

SOURCE_HASH_UNCHANGED:
YES

REF12_STATUS:
PARTIAL

L1_A29_READINESS:
BLOCKED

AUDITS_READY_FOR_PLANNING:
31/35

REMAINING_GATES:
L1-A23 — Mac evidence package transfer and focused binding; L1-A11 — human BGH period/provenance decision; L1-A24 — human external-launch-directory decision; L1-A29 — transfer and validate REF-12 operator provenance and manifest

SHARED_CONTROLLER_EXECUTABLE_CHANGED:
NO

FULL_CONTROLLER_SUITE_RERUN:
NO

R7_MODIFIED:
NO

R7_FROZEN:
NO

LIVE_AUDIT_PHASE_ADVANCED:
NO

NEXT_REQUIRED_ACTION:
Transfer REF-12_OPERATOR_PROVENANCE.txt and REF-12_MANIFEST.sha256 into the REF-12 intake directory, preserving their source-host bytes.

FINAL_STATUS:
R7_REF12_L1_A29_STILL_BLOCKED
