"""The closed set of operations the controller may perform.

An operation is a name plus a builder that produces an argv array. There is no
path from a text string to a command. If an operation is not here, it cannot
happen, and adding one is a change to this file that Codex re-verifies.

An `IN_PROCESS` operation has no argv, because it launches no process. Its
implementation lives in `in_process_ops` and its schema in
`in_process_executor`, and the correspondence between the three is asserted
by `in_process_executor.self_check`, not assumed: R7 classified sixteen
operations here and implemented none of them, and nothing noticed because
nothing compared the two lists.
"""

import os

from . import path_policy, policy


class OperationError(Exception):
    pass


class ForbiddenOperation(OperationError):
    """The operation is on the forbidden list. Not gated — forbidden."""


class UnknownOperation(OperationError):
    pass


AUTOMATIC = (
    "READ_FILE_RANGE",
    "LIST_DIRECTORY",
    "STAT_FILE",
    "FILE_TYPE",
    "PROVE_SET_NOVELTY",
    "SHA256_FILE",
    "COMPARE_HASHES",
    "COMPARE_BINARY_FILES",
    "GIT_STATUS_READONLY",
    "GIT_SHOW_READONLY",
    "GIT_LOG_READONLY",
    "ZIP_LIST",
    "TAR_LIST",
    "PYTHON_AST_PARSE",
    "PARSE_JSON_READONLY",
    "PARSE_CSV_READONLY",
    "COUNT_TEXT_MATCHES",
)

GATED = (
    "PYTEST_COLLECT_SANDBOX",
    "PYTEST_RUN_SANDBOX",
    "PYTHON_SCRIPT_RUN_SANDBOX",
    "OPENSSL_PARSE_CERT",
    "OPENSSL_VERIFY_CERT_CHAIN",
    "OPENSSL_VERIFY_CMS",
    "ARCHIVE_EXTRACT_SANDBOX",
    "DOCX_PARSE_SANDBOX",
    "XML_PARSE_SANDBOX",
    "MIME_EXTRACT_XML_PART_SANDBOX",
    "CLAUDE_LOAD_BEHAVIOUR_TEST",
    "DOCKER_METADATA_IMPORT",
    "DATABASE_EVIDENCE_IMPORT",
    "AUDIT_MODULE_RUN",
)

# Modules `AUDIT_MODULE_RUN` may execute. An allowlist, not a pattern: the
# operation runs frozen code by name, and a name the catalogue does not know
# is refused rather than resolved.
#
# Why this operation exists (R7). A phase that needs a second implementation —
# L1-A18's Java validator, L1-A31 and L1-A34's Bouncy Castle verifier — has to
# run something. `PYTHON_SCRIPT_RUN_SANDBOX` requires the script to live under
# `work/`, which is deliberately outside the control manifest because that is
# where runs write. A plan step pointing there would run executable code the
# freeze does not cover: the package frozen, the thing it runs not. Running a
# frozen module by name keeps the code inside the manifest and still produces
# a real subprocess with a real argv, stdout and stderr for the evidence.
RUNNABLE_AUDIT_MODULES = (
    "automation.a18_run_a_cli",
    "automation.a18_run_b_cli",
    "automation.a19_run_a_cli",
    "automation.a19_run_b_cli",
    "automation.independent_cms_cli",
)

FORBIDDEN = (
    "ARBITRARY_SHELL",
    "DELETE_SOURCE",
    "MODIFY_SOURCE",
    "CHANGE_PERMISSION",
    "INSTALL_PACKAGE",
    "NETWORK_REQUEST",
    "NETWORK_UPLOAD",
    "GIT_MUTATION",
    "DOCKER_SOCKET_ACCESS",
    "DOCKER_BUILD",
    "DOCKER_RUN",
    "DOCKER_EXEC",
    "DATABASE_CONNECTION",
    "DATABASE_WRITE",
    "SERVICE_MUTATION",
    "LAUNCH_AGENT_MUTATION",
    "MCP_MUTATION",
    "N8N_MUTATION",
)

