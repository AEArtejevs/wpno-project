# 12 — OPEN ITEMS THIS BUILD DID NOT CHANGE

Things noticed during the R2 and R3 builds that are real, that are outside what
each build was authorised to repair, and that were therefore recorded rather
than silently altered. Each names what was seen, why it was left alone, and who
decides.

R3 was authorised to repair exactly two things: the Unicode NFC/NFD self-test
(PV-002) and the missing build-time Git HEAD field (PV-001). Everything else
that R2 resolved is preserved unchanged, and everything R2 left open is still
open. O-01 to O-03 are carried forward verbatim in substance; O-04 is new and
belongs to R3.

Recording them here is the point. A build that quietly fixes what it was not
asked to fix leaves the next reader unable to tell which changes were
authorised.

---

## O-01 — `LC_ALL=C.UTF-8` in the controller's fixed child environment

**What is there.** `automation/policy.py` sets, in `ENV_FIXED`:

```python
"LC_ALL": "C.UTF-8",
"LANG": "C.UTF-8",
```

**Why that is worth recording.** `CLAUDE.md` § 8 states, for this machine:

> **Kein `C.UTF-8` auf macOS.** `LC_ALL=C.UTF-8` faellt still auf ASCII
> zurueck und zerstoert jeden Umlaut. Richtig: `en_US.UTF-8` oder
> `de_DE.UTF-8`.

So the project's own instruction file says this value is wrong on this
platform, and the controller sets it anyway. The predecessor package shipped
the same value.

**Why neither R2 nor R3 changed it.** Three reasons, and none of them is that
the concern is unfounded:

1. It is not one of VF-001 to VF-011, and it is neither of the two blockers R3
   was authorised to repair. Each mandate is to repair what was found and to
   preserve everything else.
2. `automation/tests/test_codex_adapter.py::TestEnvironmentInjection::test_fixed_values_override_the_caller`
   asserts `env["LC_ALL"] == "C.UTF-8"` verbatim. Changing the value would
   require editing that assertion, and editing an assertion to match a changed
   implementation is the exact pattern both rebuilds are forbidden to use.
3. The effect is bounded and does not touch any decision the controller makes.
   It affects how a child process's output is decoded when that output contains
   non-ASCII characters. It does not affect a path, a hash, an approval, a
   verdict, or a state transition.

**What it could actually cause.** A subprocess whose stdout or stderr contains
umlauts — a German filename in a `file` or `git` output, a German string in a
tool's error message — could be decoded with mangled characters in the evidence
record. The bytes on disk are written unmodified by
`evidence.EvidenceRecorder`, so the raw evidence survives; the risk is to the
readability of a decoded excerpt, not to the integrity of the stored bytes.

**Who decides.** The operator. The change is two string literals in
`policy.py` plus the corresponding assertion in the self-test. It is a
deliberate, reviewable edit and should be made as one, not folded into a
repair build.

---

## O-02 — the redaction marker in the R2 rebuild instruction differs from the marker the self-test requires

**What the instruction said.** The R2 rebuild instruction, § 13, states:

> The exact required marker must remain stable: `[[REDACTED:IBAN]]`

with two brackets on each side.

**What the package actually uses, and has always used.** One bracket:
`[REDACTED:IBAN]`. This is the value produced by `automation/redaction.py` and
the value asserted by
`automation/tests/test_redaction.py::TestRedactionIsBlunt::test_replacement_carries_no_original_characters`:

```python
self.assertEqual(out, "[REDACTED:IBAN]")
```

The predecessor's failing test output shows the same single-bracket
expectation on the right-hand side of the diff.

**What R2 did.** Kept `[REDACTED:IBAN]`, and fixed the defect the finding was
actually about. VF-004 is that the IBAN marker was being re-matched by the BIC
rule and rewritten to `[[REDACTED:BIC]:IBAN]`. R2 rebuilt redaction as a single
combined pass in which an already-written marker is the first alternative and is
returned verbatim, so no rule can rewrite another rule's output. The marker is
now stable under repeated application, which is what "remain stable" asks for.

**Why not simply adopt the double-bracket form.** Because doing so would have
required editing the assertion in the retained self-test to match a changed
implementation, and § 24 of the rebuild instruction forbids exactly that. The
single-bracket value is also what every existing test, and the predecessor's
recorded failure diff, treats as correct. Changing it is a contract change, not
a repair.

**Who decides.** The operator. If the double-bracket marker is genuinely
wanted, the change is `MARKER_TEMPLATE` in `redaction.py`, the `MARKERS` tuple
beside it, the `_MARKER_PATTERN` guard, and the two assertions that name the
literal. R2 added `TestMarkerStability::test_marker_set_matches_the_pattern_kinds`
so that the marker set and the pattern set cannot drift apart whichever value
is chosen.

---

## O-03 — the R2 source manifest includes `audit_output/`

**What was decided.** The R2 source manifest scope excludes `.git`, the
Discovery root, the failed predecessor package, and this package. It does not
exclude `audit_output/` at project root.

**Why.** The rebuild instruction says to exclude "all Level-1 runtime/audit-output
directories". Every Level-1 runtime directory (`state`, `results`, `evidence`,
`work`, `logs`, `verification`) is inside one of the two Level-1 roots and is
therefore already excluded. `audit_output/` at project root is a different
thing: it holds two files, `audit.json` and `report.md`, neither of which
references either Level-1 root. It is a project artefact.

**Consequence, stated so it is not mistaken for an oversight.** Including it
means a later write into `audit_output/` would show up as a source-manifest
difference. That is the conservative direction: a false alarm is recoverable,
a blind spot is not.

**Who decides.** The verifier, if it disagrees. The scope is stated exactly in
`00_CODEX_VERIFY_LEVEL1_PACKAGE.md` and in `11_DISCOVERY_DRIFT.md` entry D-05,
so a disagreement is visible rather than silent.

---

## O-04 — what "all audit runtime-output roots" was taken to mean for the R3 source manifest

**What was decided.** The R3 build instruction says the source-manifest scope
must exclude `.git`, the Discovery root, R1, R2, R3 and "all audit
runtime-output roots". R3 excluded exactly the five named roots and nothing
else. `audit_output/` at project root remains **inside** the scope, as it was
in R2.

**Why.** Every Level-1 runtime-output directory — `state/`, `results/`,
`evidence/`, `work/`, `logs/`, `verification/` — lives inside one of the three
Level-1 roots and is therefore already excluded by excluding those roots. The
phrase adds nothing further unless it is read as also excluding
`audit_output/`, and that directory is a project artefact unrelated to
Level-1; it is the subject of O-03.

**What this preserves.** The scope is byte-identical to R2's, plus the R3 root.
That is what makes the cross-check possible: the R3 build-start source manifest
was compared against R2's build-end source manifest and found identical over
48,682 entries. Had the scope been widened or narrowed, that comparison would
have been meaningless, and the strongest available evidence that the project
source is unchanged since R2 would have been thrown away.

**Consequence, stated so it is not mistaken for an oversight.** If the verifier
reads the phrase the other way, the two manifests will differ from its own
recomputation by exactly the `audit_output/` entries. That is a disagreement
about scope, not a contamination finding, and it is visible rather than silent.

**Who decides.** The verifier, if it disagrees. The scope is stated exactly in
`00_CODEX_VERIFY_LEVEL1_PACKAGE.md` and in `11_DISCOVERY_DRIFT.md` entry D-05.
