# R7 — the actual Level-1 scope, all 35 audits

Derived, not authored. Every column below is read from the package's own registry, bindings, prompts and phase rules; the generator is `build/all_level1_scope/build_all_level1_scope.py`.

    EXPECTED_AUDIT_COUNT=35
    DISCOVERED_AUDIT_COUNT=35
    DUPLICATE_AUDIT_IDS=0
    UNKNOWN_AUDIT_IDS=0
    MISSING_SPECIFICATIONS=0
    MISSING_BINDINGS=0

Required phases in total: **43** — 35 RUN-A, 4 RUN-B, 4 COMPARISON.

Execution order is a unique 1..N sequence: True.

No audit's written specification contradicts the controller-owned order, replication count or phase rule.

## Per audit

| # | audit | phases | target state | refs required | refs missing | deps |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | L1-A31 | RUN-A RUN-B COMPARISON | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-08 REF-09 REF-10 REF-11 | REF-10 | — |
| 2 | L1-A34 | RUN-A RUN-B COMPARISON | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-08 REF-09 REF-11 | — | — |
| 3 | L1-A18 | RUN-A RUN-B COMPARISON | TARGET_PRESENT_HASH_MATCHES | REF-01 REF-02 | — | — |
| 4 | L1-A19 | RUN-A RUN-B COMPARISON | TARGET_PRESENT_HASH_MATCHES | REF-03 REF-04 | — | — |
| 5 | L1-A17 | RUN-A | TARGET_PRESENT_HASH_MATCHES | REF-14 | — | — |
| 6 | L1-A20 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 7 | L1-A21 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-13 | — | — |
| 8 | L1-A22 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 9 | L1-A05 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 10 | L1-A06 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 11 | L1-A07 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 12 | L1-A08 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 13 | L1-A09 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 14 | L1-A10 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 15 | L1-A11 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-05 | REF-05 | — |
| 16 | L1-A12 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-07 | — | — |
| 17 | L1-A13 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 18 | L1-A14 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-06 | — | — |
| 19 | L1-A15 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 20 | L1-A16 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 21 | L1-A01 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 22 | L1-A02 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 23 | L1-A03 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 24 | L1-A04 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | L1-A03 |
| 25 | L1-A23 | RUN-A | TARGET_PRESENT_HASH_MATCHES | REF-14 | — | — |
| 26 | L1-A24 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | — | — | — |
| 27 | L1-A25 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 28 | L1-A26 | RUN-A | TARGET_PRESENT_HASH_MATCHES | — | — | — |
| 29 | L1-A27 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | — |
| 30 | L1-A28 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | — |
| 31 | L1-A29 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 REF-12 | REF-12 | — |
| 32 | L1-A30 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | — |
| 33 | L1-A32 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | — |
| 34 | L1-A33 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | — |
| 35 | L1-A35 | RUN-A | NO_PRODUCTIVE_TARGET_IN_BINDING | REF-11 | — | L1-A34 |

`target state` is measured on this machine at generation time, not copied from the binding. `refs missing` names a reference the audit requires that intake has not accepted; it is a statement about this package's contents, not about whether the material exists.

