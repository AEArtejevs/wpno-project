# 04 — PRODUCTION PATH RECONCILIATION

Level-0 Discovery: `PRODUCTION PATH CONFIDENCE: 35%`,
`ACTUAL PRODUCTION PATH: UNVERIFIED`. This reconciliation confirms that and
makes it specific.

## What actually runs without a human typing a command

Exhaustive for this Mac's user LaunchAgents referencing WPNO
(`grep -rl WPNO ~/Library/LaunchAgents`). The program strings are quoted
verbatim from the plists, because a quoted measurement is evidence and
rewriting it would not be:

| agent | program | trigger | touches audited scope? |
| --- | --- | --- | --- |
| `com.wpno.health-poller` | `/opt/homebrew/bin/node /Users/martinotten/WPNO/mcp/health-poller.mjs --serve` | RunAtLoad, WorkingDirectory `WPNO/mcp` | No |
| `com.wpno.wiki-ingest` | `/bin/bash /Users/martinotten/wpno-llm-wiki/tools/ingest_batch.sh` | `WatchPaths: /Users/martinotten/wpno-llm-wiki/_inbox` | No — outside `PROJECT_ROOT` |

There is **no** LaunchAgent, cron entry or watcher that invokes the AP16
document chain, the AP17 output guardrail, the AP18 reference checker, or the
AP18 input filter.

## Container-mounted source

`docker/litellm/docker-compose.yml`, the only compose file mounting WPNO source:

```yaml
volumes:
  - ./config.yaml:/app/config.yaml
  - ./custom_callback.py:/app/custom_callback.py
  - ./payload_scan.py:/app/payload_scan.py
  - ./tool_registry_gate.py:/app/tool_registry_gate.py
```

`docker/n8n/docker-compose.yml` mounts `tools/wiki_lister_container.py` (ro),
an iCloud path (ro), `mandate-inbox` and `wiki-inboxes`. It mounts no audited
component.

`docker/langfuse` and `docker/postgres` mount named volumes only.

So exactly one audited file — `docker/litellm/payload_scan.py` — has a
demonstrable runtime binding, and it is a bind mount of the host file. Its
content is the host content by construction. This is the strongest
production-path evidence available anywhere in the audited scope, and even it
does not establish that the container is running, or was running when it
mattered. That requires operator-exported Docker metadata (L1-A21).

## n8n

`n8n/workflows/` contains five workflow JSON files. None contains a project
absolute path (`grep -oh "/Users/martinotten[^\"]*"` returns nothing). No
audited component is referenced.

## Callers inside the source tree

No file in `PROJECT_ROOT` imports or invokes:

- `AP16_assemble_long_document`
- `AP16_verify_document`
- any `AP16_export_with_toc*`
- `AP17_output_guardrail_v3`
- `AP18_referenzpruefung`
- `AP18_eingangsfilter`

outside of `docs/` (prior audit reports) and `08.18.26_Discovery/` (inventories).
Both of those describe the components; neither executes them.

Each of these scripts has a `__main__` entry and is invoked by hand.

## What this means for the audits

Production identity requires execution-path evidence, and choosing a productive
copy by filename, version number, mtime, size, documentation, comments or
proximity is forbidden.

On this machine, for most audited components, that evidence does not exist.
The honest consequences are:

| audit | consequence |
| --- | --- |
| L1-A03 | `BLOCKED_TARGET_IDENTITY_UNCERTAIN` is the expected verdict unless the auditor finds caller evidence this reconciliation missed |
| L1-A10 | only one copy exists, so the copy question is trivial; "productive" remains unproven |
| L1-A17 | the filter has no caller — the expected verdict is `FAIL_FILTER_NOT_IN_PRODUCTION_PATH`, and it must be *proven*, not inherited from this note |
| L1-A20 | production status per copy: only the `docker/litellm` copy has a runtime binding |
| L1-A21 | `UNVERIFIED_DOCKER_PRODUCTIVE_COPY` without operator-exported metadata |

None of the above may be copied into an audit result as a finding. This
document is a starting point for the auditor, not a substitute for the audit.
It was produced by static reading and can be wrong.

## Output-path safety re-statement

`LEVEL1_ROOT` for this package is `PROJECT_ROOT/08.18.26_Level1_Audits_R3`, a
sibling of `DISCOVERY_ROOT` and of both failed predecessor packages, and
therefore inside `PROJECT_ROOT`. Checked criterion by criterion:

| criterion | result | evidence |
| --- | --- | --- |
| production input directory | No | no component reads it |
| watched inbox | No | the only watcher watches `wpno-llm-wiki/_inbox` |
| n8n watched folder | No | n8n mounts `mandate-inbox`, `wiki-inboxes` only |
| Docker production mount | No | litellm mounts four named files; n8n mounts three named paths |
| gateway input path | No | `WPNO_gateway.py` has no reference to it |
| import path | No | absent from `pytest.ini` `pythonpath` |
| LaunchAgent working directory | No | the two agents use `WPNO/mcp` and a wiki repo |
| database directory | No | DB artefacts live in `db/`, `docker/`, `authoring/`, `ap18/` |
| report-builder input | No | no builder scans `PROJECT_ROOT` recursively |
| sync source triggering production | No | not inside any synced or mounted path |

Verdict: **output path accepted**. The criteria above were established for the
predecessor packages at sibling paths and are re-stated here for the R3 path;
Codex verification re-derives them from live configuration rather than
inheriting this table.

Two residual effects are recorded rather than hidden:

- **R-01.** `08.18.26_Level1_Audits_R3/` is untracked content in the
  `PROJECT_ROOT` git repository, as are `08.18.26_Level1_Audits/`,
  `08.18.26_Level1_Audits_R2/` and `08.18.26_Discovery/`. `.gitignore` was not
  modified, because it is inside `PROJECT_ROOT`. Anyone running `git clean -fd`
  in `PROJECT_ROOT` would delete all four — which is also the mechanism L1-A25
  examines, and is a reason not to run it. The porcelain capture in
  `build_evidence/` was taken after this package already existed and is never
  described as a pre-existence snapshot; see drift entry D-05.
- **R-02.** `gateway/WPNO_devscan.py` is an operator-invoked recursive PII
  scanner that reads every text file under a given root using the egress
  guard's detector. If it is ever pointed at `PROJECT_ROOT`, it will read this
  package, which contains synthetic IBAN and tax-ID strings authored for
  L1-A18/A19 controls and for the controller's own redaction self-tests. That
  would be a false positive, not a leak. No client data is placed in this
  package.
