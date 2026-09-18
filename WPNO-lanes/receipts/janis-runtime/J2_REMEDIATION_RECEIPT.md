# J2 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 findings: `L1-A18-RUN-A-F01`, `L1-A18-RUN-A-F02`
- Result: `SUCCESS`

## Red evidence

The focused four-test IBAN suite initially produced one pass and three failures:

- an invalid-checksum German IBAN was still blocked because the German pattern
  had no validator;
- a Mod-97-valid Austrian value with an alphabetic character in its numeric
  BBAN was still blocked;
- a Mod-97-valid Austrian value with the wrong country length was still blocked.

## Change

- Added `anonymization/iban_validation.py` with the SWIFT registry release 102
  length and fixed-BBAN structures for 89 country codes plus streaming Mod-97.
- Connected both `iban` and `iban_intl` patterns to that validator in both
  active scanner candidates.
- Added a read-only Compose mount for the validator helper.
- Added `anonymization/test_iban_validation.py` with ten source-bound valid
  REF-02 vectors and malformed check-digit-valid controls.
- Updated the active J1 wrapper to stage the new helper. The historical golden
  program remains byte-identical; its old structure-invalid LV generator is
  corrected only in the temporary active test copy.

## Proof

- Focused Mac J2 suite: 4 passed.
- Focused Ubuntu J2 suite: 4 passed.
- Full Mac lane suite: 13 passed.
- Full Ubuntu lane suite: 13 passed.
- Immutable R9 REF-02 matrix: 217 applicable vectors, zero mismatches.
- German-validator bypass mutation: focused test failed.
- Country-structure bypass mutation: focused test failed.
- Docker candidate import path validated valid and invalid German controls.
- Active scanner copies are byte-identical.
- Every changed Python file compiled successfully.
- All changed source/test files are under 500 lines.
- Historical golden program SHA-256 stayed
  `dc83acf66bdb9aab18f03efaa1b292c1f9a6b1f405439ecc4dd928fd069960b0`.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- `anonymization/payload_scan.py`: baseline
  `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b`,
  final `4cd1beae37c346644c1c290b6d241d04279bc1144fd6d96eeb933fdf43e340d0`.
- `docker/litellm/payload_scan.py`: same baseline and final hashes.
- `anonymization/iban_validation.py`: baseline absent, final
  `ac8c5212c387faa3fdc2bf1830689867eadc3325e9f540564d30ed42275a75e1`.
- `anonymization/test_iban_validation.py`: baseline absent, final
  `9712d5f6d79e65304053adbf82148a2a94f8948bb27b7fd5260b938ad049b79b`.
- `anonymization/test_payload_golden.py`: J1 hash
  `3871001831150acbca05b87c81435f5158b8bf79638e8d274496e8b3f0bdd1c8`,
  final `7eaaf9da149cd92808a32504a5d65ef9297a10c4d7b3c34fa3aa1eb838dc4269`.
- `docker/litellm/docker-compose.yml`: baseline
  `cdd162fa4145c4617f8c71956cc570c50e1c9a4a1da69007b6cbd2c034281329`,
  final `0992f43ffd2ea92bd3a4f1bb15a2a9e314b88274d2b768af73acbfd5880c9649`.

## Limitations

- No container was started and no image was built or pulled.
- Productive invocation remains a later human deployment and fresh-audit gate.
- This receipt does not alter the sealed R9 verdict.