# Operations performed in-process with the standard library. They produce no
# subprocess at all, which is the safest form an operation can take.
IN_PROCESS = frozenset((
    "READ_FILE_RANGE", "LIST_DIRECTORY", "STAT_FILE", "SHA256_FILE",
    "COMPARE_HASHES", "COMPARE_BINARY_FILES", "PYTHON_AST_PARSE",
    "PARSE_JSON_READONLY", "PARSE_CSV_READONLY", "COUNT_TEXT_MATCHES",
    "ZIP_LIST", "TAR_LIST", "XML_PARSE_SANDBOX", "DOCX_PARSE_SANDBOX",
    "DOCKER_METADATA_IMPORT", "DATABASE_EVIDENCE_IMPORT",
    # R8. L1-A33's accepted reference is named .xml and is a MIME multipart
    # entity wrapping the XML. The reference is not altered; the intended
    # part is decoded into work/ and the XML parser is pointed at that. This
    # is the only IN_PROCESS operation that writes, and it writes below
    # work/ or it refuses.
    "MIME_EXTRACT_XML_PART_SANDBOX",
    # R8. L1-A16 must prove five authored cases are absent from the existing
    # corpus. Its plan bound COMPARE_HASHES to two directories, which cannot
    # run and could not answer a per-case question if it did.
    "PROVE_SET_NOVELTY",
))


# Operations no process on this machine performs. They happen on another
# host, under an approval bound to an execution packet, and what returns is a
# hash-bound evidence record rather than a subprocess result. The controller
# records them and never launches them; `automation.external_host_evidence`
# holds the packet and intake rules.
#
# They are kept apart from IN_PROCESS on purpose. IN_PROCESS means "this
# machine does it with the standard library and no subprocess"; this means
# "this machine does not do it at all". Collapsing the two would let a step
# that must leave the building look like one that never leaves the function.
OPERATOR_PERFORMED = frozenset((
    "CLAUDE_LOAD_BEHAVIOUR_TEST",
))


def classify(name):
    if name in FORBIDDEN:
        return "FORBIDDEN"
    if name in GATED:
        return "GATED"
    if name in AUTOMATIC:
        return "AUTOMATIC"
    raise UnknownOperation("operation not in catalogue: %r" % name)


def requires_approval(name):
    return classify(name) == "GATED"


def _exe(key):
    path = policy.EXECUTABLES[key]
    if not os.path.isabs(path):
        raise OperationError("executable must be absolute: %r" % path)
    return path


def _read(path):
    """Admit a read path.

    The symlink guard runs first, on the caller's string, while the components
    it exists to inspect are still present.
    """
    path_policy.assert_no_symlink_escape(path)
    return path_policy.assert_readable(path)


def _sandbox(path):
    """A path that must be inside the writable work area, not merely readable."""
    canonical = path_policy.assert_writable(path)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not (canonical == work_root or canonical.startswith(work_root + os.sep)):
        raise OperationError("sandbox operations must run under work/: %s" % canonical)
    return canonical


