# Independent pre-freeze verification of R8 — attempt 8

Result: **VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL**.

The audit stopped on the durable adverse result recorded for item 23. The bytes themselves report zero missing in-process evidence, zero note-only steps, and 169 handler invocations equal to 169 in-process steps. However, my completed scratch predicate compared those values with non-existent unprefixed reconciliation keys (the record uses `R8_IN_PROCESS_HANDLER_INVOCATIONS` and `R8_UNIQUE_IN_PROCESS_PLAN_STEPS`) and wrote `pass: false`. The instructions explicitly say a completed adverse result stands and must not be rerun, so this attempt cannot issue a pass. This is a verifier-instrument defect; the measured R8 values support item 23's substantive claim.

The multi-item scratch block did not stop internally and completed items 24–27 before raising `FileNotFoundError: state/freeze_attempts.jsonl` at item 28. The file is permitted to be absent; the code should have checked absence. Because item 23 had already triggered the stop condition, I did not repair and rerun item 28. Items 28–30 and 34–35 remain not verified.

Measured roots: read-only checks used ORIGINAL; controller and static-safety suites used CLONE; package tests used CLONE with the single location-bound test rerun unmodified at ORIGINAL. The package suite effectively passed all 361 tests; the controller suite passed all 503 tests. Static safety was clean with zero findings.

Write isolation remained intact. Both full ORIGINAL inventories contained 1,362 paths and compared equal on type, size, SHA-256, symlink target, mode, uid, gid, and mtime_ns. Manifest-fold digests before and after were both `e7d3d32e70b9782c0da9d04be31ba68b4f1ace29ddae4fbbe2495b5e565b97eb`. The clone control file was observed by one absolute canonical path; its mtime advanced from 1787935556841911690 to 1787945105532801228 while its bytes remained equal to ORIGINAL, proving the instrument live.

The build manifest digest measured `6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a` with 724 entries, zero malformed lines, duplicates, missing paths, scope differences, or hash mismatches.
