# 08 — SCOPE GAPS OUTSIDE THE ORIGINAL 35

The 35 Level-1 points are not assumed to cover the WPNO system. This file lists
components that **exist on this machine** and are **not** the direct target of
any of the 35 audits. It is the required input for
`03_CODEX_LEVEL2_ADVERSARIAL.md`.

Rule applied: only components actually found are listed. A candidate list is a
search hint, not a claim of existence; candidates that do not exist are
recorded as absent at the end so that a later reader does not re-run the same
search.

No more than 35 Level-1 prompts exist. Nothing here becomes a 36th Level-1
audit. These belong to Level-2.

## Found and not covered by the 35

| component | path | sha256 (16) | why it matters |
| --- | --- | --- | --- |
| `WPNO_egress_guard.py` | `gateway/` | 8b3a4ccba2c92db5 | the outbound PII detector; `WPNO_devscan.py` states the detection lives here **and only here**. The 35 audits examine `payload_scan.py` (A18–A21) but never the egress guard itself. Two detectors for the same question is the documented failure mode of this project. |
| `WPNO_gateway.py` | `gateway/` | b122711bda90eecc | the gateway L1-A17 asks about. A17 asks whether the *input filter* is on the production path; nothing asks what the gateway itself does. |
| `WPNO_devscan.py` | `gateway/` | 38a59e83ce4b2ad7 | recursive PII scan of a directory tree, exit 1 on finding; three-state result (SAUBER / FUND / UNGEPRUEFT). "UNGEPRUEFT passes" is a silent-skip channel of exactly the kind L1-A13 examines elsewhere. |
| `WPNO_belegpruefung.py` | `extraktion/` | a8fbcbe9c8b85ce8 | document/voucher checking — untouched by the 35 |
| `WPNO_betragspruefung.py` | `extraktion/` | 3ad487a113c0f43a | amount checking — untouched |
| `WPNO_kennzahlpruefung.py` | `extraktion/` | 954528fa14fb9ca3 | ratio checking — untouched |
| `WPNO_versionsvergleich.py` | `authoring/` | 939b7940227d91e6 | version comparison — directly relevant to L1-A03 and L1-A07, yet never named by them |
| `WPNO_jobqueue.py` | `betrieb/` | 3002178a55409de8 | a job queue. If anything schedules work, this is where it would be, and no Level-1 audit looks at it. |
| `WPNO_testkatalog.py` | root | 4d073b9c9667ed7c | the project's own test catalogue; references `verify_document`, `test_injection`, `egress_guard`. A catalogue that claims coverage is itself a claim needing verification. |
| `ap12_tool_loop.py` | `orchestrator/` | 351ff8cd6971f1c1 | the orchestrator tool loop — the plausible cross-component spine |
| `AP15_verify_evidence.py` | `authoring/` | 6a8953d8c8a8362a | evidence verification, one AP before the audited AP16 chain |
| `briefbogen_bauen.py` | `gate_test/` | 3bd534d90fdf0918 | letterhead builder — an output producer downstream of the audited chain |
| `absatzschutz.py` | `gate_test/` | a5d074ce28179371 | paragraph protection — output shaping |
| `xlsx_nach_json.py` | `anbindungen/` | fa4c3e428811b320 | spreadsheet ingestion — an untested input surface |
| `build_finanzplan.py` | `anbindungen/` | 021c1713d41bfa6a | financial plan builder — a report builder |
| `docker/litellm/custom_callback.py` | `docker/litellm/` | 6c83c40064c1727d | the caller of `payload_scan` inside the container. L1-A20/A21 examine the scanner; nothing examines its invoker. |
| `docker/litellm/tool_registry_gate.py` | `docker/litellm/` | 96dbde61dc20fa90 | the fourth bind-mounted file; a gate that no Level-1 audit opens |
| `mcp/health-poller.mjs` | `mcp/` | 0466afbdae4ad8c4 | the only continuously running WPNO process on this machine |
| `PRUEFAUFTRAG_B_CLAUDE_CODE.md` / `_CODEX.md` | root | edc6765ac749e7e4 | a **second, independent** eleven-check audit instruction (B4–B14) overlapping L1-A03/A07 (B7), L1-A10/A13 (B11) and L1-A14 (B12). Two instruction sets over the same components can disagree; Level-2 must check them against each other. |
| `Testkatalog_Protokoll.md` | root | 233c8f727068d1f1 | the catalogue's protocol, same status |

## Cross-component chain that no single Level-1 audit covers

```text
anbindungen/xlsx_nach_json.py        (input)
  → ap18/AP18_eingangsfilter.py      (L1-A17 — filter, in isolation)
  → orchestrator/ap12_tool_loop.py   (NOT covered)
  → docker/litellm/custom_callback.py (NOT covered)
  → anonymization/payload_scan.py    (L1-A18/A19/A20/A21 — scanner, in isolation)
  → gateway/WPNO_egress_guard.py     (NOT covered)
  → authoring/AP16_assemble_long_document.py (L1-A01)
  → authoring/AP17_output_guardrail_v3.py    (L1-A05..A09)
  → gate_test/briefbogen_bauen.py    (NOT covered)
```

Every Level-1 audit is a point test on this chain. Five of the nine stations
have no Level-1 coverage at all. Level-2's stated objective — prove the system
can still fail even if every Level-1 audit passed — has its material here.

## Searched and absent

These candidates do not exist anywhere in `PROJECT_ROOT`:
`WPNO_umgebungspruefung.py`, `wpno_db_mcp_server.py`,
`HR_chronological_merge.py`, `HR_pdf_zu_word.py`,
`audit_bestandsaufnahme.sh`, `audit_sammeln.sh`, `full_check_ap14.sh`,
`verify_fix1.sh`, `briefbogen_bauen_check.py`, `fundstelle_aufloesen.py`,
`build_tagesbericht_*`, `build_dienas_atskaite_*`.

Some of these exist in the **other** repositories Discovery scanned (notably
`HR_pdf_zu_word.py`, associated with `wpno-llm-wiki`). They are outside
`PROJECT_ROOT` and outside Level-1 scope. Level-2 may decide otherwise; if it
does, it must first re-establish that the file it finds is the file meant.
