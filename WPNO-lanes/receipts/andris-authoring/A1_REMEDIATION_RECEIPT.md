# A1 remediation receipt

- Date: 2026-09-01
- Lane: `ANDRIS-AUTHORING`
- Owner: Andris
- Writer: Codex desktop through the authorized SSH connection
- R9 finding: `L1-A06-RUN-A-F02`
- Result: `COMPLETED_WITH_RUNTIME_LIMITATION`

## Scope

Only the isolated lane was changed. The real project source and sealed R9 package were not modified.

Changed files:

- `authoring/AP17_output_guardrail_v3.py`
- `authoring/test_ap17_missing_config.py` (new focused regression test)

## Hashes

- Target baseline SHA-256: `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca`
- Target final SHA-256: `aaebbc54bfeeacf81f221c9c2904b3ccc1028d87a2608c0e6220350edf332cfd`
- Focused test SHA-256: `7d4bad5b2b80072aaea604eacc7b782443acef5c4b7c020008fcfd71d3d20472`

## Red reproduction

The missing reference configuration produced:

- exit `1`;
- uncaught traceback: yes;
- `FileNotFoundError`: yes;
- semantic report: absent;
- ledger file: created without a semantic configuration result.

## Fix

Reference configuration loading now validates the JSON boundary and handles missing, unreadable, malformed, or non-object configuration as a semantic `BLOCKED` result. It writes the report and ledger record, emits no traceback, and preserves exit `1`.

## Green evidence

Direct missing-file control:

- exit `1`;
- traceback: no;
- report result: `BLOCKED`;
- ledger status: `BLOCKED`.

Standard-library regression suite:

- normal Python: 4 tests passed;
- optimized Python (`-O`): 4 tests passed;
- missing configuration: passed;
- malformed configuration: passed;
- valid configuration reaches document validation: passed;
- labelled synthetic known-good document remains `ALLOWED`: passed.

Mutation control:

- removed `OSError` handling in a temporary candidate only;
- mutation count: 1;
- test exit: 1;
- mutation killed: yes.

Static checks:

- AST parse: passed;
- trailing-whitespace lines: 0;
- high-confidence secret-pattern files: 0;
- both changed files remain below 500 lines.

## Wider regression limitation

`WPNO_versionsvergleich_test.py` and `AP18_referenzpruefung_test.py` could not start because the audited Ubuntu runtime has no external `zip` executable. No package was installed. This is recorded as a runtime limitation, not as a passed regression and not as an A1 source failure. Later sections may replace that test-only dependency with the Python standard library where it is within scope.

The server also has no pytest executable. The A1 regression uses `unittest` and remains compatible with later pytest collection work in A5.

## Integrity

- Git commands used: none.
- Package installation: none.
- Network downloads: none.
- Real client data used in controls: none.
- R9 post-change verification: `ok=true`, `tampered=0`, `intact=63/63`.
- Ordinary baseline comparison reports only the two files listed above.

This receipt is remediation evidence only. It does not change the sealed R9 verdict; formal closure requires a fresh remediation audit revision.
