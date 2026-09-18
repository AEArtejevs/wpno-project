# L1-A11 BGH Decision Closure Report

## Scope and outcome

This was a targeted L1-A11 delta review only. The human decision and its manifest are valid, and the excluded organigram was not used. The two accepted PDFs are official BGH material, but they do not document the approved period through 2026-08-27. L1-A11 therefore remains blocked and R7 was not modified.

## Human-decision verification

- Decision JSON: parsed successfully; schema `wpno.r7.human-decision/1`, audit `L1-A11`, decision `APPROVED`.
- Approved inclusive period: 2026-01-01 through 2026-08-27.
- Operator fields: `operator=Andris`; `recorded_utc=2026-08-27T21:55:14+00:00`.
- Decision manifest: all three entries verified with `sha256sum -c`.
- Accepted reference set: exactly two PDFs.
- Both PDFs exist, are regular files, are not symlinks, and match their decision-record hashes.
- `2026_07_01_Externe_Organigramm_GV.pdf` is excluded and was not inspected or used.

## Bound PDF findings

### Geschäftsverteilungsplan

- SHA-256: `b103cc8b193fcfef62d9d57f5c809c925ba170394a1fe2badba9c66305d27ed5`.
- Structural result: PDF 1.7; terminal `startxref` and `%%EOF` present; compressed page streams decompressed successfully for content inspection.
- Internal title: `GESCHÄFTSVERTEILUNGSPLAN des Bundesgerichtshofs für das Geschäftsjahr 2026`.
- Issuer: Bundesgerichtshof, established from internal document text rather than filename.
- Document year and temporal scope: business year 2026. Embedded metadata records creation and modification on 2025-12-18.
- Status: ACCEPTED as the official annual baseline plan for 2026.

### Präsidium decisions

- SHA-256: `da9f847e6532bfacfc6f3a8f55edba9c3ad5f346b2242f5918668c938e7b6d18`.
- Structural result: PDF 1.7 with linearized structure, page objects, terminal `startxref` and `%%EOF`; compressed content streams decompressed successfully.
- Internal issuer: `DIE PRÄSIDENTIN DES BUNDESGERICHTSHOFS`.
- Document year: 2026.
- Internal decisions inspected include 2026-01-27, 2026-02-24, 2026-04-28, 2026-06-17, 2026-07-07, and the latest decision dated 2026-08-11.
- Latest internal issue/publication date: 2026-08-18, on the document reporting the 2026-08-11 decision. Embedded metadata also records modification on 2026-08-18.
- Status: PARTIAL for the approved period because no bound documentary statement, publication, or amendment establishes coverage after 2026-08-18.

## Coverage and readiness decision

The annual plan and decisions together are an independent official BGH oracle in source identity and substance: they identify the BGH internally, contain the 2026 allocation plan, and carry official BGH Präsidium amendments. They are not, however, a complete oracle for the human-approved period ending 2026-08-27.

Measured documentary coverage ends on 2026-08-18. The exact uncovered range is 2026-08-19 through 2026-08-27, inclusive. The human decision expressly does not waive such a gap. REF-05 is therefore PARTIAL, and the authoritative L1-A11 requirement for an official roster covering the claimed period remains unsatisfied.

No REF-05 record, L1-A11 binding, readiness record, status summary, or R7 manifest was changed. The authoritative readiness remains 33/35, with L1-A11 and L1-A24 as the remaining gates. A focused rehearsal is not required because readiness did not advance and no binding byte changed.

## Focused checks

- L1-A11 decision-manifest verification: PASS.
- Two-PDF existence, regular-file, non-symlink, and hash checks: PASS.
- Structural/content inspection: PASS for inspectability and provenance; PARTIAL for approved-period coverage.
- Changed-record schema validation: NOT APPLICABLE; no R7 record changed.
- Focused L1-A11 readiness: BLOCKED.
- Focused rehearsal: NOT_REQUIRED.
- Arithmetic reconciliation: 33 ready + 2 remaining gates = 35 total.

## Next required action

Provide a hash-bound official BGH publication or amendment statement establishing complete coverage for 2026-08-19 through 2026-08-27, inclusive.
