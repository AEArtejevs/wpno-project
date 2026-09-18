# 01 — DISCOVERY STATUS

## What Level-0 Discovery states

Source: `08.18.26_Discovery/00_DISCOVERY_SUMMARY.md`
(SHA-256 recorded in `RECONCILIATION_MANIFEST.sha256`, and the whole Discovery
tree hashed in `build_evidence/BUILD_START_DISCOVERY_MANIFEST.sha256` and again
in `build_evidence/BUILD_END_DISCOVERY_MANIFEST.sha256`).

```text
DISCOVERY STATUS: [INCOMPLETE]
SYSTEM INVENTORY CONFIDENCE: 70%
PRODUCTION PATH CONFIDENCE: 35%
DEPENDENCY MAP CONFIDENCE: 55%
TEST INVENTORY CONFIDENCE: 70%
UNKNOWN COMPONENTS: 615
UNVERIFIED COMPONENTS: 108
RECOMMENDATION: CONTINUE DISCOVERY
```

Discovery's own point 10 reads:

```text
Sufficient inventory for Level-1 35 audits: NO — production path and unknown
components remain unresolved.
```

## Was that a reason to abort this build?

No. An `INCOMPLETE` Discovery is not by itself an abort condition. Discovery's
point 10 answers a different question than this build asks. Discovery asks
whether the inventory suffices to *run* the 35 audits. This build asks whether
it suffices to *write* 35 targeted specifications with honest per-target status.

- Discovery's answer, restated: `INSUFFICIENT_FOR_AUDIT_START` for a subset.
- This reconciliation's answer: `SUFFICIENT_FOR_PROMPT_GENERATION`.

Both are recorded. Neither is quietly upgraded.

## What still holds after reconciliation

| Discovery claim | reconciliation result |
| --- | --- |
| 8 scan roots | `DISCOVERY_CONFIRMED` — all 8 exist |
| `ACTUAL PRODUCTION PATH: UNVERIFIED` | `DISCOVERY_CONFIRMED` — and narrowed, see 04 |
| 809 components, 6295 files | Not re-counted. Out of scope for this build. |
| 432 duplicate hash groups | `DISCOVERY_CONFIRMED` for the audited subset, see 06 |
| 885 test files, 0 run | `DISCOVERY_CONFIRMED` — no test was run here either |
| entry candidates are shell scripts + compose files | `DISCOVERY_CONFIRMED`, see 04 |

## Scope note

The Level-0 Discovery scanned 8 roots, of which only `PROJECT_ROOT` is the
project this package audits. The other 7 are separate repositories
(`wpno-llm-wiki`, `wpno-rechtsprechung-db`, `wpno-dav-formulare-wiki`,
`wpno-forensik-engine`, `wpno-wiki-milchhof`, `wpno-wiki-dav-insolvenzrecht`,
`wpno-wiki-template`).

The 35 Level-1 audits address components inside `PROJECT_ROOT`. Where a search
for an audit target had to establish absence, the search used the Discovery
file and hash inventories, which cover all 8 roots — so an absence statement in
this reconciliation means "absent from all 8 Discovery scan roots", not merely
"absent from `PROJECT_ROOT`". This distinction matters for L1-A27 to L1-A35 and
is stated again there.

The rest of the Mac was **not** searched. That is a deliberate limit of this
build, and it means an artefact could exist elsewhere on this machine that this
reconciliation reports as absent. Every such statement is phrased as
`EXTERNAL_EVIDENCE_REQUIRED`, not as `does not exist`.
