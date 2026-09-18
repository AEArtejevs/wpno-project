# HUMAN_GATE: ALL_LEVEL1_REQUIRED_EXTERNAL_MATERIAL

R7 · UBUNTU · MODE GENERATED_UNVERIFIED · live progress 0/35

Every readiness task that does not depend on this material is finished. The C9 finding is closed, the 35-audit scope is derived and internally consistent, the build manifest is regenerated and verifies entry for entry, and static safety is clean. What follows cannot be measured, reconstructed, downloaded or stood in for.

    HUMAN_GATE: ALL_LEVEL1_REQUIRED_EXTERNAL_MATERIAL

    MISSING_ITEM_COUNT: 8

    AUDIT_ID: L1-A19
    REF_ID: REF-03
    ROLE: Official ISO 7064 formula for the exact tax-ID scheme, once the scheme is identified
    EXACT_REQUIRED_CONTENT: Official ISO 7064 formula for the exact tax-ID scheme, once the scheme is identified
    ACCEPTABLE_FORMAT: PDF
    ACCEPTABLE_SOURCE: ISO 7064, plus the issuing authority's specification of the identifier (for the German steuerliche Identifikationsnummer: the Bundeszentralamt für Steuern specification)
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A19 (ISO 7064 tax-ID check-digit correctness) requires REF-03: Official ISO 7064 formula for the exact tax-ID scheme, once the scheme is identified. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A19
    REF_ID: REF-04
    ROLE: Independent check-digit test vectors for that scheme
    EXACT_REQUIRED_CONTENT: Independent check-digit test vectors for that scheme
    ACCEPTABLE_FORMAT: TXT/CSV
    ACCEPTABLE_SOURCE: official specification examples, or an independent implementation's vectors
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A19 (ISO 7064 tax-ID check-digit correctness) requires REF-04: Independent check-digit test vectors for that scheme. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A17
    REF_ID: REF-14
    ROLE: Production configuration export where static files are insufficient, redacted
    EXACT_REQUIRED_CONTENT: Production configuration export where static files are insufficient, redacted
    ACCEPTABLE_FORMAT: JSON/TXT
    ACCEPTABLE_SOURCE: the operator
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A17 (Production invocation path of the input filter) requires REF-14: Production configuration export where static files are insufficient, redacted. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A21
    REF_ID: REF-13
    ROLE: Docker metadata export: image ID, image digest, image and container creation timestamps, mounts, entrypoint, command, build-context evidence
    EXACT_REQUIRED_CONTENT: Docker metadata export: image ID, image digest, image and container creation timestamps, mounts, entrypoint, command, build-context evidence
    ACCEPTABLE_FORMAT: JSON
    ACCEPTABLE_SOURCE: `docker inspect` output produced **by the operator**, outside the audit
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A21 (Docker productive copy and image provenance) requires REF-13: Docker metadata export: image ID, image digest, image and container creation timestamps, mounts, entrypoint, command, build-context evidence. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A11
    REF_ID: REF-05
    ROLE: Official BGH roster covering the period the register claims
    EXACT_REQUIRED_CONTENT: Official BGH roster covering the period the register claims
    ACCEPTABLE_FORMAT: PDF/HTML saved offline
    ACCEPTABLE_SOURCE: Bundesgerichtshof official publication
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A11 (BGH_REGISTER completeness versus an independent official roster) requires REF-05: Official BGH roster covering the period the register claims. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A12
    REF_ID: REF-07
    ROLE: A real article corpus with independent labels
    EXACT_REQUIRED_CONTENT: A real article corpus with independent labels
    ACCEPTABLE_FORMAT: folder + label file
    ACCEPTABLE_SOURCE: operator-selected real documents; labels produced **not** by the checker under test
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A12 (Broad-pattern false positives on a real article corpus) requires REF-07: A real article corpus with independent labels. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A23
    REF_ID: REF-14
    ROLE: Production configuration export where static files are insufficient, redacted
    EXACT_REQUIRED_CONTENT: Production configuration export where static files are insufficient, redacted
    ACCEPTABLE_FORMAT: JSON/TXT
    ACCEPTABLE_SOURCE: the operator
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A23 (CLAUDE.md rules versus actual Mac reality) requires REF-14: Production configuration export where static files are insufficient, redacted. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    AUDIT_ID: L1-A29
    REF_ID: REF-12
    ROLE: A definition of what `376` refers to, plus the artefact itself
    EXACT_REQUIRED_CONTENT: A definition of what `376` refers to, plus the artefact itself
    ACCEPTABLE_FORMAT: statement + artefact
    ACCEPTABLE_SOURCE: the operator
    INTAKE_PATH: references/
    WHY_REQUIRED: L1-A29 (Independent 376 hash remeasurement) requires REF-12: A definition of what `376` refers to, plus the artefact itself. Without it the audit's independent oracle does not exist, and its verdict could only be a statement about the tool under audit.

    WAITING_FOR_HUMAN_MATERIAL

