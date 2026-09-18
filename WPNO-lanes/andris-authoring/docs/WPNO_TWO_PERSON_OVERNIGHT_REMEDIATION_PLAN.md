# WPNO Two-Person Overnight Remediation Plan

Date: 2026-08-31  
People: Andris and Janis  
Real project: `/home/ubuntu/project/WPNO`  
Audit source: `/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R9`

## 1. Goal

Fix the confirmed WPNO source defects faster by running two independent AI-assisted work lanes overnight.

Each section follows the same gate:

```text
reproduce failure
→ add or confirm a failing test
→ make the smallest fix
→ run focused tests
→ if failed, diagnose and repeat
→ run regression and mutation tests
→ record exact evidence
→ continue to the next section
```

R9 is historical sealed audit evidence. It must remain read-only. Remediation tests do not rewrite an R9 verdict. Formal closure happens later in a fresh audit revision.

## 2. What can and cannot be autonomous

After setup, source editing and testing can run autonomously overnight.

The following remain human-only because of the WPNO rules or because they affect an external system:

1. Approving the reviewed source-copy baseline before work begins.
2. Copying reviewed lane changes into the real project or a release package.
3. Starting or changing production services and containers.
4. Entering credentials, API keys or secrets.
5. Microsoft Word and Claude-loading checks on Martin's Mac.
6. Legal or professional approval, case-ID decisions and client/court communication.
7. Supplying missing external evidence or deciding how to treat contradictory evidence.

An agent must never claim that an external or human-only item is fixed merely because a local control passed.

## 3. Required setup before leaving the agents overnight

The real server project contains important source and sealed audit material. Do not let either overnight agent edit it directly.

The setup owner performs these steps before either overnight agent starts:

1. Save a complete backup outside the project and verify that it can be restored.
2. Review the already completed narrow remediations:
   - `CLAUDE.md`: nine states corrected to ten.
   - `authoring/AP16_verify_document.py`: semantic failure now exits 1.
   - `authoring/AP16_verify_document.py`: malformed OOXML now fails cleanly.
   - Previously authorized AP16/AP18 launcher and import-boundary changes.
3. Create two source-only working copies and two matching read-only baseline mirrors. Do not copy `.git`, audit packages, databases, virtual environments, client files, evidence, generated reports, `raw/`, or `tools/`.
4. Use these exact working directories:

```text
/home/ubuntu/project/WPNO-lanes/andris-authoring
/home/ubuntu/project/WPNO-lanes/janis-runtime
```

Use these exact read-only baseline mirrors:

```text
/home/ubuntu/project/WPNO-lanes/baseline/andris-authoring
/home/ubuntu/project/WPNO-lanes/baseline/janis-runtime
```

5. Generate sorted SHA-256 manifests for each baseline and working copy. Require each working-copy manifest to equal its matching baseline manifest before work starts.
6. Make the baseline mirrors read-only. Keep the original R9 package at its existing absolute path and read-only to both agents. Do not copy R9 into either lane.
7. Confirm the two lanes contain no `.git` directory, database, virtual environment, client document, audit package, credential file, or secret-bearing configuration.
8. Confirm each agent is started in its assigned working-copy path and has no write authority over the other lane, the baseline mirrors, or the real project.

Git is prohibited for this remediation. No person or overnight agent may invoke a Git command or write `.git/`. Overnight agents also may not install packages, download from the network, use credentials, or mutate production services.

## 4. Ownership split

Only one writer owns a file. The other lane may inspect it read-only but must not edit it.

| Area | Andris lane owns | Janis lane owns |
|---|---|---|
| AP16 document generation/verification | `authoring/AP16_*`, `scripts/wpno_ap16_export_pdf.py`, AP16 tests | Read-only |
| AP17 output guard | `authoring/AP17_*`, AP17 tests | Read-only |
| AP18 reference/input protection | `authoring/AP18_*`, `ap18/*`, AP18 tests | Read-only |
| Pytest configuration | `pytest.ini` | Read-only |
| Anonymization and payload scan | Read-only | `anonymization/*`, payload tests |
| LiteLLM payload copy/configuration | Read-only | `docker/litellm/*` and relevant Compose files |
| Inventory shell scripts | Read-only | `TrackC_bestand.sh`, `S7_bestand.sh` and their tests |
| Shared instructions and manifests | No autonomous edit | No autonomous edit |
| R9 audit package and sealed evidence | Read-only | Read-only |

