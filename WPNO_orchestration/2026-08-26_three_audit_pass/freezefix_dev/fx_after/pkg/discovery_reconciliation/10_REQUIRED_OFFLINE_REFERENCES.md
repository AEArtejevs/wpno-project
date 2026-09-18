# 10 — REQUIRED OFFLINE REFERENCES

Machine-side index of the external material Level-1 needs. The operator-facing
version, in Latvian, is `references/README_REQUIRED_OFFLINE_REFERENCES_LV.md`.

Nothing in this list was downloaded. Level-1 runs with network disabled.
Every item must be placed under `LEVEL1_ROOT/references/` by the operator, with
a `manifest.json` derived from `references/manifest.template.json`.

**None of it is required to verify and freeze this package.** External
references are not part of the immutable control plane. Their absence today
makes certain individual audits `BLOCKED` or `UNVERIFIED` when those audits
later run; it does not block verification, and a verifier must not report it as
a package defect.

| id | audit | reference | acceptable source | date/version | format | absence ⇒ |
| --- | --- | --- | --- | --- | --- | --- |
| REF-01 | L1-A18 | IBAN specification and country registry (lengths, BBAN structure per country) | ISO 13616 registry as published by SWIFT as registration authority; or an equivalent official national publication | edition current at audit date; record it | PDF or TXT | BLOCKED |
| REF-02 | L1-A18 | Independent known-valid and known-invalid IBAN test vectors for ≥ 6 countries | official registry examples, or vectors from an independent standard implementation's test suite, offline | any | TXT/CSV | BLOCKED |
| REF-03 | L1-A19 | Official ISO 7064 formula for the exact tax-ID scheme, once the scheme is identified | ISO 7064, plus the issuing authority's specification of the identifier (for the German steuerliche Identifikationsnummer: the Bundeszentralamt für Steuern specification) | current | PDF | BLOCKED_SCHEME_IDENTITY_UNCERTAIN |
| REF-04 | L1-A19 | Independent check-digit test vectors for that scheme | official specification examples, or an independent implementation's vectors | any | TXT/CSV | BLOCKED |
| REF-05 | L1-A11 | Official BGH roster covering the period the register claims | Bundesgerichtshof official publication | must cover the register's claimed period; record both | PDF/HTML saved offline | BLOCKED_MISSING_OFFICIAL_REFERENCE |
| REF-06 | L1-A14 | The real 110-page document with 43 unique citations | the operator, from the case file | the exact version the counter was run against | DOCX (the checker's input) | BLOCKED |
| REF-07 | L1-A12 | A real article corpus with independent labels | operator-selected real documents; labels produced **not** by the checker under test | any | folder + label file | UNVERIFIED |
| REF-08 | L1-A31, L1-A34 | Trust anchor certificate(s) for the signing chain | the issuing CA, or the official beA/OSCI trust list | valid at the signature's claimed time | PEM/DER | UNVERIFIED_TRUST_CHAIN |
| REF-09 | L1-A31, L1-A32, L1-A34 | Intermediate certificates | as REF-08 | as REF-08 | PEM/DER | UNVERIFIED_TRUST_CHAIN |
| REF-10 | L1-A31 | CRL or OCSP evidence, if revocation is to be assessed | the CA, captured offline | as close to validation time as available | CRL/DER or OCSP response | revocation reported as `NOT_ASSESSED_OFFLINE`, not as "not revoked" |
| REF-11 | L1-A27, L1-A28, L1-A30, L1-A32, L1-A33, L1-A34, L1-A35 | The original beA/OSCI artefacts: the ZIP archive, `563203462.xml`, `vhn.xml.p7s`, the signed content, and the 17.08 source and destination copies | the operator, from the original case material, with chain of custody | the originals, not re-exports | raw bytes, unmodified | BLOCKED |
| REF-12 | L1-A29 | A definition of what `376` refers to, plus the artefact itself | the operator | — | statement + artefact | BLOCKED_376_TARGET_UNIDENTIFIED |
| REF-13 | L1-A21 | Docker metadata export: image ID, image digest, image and container creation timestamps, mounts, entrypoint, command, build-context evidence | `docker inspect` output produced **by the operator**, outside the audit | at audit time | JSON | UNVERIFIED_DOCKER_PRODUCTIVE_COPY |
| REF-14 | L1-A17, L1-A23 | Production configuration export where static files are insufficient, redacted | the operator | at audit time | JSON/TXT | UNVERIFIED |

## Rules that apply to every item

1. **No automatic download.** Network is disabled for Level-1. If an audit
   finds itself needing a reference it does not have, it stops and reports
   BLOCKED. It does not substitute model knowledge for a retrieved source.
2. **Hash on arrival.** Every file placed in `references/` gets its own SHA-256
   in `references/manifest.json`, recorded before use, and independently
   recomputed on arrival. That hash goes into the audit's evidence. For a
   directory or corpus, every file needs its own hash and the sorted inventory
   needs a collection hash. A missing, blank or mismatching hash makes the
   artefact unusable.
3. **An independent oracle may not come from the system under test.** Comparing
   `BGH_REGISTER` against `bgh_referenz.json` is not an independent oracle;
   both are project artefacts. Using `payload_scan.py` to generate expected
   IBAN results is not an independent oracle; it is the thing being measured.
4. **REF-06 and REF-11 are client material.** They fall under professional
   confidentiality. They are read inside the audit and their **content** is not
   copied into reports; only hashes, counts, structural facts and redacted
   locators are. Redaction is enforced by `automation/redaction.py`.
5. **`references/` is not covered by `BUILD_MANIFEST.sha256`.** It is operator
   input added after the build, so freezing it here would be false. It gets its
   own `manifest.json`. Only the two instruction files that ship with the
   package — `README_REQUIRED_OFFLINE_REFERENCES_LV.md` and
   `manifest.template.json` — are in the build manifest.
6. **Unavailable is never recorded as present.** An item not delivered is
   recorded as absent with its consequence, and the audit that needs it returns
   `BLOCKED` or `UNVERIFIED`. There is no state in which a missing reference is
   treated as satisfied.
