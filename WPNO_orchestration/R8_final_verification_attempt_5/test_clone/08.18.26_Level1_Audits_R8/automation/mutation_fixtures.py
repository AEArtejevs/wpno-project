"""Mutation and negative-control fixtures, built at the layer they claim.

R6's L1-A31 plan carried a fixture called `vhn_leaf_one_byte_mutated.pem`. It
was made by flipping one byte of the PEM base64 *text* — offset 28, 'M' to
'A'. The result was a file OpenSSL refused to load at all:

    Could not find certificate file from .../vhn_leaf_one_byte_mutated.pem
    STORE routines:ossl_store_handle_load_result:unsupported

The step exited nonzero and was scored FAILS_AS_DESIGNED. What it actually
demonstrated was that OpenSSL will not parse corrupted base64. It demonstrated
nothing whatever about signature verification, which is what a mutation
control on a certificate exists to demonstrate.

The generic readiness fixture used the same construction and happened to land
at offset 664, deep in the body, where the damage stayed inside a field and
the certificate still parsed. So the readiness fixture passed and the live
plan failed, from one line of shared logic, because a base64 flip's effect
depends on where it lands. A fixture whose meaning depends on luck is not a
fixture.

This module builds each control at the layer it claims to test, and proves
each one did what it claims before returning it:

    signature_mutation   one byte inside the signatureValue BIT STRING.
                         DER length unchanged, certificate still parses,
                         signature verification fails. The intended
                         cryptographic negative control.

    parse_refusal        the DER header damaged so the file cannot be loaded.
                         A real and separate control — "this tool refuses
                         malformed input" — under its own name, never
                         confused with a signature failure.

    content_mutation     one byte of a detached content file, length
                         preserved, offset and both byte values recorded.

Four failure modes are named separately throughout and never collapsed into
one: parse refusal, signature failure, chain failure, content-digest failure.
"""

import os
import subprocess

from . import hashing, policy


class FixtureError(Exception):
    pass


OPENSSL = policy.EXECUTABLES["openssl"]
TIMEOUT_SECONDS = 120
OUTPUT_LIMIT_BYTES = 1024 * 1024

PEM_BEGIN = b"-----BEGIN CERTIFICATE-----"
PEM_END = b"-----END CERTIFICATE-----"

# Failure-reason labels. A control declares which one it expects, and the
# rehearsal checks the recorded stderr against it. R6 asserted only "nonzero
# exit", which is why two CMS controls scored FAILS_AS_DESIGNED while both
# were in fact failing on the certificate purpose, before either had compared
# a single byte of content.
REASON_PARSE_REFUSAL = "PARSE_REFUSAL"
REASON_CERT_SIGNATURE_FAILURE = "CERT_SIGNATURE_FAILURE"
REASON_CHAIN_INCOMPLETE = "CHAIN_INCOMPLETE"
REASON_CONTENT_DIGEST_FAILURE = "CONTENT_DIGEST_FAILURE"
REASON_UNSUITABLE_PURPOSE = "UNSUITABLE_PURPOSE"

# The stderr signatures each reason must produce, as OpenSSL 3.5 emits them.
REASON_SIGNATURES = {
    # Two phrasings are in circulation for the same refusal: `openssl verify`
    # says "Could not find certificate file from <path>" and `openssl x509`
    # says "Could not find certificate from <path>". Matching the longer one
    # only would miss half the cases, which is the same kind of mistake as a
    # regex without a `+`.
    REASON_PARSE_REFUSAL: ("Could not find certificate",
                           "unable to load certificate",
                           "ossl_store_handle_load_result",
                           "PEM routines"),
    REASON_CERT_SIGNATURE_FAILURE: ("certificate signature failure",),
    REASON_CHAIN_INCOMPLETE: ("unable to get local issuer certificate",
                              "self-signed certificate",
                              "unable to get issuer certificate"),
    REASON_CONTENT_DIGEST_FAILURE: ("Verify error", "digest failure",
                                    "message digest attribute",
                                    "CMS Verification failure"),
    REASON_UNSUITABLE_PURPOSE: ("unsuitable certificate purpose",),
}


def _run(argv, cwd):
    return subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
        env=policy.base_environment(), cwd=cwd, check=False)