Andris is the morning integration owner. This does not permit Andris's overnight agent to edit Janis-owned files.

Default assignment lock: Andris works only sections A1-A10, and Janis works
only sections J1-J9. Andris takes over a Janis section only if Janis is
unavailable, the Janis agent has been stopped, the Janis workspace has been
made read-only, and the ownership transfer is recorded before any edit. The
two people must never work the same section concurrently.

## 5. Mandatory section loop

For every section, the agent must perform these steps in order.

### 5.1 Preflight

1. Read `AGENTS.md` and the lane's `CLAUDE.md` completely.
2. Confirm the assigned lane path, owner and matching read-only baseline path.
3. Record the current hashes of every file in scope.
4. Run R9 `verify-evidence` from the original audit package and require `ok=true`, `tampered=[]` and 63 intact attempts.
5. Read the exact R9 finding and its supporting test behavior.
6. Confirm no file is owned by the other lane.

### 5.2 Red phase

1. Reproduce the original defect against the current candidate.
2. Add or identify a focused regression test that fails for the right reason.
3. Record the command, exit code and concise redacted output.
4. If the original defect cannot be reproduced, stop that section as `UNVERIFIED`; do not guess at a fix.

### 5.3 Green phase

1. Make the smallest source change that addresses the reproduced cause.
2. Run the focused positive and negative controls.
3. Repeat diagnosis and repair automatically if the focused test still fails.
4. Maximum: five implementation attempts or 90 minutes for one section.

### 5.4 Proof phase

A section is successful only when all are true:

- The original failing case now behaves correctly.
- A known-good case still succeeds.
- A known-bad case is rejected with the expected semantic result and exit code.
- A mutation test proves that weakening the repaired rule makes the test fail.
- The related module test suite passes.
- The wider project regression suite available in that runtime passes.
- A normal file comparison against the read-only baseline is captured with `diff -ruN` or equivalent.
- All changed text files pass the applicable syntax, parse, format or whitespace checks without invoking Git.
- No secret, client data, audit evidence or other lane's file changed.
- R9 `verify-evidence` still reports all 63 attempts intact.

### 5.5 Receipt

For each successful section, write a redacted receipt outside R9 containing:

- section ID and R9 finding IDs;
- owner and AI used;
- baseline and final source hashes;
- exact files changed;
- focused, negative, mutation and regression test commands/results;
- known limitations and external checks still required;
- final changed-file list, baseline/final SHA-256 values, and a redacted ordinary-diff summary for owned files.

Do not include client text, credentials, raw evidence content or approval tokens.

### 5.6 Failure handling

If the section is still failing after the limit:

1. Restore only that section's files from the matching read-only baseline mirror.
2. Verify the restored hashes.
3. Record `BLOCKED` with the exact reproducible cause.
4. Stop that lane if the blocker is a source/test problem.
5. If the blocker is strictly external—Mac GUI, credentials, package, service, missing evidence—the lane may continue to the next independent section, but the blocked section remains open.

## 6. Andris lane: AP16–AP18 authoring and guardrails

Recommended AI roles: Codex as the only writer; Claude Code as a read-only reviewer after each green phase.

Complete these sections in order:

### A1 — AP17 missing-reference configuration crash

Findings: `L1-A06-RUN-A-F02`.

Expected result: missing reference configuration produces a controlled semantic `BLOCKED`/failure report and a documented non-zero exit, never an uncaught traceback.

### A2 — AP17 false and unverified citations must block

