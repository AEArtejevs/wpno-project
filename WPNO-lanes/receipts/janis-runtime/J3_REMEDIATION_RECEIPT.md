# J3 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 finding: `L1-A19-RUN-A-F01`
- Result: `SUCCESS`

## Red evidence

The focused three-test suite initially produced one pass and two failures.
Checksum-valid identifiers with no repeat, four repeats, two repeated digits,
or two-and-three repeats were blocked, and a leading-zero identifier was also
blocked. The scanner therefore implemented only MOD 11,10 arithmetic and not
the official structural rules.

## Change

- Added the first-ten-digit rule: exactly one digit repeats, and it repeats
  exactly two or three times.
- Rejected a leading zero before checksum evaluation.
- Applied the same minimal validator change to both active scanner copies.
- Added `anonymization/test_tax_id_validation.py`.
- Kept the historical golden program byte-identical. Its old random generator
  is corrected only in the temporary active test copy so generated Steuer-IDs
  satisfy the official repetition rule.

## Proof

- Focused Mac J3/golden suite: 5 passed.
- Focused Ubuntu J3/golden suite: 5 passed.
- Full Mac lane suite: 16 passed.
- Full Ubuntu lane suite: 16 passed.
- All 25 REF-04 vectors eligible for the scanner's contiguous 11-digit
  validator boundary agreed with the immutable R9 oracle; zero mismatches.
- Repetition/leading-zero bypass mutation: focused test failed twice.
- Active scanner copies are byte-identical.
- Every changed Python file compiled successfully.
- Both scanner files are 496 lines; all changed files remain under 500 lines.
- Historical golden program SHA-256 remained
  `dc83acf66bdb9aab18f03efaa1b292c1f9a6b1f405439ecc4dd928fd069960b0`.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- `anonymization/payload_scan.py`: baseline
  `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b`,
  final `006ea6a7c2e7312810a4851a3915e3f47a455787056c01b789a6b9b5e2f1225c`.
- `docker/litellm/payload_scan.py`: same baseline and final hashes.
- `anonymization/test_tax_id_validation.py`: baseline absent, final
  `444f98cb65a566c16383787f34b843305c5d45bf50228b3500e9a33f211e17be`.
- `anonymization/test_payload_golden.py`: J2 hash
  `7eaaf9da149cd92808a32504a5d65ef9297a10c4d7b3c34fa3aa1eb838dc4269`,
  final `f1acf1629ea3c6655034f48495f60868bf0e8c070bf9cc5bcd1f4e6fd3802168`.

## Limitations

- This remediation changes only scanner validation behavior in the isolated
  lane. It does not alter the sealed R9 verdict or prove productive deployment.
