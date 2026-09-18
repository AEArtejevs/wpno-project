# 02 — PROJECT_ROOT INVENTORY

Read-only inventory of `PROJECT_ROOT` as observed on 2026-08-19 during the R3
build. Git HEAD at R3 build time:

```text
5548d9ae8c62a6037cf60bd68723581b2a6491ff
```

That value is also written verbatim to
`build_evidence/BUILD_START_GIT_HEAD.txt` and recorded as
`BUILD_TIME_GIT_HEAD` in `00_BUILD_STATUS.md`. R2 recorded it in the evidence
file but not in the status file, and its verification failed on precisely that
omission (PV-001).

`git status --porcelain` produced 37 lines at R3 build start; the raw capture is
in `build_evidence/BUILD_START_GIT_STATUS.txt` and the corresponding end-of-build
capture is in `build_evidence/BUILD_END_GIT_STATUS.txt`.

**The repository is not clean, and this package does not say it is.** Of those
37 lines, six are tracked modifications that were already present before this
build began, and 31 are untracked paths. The six tracked modifications are:

```text
 M Testkatalog_Protokoll.md
 M authoring/AP16_verify_report.md
 M authoring/AP17_guardrail_report.md
 M authoring/AP18_referenzpruefung.py
 M authoring/ledger.sqlite
 M docker/litellm/ledger_data/ledger.db
```

None of them was modified by this build: the build-start and build-end source
manifests are identical over 48,682 entries, which is the stronger evidence.

**How that capture may and may not be described.** It was taken after
`08.18.26_Level1_Audits_R3/` already existed, so it already lists that path as
untracked. It is therefore not a pre-existence snapshot and is never presented
as one. The immutability claim R3 actually makes rests on the content manifests
— `BUILD_START_SOURCE_MANIFEST.sha256` against
`BUILD_END_SOURCE_MANIFEST.sha256`, 48,682 entries each, compared by SHA-256 —
and porcelain status is recorded alongside as a separate observation. See
`11_DISCOVERY_DRIFT.md`, entry D-05.

No tracked file changed during this build.

## Top level, as observed

```text
  total 384
  drwxr-xr-x@ 57 martinotten  staff   1824 19 Aug. 10:27 .
  drwxr-x---+ 83 martinotten  staff   2656 19 Aug. 10:22 ..
  drwxr-xr-x@  2 martinotten  staff     64 22 Juli 10:29 .ap0607_pylibs
  -rw-r--r--@  1 martinotten  staff  14340 10 Aug. 17:17 .DS_Store
  drwxr-xr-x@ 15 martinotten  staff    480 19 Aug. 10:27 .git
  -rw-r--r--@  1 martinotten  staff    801  1 Aug. 10:15 .gitignore
  drwxr-xr-x@  6 martinotten  staff    192 21 Juli 19:20 .pytest_cache
  drwxr-xr-x@  6 martinotten  staff    192 22 Juli 10:31 .venv-ap0607
  drwxr-xr-x@ 28 martinotten  staff    896 18 Aug. 10:39 08.18.26_Discovery
  drwxr-xr-x@ 29 martinotten  staff    928 18 Aug. 15:25 08.18.26_Level1_Audits
  drwxr-xr-x  29 martinotten  staff    928 18 Aug. 21:15 08.18.26_Level1_Audits_R2
  drwxr-xr-x  23 martinotten  staff    736 19 Aug. 10:38 08.18.26_Level1_Audits_R3
  drwxr-xr-x  19 martinotten  staff    608 10 Aug. 15:58 2 Baker appendixes
  drwxr-xr-x   5 martinotten  staff    160  7 Aug. 14:04 afna
  drwxr-xr-x  14 martinotten  staff    448  4 Aug. 11:26 anbindungen
  drwxrwxr-x@ 14 martinotten  staff    448  5 Aug. 15:18 anonymization
  drwxr-xr-x  17 martinotten  staff    544  3 Aug. 18:02 AP-06-07 Test
  drwxr-xr-x   8 martinotten  staff    256  4 Aug. 13:33 ap18
  drwxr-xr-x@  4 martinotten  staff    128 10 Aug. 09:51 audit_output
  drwxr-xr-x  57 martinotten  staff   1824  5 Aug. 15:15 authoring
  drwxr-xr-x@  8 martinotten  staff    256 22 Juli 18:32 backups
  drwxr-xr-x   9 martinotten  staff    288  4 Aug. 16:34 betrieb
  drwxr-xr-x@  3 martinotten  staff     96 21 Juli 13:56 cases
  -rw-r--r--   1 martinotten  staff   7576 17 Aug. 17:58 CLAUDE.md
  -rw-r--r--   1 martinotten  staff   3942 14 Aug. 11:31 codex_config.toml
  -rw-r--r--   1 martinotten  staff    421 21 Juli 21:09 copy_klage_hr.sh
  -rw-r--r--   1 martinotten  staff     96 21 Juli 21:08 copy_klage_hr.shecho
  drwxrwxr-x@  3 martinotten  staff     96 16 Juli 09:32 db
  drwxrwxr-x@  7 martinotten  staff    224 31 Juli 11:28 docker
  drwxrwxr-x@ 32 martinotten  staff   1024 10 Aug. 17:34 docs
  drwxr-xr-x   8 martinotten  staff    256  4 Aug. 15:45 extraktion
  drwxr-xr-x  26 martinotten  staff    832  7 Aug. 14:26 gate_test
  drwxrwxr-x@ 10 martinotten  staff    320  4 Aug. 16:23 gateway
  drwxr-xr-x   8 martinotten  staff    256  4 Aug. 11:55 logs
  drwxr-xr-x@  5 martinotten  staff    160  4 Aug. 10:00 mandate-inbox
  drwxrwxr-x@ 22 martinotten  staff    704 28 Juli 18:12 mcp
  drwxrwxr-x@  3 martinotten  staff     96 16 Juli 09:32 n8n
  drwxr-xr-x  22 martinotten  staff    704 28 Juli 18:00 orchestrator
  drwxrwxr-x@  2 martinotten  staff     64 16 Juli 09:32 plain_test
  -rw-r--r--@  1 martinotten  staff  34439 10 Aug. 13:14 PRUEFAUFTRAG_B_CLAUDE_CODE.md
  -rw-r--r--   1 martinotten  staff  35385 10 Aug. 13:14 PRUEFAUFTRAG_B_CODEX.md
  -rw-r--r--@  1 martinotten  staff    210 28 Juli 11:37 pytest.ini
  drwxr-xr-x@ 14 martinotten  staff    448 29 Juli 10:14 rag
  -rw-r--r--   1 martinotten  staff    263 22 Juli 15:51 replacements2.txt
  -rw-r--r--   1 martinotten  staff     42 22 Juli 16:11 replacements3.txt
  -rw-r--r--   1 martinotten  staff   5737 14 Aug. 11:32 S7_abnahme.sh
  -rw-r--r--   1 martinotten  staff   6425 14 Aug. 11:03 S7_bestand.sh
  -rw-r--r--   1 martinotten  staff   8211 14 Aug. 12:54 S8_libra_test.sh
  drwxrwxr-x@  4 martinotten  staff    128 29 Juli 09:30 scripts
  drwxrwxr-x@  6 martinotten  staff    192 30 Juli 11:13 templates
  drwxrwxr-x@  9 martinotten  staff    288 24 Juli 11:38 test_akte
  -rw-r--r--@  1 martinotten  staff   8370  5 Aug. 15:15 Testkatalog_Protokoll.md
  drwxr-xr-x@  3 martinotten  staff     96 10 Aug. 09:49 tmp
  drwxr-xr-x   5 martinotten  staff    160  4 Aug. 11:31 tools
  -rw-r--r--   1 martinotten  staff   7134 14 Aug. 17:42 TrackC_bestand.sh
  drwxr-xr-x@  5 martinotten  staff    160  4 Aug. 12:13 wiki-inboxes
  -rw-r--r--@  1 martinotten  staff  18823  4 Aug. 16:35 WPNO_testkatalog.py
```

