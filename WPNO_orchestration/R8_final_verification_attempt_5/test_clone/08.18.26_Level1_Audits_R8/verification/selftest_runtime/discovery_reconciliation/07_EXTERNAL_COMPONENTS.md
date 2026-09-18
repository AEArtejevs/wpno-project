# 07 — EXTERNAL COMPONENTS

Static evidence only. No socket, no service, no database connection, no network
request was used to produce this file.

## Docker

Four compose stacks under `docker/`:

| stack | mounts WPNO source? | relevance |
| --- | --- | --- |
| `docker/litellm` | yes — 4 named files | L1-A20, L1-A21 |
| `docker/n8n` | yes — `tools/wiki_lister_container.py` (ro), `mandate-inbox`, `wiki-inboxes`, plus an iCloud path (ro) | none of the 35 |
| `docker/langfuse` | no — named volumes only | none |
| `docker/postgres` | no — named volume `wpno_pgdata` | none |

`docker/litellm/Dockerfile` —
`05fbf2c570ce65d64fdd7e62920293bda8a1c0cc13c5d2d64961bfabf072692a`.
`docker/litellm/config.yaml` —
`ac59d2aa9f9a950ebfd356817b962f6eaf180edf5699a9df87cbf39d41236793`.

`.env` files are present in `docker/litellm`, `docker/n8n`, `docker/postgres`
and `docker/langfuse`. They are excluded by `.gitignore` and were **not read**
by this build. They may contain secrets. No audit prompt instructs anyone to
read them; anything an audit needs from them must be requested from the
operator as a redacted export.

Not obtainable without the Docker socket, and therefore out of scope for
Level-1 unless the operator exports it: image IDs, image digests, image and
container creation timestamps, running-container inventory, effective
entrypoints and commands, build context provenance.

## MCP

`mcp/` contains 22 entries; Discovery counts 68 MCP-related files across all
roots (`10_MCP_INVENTORY.md`). `mcp/health-poller.mjs` is the program of the
`com.wpno.health-poller` LaunchAgent. No MCP server is a target of any of the
35 audits. MCP mutation is a forbidden operation throughout Level-1.

## n8n

`n8n/workflows/` — five JSON files:
`My workflow.json`, `Error Handler.json`,
`wpno_wiki_mandate_batch_detection.json`, `MCP Health Poller.json`,
`ap14_reconcile_workflow.json`.

None contains an absolute project path. None references an audited component.
`backups/n8n_backup.json` is a backup of workflow state, not a live component.

## Databases

Discovery reports 35 DB artefacts. Those inside the audited scope:

| path | relevance |
| --- | --- |
| `ap18/eingangspruefungen.sqlite` | L1-A17 — the input filter's record of checks |
| `anonymization/ledger.db`, `anonymization/ledger_data/` | related to the scanner, not a target |
| `docker/litellm/ledger.db`, `docker/litellm/ledger_data/ledger.db` | container-side ledger |

No database connection is permitted in Level-1. `DATABASE_EVIDENCE_IMPORT`
operates on an operator-provided export only, and `ap18/eingangspruefungen.sqlite`
may additionally contain records about real submissions — it must be treated as
potentially confidential and requested as a redacted export, not read directly.

## LaunchAgents

| plist | program | watch/working dir |
| --- | --- | --- |
| `~/Library/LaunchAgents/com.wpno.health-poller.plist` | `node WPNO/mcp/health-poller.mjs --serve` | WorkingDirectory `WPNO/mcp` |
| `~/Library/LaunchAgents/com.wpno.wiki-ingest.plist` | `bash wpno-llm-wiki/tools/ingest_batch.sh` | WatchPaths `wpno-llm-wiki/_inbox` |

Both were read read-only. Neither may be modified. `LAUNCH_AGENT_MUTATION` is a
forbidden operation.

## External services referenced but not reachable from Level-1

Beck-online, WK/Libra, official court portals. These appear in project
documentation and in `PRUEFAUFTRAG_B` § B12 as the required verification route
for citations. Level-1 runs with network disabled. Any audit needing them (most
directly L1-A11 and L1-A14) must return `BLOCKED` or `UNVERIFIED` rather than
substituting model knowledge for a retrieved source.