Findings: `L1-A05-RUN-A-F01`, `F02`, and `L1-A06-RUN-A-F01`.

Expected result: the known false citation is rejected; an unverified citation cannot be treated as sendable; the known-good document remains allowed.

### A3 — AP18 impossible and zero-citation handling

Findings: `L1-A13-RUN-A-F01`.

Expected result: impossible BGH senate/docket forms are blocked across punctuation, spacing, NBSP and line-break variants. Zero citations must report “none found/not examined,” never “all verified.”

### A4 — AP18 citation classification and counting

Findings: `L1-A14-RUN-A-F01`.

Expected result: the source-bound real REF-06 structural oracle and AP18 agree on identity/counting rules; the three previously overcounted BGH designators are classified correctly.

### A5 — AP18 tests must be real pytest tests

Findings: `L1-A15-RUN-A-F01`.

Expected result: default project pytest collection includes AP18 injection tests; tests contain assertions; a deliberate filter weakening produces a test failure.

### A6 — AP17 Unicode and visual-evasion normalization

Findings: `L1-A08-RUN-A-F01` through `F05`.

Expected result: NFD, special spaces, hidden format characters, embedded line breaks and mixed-script homoglyph controls are rejected without creating unacceptable clean-text false positives.

### A7 — AP18 DOCX injection and external relationships

Findings: `L1-A16-RUN-A-F01` and `F02`.

Expected result: reader-visible mixed-script instructions and payload-bearing external relationships cause `PRUEFEN` or `BLOCKIERT`; clean DOCX remains `FREI`.

### A8 — AP17 must use full AP18 reference classification

Findings: `L1-A26-RUN-A-F04`.

Expected result: AP17 no longer calls only the narrow finder; it consumes the full AP18 classification result, including foreign-court and impossible-senate checks.

### A9 — AP16 semantic verification

Findings: `L1-A02-RUN-A-F01`.

Expected result: substituted body text, changed heading, stale TOC and unresolved relationships do not pass as semantically verified.

If the expected document semantics cannot be derived from a current source-bound manifest or explicit input contract, stop this section as `BLOCKED_REQUIREMENT_CONTRACT`; do not hardcode a guessed document.

### A10 — AP16/AP17/AP18 productive invocation path

Findings: productive-path limitations in L1-A01, L1-A02 and `L1-A17-RUN-A-F01`.

Expected result: one explicit launcher/workflow invokes the canonical AP16 verifier, AP17 output guard and AP18 input/reference checks in the documented order and propagates non-zero failures.

Do not deploy or start a service overnight. Produce and test the launcher in isolation; production activation is a morning human gate.

## 7. Janis lane: anonymization, payload validation and runtime readiness

Recommended AI roles: Claude Code as the only writer; Codex as a read-only reviewer after each green phase.

Complete these sections in order:

### J1 — Collect the payload golden test

Findings: `L1-A22-RUN-A-F01`.

Expected result: default pytest collection runs the golden payload test; its deliberate allow-all mutation fails the suite.

Prefer a conventional pytest wrapper/test filename over broad pytest configuration changes. `pytest.ini` belongs to the Andris lane.

### J2 — Connect and strengthen IBAN validation

Findings: `L1-A18-RUN-A-F01` and `F02`.

Expected result: the German IBAN pattern reaches a validator; Mod-97 and country-specific length/structure are both enforced; official valid vectors pass and malformed check-digit-valid controls fail.

### J3 — Enforce tax-ID structure

Findings: `L1-A19-RUN-A-F01`.

Expected result: checksum-valid but repetition-invalid German tax IDs are rejected; official valid controls still pass.

### J4 — Fix case and delimiter false negatives

Findings: `L1-A09-RUN-A-F01` through `F04`.

Expected result: phone numbers adjacent to commas/periods, lowercase/title-case IBANs, and ordinary case variants of addresses and postal localities are detected. Clean delimiter controls must remain clean.

### J5 — Establish one canonical payload scanner

Findings: `L1-A20-RUN-A-F01` through `F04`.

