"""Controlled staging of a DER trust anchor as PEM.

Why this module exists (R5, known cause 2). The L1-A34 RUN-A harness handed
`references/REF-08-safe-root-ca-2017.der` straight to `openssl ... -CAfile`.
`-CAfile` reads PEM. The certificate was never the problem: it is valid DER,
it is the right anchor, and it is not missing. The harness was the problem.

Measured, both platforms, same input:

    macOS LibreSSL 3.3   -> exit 2, "Error loading file <path>"
    Ubuntu OpenSSL 3.5.5 -> exit 4, certificate verify error

Two different messages for one defect, and neither says "this file is DER".
That is the whole hazard: a tool that is handed the wrong encoding reports
something that reads like a finding about the evidence.

The rule this module enforces is therefore narrow and absolute:

  * the DER reference is never modified, never replaced, never converted in
    place, and nothing is ever written inside `references/`;
  * a PEM copy is staged under `work/`, used once, and kept as evidence;
  * the staged copy is proved to be the same certificate as the source, by
    fingerprint, subject, issuer and public key, before anything trusts it;
  * only that staged copy is passed as `-CAfile`.

Conversion is done in-process. DER-to-PEM is base64 with a header and a
footer, and doing it here rather than through `openssl x509 -outform PEM`
removes a subprocess from the trusted path and makes the output byte-identical
on every platform. OpenSSL is still used, but only to *read* both files back
and state what they contain, which is the part that has to be independent of
our own encoder.
"""

import base64
import json
import os
import subprocess
import time

from . import hashing, path_policy, policy


class TrustMaterialError(Exception):
    pass


PEM_LINE_LENGTH = 64
CERTIFICATE_PEM_HEADER = "-----BEGIN CERTIFICATE-----"
CERTIFICATE_PEM_FOOTER = "-----END CERTIFICATE-----"

# Bounded on purpose. A trust anchor is a few kilobytes; anything that is not
# is not an anchor, and refusing early keeps a large file out of memory.
MAX_ANCHOR_BYTES = 64 * 1024

IDENTITY_TIMEOUT_SECONDS = 30
IDENTITY_OUTPUT_LIMIT_BYTES = 256 * 1024


def _openssl(argv_tail):
    """Run one bounded, shell-free openssl read-only command.

    Fixed executable, fixed cwd, explicit environment, bounded time and
    bounded output. No shell exists anywhere in this path.
    """
    exe = policy.EXECUTABLES["openssl"]
    if not os.path.isabs(exe):
        raise TrustMaterialError("openssl path must be absolute: %r" % exe)
    argv = [exe] + list(argv_tail)
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, shell=False
            argv,
            shell=False,
            capture_output=True,
            timeout=IDENTITY_TIMEOUT_SECONDS,
            env=policy.base_environment(),
            cwd=path_policy.LEVEL1_ROOT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise TrustMaterialError(
            "openssl timed out after %ds while reading certificate identity"
            % IDENTITY_TIMEOUT_SECONDS)
    out = proc.stdout[:IDENTITY_OUTPUT_LIMIT_BYTES]
    err = proc.stderr[:IDENTITY_OUTPUT_LIMIT_BYTES]
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def _identity(path, informat):
    """Subject, issuer, SHA-256 fingerprint and public key of one certificate.

    Read with openssl so that the answer does not come from the same code that
    produced the file.
    """
    argv = ["x509", "-inform", informat, "-in", path, "-noout",
            "-subject", "-issuer", "-fingerprint", "-sha256"]
    code, out, err = _openssl(argv)
    if code != 0:
        raise TrustMaterialError(
            "openssl could not read %s as %s: %s"
            % (path, informat, err.strip()[:300]))

    fields = {}
    for line in out.splitlines():
        if line.startswith("subject="):
            fields["subject"] = line.split("=", 1)[1].strip()
        elif line.startswith("issuer="):
            fields["issuer"] = line.split("=", 1)[1].strip()
        elif "Fingerprint=" in line:
            fields["fingerprint_sha256"] = line.split("=", 1)[1].strip().upper()

    code, pubkey, err = _openssl(
        ["x509", "-inform", informat, "-in", path, "-noout", "-pubkey"])
    if code != 0:
        raise TrustMaterialError(
            "openssl could not read the public key of %s: %s"
            % (path, err.strip()[:300]))
    fields["public_key_pem"] = pubkey.strip()
    fields["public_key_sha256"] = hashing.sha256_text(pubkey.strip())

    for required in ("subject", "issuer", "fingerprint_sha256"):
        if required not in fields:
            raise TrustMaterialError(
                "openssl did not report %s for %s" % (required, path))
    return fields


