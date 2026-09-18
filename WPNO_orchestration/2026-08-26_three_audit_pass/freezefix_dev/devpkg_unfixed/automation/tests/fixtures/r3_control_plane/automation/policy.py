"""Global policy constants for the Level-1 controller.

Nothing here is configurable at runtime. A policy that can be relaxed by a
flag is not a policy, and every flag that exists will eventually be used.
"""

import os

MODE_GENERATED = "GENERATED_UNVERIFIED"
MODE_FROZEN = "FROZEN"

# --- verdicts -------------------------------------------------------------
VERDICTS = (
    "PASS",
    "PASS_WITH_WARNINGS",
    "FAIL",
    "BLOCKED",
    "UNVERIFIED",
    "ERROR",
    "CONTAMINATED",
)
TERMINAL_VERDICTS = VERDICTS

# --- execution limits -----------------------------------------------------
DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 900
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_EVIDENCE_FILE_BYTES = 64 * 1024 * 1024

# --- environment ----------------------------------------------------------
# Allowlist, not a denylist. A variable absent here is not passed through.
ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TZ",
    "PYTHONHASHSEED",
    "SOURCE_DATE_EPOCH",
    "TMPDIR",
)
ENV_FIXED = {
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}
# NOTE FOR THE AUDITOR, recorded rather than silently changed: CLAUDE.md § 8
# states that `C.UTF-8` is not a real locale on this macOS build and falls back
# to ASCII. The value above is the predecessor package's contract and its
# self-test asserts it verbatim. Changing it would change a control the
# verifier has not been asked to change, so it is left exactly as it was and
# carried as an open item in `discovery_reconciliation/12_OPEN_ITEMS.md`. It
# affects the decoding of subprocess output containing umlauts, not any path,
# hash or approval decision.

# A fixed, absolute PATH. Inheriting PATH from the caller is a hijack surface:
# a directory prepended to PATH replaces every tool the controller relies on.
FIXED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"

# --- executables ----------------------------------------------------------
# Fixed absolute identity. Never resolved through PATH at call time.
EXECUTABLES = {
    "python3": "/usr/bin/python3",
    "git": "/usr/bin/git",
    "shasum": "/usr/bin/shasum",
    "openssl": "/usr/bin/openssl",
    "unzip": "/usr/bin/unzip",
    "zipinfo": "/usr/bin/zipinfo",
    "tar": "/usr/bin/tar",
    "file": "/usr/bin/file",
    "stat": "/usr/bin/stat",
}

# --- dangerous source patterns -------------------------------------------
# Assembled from fragments so that this file does not itself contain the
# literal token a scanner searches for. The scanner in `_dangerous_tokens`
# is used by the self-tests and by the Codex verification prompt.
def _dangerous_tokens():
    return (
        "shell" + "=True",
        "os." + "system",
        "sub" + "process.getoutput",
        "e" + "val(",
        "e" + "xec(",
        "__im" + "port__(",
        "pickle." + "loads",
        "yaml." + "load(",
    )


DANGEROUS_TOKENS = _dangerous_tokens()

# --- approval -------------------------------------------------------------
APPROVAL_PREFIX = "APPROVE-EXECUTION"
APPROVAL_SUFFIX = "RUN-ONCE"
FREEZE_PREFIX = "FREEZE-LEVEL1"
ACK_PREFIX = "ACKNOWLEDGE-CRITICAL"

# Options that must not exist. Listed so the self-tests can assert their
# absence from the controller's argument parser.
FORBIDDEN_CLI_OPTIONS = (
    "--auto-approve",
    "--yes",
    "--yes-to-all",
    "--run-all",
    "--no-pause",
    "--bypass-approval",
    "--force",
)

# --- replication ----------------------------------------------------------
CRITICAL_REPLICATED_AUDITS = ("L1-A18", "L1-A19", "L1-A31", "L1-A34")
RUN_PHASES_REPLICATED = ("RUN-A", "RUN-B", "COMPARISON")
RUN_PHASES_SINGLE = ("RUN-A",)

# Keys a RUN-B context may never contain. RUN-B isolation is enforced by
# construction, not by asking the model not to look.
#
# These are KEY names. They are matched against dictionary keys only, never
# against values. The predecessor package matched them against a serialised
# blob, so the legitimate value "RUN-A" of the `run_phase` field tripped the
# guard and every valid RUN-A context was rejected. A control that rejects the
# thing it exists to permit is not a stricter control; it is a broken one.
RUN_B_FORBIDDEN_KEYS = (
    "findings",
    "verdict",
    "self_critique",
    "disproof",
    "disproof_attempt",
    "expected_conclusion",
    "conclusion",
    "run_a",
    "RUN-A",
)

# Result paths a RUN-B context may never reference, in any string value.
# A key-only check cannot see a leak that arrives as a file path, so the two
# checks sit side by side and neither substitutes for the other.
RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS = (
    "results/L1-A18/RUN-A",
    "results/L1-A19/RUN-A",
    "results/L1-A31/RUN-A",
    "results/L1-A34/RUN-A",
    "evidence/L1-A18/RUN-A",
    "evidence/L1-A19/RUN-A",
    "evidence/L1-A31/RUN-A",
    "evidence/L1-A34/RUN-A",
    "/RUN-A/verdict.json",
    "/RUN-A/findings.json",
    "/RUN-A/self_critique.md",
    "/RUN-A/disproof.md",
    "/RUN-A/report.md",
)

# --- roots that must never be written to ---------------------------------
NEVER_WRITE_PREFIXES = (
    "/Library",
    "/private",
    "/tmp",
    "/System",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/var",
)
NEVER_WRITE_HOME_SUBDIRS = (
    ".codex",
    ".claude",
    "Library",
    ".ssh",
    ".config",
    ".gnupg",
)

# --- symlink resolution bounds -------------------------------------------
# A bounded depth turns an unbounded resolution loop into a rejection with a
# message. The number is small on purpose: a legitimate path in this package
# never needs a chain this long.
MAX_SYMLINK_DEPTH = 16


def base_environment():
    """Return the exact environment handed to a subprocess.

    Built from the allowlist plus the fixed values. Nothing is inherited that
    is not named. PATH is always the fixed absolute value.
    """
    env = {}
    for name in ENV_ALLOWLIST:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    env.update(ENV_FIXED)
    env["PATH"] = FIXED_PATH
    return env