Expected result: active anonymization and Docker paths are generated from or point to one canonical implementation. Historical and golden copies remain labelled evidence/test assets and are not silently overwritten.

### J6 — Correct broad glob and ungrouped `find` expressions

Findings: `L1-A26-RUN-A-F02` and `F03`.

Expected result: beA searches do not match “Bearbeitung”; every `find -o` expression is grouped so shared type/depth/exclusion/output rules apply to every branch. Tests must run against Linux and be checked for macOS compatibility without executing on an unavailable Mac.

### J7 — Expand source-copy drift detection

Findings: `L1-A26-RUN-A-F01`.

Expected result: the detector distinguishes active, golden, backup and historical copies, checks every declared active copy and reports intentional historical differences rather than assuming all files must be identical.

### J8 — Docker/LiteLLM runtime readiness

Findings: `L1-A21-RUN-A-F01` and `F02`.

Expected result: Compose/configuration validation, local import checks and offline startup prerequisites pass. Do not pull images, enter secrets or start the productive container overnight.

### J9 — Full payload regression matrix

Expected result: all existing payload tests plus IBAN, tax-ID, phone, address, case, delimiter, clean-negative and mutation matrices pass from the canonical scanner path.

## 8. Cross-review rule

After a lane finishes a section:

1. The second AI reviews the diff read-only.
2. It checks whether the test could pass vacuously.
3. It identifies missing negative and mutation controls.
4. It confirms no file outside ownership changed.
5. The writing AI may make corrections, then reruns the entire section gate.

Claude and Codex must never both edit the same lane concurrently.

## 9. Items that cannot be fixed by an overnight code loop

These remain separate morning/external work:

| Item | Required action |
|---|---|
| L1-A25 historical Git-survivability finding | Git remains prohibited. Preserve `CLAUDE.md` through the verified backup, source-copy manifest and fresh-audit policy record; do not attempt a Git-based remediation. |
| L1-A04 Word/TOC | Run canonical v4 with Microsoft Word on a Mac and inspect the actual generated artifact. |
| L1-A24 instruction loading | Run the three approved Claude loading checks on Martin's Mac. |
| L1-A11/L1-A12 references | Supply independently labelled official BGH/register and legal-article materials. |
| L1-A21 deployment | Human authorizes credentials, image availability and productive container start. |
| L1-A31/L1-A34 trust | Perform authoritative trust-chain, revocation and profile validation in an approved environment. |
| L1-A33 chronology conflict | Preserve the original evidence and obtain authoritative clarification; never rewrite evidence timestamps. |
| L1-A35 copy causation | Supply both independently hash-bound source and destination copies plus copy-event metadata. |
| Final status | Build a fresh remediation audit revision and re-run affected findings; never edit sealed R9 verdicts. |

## 10. Morning integration sequence

1. Stop both agents and preserve their final logs.
2. Verify both lanes contain no running process and no unapproved external action.
3. Run R9 `verify-evidence`; require all 63 attempts intact.
4. Review each section receipt, changed-file list, hash manifest and complete ordinary diff against its read-only baseline.
5. Cross-run Andris tests against Janis's candidate and Janis tests against Andris's candidate where dependencies overlap.
6. Create `/home/ubuntu/project/WPNO-lanes/integration-review` as a fresh source-only copy of the approved real-project baseline, then apply reviewed lane changes file by file.
7. Run focused, full regression, mutation and security suites again.
8. Human reviews and approves each section independently before any reviewed file is copied into the real project. No bulk “everything fixed” replacement.
9. Perform the Mac, service, credential and external-evidence tasks separately.
10. Build a fresh R10 remediation audit package bound to the new source hashes.
11. Re-audit every affected R9 finding. Only the fresh audit may change the current status to PASS.

## 11. Copy-paste common overnight prompt

Use this prefix for both AI sessions:

