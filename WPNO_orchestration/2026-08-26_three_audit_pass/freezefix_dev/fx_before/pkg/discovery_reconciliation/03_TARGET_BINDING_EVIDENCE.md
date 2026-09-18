# 03 — TARGET BINDING EVIDENCE

One section per audit. Every path is canonical and relative to `PROJECT_ROOT`.
Every SHA-256 was computed with `shasum -a 256` and is repeated in the audit's
binding file. The binding files carry the same paths in absolute form, because
their schema requires it; this document uses the relative form so that no
machine account name appears in the reconciliation narrative.

Confidence values used: `HIGH` (file identity and subject match are both
direct), `MEDIUM` (identity direct, subject match inferred from content),
`LOW` (candidate only).

Reading rule: a `TARGET_CONFIRMED` binding states that the *file* is
identified. It never states that the file is the *productive* copy. See
`04_PRODUCTION_PATH_RECONCILIATION.md`.

---

## L1-A01 — assemble_long_document deterministic two-run hash — TARGET_CONFIRMED

| path | sha256 | evidence |
| --- | --- | --- |
| `authoring/AP16_assemble_long_document.py` | `4bcde78f0220eaf07a70c6a9ba20c98d66ee4d65f38a998762c30c9bd5b09932` | filename + symbol match, `grep -l assemble_long_document`, HIGH |

Related artefacts, not targets: `authoring/AP16_test_output.docx`,
`authoring/AP16_test_output_v2.docx`, `authoring/AP16_test_output_final.pdf`.

Caller evidence: none found. No other file in `PROJECT_ROOT` imports or invokes
this module outside `docs/` reports. Determinism must therefore be measured by
invoking the script directly, twice, in two clean work directories — which is a
`PYTHON_SCRIPT_RUN_SANDBOX` operation and requires human approval.

---

## L1-A02 — verify_document semantic verification — TARGET_CONFIRMED

| path | sha256 | evidence |
| --- | --- | --- |
| `authoring/AP16_verify_document.py` | `98847c6034365703585d08828fe2ee363438ba8c2570a91a262af366407ee653` | filename + symbol match, HIGH |

Mutation material available in-tree: `authoring/AP16_poisoned.docx`
(`b84dd4c676e88366d1cfd8a9d68959f7247ffa9bf19cb52f25fd0cdffbb17e64`).
Mutation control for this audit must nevertheless build its own mutants inside
the audit work directory, because `AP16_poisoned.docx` was built for AP17, not
for AP16, and reusing it would test the wrong rule.

---

## L1-A03 — export_with_toc productive-version identification — TARGET_PARTIAL

| path | sha256 | evidence |
| --- | --- | --- |
| `authoring/AP16_export_with_toc.py` | `e618eb151eb674fe435a967fed7b6e696ac75fbde390db828bd1c99c14e22f0c` | 1763 bytes, HIGH |
| `authoring/AP16_export_with_toc_v2.py` | `12e6da3ec6289523fc9d8118db8583b8a9ef7649b825a09cd4b26e44f24e6eee` | 1764 bytes, HIGH |
| `authoring/AP16_export_with_toc_v4.py` | `b204a8e5e9bd7a7489bd2d69c61242ec9da8c929186b4b3393599a3d120ebdb7` | 2325 bytes, HIGH |

**Drift D-01.** The audit is specified as "v1–v4". Only three files exist.
There is no `AP16_export_with_toc_v3.py` anywhere in the eight Discovery scan
roots (searched in `18_HASH_INVENTORY.csv`). Either v3 never existed, or it was
deleted, or "v4" is misnamed. The audit must resolve which, and must not assume
the unnumbered file is "v1" merely because it lacks a suffix.

No caller was found for any of the three. Binding is `TARGET_PARTIAL` because
the candidate set is complete and hashed, but production identity is unproven
and, absent a caller, may be unprovable from this machine.

---

## L1-A04 — TOC versus actual generated document text — TARGET_PARTIAL

Depends on the outcome of L1-A03: the TOC producer is whichever
`export_with_toc` variant is productive, which is unproven. The comparison
subject (a generated document) does not exist as a fixed artefact; it must be
produced inside the audit work directory from the target identified by A03.

