# 11 — DISCOVERY DRIFT

Where the audit specification, the project's own documentation, or the Level-0
Discovery disagrees with what this machine actually contains. Each entry names
the claim, the observation, and which audit has to settle it.

No Discovery file was modified. Drift is recorded here, not corrected there.

Package revision R3. Every entry is carried forward from R2 unchanged except
**D-05**, which is a self-report about the build and is therefore re-measured
for R3. **D-08** — the bytecode cache — keeps the twelve-artefact measurement
R2 put in place of the predecessor's false summary; the verifier re-measures it
against the live cache rather than accepting the table.

---

## D-01 — `export_with_toc` v3 does not exist

**Claim.** Build prompt § 28: "`export_with_toc` v1-v4 productive-version
identification", implying four versions.

**Observation.** Three files exist: `AP16_export_with_toc.py`,
`_v2.py`, `_v4.py`. No `_v3.py` in any of the eight Discovery scan roots
(searched in `18_HASH_INVENTORY.csv`).

**Settles it.** L1-A03. It must report the actual version set, and must not
silently treat the unnumbered file as "v1".

---

## D-02 — `report_bad` and `report_good` do not exist as identifiers

**Claim.** Build prompt § 30 and § 31 name `report_bad` and `report_good` as
the known-bad and known-good inputs to the output guard.

**Observation.** `report_bad` appears nowhere in `PROJECT_ROOT`. `report_good`
appears once, in `docs/GODAUDIT_2026-08-10/runlog.jsonl` — a log about a past
audit run, not source. The in-tree equivalents appear to be the AP17 report
files (`AP17_report.md`, `AP17_report_v2.md`, `AP17_report_poisoned.md`) and
the poisoned-document builders (`AP17_make_poisoned_test.py`,
`AP17_make_poisoned_test_v3.py`), but "appear to be" is not evidence.

**Settles it.** L1-A05 and L1-A06 must first establish the mapping and record
it as evidence, or return `BLOCKED_TARGET_IDENTITY_UNCERTAIN`.

---

## D-03 — the payload_scan copy count

**Claim.** `CLAUDE.md` § 10, bullet 9: "`payload_scan.py` existiert in vier
Kopien." Build prompt § 45 lists six historical candidate paths, two of which
(`payload_scan_ERGAENZT_2026-08-04.py`, a bare `payload_scan.py`) do not exist
as named.

**Observation.** Six files carrying the scanner name exist, with four distinct
contents. Full table in `06_DUPLICATE_COPY_RECONCILIATION.md`.

**Settles it.** L1-A20 (enumeration and semantic equality) and L1-A26 (accuracy
of the nine error classes, of which this is class 9). Their findings must not
contradict each other; consolidation checks that.

---

## D-04 — Discovery's own completeness verdict versus this build's

**Claim.** Discovery `00_DISCOVERY_SUMMARY.md` point 10: "Sufficient inventory
for Level-1 35 audits: NO."

**Observation.** This reconciliation reaches
`SUFFICIENT_FOR_PROMPT_GENERATION`, which is a different question — see
`01_DISCOVERY_STATUS.md`. For *audit start*, this reconciliation agrees with
Discovery for 21 of 35 audits.

**Settles it.** Nothing. Both verdicts stand, and both are recorded.

---

## D-05 — the R3 build's effect on `git status --porcelain`, stated without a pre-existence premise

**Claim.** None — this is a self-report, and it replaces the R2 version of this
entry with R3's own measurements.

**What R1 claimed, and why it was withdrawn.** R1 described
`build_tmp/BASELINE_GIT_STATUS.txt` as a baseline against which the appearance
of exactly one new untracked path could be checked. That file was captured by
the same command that created the Level-1 directory, so it already contained
`?? 08.18.26_Level1_Audits/`. The independent verifier recorded this as VF-008.
R2 did not repeat the premise, and R3 does not repeat it either.

**What R3 captured.** Eight measurements, all under `build_evidence/`, and all
taken after `08.18.26_Level1_Audits_R3/` already existed:

```text
BUILD_START_GIT_HEAD.txt                HEAD at R3 build start
BUILD_START_GIT_STATUS.txt              porcelain at R3 build start, 37 lines
BUILD_START_SOURCE_MANIFEST.sha256      48,682 entries, content hashes
BUILD_START_DISCOVERY_MANIFEST.sha256   26 entries, content hashes
BUILD_END_GIT_HEAD.txt                  HEAD at R3 build end
BUILD_END_GIT_STATUS.txt                porcelain at R3 build end
BUILD_END_SOURCE_MANIFEST.sha256        same scope, recomputed
BUILD_END_DISCOVERY_MANIFEST.sha256     same scope, recomputed
```

