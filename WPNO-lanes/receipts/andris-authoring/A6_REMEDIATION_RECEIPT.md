# A6 Remediation Receipt — AP17 Unicode and Visual Evasion

- Scope: isolated Andris remediation lane only.
- Findings addressed: `L1-A08-RUN-A-F01` through `L1-A08-RUN-A-F05`.
- Source input SHA-256: `d77c09816055638ff560cbc080626881b1663ecea6f1293315ef52738bd9bdf1`.
- Source output SHA-256: `d778f4066b6fadb7710453f1ab5d11b0dbec1c2b99dded9929f3f85b9d412818`.
- Focused test SHA-256: `94432c239c1638da56741a9e6a46929c71d60ba4e71b1ad0b0110c60d6f0add0`.

## Red baseline

The focused matrix reproduced the sealed audit result before the source change:
11 reader-equivalent variants were missed. The exact-name positive control and
all five clean controls behaved as expected.

## Minimal change

Name matching now uses a comparison-only shadow that:

- applies Unicode compatibility/canonical normalization;
- removes Unicode format controls;
- normalizes whitespace and line breaks;
- removes a period only when embedded between word characters; and
- maps only the confirmed Cyrillic `o/O` and `e/E` confusables.

The original document text and reported forbidden-name value are preserved.
No package, network, live WPNO source, controller, reference, or sealed evidence
was changed.

## Validation

- Focused A6 suite: 7/7 passed under normal Python.
- Focused A6 suite: 7/7 passed under optimized Python.
- Coverage: all 12 sealed edge variants detected; all five clean controls clear.
- Normalization-disabled mutation: killed with 11 failures.
- Homoglyph-map-disabled mutation: killed with two failures.
- Cumulative authoring suite: 25/25 passed under normal and optimized Python.
- Cumulative AP18 suite: 5/5 passed under normal and optimized Python.
- Syntax compilation passed; source is 403 lines and test is 70 lines.

## Integrity

- Live source remained `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca`.
- Baseline copy remained `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca`.
- R9 post-change verification: 63 sealed attempts, 63 intact, zero tampered.

Outcome: A6 complete in the isolated remediation lane.