Available in-tree output samples, usable only as reference, never as the
comparison subject: `authoring/AP16_test_output.docx`,
`authoring/AP16_test_output_v2.docx`.

---

## L1-A05 / L1-A06 / L1-A07 / L1-A08 / L1-A09 — output guardrail — see per-audit note

Guardrail version set (all in `authoring/`):

| path | sha256 | note |
| --- | --- | --- |
| `AP17_output_guardrail_VERALTET.py.txt` | `555ee5164da201864833506a7f9f6f61885f18ff506b1ed4f5f6cddd70f37d37` | v1, marked VERALTET (obsolete), `.py.txt` — not importable as-is |
| `AP17_output_guardrail_v2_VERALTET.py.txt` | `5f6b3dd78dcb76a924d5961dfc2cfafbc91eccd76ac6f2e0cef22d43b3d8a6d8` | v2, marked VERALTET, `.py.txt` |
| `AP17_output_guardrail_v3.py` | `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca` | v3, only live `.py` |

Poisoned-input builders: `AP17_make_poisoned_test.py`
(`0652ee51ece7eaec2309a467cf40f5ea48f3b199eca24b2eb151ed1af5a6d0b5`),
`AP17_make_poisoned_test_v3.py`
(`a379a344ebc8423cbfd5d50f3eb8e485bd83f1689d9a69ffc5eb2ef90140866f`).

Prior report artefacts (evidence about past runs, not oracles):
`AP17_report.md`, `AP17_report_v2.md`, `AP17_report_poisoned.md`,
`AP17_guardrail_report.md`.

**Drift D-02.** The audit specification names `report_bad` and `report_good`.
Neither identifier exists in `PROJECT_ROOT`. `grep -rl report_bad` returns
nothing; `report_good` appears only once, inside
`docs/GODAUDIT_2026-08-10/runlog.jsonl`, i.e. in a log about a past audit, not
in code. The in-tree equivalents are the report files listed above plus the
poisoned-document builders. A05 and A06 must therefore first establish what
`report_bad` / `report_good` denote on this machine and record that mapping as
evidence, or return `BLOCKED_TARGET_IDENTITY_UNCERTAIN`.

- A05 (guard catches bad) — `TARGET_CONFIRMED` for the guard, unresolved for the bad input.
- A06 (guard permits good) — `TARGET_CONFIRMED` for the guard, unresolved for the good input.
- A07 (regression v1→v3) — `TARGET_CONFIRMED`; both endpoints exist and are hashed. Note v1 is a `.py.txt` file, so any run of v1 requires copying it into the sandbox under a `.py` name; that copy must never be written into `PROJECT_ROOT`.
- A08 (five new edge cases) — `TARGET_PARTIAL`; the guard is identified, the five cases do not exist and must be authored inside the audit work directory.
- A09 (word boundaries) — `TARGET_PARTIAL`; the rule set lives in v3, but "every relevant article" is not a defined set on this machine. The audit must enumerate the pattern set from the v3 source by AST/static reading and treat that enumeration as its own evidence.

---

## L1-A10 — productive reference-checker copy — TARGET_PARTIAL

| path | sha256 | evidence |
| --- | --- | --- |
| `authoring/AP18_referenzpruefung.py` | `f5eb5a9cbeb37cada9186ba305b9a307ea40e3012ca0e2e6dd0b2560f4352d74` | only copy found in `PROJECT_ROOT`, HIGH |
| `authoring/AP18_referenzpruefung_test.py` | `5bfc3fa48809d3c55f4287928987dd2e58982af558ddad8941fc5d8f6775b071` | its test, HIGH |
| `authoring/bgh_referenz.json` | `d2451fa5720643cceb84605538a7979709ef90a44de4770e7aee06cc33579880` | reference data loaded by `referenz_laden()`, HIGH |

Only one copy exists — which is itself a finding worth stating, given that
duplicate copies are the documented failure mode of this project (CLAUDE.md
§ 10, last bullet). `TARGET_PARTIAL` rather than confirmed because "productive"
still requires a caller, and no caller exists: the script has a `__main__`
block and is invoked by hand (`python3 AP18_referenzpruefung.py dokument.docx`).

---

## L1-A11 — BGH_REGISTER vs independent official roster — EXTERNAL_EVIDENCE_REQUIRED