The start HEAD is additionally recorded as `BUILD_TIME_GIT_HEAD` inside
`00_BUILD_STATUS.md`. R2 wrote it to the evidence file but not to the status
file, and its verification failed on exactly that omission (PV-001). A value
that lives in only one place cannot be cross-checked, which is the whole reason
the field is required.

**Scope.** The source manifest scope excludes, and only excludes: `.git`, the
Discovery root, `08.18.26_Level1_Audits`, `08.18.26_Level1_Audits_R2`, and the
R3 root itself. `audit_output/` at project root is **not** excluded — it is a
project artefact unrelated to Level-1, and including it means a later write
into it would be detected. That reading of "audit runtime-output roots" is
recorded as open item O-04 in `12_OPEN_ITEMS.md` rather than applied silently.

**The repository is dirty, and this entry says so.** The 37 porcelain lines at
build start are six tracked modifications and 31 untracked paths. All six
tracked modifications predate this build. Their content is unchanged between
the start and end source manifests, which is the stronger evidence; the
porcelain line for an already-modified file would not move even if the file
changed again, and that is precisely why the manifests, not porcelain, carry
the claim.

**One side effect, recorded rather than omitted.** The only Git commands this
build ran were `git rev-parse HEAD` and `git status --porcelain`, both
read-only with respect to the working tree. `git status` may refresh
`.git/index` as a side effect. `.git` is outside the source-manifest scope by
specification, so such a refresh is invisible to the manifests; it is named
here so that no reader concludes the manifests prove `.git` unchanged. HEAD
itself is compared start against end and is unchanged.

**The sentence that governs how this evidence may be described:**

> The R3 baseline was captured at R3 build start, excluding all audit infrastructure roots. It is not represented as a pre-existence Git snapshot.

**What the comparison establishes.** Content immutability of every file in
scope between build start and build end, by SHA-256 — which is a stronger and
more specific statement than porcelain equality. Porcelain status is recorded
separately, as a second and independent observation, and the two are never
merged into one claim.

---

## D-06 — `AppleDouble` in the project is unrelated to L1-A30

**Claim.** Build prompt § 55 audits AppleDouble detection.

**Observation.** The only occurrence of the string `AppleDouble` in
`PROJECT_ROOT` is in `S7_bestand.sh`, an inventory script. It is not a
detector, and it is not the subject of L1-A30.

**Settles it.** L1-A30, which must not bind to `S7_bestand.sh` by keyword
match. Its real target is operator-supplied (REF-11).

---

## D-07 — the `iban` pattern is not in `_VALIDATORS`

**Claim.** None explicit; the audit assumes an IBAN Mod-97 implementation
exists and is applied.

**Observation.** `anonymization/payload_scan.py` defines two IBAN patterns:
`iban` (line 132, German only) and `iban_intl` (line 147, non-German). Only
`iban_intl` appears in the `_VALIDATORS` dict. Read statically, this means the
German pattern is matched without Mod-97 validation.

**Settles it.** L1-A18. This note is a static reading produced during a build,
not a finding. A18 must confirm or refute it from source and from behaviour,
and must record which. If the reading is correct, it is a substantive result
about the scanner's actual coverage.

---

## D-08 — RETRACTED AND REPLACED — bytecode cache, measured per directory

**What the predecessor claimed.** That `docker/litellm/__pycache__/` contains
both `cpython-311` and `cpython-314` artefacts for `test_payload_scan`,
`custom_callback`, `payload_scan` and `tool_registry_gate` — four families,
both variants each.

**Why it was withdrawn.** The independent verifier recorded VF-007: the live
cache does not carry both interpreter variants for all four named components.
R2 re-measured the whole scoped tree rather than restating the summary.

**Not all four families have both interpreter variants.**

**What was measured.** Every `.pyc` under the project excluding `.git`, the
Discovery root, both Level-1 roots, and every virtual environment or vendored
library directory, filtered to the four named components. Twelve artefacts
exist. Hashes are of the `.pyc` files themselves:

