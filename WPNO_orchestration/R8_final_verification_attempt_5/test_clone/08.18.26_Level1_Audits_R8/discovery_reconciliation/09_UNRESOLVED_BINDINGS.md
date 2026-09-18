# 09 — UNRESOLVED BINDINGS

Every audit whose binding is not `TARGET_CONFIRMED`, with the exact reason and
the exact thing that would resolve it. Nothing here is hidden from
`00_BUILD_STATUS.md`.

Counts:

```text
TARGET_PARTIAL              = 8
TARGET_UNRESOLVED           = 2
EXTERNAL_EVIDENCE_REQUIRED  = 10
TARGET_MISSING              = 1
UNRESOLVED_BINDINGS (total) = 21
```

## TARGET_PARTIAL — target set known, production identity or material incomplete

| audit | what is bound | what is missing | resolver |
| --- | --- | --- | --- |
| L1-A03 | three exporter files, hashed | which is productive; and whether a v3 ever existed | caller evidence, or operator statement of the invocation used in practice |
| L1-A04 | depends on A03 | the productive TOC producer, and a generated document to compare against | resolve A03 first; generate the document in the audit work directory |
| L1-A08 | guardrail v3 | the five edge cases do not exist | author them in the audit work directory; they are synthetic |
| L1-A09 | guardrail v3 | "every relevant article" is not a defined set | enumerate the pattern set from the v3 source by static parse; that enumeration is the audit's own evidence |
| L1-A10 | the single checker copy, its test, its reference JSON | a caller | none exists in-tree; likely unresolvable from this machine, in which case say so |
| L1-A12 | the checker | a real article corpus with recorded origin | operator-supplied corpus; the in-tree `ap18/korpus*` is synthetic and built for a different tool |
| L1-A13 | the checker | the five mandatory fabricated-citation strings as fixtures | construct in the audit work directory; synthetic, no client data |
| L1-A16 | the corpus builder and the existing 7-file DOCX corpus | five *new* cases | author them; they must not repeat W1–W5 |

## TARGET_UNRESOLVED — the question is runtime and cannot be answered statically

| audit | why | resolver |
| --- | --- | --- |
| L1-A21 | image ID, digest, creation timestamps and container mapping need the Docker socket, which is forbidden | operator-exported Docker metadata, imported via `DOCKER_METADATA_IMPORT`. Absent it: `UNVERIFIED_DOCKER_PRODUCTIVE_COPY` |
| L1-A24 | which instruction file a Claude Code process loads from a given directory is a runtime property | `CLAUDE_LOAD_BEHAVIOUR_TEST` under human approval, plus a recorded Claude Code version, plus an operator-approved external launch directory bound in the plan and hashed before and after. User configuration must not be modified |

## EXTERNAL_EVIDENCE_REQUIRED — specification complete, material absent

| audit | material required |
| --- | --- |
| L1-A11 | an official BGH roster for the checked period, offline, with recorded source identity and hash. Comparing against `bgh_referenz.json` does not qualify — that is a project artefact, not an official source |
| L1-A14 | the real 110-page, 43-citation document, identified and hashed by the operator. It is a client Schriftsatz |
| L1-A27 | the exact ZIP archive |
| L1-A28 | the signed content, encapsulated or detached, plus the CMS structure |
| L1-A30 | the archive to inspect for AppleDouble entries |
| L1-A31 | leaf certificate, intermediates, trust anchor, and revocation evidence if any |
| L1-A32 | the CMS/PKCS#7 object with all SignerInfo entries |
| L1-A33 | the OSCI container and `563203462.xml` |
| L1-A34 | `vhn.xml.p7s` and the content it covers |
| L1-A35 | source copy, destination copy, and copy metadata from 17.08 |

A27–A35 were searched for across all 6295 files in all eight Discovery scan
roots via `02_FILE_INVENTORY.csv` and `18_HASH_INVENTORY.csv`. Zero hits for
`p7s`, `vhn`, `563203462`, `osci`, `pkcs7`. The rest of the Mac was not
searched, by instruction — so this is "not in scope", not "does not exist".

## TARGET_MISSING

| audit | why |
| --- | --- |
| L1-A29 | `376` has no referent anywhere on this machine. It is not a filename, not a path fragment in the inventories, and not defined in any project document read during this build. The audit's own first step is to establish what `376` denotes; if it cannot, the required verdict is `BLOCKED_376_TARGET_UNIDENTIFIED` |

## What this means for starting Level-1

Fourteen audits (A01, A02, A05, A06, A07, A15, A17, A18, A19, A20, A22, A23,
A25, A26) are bound to confirmed targets and can be planned immediately.
Execution still requires the human approval token for every gated operation.

Twenty-one audits carry an unresolved element. Eleven of those (A11, A14,
A27–A35) cannot start at all without operator-supplied material, which is nine
of the last nine points plus two citation audits. That is a material limit on
Level-1 coverage and it is stated in `00_BUILD_STATUS.md` rather than absorbed.

## What this does **not** block

None of the twenty-one unresolved bindings blocks verification of this package.
Verification checks the control plane: structure, manifests, schemas,
controller behaviour and the self-test suite. Missing operator material makes
individual audits `BLOCKED` or `UNVERIFIED` when they later run. It does not
make the package unverifiable, and a verifier must not treat it as such.
