# J4 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 findings in Janis ownership: `L1-A09-RUN-A-F01`, `F03`, `F04`
- Result: `SUCCESS_JANIS_SCOPE`

## Red evidence

The focused four-test suite initially produced two passes and two failures.
Domestic phone numbers immediately preceded by comma or period were missed,
and lower/upper/mixed-case street and locality forms were missed.

## Change

- Allowed comma and period as normal left delimiters for domestic phone values
  while retaining digit and slash boundary protection.
- Made both street-address and postal-locality patterns case-insensitive.
- Accepted both `Straße` and `Strasse`, including ordinary uppercase rendering.
- Applied identical changes to both active scanner copies.
- Added `anonymization/test_case_delimiter_matrix.py` with positive case and
  delimiter rows plus clean delimiter controls.

## Proof

- Focused Mac J4 suite: 4 passed.
- Focused Ubuntu J4 suite: 4 passed.
- Full Mac lane suite: 20 passed.
- Full Ubuntu lane suite: 20 passed.
- Lowercase and title-case German IBAN controls remained detected.
- Phone-boundary rollback mutation: focused test failed.
- Address-case rollback mutation: focused test failed.
- Active scanner copies are byte-identical and compile successfully.
- Both scanner files remain 496 lines.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- Both active scanner copies: J3
  `006ea6a7c2e7312810a4851a3915e3f47a455787056c01b789a6b9b5e2f1225c`,
  final `97bff976839ace8b6c1d934d7071477d968bdd1be10124fd5123f86c0a865932`.
- `anonymization/test_case_delimiter_matrix.py`: baseline absent, final
  `3387cfef82309c5c01a142319c76e2053540f8021d8b077d391b0ff8ff9be512`.

## Scope boundary

`L1-A09-RUN-A-F02` applies to
`authoring/AP17_output_guardrail_v3.py`, which is not present in or owned by
the Janis runtime lane. It was not modified here. The equivalent payload
scanner lower/title-case IBAN controls already pass; this does not claim the
separate AP17 finding is remediated.

## Limitations

- No container was started. This receipt does not alter sealed R9 or prove a
  productive deployment.
