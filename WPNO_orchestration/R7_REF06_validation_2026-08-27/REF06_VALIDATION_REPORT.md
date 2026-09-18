# REF-06 targeted validation report

Validation date: 2026-08-27  
Scope: REF-06 only, for R7 L1-A14  
R7 modification: none

## Result

`REF06_STATUS: PARTIAL`

The supplied package is internally sound: its SHA-256 manifest validates, all three DOCX files independently hash to `9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc48722675`, and binary comparison confirms that they are byte-identical. `REF-06_S01.docx` is a valid OOXML DOCX ZIP package with all archive members passing integrity testing.

The original Microsoft Word extended-properties metadata in `docProps/app.xml` records `<Pages>111</Pages>`. Therefore `WORD_STORED_PAGE_COUNT` is 111. No parser- or renderer-produced page count was used or substituted. The historical description of approximately 110 pages is consistent with this Word-stored value; the specification does not impose an invented exact-110 rule.

The authoritative L1-A14 identity/count requirement is not satisfied. Applying the R7 rule described below produced 165 total citation occurrences and 64 unique citations, rather than the stated identity hypothesis of 82 hits and 43 unique citations. This mismatch is capable of changing whether this is the exact version required by L1-A14, so REF-06 cannot be accepted for intake closure.

## Authoritative R7 specification and binding

- Prompt: `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7/prompts/L1-A14.md`, SHA-256 `a75e99676d280abba87381a7ae92e27612c4753ece7289c095608fa79d9446e7`.
- Binding: `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7/bindings/L1-A14.binding.json`, SHA-256 `aa92cd401aa9a878711fd7a1b439c676b076e6696dbd68fa9a44f7e7f2c5c700`.
- Intake specification: `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7/build/all_level1_scope/R7_ALL35_INPUT_READINESS.md`, SHA-256 `ca585b0afc70cf6d815449560d69b2128712285b976d42e54b309ab7363c6096`.

The prompt requires independent extraction from `word/document.xml`; enumeration using a citation grammar based on the structural rules of German case references; review of every candidate; separate counts for total occurrences and unique citations; and court classification from the court designator. It expressly treats “43 unique citations, 82 hits” as a hypothesis to test, not an assumed result. The intake specification requires the real checker-input DOCX, described as approximately 110 pages with 43 unique citations, and the exact version against which the counter was run.

## Counting application

Text was read directly from the OOXML main document without opening or modifying the DOCX. A citation occurrence was accepted only where the candidate contained the structural identity fields of a German court decision: issuing-court designator, decision date, and register sign. Candidates were reviewed against those structural fields rather than accepted merely because a production-counter pattern matched. Uniqueness was determined by the normalized tuple `(court designator, decision date, register sign)`; repeated appearances of the same tuple remained separate occurrences.

- `TOTAL_CITATION_OCCURRENCES: 165`
- `UNIQUE_CITATIONS: 64`

This is the independent L1-A14 enumeration. The production counter was not used as the oracle and no live audit was run.

## Provenance conclusion

`REF-06_PROVENANCE.txt` identifies the three copies as the S01 checker input, AFNA uploaded-source copy, and iCloud source copy. Their byte identity independently shows that those three named copies contain the same bytes. Together, this supports—without conclusively proving—the claim that the supplied S01 was an original checker input. Accordingly, `ORIGINAL_CHECKER_INPUT_SUPPORTED: YES`. This conclusion does not establish a stronger chain of custody or overcome the citation-count identity mismatch.

## Intake bookkeeping

No operator-intake manifest update was made. The existing `OPERATOR_MATERIAL_MANIFEST.json` has no REF-06 entry and no lawful REF-06 status field, and the acceptance condition was not met. No unrelated status was touched.

## Classification

- Manifest valid: YES
- Three-way byte identity: YES
- Word-stored page count: 111
- L1-A14 requirement satisfied: NO
- Original checker input supported: YES
- REF-06 status: PARTIAL

Next required action: Supply the exact checker-input DOCX that independently enumerates to 82 total citation occurrences and 43 unique citations under the authoritative L1-A14 rule.