# --------------------------------------------------------------- DER walking
def _read_tlv(data, offset):
    """Return (tag, header_length, content_length, content_offset).

    A minimal DER reader. It handles the definite-length forms DER permits and
    refuses everything else, rather than guessing: an indefinite length in
    what is supposed to be DER means the input is not what it claims to be.
    """
    if offset >= len(data):
        raise FixtureError("truncated DER at offset %d" % offset)
    tag = data[offset]
    if tag & 0x1F == 0x1F:
        raise FixtureError("multi-byte DER tags are not expected here")
    pos = offset + 1
    if pos >= len(data):
        raise FixtureError("truncated DER length at offset %d" % pos)
    first = data[pos]
    pos += 1
    if first == 0x80:
        raise FixtureError("indefinite length is not valid DER")
    if first < 0x80:
        length = first
    else:
        count = first & 0x7F
        if count == 0 or count > 4:
            raise FixtureError("unsupported DER length form: %d octets" % count)
        if pos + count > len(data):
            raise FixtureError("truncated DER long-form length")
        length = int.from_bytes(data[pos:pos + count], "big")
        pos += count
    if pos + length > len(data):
        raise FixtureError("DER content runs past the end of the buffer")
    return tag, pos - offset, length, pos


def signature_value_span(der):
    """Byte range of the signatureValue BIT STRING's value inside a cert.

    Certificate ::= SEQUENCE { tbsCertificate, signatureAlgorithm,
    signatureValue BIT STRING }. The span returned excludes the tag, the
    length octets and the leading unused-bits octet, so a byte written into it
    changes the signature and nothing structural: every length octet in the
    encoding keeps its value and the certificate still parses.
    """
    tag, header, length, content = _read_tlv(der, 0)
    if tag != 0x30:
        raise FixtureError("certificate does not begin with a SEQUENCE")
    end = content + length
    pos = content
    spans = []
    while pos < end:
        child_tag, child_header, child_length, child_content = _read_tlv(der, pos)
        spans.append((child_tag, child_content, child_length))
        pos = child_content + child_length
    if len(spans) != 3:
        raise FixtureError(
            "expected 3 elements in Certificate, found %d" % len(spans))
    sig_tag, sig_content, sig_length = spans[2]
    if sig_tag != 0x03:
        raise FixtureError(
            "third element of Certificate is tag 0x%02x, not a BIT STRING"
            % sig_tag)
    if sig_length < 2:
        raise FixtureError("signatureValue is too short to mutate")
    # Skip the unused-bits octet, which is structural.
    return sig_content + 1, sig_content + sig_length