def build_argv(name, params):
    """Return the argv array for a subprocess operation.

    Every element is a literal or a policy-admitted path. No element is ever
    built by joining user or model text into a command line, and no element
    is interpreted by a shell — there is no shell in the call path.
    """
    kind = classify(name)
    if kind == "FORBIDDEN":
        raise ForbiddenOperation("operation is forbidden: %s" % name)
    if name in IN_PROCESS:
        raise OperationError(
            "%s is performed in-process and has no argv" % name)

    if name == "FILE_TYPE":
        return [_exe("file"), "--brief", "--", _read(params["path"])]

    if name == "GIT_STATUS_READONLY":
        return [_exe("git"), "-C", _read(params["repo"]), "status", "--porcelain"]

    if name == "GIT_LOG_READONLY":
        argv = [_exe("git"), "-C", _read(params["repo"]), "log", "-1",
                "--no-color", "--"]
        if params.get("path"):
            argv.append(_read(params["path"]))
        return argv

    if name == "GIT_SHOW_READONLY":
        rev = params["rev"]
        if not isinstance(rev, str) or any(c.isspace() for c in rev):
            raise OperationError("git rev must be a single bare token")
        return [_exe("git"), "-C", _read(params["repo"]), "show", "--no-color",
                "--no-ext-diff", rev]

    if name == "PYTEST_COLLECT_SANDBOX":
        return [_exe("python3"), "-m", "pytest", "--collect-only", "-q",
                "--rootdir", _sandbox(params["rootdir"]), _sandbox(params["target"])]

    if name == "PYTEST_RUN_SANDBOX":
        return [_exe("python3"), "-m", "pytest", "-vv", "-p", "no:cacheprovider",
                "--rootdir", _sandbox(params["rootdir"]), _sandbox(params["target"])]

    if name == "PYTHON_SCRIPT_RUN_SANDBOX":
        argv = [_exe("python3"), "-I", "-B", _sandbox(params["script"])]
        for arg in params.get("args", []):
            if not isinstance(arg, str):
                raise OperationError("script arguments must be strings")
            argv.append(arg)
        return argv

    if name == "AUDIT_MODULE_RUN":
        module = params.get("module")
        if module not in RUNNABLE_AUDIT_MODULES:
            raise OperationError(
                "module %r is not in the runnable audit-module allowlist %r"
                % (module, list(RUNNABLE_AUDIT_MODULES)))
        # `-I` isolates the interpreter: no user site directory, no
        # PYTHONPATH, no current directory on sys.path. `-B` writes no
        # bytecode.
        #
        # The module cannot be reached with `-m` under `-I`, because `-I` is
        # precisely what removes the working directory from sys.path — the
        # rehearsal found this before the freeze, with
        # "No module named 'automation'". It is reached through the frozen
        # launcher at the package root instead: under `-I` the interpreter
        # puts the script's own directory first on sys.path, and that
        # directory is the package root. The launcher re-checks the module
        # against this same allowlist, so the check is made on both sides.
        launcher = os.path.join(path_policy.LEVEL1_ROOT, "run_audit_module.py")
        argv = [_exe("python3"), "-I", "-B", _read(launcher), module]
        for arg in params.get("args", []):
            if not isinstance(arg, str):
                raise OperationError(
                    "audit-module arguments must be strings, got %r"
                    % (type(arg).__name__,))
            if arg.startswith("-") and arg not in _module_option_allowlist():
                raise OperationError(
                    "audit-module option %r is not allowed; an option the "
                    "catalogue does not know is not passed through" % arg)
            argv.append(arg)
        for flag in policy.FORBIDDEN_CLI_OPTIONS:
            if flag in argv:
                raise ForbiddenOperation(
                    "forbidden option in audit-module argv: %s" % flag)
        return _reject_suppression(argv)

    if name == "OPENSSL_PARSE_CERT":
        return [_exe("openssl"), "x509", "-in", _read(params["cert"]),
                "-noout", "-text", "-fingerprint", "-sha256"]

    if name == "OPENSSL_VERIFY_CERT_CHAIN":
        anchor = _pem_anchor(params["anchor"])
        leaf = _operand(_read(params["leaf"]))
        argv = [_exe("openssl"), "verify"]
        argv += NO_DEFAULT_TRUST_FLAGS
        argv += ["-CAfile", anchor]
        if params.get("intermediates"):
            argv += ["-untrusted", _read(params["intermediates"])]
        argv += ["-attime", str(_attime(params.get("attime")))]
        if params.get("purpose"):
            argv += ["-purpose", _purpose(params["purpose"])]
        # No `--` here. See END_OF_OPTIONS_NOTE.
        argv.append(leaf)
        return _reject_suppression(argv)

    if name == "OPENSSL_VERIFY_CMS":
        inform = params.get("inform", "DER")
        if inform not in ("DER", "PEM", "SMIME"):
            raise OperationError("unknown CMS input format: %r" % inform)
        anchor = _pem_anchor(params["anchor"])
        argv = [_exe("openssl"), "cms", "-verify"]
        # Canonicalization mode. Detached CMS over an octet stream is signed
        # with `-binary`; verifying the same bytes without it makes OpenSSL
        # apply MIME text canonicalization first, the digest then does not
        # match, and the failure is reported as
        #   CMS_SignerInfo_verify_content: verification failure
        # which is indistinguishable from a genuinely altered file. Measured
        # on the R5 synthetic fixture: same signature, same content, exit 4
        # without the flag and exit 0 with it. It is therefore explicit and
        # recorded, never inferred.
        if params.get("binary", True):
            argv.append("-binary")
        argv += NO_DEFAULT_TRUST_FLAGS
        argv += ["-in", _read(params["cms"]),
                 "-inform", inform,
                 "-CAfile", anchor]
        # A detached CMS with no content is a signature over nothing the
        # caller named. It is required, not optional: R4 made it optional and
        # an omitted `-content` is indistinguishable in the exit code from a
        # verified one.
        if not params.get("content"):
            raise OperationError(
                "OPENSSL_VERIFY_CMS requires an explicit detached content "
                "path; a CMS verified without naming its content proves "
                "nothing about any file")
        argv += ["-content", _read(params["content"])]
        if params.get("certfile"):
            argv += ["-certfile", _read(params["certfile"])]
        argv += ["-attime", str(_attime(params.get("attime")))]
        if params.get("purpose"):
            argv += ["-purpose", _purpose(params["purpose"])]
        argv += ["-out", _sandbox(params["out"])]
        return _reject_suppression(argv)

    if name == "ARCHIVE_EXTRACT_SANDBOX":
        return [_exe("unzip"), "-q", "-n", _read(params["archive"]),
                "-d", _sandbox(params["dest"])]

    if name in OPERATOR_PERFORMED:
        raise OperationError(
            "%s is operator-performed and has no argv on this machine. It is "
            "carried out on the external host named in its execution packet, "
            "under an approval bound to that packet's digest, with HOME, "
            "TMPDIR and every cache and configuration output redirected below "
            "the audit's own work directory. What returns is a hash-bound "
            "intake record, admitted by "
            "automation.external_host_evidence.validate_intake. The controller "
            "does not launch it and never writes to the external directory."
            % name)

    raise UnknownOperation("no argv builder for %s" % name)



