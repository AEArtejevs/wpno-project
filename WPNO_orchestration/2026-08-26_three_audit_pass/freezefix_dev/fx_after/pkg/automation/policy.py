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
#
# R5 MEASUREMENT (Ubuntu). On this machine `C.UTF-8` is a real installed
# locale: `locale -a` lists `C.utf8` and a process started under
# LC_ALL=C.UTF-8 reports preferred encoding UTF-8 and round-trips umlauts.
# The macOS caveat above therefore does not apply to an Ubuntu run. The
# value is still not changed, because the contract is the contract; it is
# now measured rather than merely inherited.

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
#
# R5 CHANGE (known cause 5). R4 covered `results/<audit>/RUN-A` and
# `evidence/<audit>/RUN-A` and stopped there. It did not cover
# `work/<audit>/RUN-A`, which is where RUN-A's mutation fixtures, staged
# material and intermediate outputs actually live. A RUN-B handed that
# directory could reconstruct RUN-A's reasoning from its working set without
# ever touching `results/` — the covered path was not the only path. The
# work tree is now covered for every replicated audit, and so is the
# operator-intake material that carries a RUN-A conclusion.
REPLICATED_AUDIT_IDS_FOR_ISOLATION = ("L1-A18", "L1-A19", "L1-A31", "L1-A34")


def _run_a_directory_fragments():
    """Every `<tree>/<audit>/RUN-A` directory a RUN-B may not reference.

    Built from the audit list rather than typed out, so a new replicated audit
    cannot be added to the registry while silently missing from the guard.
    That drift is exactly how `work/` came to be uncovered in R4.
    """
    out = []
    for tree in ("results", "evidence", "work"):
        for audit in REPLICATED_AUDIT_IDS_FOR_ISOLATION:
            out.append("%s/%s/RUN-A" % (tree, audit))
    return tuple(out)


# Filenames that carry a RUN-A conclusion wherever they sit, including inside
# `work/operator_intake/`. Operator intake is migrated evidence and a RUN-B may
# legitimately read parts of it; these parts are not among them.
RUN_A_CONCLUSION_FILE_FRAGMENTS = (
    "/RUN-A/verdict.json",
    "/RUN-A/findings.json",
    "/RUN-A/self_critique.md",
    "/RUN-A/disproof.md",
    "/RUN-A/report.md",
    "/RUN-A/commands.jsonl",
    "/RUN-A/plan.json",
    "/RUN-A/plan.sha256",
)

# Operator-intake material that states or implies a RUN-A conclusion. Matched
# case-insensitively against the normalized path by the isolation check.
RUN_A_OPERATOR_INTAKE_FRAGMENTS = (
    "operator_intake/l1-a31/2026-08-21_provenance_findings",
    "operator_intake/l1-a31/2026-08-21_provenance_conclusions_after_mail_zip",
    "operator_intake/l1-a31/2026-08-21_provenance_review",
    "operator_intake/l1-a31/2026-08-21_mail_zip_provenance_report",
    "operator_intake/l1-a31/2026-08-21_mail_zip_provenance_plan_review",
    "operator_intake/l1-a31/2026-08-21_p7s_cms_parse_report",
    "operator_intake/l1-a31/2026-08-21_combined_p7s_cms_parse_plan_review",
    "operator_intake/l1-a31/2026-08-21_ref11_import_report",
    "operator_intake/l1-a31/2026-08-21_ref11_import_plan_review",
    "operator_intake/l1-a31/reference_selection_review",
    "operator_intake/l1-a31/2026-08-21_human_provenance_questionnaire",
    "operator_intake/l1-a31/comparison_",
)

RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS = (
    _run_a_directory_fragments()
    + RUN_A_CONCLUSION_FILE_FRAGMENTS
)

# The complete set the normalized-path check uses. Kept separate from the
# tuple above so the R4 contract for that name is not widened silently.
RUN_B_FORBIDDEN_PATH_FRAGMENTS_NORMALIZED = tuple(
    f.lower() for f in RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS
) + RUN_A_OPERATOR_INTAKE_FRAGMENTS

# The complete allowlist of what a RUN-B context may contain. RUN-B isolation
# is an allowlist, not a denylist: anything not named here cannot reach RUN-B,
# so a leak has to be added deliberately rather than merely forgotten about.
RUN_B_ALLOWED_KEYS = (
    "audit_id",
    "phase_sequencing",
    "run_a_terminal",
    "run_a_seal_integrity",
    "target_path",
    "target_sha256",
    "immutable_pre_run_packet",
    "validation_time",
    "independent_method",
    "required_controls",
    "run_phase",
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
