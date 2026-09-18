# R8 — status after the authorised targeted convergence

Recorded 2026-08-28. Supersedes the earlier record of the same name, which
described the state before L1-A16 and the other recorded findings were
repaired. Every number below is read from the record that measured it.

---

## 1 · Every pre-freeze requirement passes

    43/43 plans valid, 0 missing, 0 duplicate, 0 unknown
    43/43 rehearsals PASS_READY
    169/169 in-process steps invoked their handler
    0 note-only in-process steps
    0 required in-process steps without evidence
    0 phases producing no evidence
    live R8 state unchanged by rehearsal
    122/122 control-role steps carry a machine-checkable expectation
    0 control steps unenforced
    0 steps reading outside their plan's declared allowance
    controller suite  503 ran / 0 failures / 0 errors / 0 skips
    package suite     361 ran / 0 failures / 0 errors / 0 skips
    static safety     0 findings, clean
    final manifest    724 entries, 0 missing / mismatching / malformed /
                      duplicate / unlisted / symlink, reconciles exactly
    R8 active state   35 audits, 43 phases, all NOT_STARTED
                      0 approvals, 0 results, 0 evidence, 0 raw tokens
    migration packet  prepared, bound, NOT applied and NOT consumed

## 2 · What was repaired this session

**L1-A16 — the blocking defect.** `prove_cases_are_novel` bound
`COMPARE_HASHES` to two directories and raised `IsADirectoryError`. It had
never executed in any revision: R7 deferred it for a missing input and the
deferral hid it. Beyond the type error, one directory digest against another
cannot answer a per-case question, and `ap18` is the AP18 source tree.

The specification names the corpus exactly — STATIC ANALYSIS 1: "ap18/
korpus_docx contains W1 hidden, W2 white text, W3 tiny font, W4 document
properties, W5 footnote, and two clean files". Classification:
**A — AN_EXISTING_ORIGINAL_SCOPE_REFERENCE_CORPUS_ON_SERVER**.

A generic operation `PROVE_SET_NOVELTY` now measures novelty per case by
content digest against that corpus, binding an expected entry count of 7 so
an absent, empty or resized corpus fails closed rather than making every
candidate look novel. Measured in rehearsal: reference set
`AP18_KORPUS_DOCX_W1_W5_PLUS_TWO_CLEAN`, 7 entries, hash-set digest
`12084436…`, five candidates all unique.

Three controls, all AS_EXPECTED, prove the measurement can tell the answers
apart: a novel case is accepted; a byte-identical copy of W1 is rejected; and
the same bytes under a different filename are still rejected — renaming being
the evasion a name-based check would miss.

**The six self-comparisons.** Six steps passed the same path as both operands
of `COMPARE_HASHES` and were therefore equal by construction; none could ever
fail. Three whose purpose is a genuine two-artefact comparison now compare
against the CMS-emitted copy of the covered content, which reaches the same
bytes by a different route and can therefore disagree. All six now bind
`expected_sha256`, so each can fail.

**The under-declared allowance.** L1-A17's envelope declared three
subdirectories while three of its steps scan the project root — which its
specification requires: "Record the search set exhaustively, including every
location searched and found empty, so absence is documented rather than
assumed." Absence cannot be shown by searching three subdirectories, so the
envelope was under-declared. It was corrected, two narrow paths introduced by
the L1-A33 repair were declared by exact filename, and the allowance is now
**enforced as a gate** rather than recorded as a finding. That is a
strengthening: a read outside what a plan declares is now refused.

**A false annotation of my own.** The earlier record said L1-A24's
`negative_control_impossible_file` carried an assertion its step could not
express. That was wrong: the step does carry `expect_absent`, and
`PARSE_JSON_READONLY` enforces it. The annotation described a real check as an
absent one and has been corrected.

**Two genuine package defects found while doing the above.**

- `freeze.py` read its predecessor baseline from `lineage/R6_EXECUTION/`, a
  physical tree R8 does not carry, so the freeze path could not build a
  baseline at all. R8 now carries the predecessor's baseline itself — one
  12 KiB file, byte-identical to R7's, digest-bound in the lineage record —
  which keeps the "read only your own package" rule without the 555 MiB copy.