```text
You are repairing the real WPNO project in your assigned isolated source-copy lane. Read AGENTS.md and CLAUDE.md completely before acting. R9 at /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R9 is sealed, read-only historical audit evidence. Never modify it or present remediation tests as an R9 PASS.

You are the only writer in this lane. Edit only your assigned file scope. Git is prohibited: do not invoke any Git command and do not create or write .git/. Do not install packages, use network access, enter or reveal credentials, start production services, write raw/ or tools/, change external volumes, or touch the real project, baseline mirrors, R9, or another lane's files.

Process sections strictly in order. For each section: verify the starting hashes against the read-only lane baseline; reproduce the exact finding; create or confirm a failing regression test; make the smallest fix; run focused positive, negative and mutation controls; repeat automatically until green; run the related and wider regression suites; capture an ordinary diff and final SHA-256 manifest; verify no out-of-scope files changed; verify all 63 R9 sealed attempts remain intact; then write a redacted remediation receipt outside R9 before continuing.

Use no real client data in prompts, tests or logs. Synthetic material is allowed only as a labelled control and cannot prove a substantive real-project requirement. If a source problem remains after five implementation attempts or 90 minutes, restore that section's files and stop the lane with a precise blocker. If the blocker is strictly external, restore partial changes, record BLOCKED, and continue only to an independent section.
```

## 12. Andris overnight prompt suffix

```text
Your lane is ANDRIS-AUTHORING. Your writable scope is authoring/AP16_*, authoring/AP17_*, authoring/AP18_*, ap18/*, pytest.ini, scripts/wpno_ap16_export_pdf.py, and newly created tests dedicated to those modules. All anonymization, docker/litellm, TrackC_bestand.sh and S7_bestand.sh files are read-only.

Work only in /home/ubuntu/project/WPNO-lanes/andris-authoring. Compare against the read-only baseline /home/ubuntu/project/WPNO-lanes/baseline/andris-authoring and write redacted section receipts only under /home/ubuntu/project/WPNO-lanes/receipts/andris-authoring. The authoritative starting manifests are under /home/ubuntu/project/WPNO-lanes/manifests.

Execute sections A1 through A10 from WPNO_TWO_PERSON_OVERNIGHT_REMEDIATION_PLAN.md. Codex is the writing driver through its authorized SSH connection to the isolated lane. Use Claude Code only for read-only review. Never proceed past a section with an unresolved source/test failure. For A9, stop instead of inventing a document semantic contract. For A10, create and test integration wiring only; do not activate production services.
```

## 13. Janis overnight prompt suffix

```text
Your lane is JANIS-RUNTIME. Your writable scope is anonymization/*, docker/litellm/*, relevant Compose configuration, TrackC_bestand.sh, S7_bestand.sh, and newly created tests dedicated to those modules. All authoring/*, ap18/* and pytest.ini files are read-only.

Work only in /home/ubuntu/project/WPNO-lanes/janis-runtime. Compare against the read-only baseline /home/ubuntu/project/WPNO-lanes/baseline/janis-runtime and write redacted section receipts only under /home/ubuntu/project/WPNO-lanes/receipts/janis-runtime. The authoritative starting manifests are under /home/ubuntu/project/WPNO-lanes/manifests.

Execute sections J1 through J9 from WPNO_TWO_PERSON_OVERNIGHT_REMEDIATION_PLAN.md. Claude Code is the writing driver. Use Codex only for read-only review. Never proceed past a section with an unresolved source/test failure. Do not pull images, install packages, enter secrets or start productive containers. J8 ends at offline runtime readiness and a human deployment checklist.
```

## 14. Definition of overnight success

The overnight run is successful when:

- Every completed section has reproducible red-before/green-after evidence.
- No section is marked fixed merely because a script exited 0.
- No two writers touched the same file.
- No Git command was invoked and no `.git` content was created or changed.
- No audit evidence, real client data, credentials or external systems were changed.
- Every surviving source change has focused, negative, mutation and regression coverage.
- Blocked items are explicit and not hidden.
- R9 remains 63/63 intact.
- The morning human review can accept or reject each section independently.
