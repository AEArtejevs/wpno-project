# A5 Remediation Receipt — Collectable AP18 Injection Tests

Date: 2026-09-01  
Lane: `/home/ubuntu/project/WPNO-lanes/andris-authoring`  
Finding: `L1-A15-RUN-A-F01`

## Scope

Only the isolated AP18 injection-test module, pytest configuration, and one focused collection-contract test were changed. `AP18_eingangsfilter.py` remained byte-identical. The live WPNO source, baseline mirror, R9, references, and sealed evidence remained read-only.

## Red reproduction

The corrected red-phase contract produced four failures:

- `ap18` was absent from configured pytest test paths;
- the `AP18_test_*.py` filename pattern was not configured;
- the hash-bound AP18 injection module had zero `test_*` functions and zero `assert` statements;
- importing or loading the module exited immediately because PyMuPDF was unavailable.

## Fix

- Add `ap18` to `pytest.ini` test paths and Python paths.
- Add `AP18_test_*.py` to pytest's configured filename patterns.
- Move the PyMuPDF import into the PDF-only effectiveness path so DOCX test collection does not require that optional dependency.
- Add three pytest/unittest-compatible synthetic DOCX tests directly to `AP18_test_injection.py`.
- Add 11 real Python `assert` statements for pytest assertion rewriting and parallel unittest assertions so optimized Python cannot make the suite vacuous.
- Preserve the existing command-line corpus runner; missing PyMuPDF now produces a controlled per-PDF test error instead of import-time termination.

## Source binding

- Starting `AP18_test_injection.py` SHA-256: `f01e65bc9eff2efec3cac2f55ef5238ea5a28139fec2080e6004816c7181eb9d`
- Final `AP18_test_injection.py` SHA-256: `a8bf0467165fe478feebf8433c9e24cc81a48d20d9b2507e8eef32bee2611855`
- Unchanged `AP18_eingangsfilter.py` SHA-256: `a9ba953f66c03a552dff654f842b7648ab28cad5d2116d03764938d844bc5f92`
- Starting `pytest.ini` SHA-256: `3259aae6b1feea94c78ee30440a63e82f2e4d5a4caa5a291820307c83323f227`
- Final `pytest.ini` SHA-256: `d00e6af3e61b18cb437f13318998ef971d4a3cec9a9f9b48246f85375f1520ec`
- Collection-contract test SHA-256: `83b5d36705f93ac058482e8b246095a3707645c56a0030df685bcb49436d9511`
- Line counts: target 233; contract test 117; pytest configuration 6.

## Validation

- Three functional AP18 injection tests passed: clean DOCX `FREI`, hidden instruction `BLOCKIERT`, visible instruction `PRUEFEN`.
- Five collection-contract/mutation checks passed.
- The allow-all instruction-detector mutation caused the hidden-instruction test to fail in both normal and optimized child runtimes.
- Eight A5 tests passed under normal Python and under `python3 -O`.
- Twenty-six combined A1–A5 tests passed under normal and optimized Python.
- AST parsing passed; ordinary diffs were reviewed; no trailing whitespace or secret-pattern match was found.

The combined run emitted Python 3.14 `ResourceWarning` messages for SQLite connections created by the previously completed AP17 test helpers. All tests still passed; A5 does not modify those earlier receipt-bound test files.

The audited Ubuntu runtime has no pytest module (`pytest_available=False`). No package was installed. Therefore actual `pytest --collect-only` execution remains unavailable; collection readiness is established by the configuration/AST contract and executable unittest loading, and must be confirmed in the later dependency-complete R10 runtime.

## Integrity and result

The real WPNO copies retained their original hashes. Post-change R9 verification returned 63 intact records out of 63 sealed attempts, `ok: true`, and no tampering. Test-generated Python cache files were removed.

Result: `COMPLETED_WITH_RUNTIME_LIMITATION`.

This receipt is remediation evidence, not a replacement R9 verdict.