- Two build scripts moved from `build/resume_r7/` to `build/` kept three
  `dirname` calls and resolved ROOT to the directory above the package.

## 3 · The test suites were retargeted, not weakened

50 failures and errors at the start of this session, classified before any
test was touched:

| cause | count | disposition |
|---|---|---|
| depends on the physical `lineage/R6_EXECUTION` tree | 18 | retargeted to the hash-bound resolver, which verifies the recorded digest before returning a path |
| reads R7-specific records excluded from R8 | 16 | retargeted to R8's equivalents |
| asserts R7 is final / R8 absent | 2 | rewritten as the finality *rule*: the successor of the declared final revision must not exist |
| the 42/43 rehearsal status | 1 | fixed by repairing L1-A16 |
| a magnitude literal (`> 1000` manifest entries) | 1 | replaced by a membership assertion — every control-plane executable and schema must be inside the manifest |
| other | 12 | retargeted individually |

No test was deleted, none was skipped, and no integrity assertion was
loosened. `generation_root` now also resolves R4, which it could not before.

## 4 · The migration route

`automation/migration.py`, driven by the controller route
`import-sealed-predecessor-attempt`. It runs only after R8 is FROZEN — it
refuses while MODE is GENERATED_UNVERIFIED, which is what keeps the pre-freeze
43/43 NOT_STARTED invariant true while it is being claimed.

It admits an attempt on its merits, not by name: sealed, evidence manifest
verifies, seal covers that manifest, target and every bound reference stable,
plan binds no operation the frozen controller could not perform, and one real
operation record per required step. R7's L1-A31 COMPARISON fails the first of
those and is excluded with the measured reason
`EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`.

30 tests cover it, including a counter-proof that the synthetic predecessor is
admissible when clean — without which the in-process refusal would only prove
the fixture was malformed.

Packet is prepared and bound; `state/migrations.jsonl` does not exist, so
nothing has been consumed.

---

## 5 · The one thing blocking the freeze token

**A fresh Codex verification is required, and the authorised maximum of three
attempts is used up.**

Three attempts were made:

| attempt | result | why |
|---|---|---|
| 1 | FAIL, 22/30 | It ran the suites and the static-safety review with their default outputs, which write into `build/`, and then correctly reported the manifest mismatch it had caused itself. A real process finding. |
| 2 | FAIL, 28/30 | Both remaining failures were in the shape of its own checks; every value it measured was correct. |
| 3 | **PASS, 30/30, unresolved_findings []** | `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` |

Attempt 3 verified build manifest `796fd1301ac148eb76eaa7bf0b947c1559d6820e547e4bccf0595fa4e5a45d91`.

After it passed, I found and repaired the freeze-plan builder's ROOT defect —
it computed the project root instead of the package root and could not be
imported at all. Repairing it meant moving it into `build/freeze_plan_attempt_1/`,
the excluded directory where a freeze-plan builder belongs, and that changed
the package. The final manifest is now
`6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a`.

The freeze token binds three digests: the build manifest, the verification
result, and the freeze plan. Issuing it now would bind a verification result
to a manifest that verification never examined — an artefact asserting a check
that did not happen against these bytes. So the token has **not** been
generated, and the freeze plan built against the superseded manifest was
discarded rather than left to be read as current.

**Decision required: authorise a fourth fresh Codex verification.** Nothing
else is outstanding. On a pass, the freeze plan and token follow directly.

---

## 6 · Predecessors, re-verified after all work

    R4  FROZEN  1915/1915    0 mismatching
    R5  FROZEN  14159/14160  1 mismatching — MODE only, the historical
                             freeze-order defect, dated 2026-08-26
    R6  FROZEN  14781/14781  0 mismatching
    R7  FROZEN  15804/15804  0 mismatching

No file under R4, R5, R6 or R7 was modified. R9 does not exist. R7's
post-freeze modification incident is carried in
`lineage/R7_POST_FREEZE_INCIDENT` (15/15 verified) and R8 nowhere claims R7
had continuous post-freeze immutability.
