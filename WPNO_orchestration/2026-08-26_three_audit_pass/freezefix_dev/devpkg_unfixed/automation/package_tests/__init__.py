"""Tests that must run against the real R5 package, not the replica.

The controller self-tests run inside `verification/selftest_runtime` because
they rewrite `state/`. These do the opposite: they assert facts about this
package — that R4 is unchanged, that the lineage copy is byte-identical, that
the migrated references are equal, that the DER anchor stages correctly. A
replica has none of that material, so asserting it there would assert nothing.

Nothing here writes outside `work/_r5_selftest/`.
"""