`BGH_REGISTER` is defined in `authoring/AP18_referenzpruefung.py` (the only
file in `PROJECT_ROOT` containing the identifier). The register itself is
therefore bound.

What is **not** available: an independent official roster to compare against.
No offline BGH roster exists in any Discovery scan root. Comparing
`BGH_REGISTER` against `bgh_referenz.json` would not satisfy the audit, because
both are project artefacts and neither is an official source.

Required verdict if the operator supplies nothing:
`BLOCKED_MISSING_OFFICIAL_REFERENCE`.

---

## L1-A12 — broad-pattern false positives on a real article corpus — TARGET_PARTIAL

Checker: `authoring/AP18_referenzpruefung.py` (hashed above).

Corpus candidates present in-tree, all synthetic and all built for the *input
filter*, not for the reference checker:

| path | note |
| --- | --- |
| `ap18/korpus/` | 8 PDFs: 6 attack, 2 clean |
| `ap18/korpus_docx/` | 7 DOCX: 5 attack, 2 clean |

These are **not** a real article corpus. Using them would measure the wrong
thing. A real corpus must be supplied by the operator with recorded origin and
hashes, or the audit returns `UNVERIFIED`.

---

## L1-A13 — fabricated citation blocking — TARGET_PARTIAL

Checker bound (`AP18_referenzpruefung.py`). The five mandatory case strings
(`XY ZR 999/99`, `ABC ZR 1/20`, `IIII ZR 1/20`, `0 ZR 1/20`, `14 StR 1/20`) do
not exist as fixtures anywhere in `PROJECT_ROOT` and must be constructed inside
the audit work directory. They are synthetic strings and contain no client data.

Known prior defect to keep in view, recorded in `PRUEFAUFTRAG_B_CLAUDE_CODE.md`
§ B11 as F-004: only Roman senate numbering is recognised, so OLG, LG and BAG
citations pass **unexamined**. "Unexamined" and "approved" are indistinguishable
in the tool's output. The audit must separate the two.

---

## L1-A14 — "davon BGH N" on a real 43-citation document — EXTERNAL_EVIDENCE_REQUIRED

The counter is in `authoring/AP18_referenzpruefung.py` (`grep -l "davon BGH"`
returns that file only).

The document is not in the repository. `PRUEFAUFTRAG_B_CLAUDE_CODE.md` § B11
describes it as a 110-page document with 43 unique citations and 82 hits, six
in a high-risk band, one `I ZR` outlier, none before 2000. The checker takes
its input as `sys.argv[1]`, so the document is operator-supplied at call time
and has no fixed path.

The document is a client Schriftsatz. It must be identified and hashed by the
operator, and the audit must record that hash. Absent it: `BLOCKED`.

---

## L1-A15 — test_injection assertion validity — TARGET_CONFIRMED

| path | sha256 |
| --- | --- |
| `ap18/AP18_test_injection.py` | `f01e65bc9eff2efec3cac2f55ef5238ea5a28139fec2080e6004816c7181eb9d` |

Directly relevant prior finding, CLAUDE.md § 10, bullet 4: "Test mit Exit 0,
der nichts prueft. Zwei Testfunktionen, kein `__main__`-Block. Ein direkter
Aufruf definiert sie nur." That is the exact vacuous-zero pattern this audit
must detect, and it is documented as having already occurred in this project.

---

## L1-A16 — five novel DOCX injection cases — TARGET_PARTIAL

Corpus builder: `ap18/AP18_erzeuge_testkorpus_docx.py`
(`a0a0378783c360626d57cd19075a4a820b21f777a9344789541c04e73beabef1`).
Existing corpus: `ap18/korpus_docx/` — W1 hidden, W2 white text, W3 tiny font,
W4 document properties, W5 footnote, plus two clean files.

The five new cases must not repeat those five vectors. The required coverage
(run-split XML text, hidden/alternate text, homoglyphs, external relationship
reference, nested/obfuscated instruction text) overlaps existing W1/W2 only at
the surface; the audit must state the difference per case.

---

## L1-A17 — production invocation path of the input filter — TARGET_CONFIRMED