def der_to_pem_bytes(der):
    """Encode DER certificate bytes as PEM. In-process, no subprocess.

    The output is the standard 64-column base64 body between the certificate
    header and footer, with a trailing newline — byte-identical on every
    platform, which a subprocess conversion is not guaranteed to be.
    """
    if not isinstance(der, bytes):
        raise TrustMaterialError("DER input must be bytes")
    if not der:
        raise TrustMaterialError("DER input is empty")
    if der[0] != 0x30:
        raise TrustMaterialError(
            "input does not begin with an ASN.1 SEQUENCE tag (0x30); it is "
            "not DER. First byte is 0x%02x" % der[0])
    if der.lstrip()[:5] == b"-----":
        raise TrustMaterialError("input is already PEM, not DER")

    body = base64.b64encode(der).decode("ascii")
    lines = [CERTIFICATE_PEM_HEADER]
    lines += [body[i:i + PEM_LINE_LENGTH]
              for i in range(0, len(body), PEM_LINE_LENGTH)]
    lines.append(CERTIFICATE_PEM_FOOTER)
    return ("\n".join(lines) + "\n").encode("ascii")


def _assert_under_work(path):
    canonical = path_policy.assert_writable(path)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not (canonical == work_root or canonical.startswith(work_root + os.sep)):
        raise TrustMaterialError(
            "trust material may only be staged under work/: %s" % canonical)
    return canonical


def _assert_not_in_references(path):
    """Nothing is ever written into references/. Stated separately so the
    error names the rule rather than a generic path rejection."""
    canonical = path_policy.normalize(path)
    refs = os.path.join(path_policy.LEVEL1_ROOT, "references")
    refs = path_policy.normalize(refs) if os.path.exists(refs) else refs
    if canonical == refs or canonical.startswith(refs + os.sep):
        raise TrustMaterialError(
            "conversion inside references/ is forbidden; the reference is "
            "immutable and the staged copy belongs under work/: %s" % canonical)
    return canonical


