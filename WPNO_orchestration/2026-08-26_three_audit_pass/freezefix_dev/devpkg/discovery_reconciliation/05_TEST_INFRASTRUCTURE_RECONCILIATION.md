# 05 — TEST INFRASTRUCTURE RECONCILIATION

## Configuration

`pytest.ini` at `PROJECT_ROOT`, SHA-256
`3259aae6b1feea94c78ee30440a63e82f2e4d5a4caa5a291820307c83323f227`:

```ini
[pytest]
addopts = --import-mode=importlib
testpaths = anonymization docker orchestrator
norecursedirs = test_akte plain_test .git node_modules cases venv
pythonpath = anonymization docker/litellm orchestrator
```

Consequences read statically, to be verified by L1-A22 rather than assumed:

- `testpaths` covers three directories. `authoring/`, `ap18/` and `gateway/`
  are **not** in `testpaths`, so a bare `pytest` at `PROJECT_ROOT` does not
  reach the AP16, AP17, AP18 or gateway tests at all.
- `python_files` is not overridden, so pytest's defaults (`test_*.py`,
  `*_test.py`) apply.
- `pythonpath` adds `anonymization`, `docker/litellm` and `orchestrator`, but
  not `anonymization/golden`.
- `norecursedirs` does not exclude `golden`.

## Test files relevant to the 35 audits

| path | sha256 | reached by bare `pytest`? |
| --- | --- | --- |
| `anonymization/test_payload_scan.py` | `341549bb566487b5f8db8e1bf34bfb73ada93e3c7e3b36f4db6ecd115234fbd1` | in `testpaths` |
| `anonymization/test_payload_corpus.py` | `b6cb47353d2fbac9d0d9d1a0b2671f8a57f8f28a6e19aadd6d9e0e2b4b4ffe94` | in `testpaths` |
| `anonymization/test_audit_hardening.py` | recorded at audit time | in `testpaths` |
| `anonymization/test_copy_sync.py` | recorded at audit time | in `testpaths` |
| `anonymization/golden/payload_scan_golden_test.py` | `dc83acf66bdb9aab18f03efaa1b292c1f9a6b1f405439ecc4dd928fd069960b0` | under `testpaths`; collection is L1-A22's question |
| `docker/litellm/test_payload_scan.py` | `341549bb566487b5f8db8e1bf34bfb73ada93e3c7e3b36f4db6ecd115234fbd1` | in `testpaths` |
| `authoring/AP18_referenzpruefung_test.py` | `5bfc3fa48809d3c55f4287928987dd2e58982af558ddad8941fc5d8f6775b071` | **no** — `authoring/` not in `testpaths` |
| `ap18/AP18_test_injection.py` | `f01e65bc9eff2efec3cac2f55ef5238ea5a28139fec2080e6004816c7181eb9d` | **no** — `ap18/` not in `testpaths`, and the filename matches neither default pattern |
| `gateway/WPNO_egress_guard_test.py` | `e20be533b835f7a3fa7d1dcc96fe1f460269fa62ce77bf3e3bb0cd6dcd3e1546` | **no** — `gateway/` not in `testpaths` |
| `gateway/WPNO_devscan_test.py` | recorded at audit time | **no** |

Note that `anonymization/test_payload_scan.py` and
`docker/litellm/test_payload_scan.py` are byte-identical. Two copies of the same
test are not two tests.

## Tests never run

Level-0 Discovery reports 885 test candidate files, 0 executed during a
read-only discovery. This build executed 0 as well:

```text
WPNO_TESTS_EXECUTED=0
CONTROLLER_SELFTESTS_EXECUTED=0
```

The second line is about this package's own self-tests, and it is a statement
about the R3 build, not a prediction about verification. Codex verification
runs them; this build did not, and does not claim they pass.

`08_UNRUN_TESTS.md` in Discovery is the inventory. `PRUEFAUFTRAG_B_CLAUDE_CODE.md`
§ B11 records `AP18_referenzpruefung.py` as "Never run. On the list since 09.08."

## Manual test instructions found

- `Testkatalog_Protokoll.md` and `WPNO_testkatalog.py`
  (`4d073b9c9667ed7c6324cb0bbcb014f643ea10a5f16f1625e74da9a398684976`) —
  the project's own test catalogue, referencing `verify_document`,
  `test_injection` and `egress_guard`.
- `PRUEFAUFTRAG_B_CLAUDE_CODE.md` / `PRUEFAUFTRAG_B_CODEX.md` — an eleven-check
  audit instruction (B4–B14), separate from these 35 points, whose subject
  matter overlaps L1-A03/A07 (B7, exporter and guardrail version diff),
  L1-A10/A13 (B11), L1-A14 (B12).

That overlap is recorded in `08_SCOPE_GAPS_OUTSIDE_35.md` so that Level-2 can
check the two instruction sets against each other.

## Caches present in the source tree

`.pytest_cache/` at `PROJECT_ROOT` and in `anonymization/`, and `__pycache__/`
directories under `anonymization/`, `anonymization/golden/` and
`docker/litellm/`.

Stated precisely, because the predecessor package's summary of this was wrong
and the verifier recorded it as VF-007: two interpreter generations appear, but
not uniformly. `test_payload_scan` has both a `cpython-311` and a `cpython-314`
artefact, in both `anonymization/` and `docker/litellm/`. `custom_callback` and
`tool_registry_gate` appear only as `cpython-314`. `payload_scan` appears as
`cpython-314` only under `docker/litellm/`, and as both `cpython-311` and
`cpython-314` under `anonymization/`. The twelve artefacts and their hashes are
tabulated in `11_DISCOVERY_DRIFT.md`, entry D-08.

They are evidence that some interpreter imported or collected those modules at
some time, and nothing more: not that the interpreter is current, not that the
artefact matches the present source, not that the module is on a production
path. They were read only as metadata and hashed; none was modified or removed.
The interpreter-version question matters for L1-A15 and L1-A22 and is left to
those audits, which must re-measure rather than inherit this table.
