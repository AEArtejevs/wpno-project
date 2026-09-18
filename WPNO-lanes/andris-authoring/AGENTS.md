# Real WPNO Remediation Guardrails

## Mission

- Repair the real WPNO project on the AWS Ubuntu server.
- Real project: `/home/ubuntu/project/WPNO`.
- Sealed audit source: `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R9`.
- R9 is the completed real-project audit. R8 and earlier revisions are historical
  lineage and must never be resumed or presented as current evidence.
- R9 reached 43/43 phase coverage. This is 100% coverage, not an overall PASS.
- R9 contains 63 sealed attempts. It must remain immutable and read-only.
- Remediation changes do not alter an R9 verdict. Formal closure requires a new
  audit revision bound to the repaired source.

## Required reading and preflight

Before editing, testing, reporting progress, or starting an overnight run:

1. Read this file and root `CLAUDE.md` completely.
2. Read `docs/WPNO_TWO_PERSON_OVERNIGHT_REMEDIATION_PLAN.md` completely.
3. Confirm the exact source-copy lane, matching read-only baseline, and lane owner.
4. Confirm the working-lane SHA-256 manifest matches its baseline manifest.
5. From the original R9 path, run the controller's `verify-evidence` command.
6. Require `ok=true`, `tampered=[]`, and all 63 attempts intact.
7. Record hashes for every file in the current section before editing.
8. Reproduce the exact R9 defect before attempting a fix.

If any check is uncertain, stop and inspect. Do not guess.

## Human-only actions

Agents must never perform:

- any Git command or any read/write under `.git/`;
- writes to `raw/` or `tools/`;
- production ingest, case-ID assignment, service/container activation, or deploy;
- credential, password, token, API-key, or secret entry/copying;
- legal/professional approval, court/client communication, or evidence rewriting;
- package installation or Internet downloads unless separately authorized.

The setup owner creates verified source-copy lanes and read-only baselines. The
human performs final file-by-file integration, deployment, Mac/Word checks, and
external-evidence decisions.

## Real evidence and privacy

- Never send client data to web searches, external models, examples, or logs.
- Never expose credentials or unrelated personal material.
- Synthetic data is allowed only as a labelled positive, negative, mutation, or
  adversarial control. It cannot prove a real-project requirement.
- Missing or unverifiable real input remains `UNVERIFIED`, `UNKNOWN`, or
  `BLOCKED`; never substitute dummy data to claim success.
- Do not treat filenames, comments, reports, screenshots, or exit code alone as
  runtime proof.
- Preserve contradictions as contradictions. Never rewrite original evidence.

## Two-lane ownership

Only one writer may own a file.

### Andris lane: `/home/ubuntu/project/WPNO-lanes/andris-authoring`

Read-only baseline: `/home/ubuntu/project/WPNO-lanes/baseline/andris-authoring`  
Receipt directory: `/home/ubuntu/project/WPNO-lanes/receipts/andris-authoring`

Writable scope:

- `authoring/AP16_*`
- `authoring/AP17_*`
- `authoring/AP18_*`
- `ap18/*`
- `pytest.ini`
- `scripts/wpno_ap16_export_pdf.py`
- tests and redacted receipts dedicated to those modules

Andris executes only plan sections A1-A10.

### Janis lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`

Read-only baseline: `/home/ubuntu/project/WPNO-lanes/baseline/janis-runtime`  
Receipt directory: `/home/ubuntu/project/WPNO-lanes/receipts/janis-runtime`

Writable scope:

- `anonymization/*`
- `docker/litellm/*`
- relevant Compose configuration
- `TrackC_bestand.sh`
- `S7_bestand.sh`
- tests and redacted receipts dedicated to those modules

Janis executes only plan sections J1-J9.

### Ownership transfer

Andris may take a Janis section only when Janis is unavailable, the Janis agent
has stopped, the Janis lane is read-only, and the transfer is recorded before
any edit. Never allow concurrent writers on one section or lane.

Shared instructions, manifests, external evidence, and R9 are read-only to both
lanes. Claude and Codex may review each other read-only but must not both edit.

## Mandatory section loop

Process sections strictly in plan order:

1. Reproduce the original defect.
2. Add or confirm a focused test that fails for the correct reason.
3. Record the red command, exit code, and redacted result.
4. Make the smallest source change addressing the reproduced cause.
5. Run focused positive and negative controls.
6. If still failing, diagnose and repeat automatically.
7. Maximum five implementation attempts or 90 minutes per section.
8. Run a mutation test proving that weakening the repaired rule fails.
9. Run the related module suite and wider available regression suite.
10. Capture a normal `diff -ruN` comparison and final SHA-256 manifest against
    the matching read-only baseline; run applicable syntax and whitespace checks.
11. Confirm no out-of-scope file, secret, client data, or audit evidence changed.
12. Re-run R9 evidence verification and require all 63 attempts intact.
13. Write a redacted receipt outside R9.
14. Continue only after every source/test gate for the section is green.

A successful receipt records the section and finding IDs, owner/AI, baseline and
final hashes, files changed, exact test results, mutation result, limitations,
and a redacted ordinary-diff summary. Do not include client text, credentials,
raw evidence, or approval tokens.

## Failure handling

- If the original defect cannot be reproduced, record `UNVERIFIED`; do not fix by
  guesswork.
- If a source/test problem remains after the section limit, restore only that
  section from its read-only baseline mirror, verify the restored hashes, record the
  exact blocker, and stop that lane.
- If a blocker is strictly external, restore partial changes, record `BLOCKED`,
  and continue only to an independent section.
- Never hide a blocked section or weaken a test to make it green.
- Never modify sealed R9 evidence, controller state, or historical verdicts.

## Current R9 remediation map

Andris lane findings include:

- AP17 missing configuration and false/unverified citation handling: L1-A05/A06.
- Unicode and visual-evasion handling: L1-A08.
- impossible and zero-citation handling: L1-A13.
- citation counting/classification: L1-A14.
- uncollected/non-asserting AP18 tests: L1-A15.
- DOCX injection and external relationships: L1-A16.
- AP17 bypass of full AP18 classification: L1-A26.
- AP16 semantic verification and productive-path identity: L1-A01/A02/A17.

Janis lane findings include:

- uncollected payload golden test: L1-A22.
- IBAN validation: L1-A18.
- tax-ID structure: L1-A19.
- case and delimiter false negatives: L1-A09.
- payload scanner copy drift/canonical source: L1-A20/A26.
- broad beA glob and ungrouped `find`: L1-A26.
- Docker/LiteLLM offline readiness: L1-A21.

Use the exact sealed finding records and the shared plan for acceptance criteria.

## External items

The overnight code loop cannot establish:

- Microsoft Word/TOC behavior on a Mac (L1-A04);
- Claude instruction loading on Martin's Mac (L1-A24);
- missing official reference corpora (L1-A11/L1-A12);
- production deployment with credentials/services (L1-A21);
- authoritative trust/revocation/profile validation (L1-A31/L1-A34);
- correction of the original chronology contradiction (L1-A33);
- missing source/destination copy pair and event metadata (L1-A35).

Keep these open for human/external handling. Never claim they passed locally.

## Completion

Overnight remediation is complete only when each finished section has red-before,
green-after, negative, mutation, and regression evidence; ownership is clean;
blocked items are explicit; and R9 still verifies 63/63 intact. Final WPNO status
is determined only by a fresh remediation audit, never by editing R9.
