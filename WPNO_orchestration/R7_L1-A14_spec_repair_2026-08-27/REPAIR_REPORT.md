# R7 L1-A14 targeted specification repair

## Outcome

REF-06 is **ACCEPTED** and L1-A14 is **READY_FOR_PLANNING**. This is readiness only; no live audit was run and no PASS verdict is claimed.

The unsupported historical `82_TOTAL_43_UNIQUE` expectation is preserved as `SUPERSEDED_UNSUPPORTED_EXPECTATION`. It was replaced only in active R7 normative control material with the recovered, source-bound oracle:

- DOCX SHA-256: `9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc48722675`
- Word stored page count: 111
- Total citation occurrences: 165
- Unique citations: 64
- Citation-counting rule changed: no

The correction record states the required reason: the real S01 checker input was recovered; the S01 checker object, AFNA uploaded source, and iCloud source copy are byte-identical; the unchanged authoritative citation-counting rule yields 165/64; and no source-bound original DOCX, hash, or measurement result supporting 82/43 was found. The earliest located historical assertion remains traceable at `PRUEFAUFTRAG_B_CODEX.md:701`, associated with `AP18_referenzpruefung.py`.

## Scope identification and repair

The active normative dependency chain was:

- `audit_registry.json`
- `bindings/L1-A14.binding.json`
- `prompts/L1-A14.md`
- `discovery_reconciliation/03_TARGET_BINDING_EVIDENCE.md`
- `discovery_reconciliation/10_REQUIRED_OFFLINE_REFERENCES.md`
- `references/README_REQUIRED_OFFLINE_REFERENCES_LV.md`
- `references/manifest.json`
- derived all-35 scope/readiness and human-gate bookkeeping
- R7 resume readiness bookkeeping

Historical project specifications containing 82/43 and all R7 lineage copies were left unchanged as historical evidence. R4, R5, and R6 were not modified. No shared controller executable or citation-counting implementation changed.

## REF-06 acceptance checks

- Operator manifest: valid; all three declared files match the authoritative hash.
- Three-way byte identity: verified.
- Package S01 copy: valid DOCX/ZIP with required Word members and no ZIP CRC error.
- Original checker-input provenance: supported by recovered S01/AFNA identity.
- Word stored page count: independently re-read as 111.
- Existing authoritative counting rule: established targeted server result 165 total / 64 unique; rule unchanged.
- Repaired binding, prompt, and manifest: match the source hash, page count, and measured counts.

## Targeted validation

- Static JSON parsing: passed for the changed binding and reference manifest.
- Binding schema/registry tests: 3 passed (`registry schema`, `all bindings validate`, `binding/registry agreement`).
- Scope generator: 35/35 discovered, zero missing specifications/bindings, zero contradictions.
- Readiness generator: passed; L1-A14 has no blocking reason.
- L1-A14 structural rehearsal: passed.
- Reconciliation manifest: all 13 entries verified.
- R7 build manifest: all 15,503 entries verified.
- Full controller suite: not rerun because no shared controller executable changed.
- Live audits/full evidence closure/all-35 rehearsal: not run.

## Readiness impact

Audits ready for planning: **27/35**. Remaining blocked audits and exact reasons:

- L1-A19 — `REFERENCE_ABSENT:REF-03`; `REFERENCE_ABSENT:REF-04`
- L1-A17 — `REFERENCE_ABSENT:REF-14`
- L1-A21 — `REFERENCE_ABSENT:REF-13`
- L1-A11 — `REFERENCE_ABSENT:REF-05`
- L1-A12 — `REFERENCE_ABSENT:REF-07`
- L1-A23 — `REFERENCE_ABSENT:REF-14`
- L1-A24 — `TARGET_NOT_READY:TARGET_CANDIDATES_PARTIALLY_ABSENT`
- L1-A29 — `REFERENCE_ABSENT:REF-12`; `TARGET_NOT_READY:TARGET_UNAVAILABLE_NO_CANDIDATE_NO_REFERENCE`

R7 L1-A14 SPEC REPAIR COMPLETE

OLD_EXPECTATION:
82_TOTAL_43_UNIQUE

OLD_EXPECTATION_PROVENANCE:
UNSUPPORTED

NEW_SOURCE_SHA256:
9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc48722675

NEW_WORD_STORED_PAGE_COUNT:
111

NEW_TOTAL_CITATION_OCCURRENCES:
165

NEW_UNIQUE_CITATIONS:
64

COUNTING_RULE_CHANGED:
NO

REF06_STATUS:
ACCEPTED

L1_A14_READINESS:
READY

AFFECTED_TESTS:
PASS

L1_A14_REHEARSAL:
PASS

SHARED_CONTROLLER_EXECUTABLE_CHANGED:
NO

FULL_CONTROLLER_SUITE_RERUN:
NO

AUDITS_READY_FOR_PLANNING:
27/35

REMAINING_BLOCKED_AUDITS:
L1-A19:REFERENCE_ABSENT:REF-03,REFERENCE_ABSENT:REF-04; L1-A17:REFERENCE_ABSENT:REF-14; L1-A21:REFERENCE_ABSENT:REF-13; L1-A11:REFERENCE_ABSENT:REF-05; L1-A12:REFERENCE_ABSENT:REF-07; L1-A23:REFERENCE_ABSENT:REF-14; L1-A24:TARGET_NOT_READY:TARGET_CANDIDATES_PARTIALLY_ABSENT; L1-A29:REFERENCE_ABSENT:REF-12,TARGET_NOT_READY:TARGET_UNAVAILABLE_NO_CANDIDATE_NO_REFERENCE

R7_MODIFIED:
YES

R7_FROZEN:
NO

LIVE_AUDIT_PHASE_ADVANCED:
NO

NEXT_REQUIRED_ACTION:
BUILD_AND_REHEARSE_L1-A14_RUN-A_CANDIDATE_PLAN