| path relative to PROJECT_ROOT | sha256 |
| --- | --- |
| `anonymization/__pycache__/payload_scan.cpython-311.pyc` | `d180bed2f05cdddb66756a88293aedd9d4a328eee1af642f597ae0d65f72d6d2` |
| `anonymization/__pycache__/payload_scan.cpython-314.pyc` | `e9829660ab1c30d35b42c040e0a5aa947b33d6e2766d766cb914c47751060945` |
| `anonymization/__pycache__/test_payload_scan.cpython-311-pytest-9.1.1.pyc` | `e593f36c3bac2a00ef72d7c6ab26a147f283b82b2896b27a06ccdb3367b0182c` |
| `anonymization/__pycache__/test_payload_scan.cpython-314-pytest-9.1.1.pyc` | `6f2381ffbd64341d7a155d8c693cd5903a6530671cd537eebd65fde6c20ffdac` |
| `anonymization/__pycache__/test_payload_scan.cpython-314.pyc` | `bbbba3136f16df3bb7b33e8c362dde559a433ef7ef9982aa98cb6d31ebf34c90` |
| `anonymization/golden/__pycache__/payload_scan_golden_test.cpython-311-pytest-9.1.1.pyc` | `e1662215bfeb8e71af4ce315454ec9de02108fd55c58e9907846da5660ecf8a2` |
| `docker/litellm/__pycache__/custom_callback.cpython-314.pyc` | `db57dc50266233742f850f15d422e3f4a8866608db5bd45a906aad5cb38f23a8` |
| `docker/litellm/__pycache__/payload_scan.cpython-314.pyc` | `ca091b79f06c32997d28701a751a1b28f3ae6dccda31808d85da77c3029710b1` |
| `docker/litellm/__pycache__/test_payload_scan.cpython-311-pytest-9.1.1.pyc` | `9e051466454f077f56b56685c9d9136acc7942e5914f0949efb730b609c9bdd1` |
| `docker/litellm/__pycache__/test_payload_scan.cpython-314-pytest-9.1.1.pyc` | `52ee9e303e32b53f3ba44d7a9a7d449fc2fb64c376f99bc75507d8fcbf1317cf` |
| `docker/litellm/__pycache__/test_payload_scan.cpython-314.pyc` | `a4d24dc4ae41c3382124fe73d81e27debe3ce7ee5f18a7fe7f6f68020df0d755` |
| `docker/litellm/__pycache__/tool_registry_gate.cpython-314.pyc` | `8ff48a250e86b52061b93c29aa4b48c2ba446e5fc138c31fda407fc513da5381` |

**The four families, stated per family:**

- `test_payload_scan has both CPython 3.11 and 3.14 cache artefacts`, and it
  has them in both `anonymization/__pycache__/` and
  `docker/litellm/__pycache__/`. This is the one family for which the
  predecessor's summary held.
- `custom_callback: CPython 3.14 only`. It exists in one location,
  `docker/litellm/__pycache__/`, and only as a 3.14 artefact.
- `tool_registry_gate: CPython 3.14 only`. Likewise one location, one variant.
- `payload_scan: CPython 3.14 only under docker/litellm, and both 3.11 and 3.14 under anonymization`.
  This is the family the predecessor's summary got
  wrong in the other direction: the verifier described the family as 3.14-only,
  which holds for `docker/litellm` and does not hold for `anonymization`, where
  `payload_scan.cpython-311.pyc` exists and predates the verification run.

**A note on what a cache artefact proves.** It proves that some interpreter
imported or collected that module at some time. It does not prove that the
interpreter is current, that the artefact matches the present source, or that
the module is on any production path. The caches were read as metadata and
hashed; nothing was removed, and nothing under `PROJECT_ROOT` was written.

**Settles it.** L1-A15 and L1-A22, both of which depend on which interpreter
collects and runs a test. Both prompts now name the measured fact for
`test_payload_scan` specifically and instruct the auditor to verify it on the
live tree rather than inherit it from this note.

---

## D-09 — a second, independent audit instruction set exists

**Observation.** `PRUEFAUFTRAG_B_CLAUDE_CODE.md` and `PRUEFAUFTRAG_B_CODEX.md`
specify eleven checks (B4–B14) over overlapping components: B7 covers AP16
exporters and AP17 guardrails (L1-A03, L1-A07), B11 covers
`AP18_referenzpruefung.py` (L1-A10, L1-A13), B12 covers the 43 citations
(L1-A14).

**Settles it.** Not Level-1. Recorded in `08_SCOPE_GAPS_OUTSIDE_35.md` for
Level-2, which must check the two instruction sets for contradictory
requirements rather than assuming they agree.
