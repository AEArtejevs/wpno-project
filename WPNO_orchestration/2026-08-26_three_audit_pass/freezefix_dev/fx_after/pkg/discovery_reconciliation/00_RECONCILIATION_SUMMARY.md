# 00 — TARGET-MAC DISCOVERY RECONCILIATION — SUMMARY

```text
BUILD_ID:       L1BUILD-R3-2026-08-19-823680e9bb94
BUILD_REVISION: R3
MODE:           GENERATED_UNVERIFIED
Reconciliation date: 2026-08-19 (carried forward from the R2 reconciliation of 2026-08-18; D-05, O-04 and the project-root inventory re-measured)
PROJECT_ROOT:   the parent of LEVEL1_ROOT      (paths.json: "..")
DISCOVERY_ROOT: PROJECT_ROOT/08.18.26_Discovery (paths.json: "../08.18.26_Discovery")
LEVEL1_ROOT:    this package                    (paths.json: ".")
```

The roots are written in their resolved-at-runtime form rather than as literal
user paths, so this package names no machine account. `automation/path_policy.py`
performs the resolution once.

## What this document is

This is **not** a replacement for, or a correction of, the Level-0 Discovery.
No Discovery file was read for anything other than reading, and no Discovery
file was modified. This is a separate, read-only reconciliation whose only
purpose is to resolve enough target identity to write 35 audit specifications.

## Predecessor

A previous package at `08.18.26_Level1_Audits` failed independent pre-freeze
verification (`VERIFICATION_FAIL`). Its reconciliation content is reused here
where it was verified as correct, and corrected where the verifier found it
wrong. Two entries changed: drift **D-05** (the Git baseline premise, VF-008)
and drift **D-08** (the bytecode cache, VF-007). Both changes are recorded in
`11_DISCOVERY_DRIFT.md` as retractions with the replacing measurement, not as
silent edits. The failed package itself was not modified.

## Verdict

```text
SUFFICIENT_FOR_PROMPT_GENERATION
```

This verdict means exactly one thing: 35 audit specifications and 35 target
bindings could be written with explicit, evidence-backed status per audit.

It does **not** mean:

- that the Level-0 Discovery became complete;
- that the production path is proven;
- that all 35 audits can be started;
- that the system is in any sense verified;
- that this package is verified. It is `GENERATED_UNVERIFIED`, and its own
  self-tests have not been run.

Nine audits (L1-A27 through L1-A35) have **no target inside any Discovery scan
root**. They are bound as `EXTERNAL_EVIDENCE_REQUIRED` or `TARGET_MISSING`.
Those audits cannot start until the operator supplies the artefacts named in
`references/README_REQUIRED_OFFLINE_REFERENCES_LV.md`.

## Binding status distribution

| status | count | audits |
| --- | --- | --- |
| TARGET_CONFIRMED | 14 | A01 A02 A05 A06 A07 A15 A17 A18 A19 A20 A22 A23 A25 A26 |
| TARGET_PARTIAL | 8 | A03 A04 A08 A09 A10 A12 A13 A16 |
| TARGET_UNRESOLVED | 2 | A21 A24 |
| EXTERNAL_EVIDENCE_REQUIRED | 10 | A11 A14 A27 A28 A30 A31 A32 A33 A34 A35 |
| TARGET_MISSING | 1 | A29 |

`TARGET_CONFIRMED` here means: the file exists, its SHA-256 is recorded, and
static evidence ties it to the audit subject. It does **not** by itself mean
that the file is the productive copy. Production identity is a separate
question, tracked per audit in `04_PRODUCTION_PATH_RECONCILIATION.md`, and is
`UNPROVEN` for the whole system (see below).

## The single most important reconciliation result

Level-0 Discovery reports `PRODUCTION PATH CONFIDENCE: 35%` and
`ACTUAL PRODUCTION PATH: UNVERIFIED`. This reconciliation confirms that and
narrows it:

- there is **no runtime supervisor** (LaunchAgent, cron, watcher) that invokes
  the document chain, the output guardrail, the reference checker or the input
  filter (`03_TARGET_BINDING_EVIDENCE.md`, `04_PRODUCTION_PATH_RECONCILIATION.md`);
- the only two WPNO LaunchAgents are `com.wpno.health-poller` (MCP health
  poller) and `com.wpno.wiki-ingest` (watches a path outside `PROJECT_ROOT`);
- the only container that mounts WPNO source is `docker/litellm`, and it mounts
  exactly four files;
- everything else in the audited scope is **operator-invoked from a shell**.

Consequence for Level-1: for most audits, "which copy is productive" cannot be
answered by execution-path evidence, because there is no persistent execution
path. The correct verdict for those audits is `BLOCKED_TARGET_IDENTITY_UNCERTAIN`
or `UNVERIFIED`, not a guess. Every affected prompt says so explicitly.

## Method

Read-only only. Commands used were confined to reading, listing, stat, file
typing, scoped searching, SHA-256 hashing, and read-only git
(`git status --porcelain`, `git rev-parse`). No WPNO Python file was imported
or executed. No test was run. No container, database, MCP server or n8n
workflow was contacted. No network request was made.

**Build tooling disclosure for R3, unchanged in kind from R2.** R1
generated its files with `python3` generator scripts kept in
`build_tmp/`, and its verifier recorded that as deviation D-A. Neither R2 nor
R3 has a `build_tmp/`, a generator script, or any generated-code execution:

```text
GENERATED_CONTROLLER_EXECUTED=NO
GENERATED_SCHEMA_VALIDATOR_IMPORTED=NO
CONTROLLER_SELFTESTS_EXECUTED=0
WPNO_TESTS_EXECUTED=0
LEVEL1_AUDITS_EXECUTED=0
```

Every R3 file was either copied byte-for-byte from R2 and re-hashed to prove
the copy faithful, or written directly. The only programs run during the R3
build were system measurement tools (`find`, `shasum`, `stat`, `git rev-parse`,
`git status`, `grep`, `wc`, `diff`, `sed`, `cp`, `ls`), none of which imports
anything from this package. `BUILD_JOURNAL.jsonl` records this in full.

## Files in this reconciliation

| file | content |
| --- | --- |
| `01_DISCOVERY_STATUS.md` | what Level-0 claims, what still holds |
| `02_PROJECT_ROOT_INVENTORY.md` | actual top-level inventory of PROJECT_ROOT |
| `03_TARGET_BINDING_EVIDENCE.md` | per-audit target evidence with hashes |
| `04_PRODUCTION_PATH_RECONCILIATION.md` | what invokes what, and what does not |
| `05_TEST_INFRASTRUCTURE_RECONCILIATION.md` | pytest config, collection reach |
| `06_DUPLICATE_COPY_RECONCILIATION.md` | duplicate copies by hash |
| `07_EXTERNAL_COMPONENTS.md` | Docker, MCP, n8n, DB, LaunchAgents |
| `08_SCOPE_GAPS_OUTSIDE_35.md` | components found but not covered by the 35 |
| `09_UNRESOLVED_BINDINGS.md` | every unresolved binding and why |
| `10_REQUIRED_OFFLINE_REFERENCES.md` | external evidence the operator must supply |
| `11_DISCOVERY_DRIFT.md` | where Discovery and the Mac disagree |
| `12_OPEN_ITEMS.md` | known open items this build did not change |
| `RECONCILIATION_MANIFEST.sha256` | hashes of the files above |