## Human directory gate status

**L1-A24 — CLAUDE.md loading outside the project root.** The human directory gate is closed. The operator approved `/Users/martinotten/Downloads`, and that exact path is present in the previously measured Mac candidate evidence with `directory_exists=true` and `directory_symlink_status=false`. The directory is now bound for planning. Its pre-run and post-run manifests remain requirements of the later approved live audit; no live result is claimed here.

## What the absence of each item means when its audit runs

These consequences are the package's own, from `discovery_reconciliation/10_REQUIRED_OFFLINE_REFERENCES.md`. They are recorded here because they bear directly on what a completed Level-1 run can be.

| audit | reference | absence ⇒ |
| --- | --- | --- |
| L1-A19 | REF-03 | `BLOCKED_SCHEME_IDENTITY_UNCERTAIN` |
| L1-A19 | REF-04 | `BLOCKED` |
| L1-A17 | REF-14 | `UNVERIFIED` |
| L1-A21 | REF-13 | `UNVERIFIED_DOCKER_PRODUCTIVE_COPY` |
| L1-A11 | REF-05 | `BLOCKED_MISSING_OFFICIAL_REFERENCE` |
| L1-A12 | REF-07 | `UNVERIFIED` |
| L1-A23 | REF-14 | `UNVERIFIED` |
| L1-A29 | REF-12 | `BLOCKED_376_TARGET_UNIDENTIFIED` |

That same document states, in its own words, that none of this material is required to verify and freeze the package: *"External references are not part of the immutable control plane. Their absence today makes certain individual audits BLOCKED or UNVERIFIED when those audits later run; it does not block verification, and a verifier must not report it as a package defect."*

And rule 6 of the same document: *"Unavailable is never recorded as present. An item not delivered is recorded as absent with its consequence, and the audit that needs it returns BLOCKED or UNVERIFIED. There is no state in which a missing reference is treated as satisfied."*

## The consequence for a 35/35 PASS

Section 14 permits the control-plane freeze only at `AUDITS_BLOCKED=0`, and Section 18 permits the final seal only at `ALL_35_FINAL_VERDICTS=PASS`. With this material absent, eight audits remain blocked — not because the harness fails, but because each one's own criteria require an independent oracle or target that is not on this machine. Recording them as ready would be the one thing every rule in this package exists to prevent.

Two routes are open, and the choice is the operator's:

1. **Supply the material.** The nine items above, at `references/`, each with its SHA-256 in an operator manifest. Readiness is then re-measured and the run continues from Section 8.
2. **Redefine completion.** Freeze and execute against the audits that can be answered, and record the rest as BLOCKED with their consequences, which is what the package's own rules describe as a legitimate and complete outcome. This is not the `35/35 PASS` the instruction names, and it is not a change this session may make on its own.

Nothing was frozen. No phase was prepared, approved, executed or sealed. R4, R5 and R6 are byte-identical to the digests lineage recorded. No R8 was created.
