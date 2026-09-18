"""The independent CMS verifier: a bounded wrapper around the Java program.

RUN-B exists to be able to disagree with RUN-A. Two runs of the same openssl
binary cannot disagree about anything except their arguments, so the second
opinion has to come from a different implementation. This is that
implementation's entry point.

What makes it materially independent, stated so it can be checked rather than
believed:

  * a different language and runtime - JDK 21, not the C openssl binary;
  * a different cryptographic library - Bouncy Castle 1.85, not OpenSSL 3.5.5;
  * a different path-validation engine - the JDK's PKIX CertPathValidator,
    not OpenSSL's X509_verify_cert;
  * no shared code, no shared configuration, and no shared trust store.

The Java program launches no subprocess of its own and never calls OpenSSL.
This wrapper launches exactly one process, with a bounded timeout, a bounded
output, an explicit environment and a fixed working directory - the same
discipline every other subprocess in this package runs under.
"""

import json
import os
import subprocess

from . import hashing, path_policy, policy


class IndependentCmsError(Exception):
    pass


TOOL_ROOT = os.path.join(path_policy.LEVEL1_ROOT, "tools")
CLASSES_DIR = os.path.join(TOOL_ROOT, "cms_verifier", "classes")
JAR_DIR = os.path.join(TOOL_ROOT, "bouncycastle")

JARS = ("bcprov-jdk18on-1.85.2.jar",
        "bcpkix-jdk18on-1.85.jar",
        "bcutil-jdk18on-1.85.jar")

MAIN_CLASS = "WpnoCmsVerify"
JAVA = "/usr/bin/java"

TIMEOUT_SECONDS = 180
OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024

# The checks the Java program reports. Listed here so that a silently removed
# check is a failure of this wrapper rather than an unnoticed gap: a verifier
# that stops checking something and still exits 0 is the failure mode this
# whole package exists to prevent.
REQUIRED_CHECKS = (
    "cms_parses",
    "is_detached_signature",
    "exactly_one_signer",
    "signer_id_matches_supplied_leaf",
    "signed_attributes_present",
    "message_digest_attribute_present",
    "message_digest_matches_content",
    "signature_verifies",
    "certificate_path_validates_against_explicit_anchor",
    "all_certificates_valid_at_validation_time",
)


def available():
    """Is the independent verifier built and usable on this machine?"""
    if not os.path.exists(JAVA):
        return False, "java is not installed at %s" % JAVA
    if not os.path.exists(os.path.join(CLASSES_DIR, MAIN_CLASS + ".class")):
        return False, "the verifier is not compiled: %s" % CLASSES_DIR
    for jar in JARS:
        if not os.path.exists(os.path.join(JAR_DIR, jar)):
            return False, "missing validated JAR: %s" % jar
    return True, "JDK 21 + Bouncy Castle 1.85, compiled and present"


def classpath():
    parts = [CLASSES_DIR] + [os.path.join(JAR_DIR, j) for j in JARS]
    for part in parts:
        if not os.path.exists(part):
            raise IndependentCmsError("classpath element missing: %s" % part)
    return ":".join(parts)


def _readable(path):
    path_policy.assert_no_symlink_escape(path)
    return path_policy.assert_readable(path)


def build_argv(cms, content, leaf, root, validation_time, intermediate=None):
    """The exact argv. Every input explicit, nothing defaulted."""
    if isinstance(validation_time, bool) or not isinstance(validation_time, int):
        raise IndependentCmsError(
            "validation_time must be an integer epoch second; a verifier that "
            "defaults to 'now' gives a different answer on every run")
    if validation_time <= 0:
        raise IndependentCmsError("validation_time must be positive")

    argv = [JAVA, "-cp", classpath(), MAIN_CLASS,
            "--cms", _readable(cms),
            "--content", _readable(content),
            "--leaf", _readable(leaf),
            "--root", _readable(root),
            "--validation-time", str(validation_time)]
    if intermediate:
        argv += ["--intermediate", _readable(intermediate)]

    for flag in policy.FORBIDDEN_CLI_OPTIONS:
        if flag in argv:
            raise IndependentCmsError("forbidden option in argv: %s" % flag)
    return argv


def verify(cms, content, leaf, root, validation_time, intermediate=None):
    """Run the independent verifier once. Returns (result, argv, exit_code).

    A non-zero exit is an answer, not an error: the point of a verifier is to
    be able to say no.
    """
    argv = build_argv(cms, content, leaf, root, validation_time,
                      intermediate=intermediate)

    inputs = {"cms": cms, "content": content, "leaf": leaf, "root": root}
    if intermediate:
        inputs["intermediate"] = intermediate
    before = {k: hashing.sha256_file(v) for k, v in inputs.items()}

    try:
        proc = subprocess.run(  # noqa: S603 - argv list, shell=False
            argv, shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
            env=policy.base_environment(), cwd=path_policy.LEVEL1_ROOT,
            check=False)
    except subprocess.TimeoutExpired:
        raise IndependentCmsError(
            "independent verifier timed out after %ds" % TIMEOUT_SECONDS)

    stdout = proc.stdout[:OUTPUT_LIMIT_BYTES]
    stderr = proc.stderr[:OUTPUT_LIMIT_BYTES]

    after = {k: hashing.sha256_file(v) for k, v in inputs.items()}
    if before != after:
        raise IndependentCmsError(
            "the independent verifier changed its inputs; a verifier that "
            "alters what it measures is not a verifier")

    try:
        result = json.loads(stdout.decode("utf-8"))
    except ValueError:
        raise IndependentCmsError(
            "independent verifier produced no parsable result (exit %s): %s"
            % (proc.returncode,
               stderr.decode("utf-8", "replace")[:400]))

    # A missing check is only a defect when the verifier claims success.
    #
    # The first version of this guard raised whenever any required check was
    # absent. That turned a legitimate refusal into a crash: a certificate
    # mutated by one byte can be corrupt enough that it does not parse at
    # all, the Java program reports a fatal error and stops before running
    # the later checks, and stopping early is the correct behaviour -- the
    # answer is still "not verified". Which of the two failure modes a
    # one-byte mutation produces depends on where the byte lands, so the
    # crash appeared only on some fixture generations.
    #
    # The property worth enforcing is the other one: a verifier that reports
    # success while quietly not having checked something. That is what this
    # guard now says.
    missing = [c for c in REQUIRED_CHECKS if c not in result]
    result["checks_reported"] = [c for c in REQUIRED_CHECKS if c in result]
    result["checks_not_reached"] = missing
    if missing and result.get("verified"):
        raise IndependentCmsError(
            "the independent verifier reported success without reporting %r"
            % missing)

    result["input_sha256"] = before
    result["inputs_unchanged"] = True
    result["exit_code"] = proc.returncode
    return result, argv, proc.returncode