| path | sha256 |
| --- | --- |
| `ap18/AP18_eingangsfilter.py` | `e8ad639cbeb238b16985f240ed1045297c26a9202c603695b29f29a3ea74ffb3` |
| `ap18/eingangspruefungen.sqlite` | recorded at audit time; a DB artefact, read via `DATABASE_EVIDENCE_IMPORT` only |

Target confirmed, and the expected answer is already visible statically: no
gateway, orchestrator, container, LaunchAgent or n8n workflow references
`AP18_eingangsfilter`. See `04_PRODUCTION_PATH_RECONCILIATION.md`. The audit
must prove or refute that independently, and if it holds, the verdict is
`FAIL_FILTER_NOT_IN_PRODUCTION_PATH` — not `PASS` on the grounds that the file
exists and looks correct.

---

## L1-A18 — IBAN Mod-97 — TARGET_CONFIRMED — CRITICAL — 2 replications

| path | sha256 | locator |
| --- | --- | --- |
| `anonymization/payload_scan.py` | `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b` | `_validate_iban_intl`, line 238; pattern `iban_intl`, line 147; pattern `iban`, line 132 |
| `docker/litellm/payload_scan.py` | `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b` | byte-identical to the above |
| `anonymization/golden/payload_scan.py` | `ab29a4fa3e972f865f0f3dfb10887888a0464922070454e02584a34a4c54ba0a` | different content — must be checked separately |

Static observation to be verified, not assumed, by the audit: the `iban`
pattern at line 132 matches German IBANs only and is **not** listed in
`_VALIDATORS`, so no Mod-97 check applies to it; only `iban_intl` is validated.
If that reading is correct, German IBANs are matched without check-digit
validation while non-German ones are validated. The audit must confirm or
refute this from the source and from behaviour, and must not take this note as
established fact.

---

## L1-A19 — ISO 7064 tax-ID check digit — TARGET_CONFIRMED — CRITICAL — 2 replications

Same files as A18. Function: `_validate_steuid11`, ending line 235 in
`anonymization/payload_scan.py`; registered in `_VALIDATORS` as `steuid11`.

Scheme identification required before testing: the identifier is the German
*steuerliche Identifikationsnummer* (11 digits). The implemented loop is the
Mod 11,10 construction. The audit must independently establish country,
identifier type, exact ISO 7064 variant, modulus, radix, character mapping,
check-digit position and preprocessing from an official offline source before
producing any expected value. If it cannot:
`BLOCKED_SCHEME_IDENTITY_UNCERTAIN`.

---

## L1-A20 — all payload_scan copies and semantic equality — TARGET_CONFIRMED

Complete copy set from `18_HASH_INVENTORY.csv`, all eight Discovery roots:

| path | sha256 | size |
| --- | --- | --- |
| `anonymization/payload_scan.py` | `99b9e18b…5153b` | 21564 |
| `docker/litellm/payload_scan.py` | `99b9e18b…5153b` | 21564 |
| `anonymization/golden/payload_scan.py` | `ab29a4fa…4ba0a` | 22831 |
| `anonymization/payload_scan.py.ALT.2026-08-05.bak` | `7ca51777…2aca3` | 16350 |
| `docker/litellm/payload_scan.py.ALT.2026-08-05.bak` | `7ca51777…2aca3` | 16350 |
| `docs/Test_07.28.26/AP-03/logs/payload_scan.py.before_F-AP03` | `9f466036…44f77` | 15524 |

Six files, **four** distinct hashes. Test files (`test_payload_scan.py` in two
locations, identical hash `341549bb…4fbd1`) and
`anonymization/golden/payload_scan_golden_test.py` (`dc83acf6…960b0`) are
related components, not copies of the scanner.

**Drift D-03.** The audit specification lists `payload_scan_ERGAENZT_2026-08-04.py`
and a bare `payload_scan.py` as historical candidates. Neither exists as named.
CLAUDE.md § 10 states four copies; six files carrying the scanner name exist
today. Both numbers must be treated as claims, and the audit's own enumeration
as the evidence.

The two live copies being byte-identical is the single most consequential fact
here and it must be reported at the stated comparison level, not as
"the copies are identical" without qualification: `anonymization/` and
`docker/litellm/` agree byte-for-byte; `golden/` does not.

---

## L1-A21 — Docker productive copy and image provenance — TARGET_UNRESOLVED

Static evidence available:

