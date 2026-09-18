# A7 Remediation Receipt — AP18 DOCX Injection Edges

- Scope: isolated Andris remediation lane only.
- Findings addressed: `L1-A16-RUN-A-F01` and `L1-A16-RUN-A-F02`.
- Filter input SHA-256: `a9ba953f66c03a552dff654f842b7648ab28cad5d2116d03764938d844bc5f92`.
- Filter output SHA-256: `623ae5b3392340360aabf408476dd6ff7a324b063407f6ec48e8e0ef23a99807`.
- Focused A7 test SHA-256: `9b30a4b69e820719c379027c09137072fd42d302402e1efd444f9cb9a82aa69d`.

## Red baseline

The focused tests reproduced three failures before the change: the exact
mixed-script instruction was not recognized, a reader-visible DOCX carrying it
was `FREI`, and the exact payload-bearing external relationship was `FREI`.
The plain-instruction and benign-external-link controls behaved correctly.

## Minimal change

- Instruction matching applies Unicode normalization plus only the confirmed
  Cyrillic `I/i` to Latin `I/i` mapping.
- DOCX relationship declarations are parsed offline. External targets are
  decoded and tokenized for instruction matching, but are never resolved.
- Only payload-bearing external targets generate a finding; the clean external
  hyperlink control remains `FREI`.

No package, network access, live WPNO source, controller, reference, or sealed
evidence was changed.

## Validation

- Focused A7 suite: 5/5 passed under normal and optimized Python.
- Confusable-map-disabled mutation: killed with two failures.
- Relationship-inspection-disabled mutation: killed with one failure.
- Cumulative authoring suite: 25/25 passed under normal and optimized Python.
- Cumulative AP18 suite: 10/10 passed under normal and optimized Python.
- Syntax compilation passed; the filter remains under the 500-line limit at
  483 lines.

## A5 compatibility correction

A7 legitimately changed the opening lines of `anweisungen_finden`, exposing a
brittle A5 mutation test that searched for a fixed two-line string. That test
now locates the function by AST line range before replacing it with the same
deliberate allow-all mutation. Its new SHA-256 is
`9fba2302de6a1ab01000da999cf2b0056e67f7d245633a3634dffda9a4e82a08`.
The product behavior and A5 target/configuration were not changed.

## Integrity

- Live and baseline filter copies remained
  `a9ba953f66c03a552dff654f842b7648ab28cad5d2116d03764938d844bc5f92`.
- R9 post-change verification: 63 sealed attempts, 63 intact, zero tampered.

Outcome: A7 complete in the isolated remediation lane.
