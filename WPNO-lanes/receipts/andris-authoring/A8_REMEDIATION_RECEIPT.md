# A8 Remediation Receipt — AP17 Full AP18 Classification

- Scope: isolated Andris remediation lane only.
- Finding addressed: `L1-A26-RUN-A-F04`.
- AP17 input SHA-256: `d778f4066b6fadb7710453f1ab5d11b0dbec1c2b99dded9929f3f85b9d412818`.
- AP17 output SHA-256: `d606c9504642b212dfaa14684964f401f74881f2816f513d73e248b7c64775ae`.
- Focused A8 test SHA-256: `dd2438b4362484bc847b004442f5adb7eaf3f08c52e481e1b6b2a1d743a2a2dc`.

## Red baseline

Four of five focused tests failed before the change. AP17 called only
`referenz_laden` and `aktenzeichen_finden`; it allowed the foreign-court and
wide-docket controls, and it blocked the impossible BGH senate only as a
generic unverified citation instead of classifying the impossibility.

## Minimal change

AP17 now calls `AP18_referenzpruefung.pruefen` and consumes every returned
classification: `belegt`, `ungeprueft`, `nicht_vorhanden`, `unplausibel`,
`fremdes_gericht`, `ausserhalb`, and `nicht_strukturell`. Every unresolved or
invalid category blocks the output guard. The document's own separately
validated proceeding docket is excluded from the non-structural citation list.

No AP18 implementation, package, network access, live WPNO source, controller,
reference, or sealed evidence was changed.

## Validation

- Focused A8 suite: 5/5 passed under normal and optimized Python.
- Existing A2 plus A8 integration suite: 8/8 passed in both runtimes.
- Full-classifier-bypass mutation: killed with four failures.
- Foreign-court-block-removal mutation: killed with one failure.
- Cumulative authoring suite: 30/30 passed under normal and optimized Python.
- Cumulative AP18 suite: 10/10 passed under normal and optimized Python.
- Syntax compilation passed; AP17 remains under the 500-line limit at 418.

## A2 test compatibility correction

The older A2 DOCX fixture used the placeholder namespace `urn:test`, which the
full OOXML classifier correctly does not recognize. It now uses the official
WordprocessingML namespace and explicitly closes its SQLite read connection.
Its new SHA-256 is
`dd17518a2d2b8ec82b5c779f2d6190244b3f00780298360d80b9163b498fbae7`.
No A2 product behavior was weakened.

## Integrity

- Live and baseline AP17 copies remained
  `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca`.
- R9 post-change verification: 63 sealed attempts, 63 intact, zero tampered.

Outcome: A8 complete in the isolated remediation lane.
