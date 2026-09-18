"""Level-1 audit controller, package revision R3.

Standard library only. No third-party dependency. No installation step.

This package is generated control-plane code. It was NOT executed, imported,
byte-compiled or tested during the R3 package build. Codex verification runs
the self-tests under `tests/` inside an isolated replica before the package may
be frozen.

Writing boundary: every path this package writes to must resolve below
LEVEL1_ROOT. `path_policy` enforces that and is the single place the rule
lives. The three roots are resolved at runtime from `paths.json`; no user name
appears in this package.
"""

__all__ = [
    "audit_context",
    "codex_adapter",
    "controller",
    "evidence",
    "hashing",
    "locking",
    "operation_catalog",
    "path_policy",
    "policy",
    "redaction",
    "schema_validation",
    "state_machine",
]

PACKAGE_VERSION = "3.0.0-generated-unverified"
BUILD_REVISION = "R3"
