# 02 — CODEX: CONSOLIDATE LEVEL-1

Run this only when **all 35 audits have a terminal status**. Terminal means
`SEALED`, `BLOCKED`, `ERROR` or `CONTAMINATED` for every required phase —
including `RUN-A`, `RUN-B` and `COMPARISON` for the four replicated audits.

Verify that yourself before starting. If any phase is outstanding, stop and
name it. Consolidating an incomplete run produces a document that reads as a
conclusion and is not one.

```text
DO NOT REPAIR FINDINGS
DO NOT CHANGE A VERDICT WITHOUT AN AMENDMENT
```

---

## 1 · Verify every evidence manifest

For each audit and phase:

- confirm `SEAL.json` exists;
- recompute `EVIDENCE_MANIFEST.sha256` in full;
- report any file that changed, is missing, or was added after sealing.

Tampered or altered evidence makes that audit's verdict unusable. Say so
plainly; do not average it away against the others.

---

## 2 · Verify the RUN-A / RUN-B pairs

For `L1-A18`, `L1-A19`, `L1-A31` and `L1-A34`:

- both runs exist and are sealed;
- `COMPARISON` exists and is sealed, and was sealed **after** both runs — check
  the seal timestamps, not the claim;
- the two runs used **independent methods** — check the recorded plans, not the
  claim. Two plans with identical operation sequences are one method run twice,
  and the replication requirement was not met;
- `RUN-B` shows no evidence of having seen `RUN-A`: no reference to its
  findings, verdict, self-critique, disproof attempt or expected conclusion,
  and no path into `RUN-A`'s results or evidence directory;
- where the two runs disagreed, the disagreement is reported as a finding and
  was not resolved by preferring either run.

A failure of any of these invalidates the replication for that audit. Report it
as such rather than reporting two agreeing runs.

---

## 3 · Verdict inventory

List every audit under each heading. No audit appears twice, and none is
omitted:

```text
PASS
PASS_WITH_WARNINGS
FAIL
BLOCKED
UNVERIFIED
CONTAMINATED
```

`ERROR` is listed separately — it describes the harness, not the system, and
mixing it with system verdicts misstates both.

For each `BLOCKED`, state what is missing and what would unblock it. Eleven
audits were expected to be blocked on operator-supplied material (`L1-A11`,
`L1-A14`, `L1-A27` through `L1-A35`); confirm whether that expectation held and
report any difference.

---

## 4 · Contradictions between audits

Search for and report:

- **Shared targets with conflicting hashes.** If two audits recorded different
  hashes for the same path, one measured a different file, or the file changed
  mid-run. Either is serious.
- **Production-path contradictions.** If one audit concluded a component is on
  the production path and another concluded it is not, both cannot be right.
  Name both, quote the evidence, and do not resolve it by preferring the more
  confident one.
- **Overlapping subject matter with different conclusions.** `L1-A26` covers
  the nine error classes in `CLAUDE.md` § 10, and classes 1, 4, 5, 8 and 9 are
  the direct subject of `L1-A09`, `L1-A15`, `L1-A14`, `L1-A22` and `L1-A20`.
  Cross-check each pair explicitly.
- **`L1-A20` versus `L1-A21`.** Copy enumeration versus container provenance:
  they must agree about which copy is in the container.
- **`L1-A30` / `L1-A35` versus `L1-A34`.** Both depend on the signature
  coverage boundary `L1-A34` establishes. If `L1-A34` was blocked, any
  conclusion in the other two that assumes a boundary is unsupported.
- **`L1-A03` versus `L1-A04`.** `L1-A04` runs against whatever `L1-A03`
  identified. If `L1-A03` returned `BLOCKED_TARGET_IDENTITY_UNCERTAIN`, every
  `L1-A04` conclusion carries that qualification and must be shown carrying it.

---

## 5 · Repeated findings

Group findings that recur across audits. A defect appearing in five audits is
one defect with five witnesses, not five defects — and counting it five times
inflates the total while hiding that a single fix addresses all of them.

Report both numbers: distinct defects, and total findings.

---

## 6 · Untested scope

State plainly what Level-1 did **not** cover:

- the components in
  `discovery_reconciliation/08_SCOPE_GAPS_OUTSIDE_35.md`, including
  `WPNO_egress_guard.py`, `WPNO_gateway.py`, `WPNO_devscan.py`,
  `WPNO_jobqueue.py`, `ap12_tool_loop.py`, `custom_callback.py`,
  `tool_registry_gate.py` and the `extraktion/` checkers;
- the five of nine stations on the processing chain with no Level-1 coverage;
- every audit that ended `BLOCKED` or `UNVERIFIED`, since those are questions
  asked and not answered.

A consolidated report that lists only what was tested reads as though the
system was covered. It was not.

---

## 7 · The sealed report

Write:

```text
results/LEVEL1_CONSOLIDATED_REPORT.md
results/LEVEL1_CONSOLIDATED_REPORT.json
results/LEVEL1_CONSOLIDATED_MANIFEST.sha256
state/LEVEL1_CONSOLIDATED.json
```

The report must state, near the top and without softening:

- how many audits reached each verdict;
- how many were blocked, and on what;
- how many distinct defects were found, and how many are critical;
- what was not covered;
- and that Level-1 is a set of point tests, so passing them does not establish
  that the system works end to end. That is `03_CODEX_LEVEL2_ADVERSARIAL.md`.

Seal it with a manifest. Then stop.

---

## 8 · What this prompt may not do

- It may not repair a finding.
- It may not change an individual verdict. If a verdict is wrong, write an
  **amendment** with its own ID, its evidence, and a pointer to the original.
  The original stays.
- It may not downgrade `FAIL` to `PASS_WITH_WARNINGS`, or `BLOCKED` to `PASS`,
  because 35 red entries look bad in a summary.
- It may not start Level-2.