# --------------------------------------------------------------------------
# R5 CHANGE (known cause 1): the end-of-options separator
# --------------------------------------------------------------------------
END_OF_OPTIONS_NOTE = """
R4's OPENSSL_VERIFY_CERT_CHAIN builder ended every argv with

    ..., "--", <leaf path>

`--` is the POSIX end-of-options separator and it is correct for `file(1)`,
which is why `FILE_TYPE` still uses it and why its use looked safe. The
`verify` applet of LibreSSL — the openssl on the macOS machine R4 ran on —
does not implement it. It treated `--` as an unrecognised option, printed its
usage block to stderr and exited 1, before reading a single certificate.

That is what the sealed R4 evidence records. Every OPENSSL_VERIFY_CERT_CHAIN
operation of L1-A31 RUN-A (E0007, E0008, E0009, E0010, E0013) has the same
usage text as its stderr. The positive synthetic-chain control, E0008, is
among them. A positive control that never ran cannot pass, the audit could
not distinguish "control failed" from "chain invalid", and RUN-A ended ERROR.

The separator is removed rather than made conditional. It was never load
bearing: every operand reaches this builder through `path_policy`, which
admits absolute paths only, and an absolute path begins with `/` and can
never be parsed as an option. `_operand` asserts that property instead of
assuming it, so the guarantee the separator was supposed to give is now
actually checked.
"""

# Explicit refusal of every default trust source. Naming an anchor with
# -CAfile does not by itself stop OpenSSL consulting its built-in file,
# directory and store, so a chain could verify against a CA the audit never
# named and the exit code would look identical.
NO_DEFAULT_TRUST_FLAGS = ("-no-CAfile", "-no-CApath", "-no-CAstore")

# Purposes the catalogue will emit. An arbitrary string here becomes an
# arbitrary token on a command line.
ALLOWED_PURPOSES = (
    "any", "smimesign", "smimeencrypt", "sslclient", "sslserver",
    "crlsign", "timestampsign", "ocsphelper",
)