def _pem_to_der(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if PEM_BEGIN not in data:
        raise FixtureError("not a PEM certificate: %s" % path)
    body_start = data.index(b"\n", data.index(PEM_BEGIN)) + 1
    body_end = data.index(PEM_END)
    import base64
    return base64.b64decode(data[body_start:body_end])


def _der_to_pem(der):
    import base64
    encoded = base64.b64encode(der)
    lines = [encoded[i:i + 64] for i in range(0, len(encoded), 64)]
    return PEM_BEGIN + b"\n" + b"\n".join(lines) + b"\n" + PEM_END + b"\n"


# ------------------------------------------------------------------ fixtures
def signature_mutation(source_pem, destination_pem, anchor_pem, work_dir,
                       intermediates_pem=None):
    """One byte inside signatureValue. Parses; signature fails. Proven.

    The proof is not optional and is not a comment. The fixture is parsed and
    its signature is checked against the issuer before this function returns,
    and a fixture that parses when it should not, or verifies when it should
    not, raises instead of being written into a plan.
    """
    der = _pem_to_der(source_pem)
    start, end = signature_value_span(der)
    offset = start + (end - start) // 2
    mutated = bytearray(der)
    original = mutated[offset]
    mutated[offset] = (original + 1) % 256
    mutated = bytes(mutated)

    if len(mutated) != len(der):
        raise FixtureError("DER length changed")
    differing = [i for i in range(len(der)) if der[i] != mutated[i]]
    if differing != [offset]:
        raise FixtureError(
            "expected exactly one differing byte at %d, got %r"
            % (offset, differing))

    with open(destination_pem, "wb") as fh:
        fh.write(_der_to_pem(mutated))

    # Proof 1: it still parses. A parse refusal here would make this the
    # wrong control, which is exactly what happened in R6.
    parsed = _run([OPENSSL, "x509", "-in", destination_pem, "-noout",
                   "-subject"], cwd=work_dir)
    if parsed.returncode != 0:
        raise FixtureError(
            "the mutated certificate does not parse, so it cannot be a "
            "signature-failure control: %s"
            % parsed.stderr[:2000].decode("utf-8", "replace"))

    # Proof 2: its signature no longer verifies against its real chain, and
    # the reason OpenSSL gives is the reason claimed.
    #
    # The full chain is used — anchor as -CAfile, intermediate as -untrusted —
    # rather than the shortcut of trusting the intermediate directly under
    # `-partial_chain`. That flag is on this package's suppression list, and a
    # fixture proved with a flag the controller may not emit is proved under
    # conditions the audit will never run under.
    argv = [OPENSSL, "verify", "-no-CAfile", "-no-CApath", "-no-CAstore",
            "-CAfile", anchor_pem]
    if intermediates_pem:
        argv += ["-untrusted", intermediates_pem]
    argv += ["-purpose", "any", destination_pem]
    checked = _run(argv, cwd=work_dir)
    stderr = checked.stderr.decode("utf-8", "replace")
    if checked.returncode == 0:
        raise FixtureError(
            "the mutated certificate still verifies; the mutation did not "
            "reach the signature")
    if "certificate signature failure" not in stderr:
        raise FixtureError(
            "the mutated certificate fails for the wrong reason: %s" % stderr)

    return {
        "kind": "CERT_SIGNATURE_MUTATION",
        "layer": "DER_signatureValue_BIT_STRING",
        "expected_failure_reason": REASON_CERT_SIGNATURE_FAILURE,
        "source": source_pem,
        "path": destination_pem,
        "der_offset": offset,
        "signature_value_span": [start, end],
        "byte_from": original,
        "byte_to": mutated[offset],
        "der_length_before": len(der),
        "der_length_after": len(mutated),
        "differing_der_bytes": 1,
        "source_sha256": hashing.sha256_file(source_pem),
        "fixture_sha256": hashing.sha256_file(destination_pem),
        "proven_parseable": True,
        "proven_signature_fails": True,
        "observed_reason": "certificate signature failure",
    }


def parse_refusal(source_pem, destination_pem, work_dir):
    """A file the certificate loader refuses. Its own control, its own name."""
    der = bytearray(_pem_to_der(source_pem))
    original = der[0]
    der[0] = 0x04                      # SEQUENCE becomes OCTET STRING
    with open(destination_pem, "wb") as fh:
        fh.write(_der_to_pem(bytes(der)))

    parsed = _run([OPENSSL, "x509", "-in", destination_pem, "-noout",
                   "-subject"], cwd=work_dir)
    if parsed.returncode == 0:
        raise FixtureError(
            "the parse-refusal fixture parses, so it is not a parse-refusal "
            "control")
    stderr = parsed.stderr.decode("utf-8", "replace")
    if not any(sig in stderr for sig in REASON_SIGNATURES[REASON_PARSE_REFUSAL]):
        raise FixtureError(
            "the parse-refusal fixture fails for an unrecognised reason: %s"
            % stderr)

    return {
        "kind": "CERT_PARSE_REFUSAL",
        "layer": "DER_outer_tag",
        "expected_failure_reason": REASON_PARSE_REFUSAL,
        "source": source_pem,
        "path": destination_pem,
        "der_offset": 0,
        "byte_from": original,
        "byte_to": 0x04,
        "source_sha256": hashing.sha256_file(source_pem),
        "fixture_sha256": hashing.sha256_file(destination_pem),
        "proven_unparseable": True,
        "note": ("This is NOT a signature-failure control and must never be "
                 "scored as one. R6 conflated the two and recorded a parse "
                 "refusal as a passing mutation control."),
    }


def content_mutation(source, destination, offset=0):
    """One byte of a content file. Length preserved, everything recorded."""
    with open(source, "rb") as fh:
        data = bytearray(fh.read())
    if offset >= len(data):
        raise FixtureError("mutation offset beyond end of file")
    original = data[offset]
    data[offset] = (original + 1) % 256
    with open(destination, "wb") as fh:
        fh.write(bytes(data))

    before = hashing.sha256_file(source)
    after = hashing.sha256_file(destination)
    if before == after:
        raise FixtureError(
            "the mutated content has the same digest as the source; zero "
            "changed bytes is a measurement error, not a passing control")
    if os.path.getsize(source) != os.path.getsize(destination):
        raise FixtureError("mutation changed the file length")
    with open(source, "rb") as a, open(destination, "rb") as b:
        left, right = a.read(), b.read()
    differing = [i for i in range(len(left)) if left[i] != right[i]]
    if differing != [offset]:
        raise FixtureError(
            "expected exactly one differing byte at %d, got %r"
            % (offset, differing))

    return {
        "kind": "CONTENT_ONE_BYTE_MUTATION",
        "layer": "detached_content_bytes",
        "expected_failure_reason": REASON_CONTENT_DIGEST_FAILURE,
        "source": source,
        "path": destination,
        "offset": offset,
        "byte_from": original,
        "byte_to": data[offset],
        "length_before": len(left),
        "length_after": len(right),
        "differing_bytes": 1,
        "source_sha256": before,
        "fixture_sha256": after,
        "digest_differs": True,
    }


def reason_is_present(stderr_text, reason):
    """Does this stderr actually show the failure reason claimed?"""
    if reason not in REASON_SIGNATURES:
        raise FixtureError("unknown failure reason: %r" % reason)
    return any(sig in stderr_text for sig in REASON_SIGNATURES[reason])
