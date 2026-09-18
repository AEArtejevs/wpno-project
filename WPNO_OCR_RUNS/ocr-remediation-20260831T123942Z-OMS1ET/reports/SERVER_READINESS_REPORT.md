# WPNO OCR Server Readiness Report

Overall status: **NOT_READY**

Created: 2026-08-31T12:40:58Z  
Host: ip-172-31-17-52  
User: ubuntu  
Preparation working directory: `/home/ubuntu`  
Ubuntu: 26.04 LTS (Resolute Raccoon)  
Kernel: `7.0.0-1006-aws` x86_64  

## Step status

1. **PASS — Host facts captured.** Two CPUs. Memory 952,856,576 bytes; swap 2,147,479,552 bytes; combined 3,100,336,128 bytes. Root/home filesystem is ext-family (`df` reports ext4; `statfs` reports ext2/ext3), with 30,010,245,120 bytes total, 25,720,389,632 bytes used, and 4,273,078,272 bytes available at the final measurement. Inodes: 3,637,760 total, 383,703 used, 3,254,057 free. Open-file limit 524,288; process limit 2,092; stack limit 8,192 KiB. A bounded process summary was readable. The listening-port query returned no entries. No OCR/database-related environment-variable names were present. No values or secrets were recorded.
2. **PASS — Project discovery.** Exactly one candidate met the “all or nearly all” rule: `/home/ubuntu/project/WPNO` (7/8 markers). It is a real directory, device 66305, mode 0775, containing 103,846 regular files totaling 4,127,257,370 bytes. It has zero symlinks and therefore no external symlinks. The only absent marker is root `AGENTS.md`; all seven functional markers are present. Nested `AGENTS.md` files occur only within unrelated audit/archive subtrees and do not govern this root-level preparation output.
3. **PASS — Inputs validated.** Exactly one readable copy of each exact filename was found in the bounded search. The JSON manifest parsed successfully; both manifests are nonempty.
4. **NOT_READY — Resource requirements failed.** Current free space is 4,273,078,272 bytes (~3.98 GiB), below the required 15 GiB and also insufficient for a 4,127,257,370-byte copy plus the 12 GiB reserve (required minimum 17,012,159,146 bytes). RAM plus swap is 3,100,336,128 bytes (~2.89 GiB), below 4 GiB. Free inodes pass: 3,254,057 available versus 227,692 required (twice 103,846 files plus 20,000).
5. **BLOCKED — Isolated coding workspace not created.** A mode-0700 diagnostic run root was created outside the source solely to retain this failure report. No `input`, `work/WPNO`, baseline, checkpoint, or temporary workspace was created.
6. **BLOCKED — Project/input copy not attempted** because Step 4 failed.
7. **BLOCKED — Baseline not created** because there is no working copy.
8. **BLOCKED — RUN_CONTEXT.json and READY not created.** A `NOT_READY` marker records this result.
9. **PASS — Operator hold instructions written.** They explicitly prohibit launching remediation from this failed run.

## Source and markers

Selected source real path: `/home/ubuntu/project/WPNO`

Present markers: `AP-06-07 Test/test.py`, `AP-06-07 Test/AP-07/test.py`, `AP-06-07 Test/split_pdf.py`, `rag/ingest_seiten.py`, `db/ddl/002_schema_v2_corrected.sql`, `docs/AP-07_evidence.md`, `Testkatalog_Protokoll.md`.

## Required inputs

| Path | SHA-256 | Bytes | Owner | Mode | Modified UTC |
|---|---|---:|---|---|---|
| `/home/ubuntu/project/WPNO/Prompts/OCR_FINDINGS_REMEDIATION_MANIFEST.json` | `d89c670c8167acd53441ba7c2fc1d31ffb2205c6912af61b03501d54e4100458` | 5,608 | ubuntu | 0664 | 2026-08-31 11:00:40.746797692 |
| `/home/ubuntu/project/WPNO/Prompts/OCR_FINDINGS_REMEDIATION_MANIFEST.md` | `7cb3827995260592b4b498307a482893fd20ea54d712da90eca9604e18330920` | 20,634 | ubuntu | 0664 | 2026-08-31 11:00:40.622796753 |
| `/home/ubuntu/project/WPNO/Prompts/AWS_OCR_OVERNIGHT_REMEDIATION_PROMPT_NO_GIT.md` | `826220098efe69c0b133e6d76e17d6e0bd6a7282c87efec1cc81a6185c253c99` | 17,246 | ubuntu | 0664 | 2026-08-31 12:21:07.026202838 |

No baseline hashes exist because copying was correctly blocked.

## Tools and service readability

Available: Codex CLI 0.151.0, tmux 3.6, rsync 3.4.1, sha256sum 0.8.0, Python 3.14.4, jq 1.8.1, Docker client 29.1.3, and GNU coreutils/process/network inspection utilities. Absent: Podman, psql, pytest, tesseract, pdftoppm, pdfinfo, and qpdf. Docker is **not readable** by the current user: access to `/var/run/docker.sock` was denied. Podman is absent. Codex Goal mode could not be confirmed from CLI help text; the CLI is installed and `/goal` is referenced by the supplied execution workflow.

## Blockers and remediation

- Increase available storage on the target filesystem to at least 17,012,159,146 bytes for this measured source plus reserve, while also satisfying the independent 15 GiB-currently-free gate. A modest safety margin above that number is recommended because the source may grow.
- Increase physical RAM plus swap to at least 4 GiB. This preparation did not add swap or change the host.
- Rerun the preparation prompt after those host-level changes. Tool absences and unreadable Docker should then be evaluated against the later remediation’s actual runtime needs; no packages or permissions were changed here.

The preserved source project was not modified. Its pre/post marker state remained present during checks. No version-control command was run. No OCR, tests, database writes, service changes, package operations, uploads, or external transmissions occurred.
