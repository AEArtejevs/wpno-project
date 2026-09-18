"""The closed set of operations the controller may perform.

An operation is a name plus a builder that produces an argv array. There is no
path from a text string to a command. If an operation is not here, it cannot
happen, and adding one is a change to this file that Codex re-verifies.
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
    "CLAUDE_LOAD_BEHAVIOUR_TEST",
    "DOCKER_METADATA_IMPORT",
    "DATABASE_EVIDENCE_IMPORT",
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

    if name == "OPENSSL_PARSE_CERT":
        return [_exe("openssl"), "x509", "-in", _read(params["cert"]),
                "-noout", "-text", "-fingerprint", "-sha256"]

    if name == "OPENSSL_VERIFY_CERT_CHAIN":
        argv = [_exe("openssl"), "verify", "-CAfile", _read(params["anchor"])]
        if params.get("intermediates"):
            argv += ["-untrusted", _read(params["intermediates"])]
        if params.get("attime"):
            attime = params["attime"]
            if not isinstance(attime, int):
                raise OperationError("attime must be an integer epoch second")
            argv += ["-attime", str(attime)]
        if params.get("purpose"):
            argv += ["-purpose", str(params["purpose"])]
        argv += ["--", _read(params["leaf"])]
        return _reject_suppression(argv)

    if name == "OPENSSL_VERIFY_CMS":
        argv = [_exe("openssl"), "cms", "-verify",
                "-in", _read(params["cms"]),
                "-inform", params.get("inform", "DER"),
                "-CAfile", _read(params["anchor"])]
        if params.get("content"):
            argv += ["-content", _read(params["content"])]
        if params.get("certfile"):
            argv += ["-certfile", _read(params["certfile"])]
        argv += ["-out", _sandbox(params["out"])]
        return _reject_suppression(argv)

    if name == "ARCHIVE_EXTRACT_SANDBOX":
        return [_exe("unzip"), "-q", "-n", _read(params["archive"]),
                "-d", _sandbox(params["dest"])]

    if name == "CLAUDE_LOAD_BEHAVIOUR_TEST":
        raise OperationError(
            "CLAUDE_LOAD_BEHAVIOUR_TEST has no fixed argv. It is performed by "
            "the operator under approval, in an operator-approved external "
            "working directory, with HOME, TMPDIR and every cache and "
            "configuration output redirected below the audit's own work "
            "directory. Its transcript is imported as evidence. The controller "
            "does not launch it and never writes to the external directory.")

    raise UnknownOperation("no argv builder for %s" % name)


SUPPRESSION_FLAGS = (
    "-noverify", "-nosigs", "-no_attr_verify", "-no_content_verify", "-nocerts",
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