The listing differs from the R2 package's in exactly one entry:
`08.18.26_Level1_Audits_R3/` now exists. The entry set is otherwise the same.
Both failed predecessor packages, `08.18.26_Level1_Audits/` and
`08.18.26_Level1_Audits_R2/`, are still present and untouched.

## Directories relevant to the 35 audits

| directory | role for Level-1 |
| --- | --- |
| `authoring/` | AP16 document chain (A01–A04), AP17 output guardrail (A05–A08), AP18 reference checker (A10–A14) |
| `ap18/` | input filter (A17), injection test (A15), DOCX corpus builder (A16) |
| `anonymization/` | payload scanner + golden copy + tests (A20, A22) |
| `docker/litellm/` | payload scanner container copy (A20, A21) |
| `gateway/` | egress guard, gateway, devscan |
| `docs/` | prior audit reports — evidence about the system, not the system |
| `08.18.26_Discovery/` | Level-0 Discovery, read-only |
| `08.18.26_Level1_Audits/` | R1, the first failed package, read-only evidence |
| `08.18.26_Level1_Audits_R2/` | R2, the second failed package, read-only evidence |
| `08.18.26_Level1_Audits_R3/` | this package (created by this build) |

## Directories deliberately not inventoried in detail

`rag/venv`, `.venv-ap0607`, `orchestrator/venv`, `node_modules`, `__pycache__`,
`.git/objects`. These are third-party or generated content. Excluding them from
the *narrative* inventory is recorded here so that a later reader does not
mistake the exclusion for absence.

They are, however, **included** in `build_evidence/BUILD_START_SOURCE_MANIFEST.sha256`
and its end-of-build counterpart. The manifest scope excludes only `.git`, the
Discovery root, both failed predecessor packages, and this package. Everything
else under `PROJECT_ROOT` is hashed, including `audit_output/`, which is a
project artefact unrelated to Level-1 and is therefore not treated as an
audit-infrastructure root.

## Repository facts

- `PROJECT_ROOT` is a git repository (`.git/` present).
- `.gitignore` excludes, among others, `cases/`, `logs/`, `mandate-inbox/`,
  `wiki-inboxes/`, `*.bak`, `**/.env`, and several venv paths.
- `.gitignore` does **not** exclude `08.18.26_Discovery/`,
  `08.18.26_Level1_Audits/`, `08.18.26_Level1_Audits_R2/` or
  `08.18.26_Level1_Audits_R3/`. All four therefore appear as untracked
  content. This build did not modify
  `.gitignore`, because `.gitignore` is inside `PROJECT_ROOT` and
  `PROJECT_ROOT` is read-only for this build.