def stage_der_anchor_as_pem(der_path, dest_path, expected_sha256=None,
                            audit_id=None, run_phase=None):
    """Stage a DER trust anchor as an exclusive PEM copy and prove identity.

    Returns the staging evidence record. Raises unless every identity field of
    the staged copy matches the source.

    `dest_path` must not already exist. Overwriting a staged anchor would make
    the evidence describe a file that is no longer there.
    """
    path_policy.assert_no_symlink_escape(der_path)
    source = path_policy.assert_readable(der_path)

    size = os.path.getsize(source)
    if size > MAX_ANCHOR_BYTES:
        raise TrustMaterialError(
            "trust anchor exceeds MAX_ANCHOR_BYTES: %s (%d bytes)"
            % (source, size))

    der_sha256 = hashing.sha256_file(source)
    if expected_sha256 is not None:
        if not hashing.is_hex64(expected_sha256):
            raise TrustMaterialError(
                "expected_sha256 must be 64 hex characters")
        if der_sha256 != expected_sha256.lower():
            raise TrustMaterialError(
                "source DER SHA-256 mismatch: expected %s, measured %s"
                % (expected_sha256.lower(), der_sha256))

    with open(source, "rb") as fh:
        der = fh.read()

    _assert_not_in_references(dest_path)
    destination = _assert_under_work(dest_path)
    if os.path.exists(destination):
        raise TrustMaterialError(
            "staged PEM already exists and is never overwritten: %s"
            % destination)

    source_identity = _identity(source, "DER")

    pem = der_to_pem_bytes(der)
    path_policy.ensure_dir(os.path.dirname(destination))
    with open(destination, "wb") as fh:
        fh.write(pem)
    os.chmod(destination, 0o444)

    pem_sha256 = hashing.sha256_file(destination)
    staged_identity = _identity(destination, "PEM")

    equality = {
        "fingerprint_equal":
            source_identity["fingerprint_sha256"] == staged_identity["fingerprint_sha256"],
        "subject_equal":
            source_identity["subject"] == staged_identity["subject"],
        "issuer_equal":
            source_identity["issuer"] == staged_identity["issuer"],
        "public_key_equal":
            source_identity["public_key_sha256"] == staged_identity["public_key_sha256"],
    }

    source_sha_after = hashing.sha256_file(source)
    source_unchanged = (source_sha_after == der_sha256)

    record = {
        "schema": "wpno.level1.trust_staging/1",
        "audit_id": audit_id,
        "run_phase": run_phase,
        "source_der_path": os.path.relpath(source, path_policy.LEVEL1_ROOT),
        "source_der_sha256": der_sha256,
        "source_der_sha256_after_staging": source_sha_after,
        "source_reference_unchanged": source_unchanged,
        "staged_pem_path": os.path.relpath(destination, path_policy.LEVEL1_ROOT),
        "staged_pem_sha256": pem_sha256,
        "staged_pem_mode": "0444",
        "conversion_method": "IN_PROCESS_BASE64_NO_SUBPROCESS",
        "conversion_inside_references": False,
        "overwrote_existing": False,
        "source_identity": source_identity,
        "staged_identity": staged_identity,
        "identity_equality": equality,
        "identity_equal": all(equality.values()),
        "system_trust_used": False,
        "default_trust_used": False,
        "staged_at": time.time(),
    }

    if not record["identity_equal"]:
        raise TrustMaterialError(
            "staged PEM is not the same certificate as the DER source: %r"
            % equality)
    if not source_unchanged:
        raise TrustMaterialError(
            "source DER changed during staging: %s -> %s"
            % (der_sha256, source_sha_after))
    return record


def write_staging_evidence(record, out_path):
    """Persist the staging record beside the staged certificate."""
    _assert_not_in_references(out_path)
    canonical = _assert_under_work(out_path)
    path_policy.ensure_dir(os.path.dirname(canonical))
    with open(canonical, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return canonical


def resolve_anchor_for_cafile(anchor_path, staging_dir, audit_id=None,
                              run_phase=None, expected_sha256=None,
                              label=None):
    """Return a path safe to hand to `-CAfile`, staging it if it is DER.

    A PEM anchor is returned unchanged and nothing is staged. A DER anchor is
    staged and the staged path is returned. The caller always passes the
    returned value, so no call site has to remember which case it is in — that
    memory is what failed in R4.
    """
    path_policy.assert_no_symlink_escape(anchor_path)
    source = path_policy.assert_readable(anchor_path)
    with open(source, "rb") as fh:
        head = fh.read(64)

    if head.lstrip()[:5] == b"-----":
        return {
            "cafile_path": source,
            "staged": False,
            "reason": "SOURCE_IS_ALREADY_PEM",
            "source_sha256": hashing.sha256_file(source),
            "record": None,
        }

    name = label or os.path.splitext(os.path.basename(source))[0]
    dest = os.path.join(staging_dir, "%s.staged.pem" % name)
    record = stage_der_anchor_as_pem(
        source, dest, expected_sha256=expected_sha256,
        audit_id=audit_id, run_phase=run_phase)
    evidence_path = os.path.join(staging_dir, "%s.staging_evidence.json" % name)
    write_staging_evidence(record, evidence_path)
    return {
        "cafile_path": path_policy.normalize(dest),
        "staged": True,
        "reason": "SOURCE_IS_DER_STAGED_AS_PEM",
        "source_sha256": record["source_der_sha256"],
        "staged_sha256": record["staged_pem_sha256"],
        "staging_evidence_path": evidence_path,
        "record": record,
    }