def _module_option_allowlist():
    """Options an audit module may be given.

    Every one belongs to a frozen CLI in `RUNNABLE_AUDIT_MODULES` and is
    listed here so that an option arriving from a plan cannot be a flag the
    catalogue has never seen. `--sabotage` is here on purpose: the sabotage
    control is part of the method and is recorded in the argv, which is where
    a reader can see that it ran.
    """
    return frozenset((
        "--vectors", "--rules", "--out", "--work-dir", "--sabotage",
        "--cms", "--content", "--leaf", "--root", "--intermediate",
        "--validation-time",
    ))


def _operand(path):
    """A non-option positional argument.

    The end-of-options separator is not emitted (see END_OF_OPTIONS_NOTE), so
    the property it was standing in for is asserted here directly.
    """
    if not path.startswith("/"):
        raise OperationError(
            "operand must be an absolute path so it cannot be read as an "
            "option: %r" % path)
    return path


def _attime(value):
    """The validation time. Required, never defaulted.

    Omitting `-attime` does not mean "no time". It means "now", which is a
    different answer on every run and is not reproducible.
    """
    if value is None:
        raise OperationError(
            "a verification time is required; omitting -attime silently means "
            "'now', which is a different answer on every run")
    if isinstance(value, bool) or not isinstance(value, int):
        raise OperationError(
            "attime must be an integer epoch second; verification time is "
            "never left to the clock")
    if value <= 0:
        raise OperationError("attime must be a positive epoch second")
    return value


def _purpose(value):
    if value not in ALLOWED_PURPOSES:
        raise OperationError(
            "purpose %r is not in the allowed set %r"
            % (value, list(ALLOWED_PURPOSES)))
    return value


def _pem_anchor(path):
    """Admit a trust anchor for `-CAfile`, refusing DER by inspection.

    `-CAfile` reads PEM. R4 handed it DER and the failure surfaced as a
    certificate error rather than an encoding error. The check is on the
    file's first bytes, not on its extension: a name is not evidence of a
    format.

    A DER anchor is not rejected as unusable — it is rejected *here*, with the
    instruction to stage it, because `trust_material.stage_der_anchor_as_pem`
    is the only sanctioned way to obtain a PEM form of it.
    """
    canonical = _read(path)
    with open(canonical, "rb") as fh:
        head = fh.read(64)
    if head.lstrip()[:5] == b"-----":
        return canonical
    if head[:1] == b"\x30":
        raise OperationError(
            "-CAfile requires PEM and %s is DER (first byte 0x30). The "
            "reference is valid and must not be replaced: stage a PEM copy "
            "under work/ with trust_material.stage_der_anchor_as_pem and pass "
            "the staged copy." % canonical)
    raise OperationError(
        "-CAfile input is neither PEM nor DER: %s" % canonical)


SUPPRESSION_FLAGS = (
    # R4 set
    "-noverify", "-nosigs", "-no_attr_verify", "-no_content_verify", "-nocerts",
    # R5 additions. Each of these turns a failed verification into a passing
    # exit code while leaving the command looking like a verification.
    "-no_signer_cert_verify",
    "-noattr",
    "-nointern",
    "-ignore_critical",
    "-no_check_time",
    "-partial_chain",
    "-x509_ignore_critical",
    "-check_ss_sig_off",
    "-allow_proxy_certs",
)


def _reject_suppression(argv):
    """Refuse to build a verification command that suppresses verification.

    These flags turn a verification into a parse while leaving the exit code
    looking the same. They are not merely discouraged in a prompt: the
    controller cannot emit them.
    """
    for flag in SUPPRESSION_FLAGS:
        if flag in argv:
            raise ForbiddenOperation(
                "verification suppression flag %s may not appear in a "
                "verification command" % flag)
    return argv


def validate_plan_operations(plan):
    """Every operation in a plan must be in the catalogue and not forbidden.

    Returns the list of operations that will need human approval.
    """
    gated = []
    for step in plan.get("steps", []):
        name = step.get("operation")
        kind = classify(name)
        if kind == "FORBIDDEN":
            raise ForbiddenOperation("plan contains forbidden operation: %s" % name)
        if kind == "GATED":
            gated.append(name)
    return gated