- `docker/litellm/docker-compose.yml` (`cdd162fa4145c4617f8c71956cc570c50e1c9a4a1da69007b6cbd2c034281329`) mounts exactly four host files into the container:
  `./config.yaml:/app/config.yaml`, `./custom_callback.py:/app/custom_callback.py`,
  `./payload_scan.py:/app/payload_scan.py`, `./tool_registry_gate.py:/app/tool_registry_gate.py`.
- `docker/litellm/Dockerfile` (`05fbf2c570ce65d64fdd7e62920293bda8a1c0cc13c5d2d64961bfabf072692a`).
- `docker/litellm/custom_callback.py` (`6c83c40064c1727d0753bcaa6230314c2a4510858427542cfa5bd1ef2231b44b`) references `payload_scan`.

Because `payload_scan.py` is **bind-mounted** rather than baked in, the file
inside a running container is the host file, and the question "was the image
rebuilt after the 04.08 change" may be irrelevant for this file while remaining
relevant for anything the Dockerfile copies. The audit must distinguish those
two cases and not answer one while claiming the other.

Image ID, digest, creation timestamps, container mapping: not obtainable
without the Docker socket, which is forbidden. `DOCKER_METADATA_IMPORT` of an
operator-produced export is the only permitted route. Absent it:
`UNVERIFIED_DOCKER_PRODUCTIVE_COPY`.

---

## L1-A22 — pytest golden-test collection — TARGET_CONFIRMED

| path | sha256 |
| --- | --- |
| `pytest.ini` | `3259aae6b1feea94c78ee30440a63e82f2e4d5a4caa5a291820307c83323f227` |
| `anonymization/golden/payload_scan_golden_test.py` | `dc83acf66bdb9aab18f03efaa1b292c1f9a6b1f405439ecc4dd928fd069960b0` |
| `anonymization/golden/payload_scan.py` | `ab29a4fa3e972f865f0f3dfb10887888a0464922070454e02584a34a4c54ba0a` |

`pytest.ini` verbatim:

```ini
[pytest]
addopts = --import-mode=importlib
testpaths = anonymization docker orchestrator
norecursedirs = test_akte plain_test .git node_modules cases venv
pythonpath = anonymization docker/litellm orchestrator
```

Facts the audit must work from, and must re-derive rather than inherit:
`anonymization/golden/` lies under a `testpaths` entry; the filename ends in
`_test.py`; `pythonpath` includes `anonymization` but not
`anonymization/golden`. Whether the file is collected, and if not why, is the
audit's question — file naming is only one of the thirteen listed causes.

---

## L1-A23 — CLAUDE.md rules versus Mac reality — TARGET_CONFIRMED

| path | sha256 |
| --- | --- |
| `CLAUDE.md` | `f6734d0d0f7a25933a87efeec89cfdb2ba97f79956a546c13de9a94fac3d1ef8` |

Structure: 11 numbered sections. § 8 ("Diese Maschine", lines 98–131) is the
section that makes checkable factual claims about paths, tools, versions and
services and is the primary comparison surface.

---

## L1-A24 — CLAUDE.md loading outside the project root — TARGET_UNRESOLVED

The instruction files that could be loaded are identified:

| path | note |
| --- | --- |
| `CLAUDE.md` (relative to `PROJECT_ROOT`) | project file, hashed above |
| `~/.claude/CLAUDE.md` | user-level global file, exists; expanded and hashed at audit time |

What cannot be resolved statically is which of these a Claude Code process
actually loads from a given working directory, and at which version. That is a
runtime property. The audit needs `CLAUDE_LOAD_BEHAVIOUR_TEST`, which is a
gated operation, and it must record the Claude Code version. It must not modify
either file, and it must not modify user configuration.

**Specification defect corrected in R2 (VF-011), preserved unchanged in R3.** The R1 prompt
required the test's isolated directory to be simultaneously below the audit
work directory and outside the project. Level-1 lives inside the project, so
every audit work directory is inside the project, and no such directory exists;
the audit could never be planned. R2 separated the two, and R3 keeps that
separation exactly:

- the **launch working directory** is an existing, operator-approved directory
  outside `PROJECT_ROOT`, is never written to, and is hashed before and after;
