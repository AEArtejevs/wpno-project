# R7 — the human gates, in order

Ten decisions in this revision belong to a person and to nobody else. An agent
prepares each one, prints the exact token the controller will demand, and
stops. It never issues a token, and the controller refuses one it produced.

Every token is one physical line, bound to exact digests, and RUN-ONCE. A
token that has been used once is refused the second time. A token stops being
valid the moment the plan or the target it names changes by one byte.

**Do not paste a token into a report, a commit message, a chat, or a file.**
The controller records that an approval happened and what it was bound to; it
never records the token text.

---

## Gate 1 — freeze R7

    HUMAN_GATE: FREEZE_R7_FINAL

Prepared by `build/build_r7_freeze_plan.py`, which prints the required token
and issues nothing. Supply it with:

    cd /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7
    python3 -m automation.controller freeze-level1 \
      --plan build/freeze_plan_attempt_1/FREEZE_PLAN_R7_ATTEMPT_1.json \
      --token '<the token, in single quotes>'

The route verifies the token, the plan, every bound digest, the Ubuntu
baseline, the replay ledger and the predecessor lineage **before it writes a
single byte**. Any failure leaves `MODE` at `GENERATED_UNVERIFIED`, writes
nothing, and does not consume the token.

After it succeeds, R7 is `FROZEN` and its executable bytes are final. A defect
found in them after this point is `HUMAN_GATE: R7_FINAL_REVISION_CONFLICT` and
not an eleventh revision. There is no R8.

---

## Gates 2 to 10 — the nine phase attempts

In this fixed order, one process per phase, no parallelism:

    L1-A31  RUN-A   RUN-B   COMPARISON
    L1-A34  RUN-A   RUN-B   COMPARISON
    L1-A18  RUN-A   RUN-B   COMPARISON

Each stops at:

    HUMAN_GATE: PHASE_ATTEMPT_APPROVAL

and prints the audit, the phase, the attempt number, the plan path and its
SHA-256, the target path and its SHA-256, and the exact token. Supply it with:

    python3 -m automation.controller record-approval --token '<token>'

then the phase runs once, seals its attempt, and stops again.

`COMPARISON` refuses to run until both runs have an accepted, usable, sealed
attempt. That refusal is not an obstacle; comparing one run against nothing is
not a comparison.

---

## If a phase fails

The controller classifies the sealed attempt and puts the phase somewhere
specific. What you do next follows from where it put it.

| Aggregate state | What it means | What happens next |
| --- | --- | --- |
| `SEALED` | a substantive result: PASS, PASS_WITH_WARNINGS, FAIL or UNVERIFIED | the phase is finished. A FAIL is a finding about the audited material and has **no** retry route. |
| `RETRYABLE_INTERNAL_ERROR` | our harness, plan or environment broke | the cause is repaired, a new plan is written, and `prepare-retry` prepares attempt N+1. **A new token is required.** |
| `BLOCKED_FOR_EXTERNAL_MATERIAL` | material only you can supply is missing | you are told exactly what file, what content and what provenance. Nothing resumes until it arrives and is verified. |
| `HALT_CRITICAL` | the control plane itself is in question | everything stops for you. |

A retry never reuses a token, never reuses a plan, and never happens without
a named root cause and evidence that the cause was repaired. At most three
attempts per phase, and at most two repairs of any one root cause.

---

## What an agent must never do here

- issue, guess, reconstruct or auto-supply a token;
- re-run a phase to get a different answer;
- record a FAIL as a defect in the harness;
- write into R4, R5 or R6;
- start a phase before the freeze, or freeze after a phase has started.

---

## The one thing worth knowing before Gate 2

L1-A31's corrected plan separates two questions R6 had merged into one
`-purpose` value:

1. **does the chain validate** — issuer chaining, signatures, validity at the
   claimed signing time, no default trust store, no suppression flag; and
2. **was the certificate entitled to sign what it signed** — key usage and
   extended key usage, answered explicitly and recorded in its own right.

For the beA VHN signer certificate those two questions have different answers,
and the second one is a finding rather than a formality. Its key usage carries
`digitalSignature` and `nonRepudiation`, which is what RFC 5652 asks of a CMS
signing key. Its extended key usage carries `id-kp-clientAuth` and nothing
else — no `emailProtection`, no `anyExtendedKeyUsage`. That is exactly the
edge case `prompts/L1-A31.md` lists: "a certificate whose extended key usage
does not include the purpose in question."

Whether a beA VHN certificate carrying only `clientAuth` is conforming for its
own profile cannot be settled from the material bound to this audit. The runs
will measure and record it; they will not decide it. If that determination
turns out to bear on the verdict, the honest outcome may be
`PASS_WITH_WARNINGS` or `UNVERIFIED` rather than `PASS`, and that outcome will
be sealed as it is and brought to you.