- the **audit work directory** is `work/L1-A24/<RUN-ID>/` inside `LEVEL1_ROOT`,
  and `HOME`, `TMPDIR` and every cache and configuration output are redirected
  into it before the process starts.

The external directory is not named by this package and must be bound by the
operator before execution.

---

## L1-A25 — CLAUDE.md git tracking and git-clean survivability — TARGET_CONFIRMED

`CLAUDE.md` is inside the `PROJECT_ROOT` git repository (HEAD
`5548d9ae8c62a6037cf60bd68723581b2a6491ff`). Tracked/ignored/untracked status
must be read with `git ls-files` and `git status --porcelain`, both read-only.

`git clean -fd` must never be run in the real repository. `git clean -nd` is
dry-run and is permitted **only** under explicit human approval. The
survivability question is properly answered in a disposable synthetic
repository, not here.

---

## L1-A26 — the nine error classes in section ten — TARGET_CONFIRMED

`CLAUDE.md` § 10 ("Fehler, die hier schon passiert sind"), lines 158–195,
contains exactly nine bullet items:

1. word boundary forgotten (`*bea*` matching `Bearbeitung`)
2. regex without `+` (Schriftschluessel `/F1+0`)
3. one court's rule applied to all (BGH senate rule)
4. test with exit 0 that checks nothing
5. a counter that counts only what it knows
6. `find … -name A -o -name B` without parentheses
7. a check that counts itself (`grep -c sk-ant ~/.zsh_history`)
8. green tests that never touch the new code
9. the same file in several places (`payload_scan.py`, four copies)

Each must be individually accounted for. Note that classes 1, 4, 5, 8 and 9 are
the direct subject matter of L1-A09, L1-A15, L1-A14, L1-A22 and L1-A20
respectively, so A26's findings and those audits' findings must be checked for
contradiction during consolidation.

---

## L1-A27 to L1-A35 — beA / OSCI / signature forensics — NO TARGET IN SCOPE

Searched: `08.18.26_Discovery/02_FILE_INVENTORY.csv` and
`18_HASH_INVENTORY.csv`, which together cover all 6295 files across all eight
Discovery scan roots.

| search term | hits |
| --- | --- |
| `p7s` | 0 |
| `vhn` | 0 |
| `563203462` | 0 |
| `osci` | 0 |
| `pkcs7` | 0 |
| `messageDigest` | 0 in project source |
| `noverify` | 0 in project source |

Consequence per audit:

| audit | subject | binding |
| --- | --- | --- |
| L1-A27 | ZIP hash remeasurement | `EXTERNAL_EVIDENCE_REQUIRED` — archive not identified |
| L1-A28 | messageDigest remeasurement | `EXTERNAL_EVIDENCE_REQUIRED` |
| L1-A29 | "376" hash remeasurement | `TARGET_MISSING` — the referent of `376` is not defined anywhere on this machine; required verdict `BLOCKED_376_TARGET_UNIDENTIFIED` |
| L1-A30 | AppleDouble detection | `EXTERNAL_EVIDENCE_REQUIRED` — the only `AppleDouble` string in `PROJECT_ROOT` is in `S7_bestand.sh`, which is an unrelated inventory script |
| L1-A31 | certificate chain without `-noverify` | `EXTERNAL_EVIDENCE_REQUIRED` — no certificate, no trust anchor |
| L1-A32 | SignerInfo multiplicity | `EXTERNAL_EVIDENCE_REQUIRED` |
| L1-A33 | OSCI container `563203462.xml` | `EXTERNAL_EVIDENCE_REQUIRED` |
| L1-A34 | `vhn.xml.p7s` full verification | `EXTERNAL_EVIDENCE_REQUIRED` |
| L1-A35 | did copying on 17.08 cause the damage | `EXTERNAL_EVIDENCE_REQUIRED` — needs source and destination copies plus copy metadata |

These nine audits are fully specified and ready to run. They are blocked on
material, not on specification. What the operator must provide, and in what
form, is in `10_REQUIRED_OFFLINE_REFERENCES.md` and
`references/README_REQUIRED_OFFLINE_REFERENCES_LV.md`.

Absence statement, precisely: these artefacts are absent from all eight
Discovery scan roots. The remainder of this Mac was not searched, by
instruction. Absence here is not proof of absence on the machine.
