"""Build a synthetic certificate chain and detached CMS for the controls.

Everything here is generated, disposable and unrelated to any case material.
A control has to be exercised against material whose right answer is known in
advance, and the only way to know it in advance is to have made it.

The five controls the L1-A31 and L1-A34 harnesses must pass need, between
them: a chain that verifies, a chain that does not, a detached signature over
the wrong content, a content file altered by one byte, and a certificate
altered by one byte. This module produces all five inputs from one root.

The leaf carries `emailProtection` so that `-purpose smimesign` — the purpose
`openssl cms -verify` applies — is satisfied by the positive control. A
positive control that fails for a purpose mismatch proves nothing about the
signature.
"""

import os
import subprocess
import time

OPENSSL = "/usr/bin/openssl"
KEY_BITS = "2048"

# Bounded like every other subprocess in this package.
TIMEOUT_SECONDS = 120
OUTPUT_LIMIT_BYTES = 1024 * 1024

FIXED_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
}


class FixtureError(Exception):
    pass


def _run(argv, cwd):
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
        env=dict(FIXED_ENV), cwd=cwd, check=False)
    if proc.returncode != 0:
        raise FixtureError(
            "fixture command failed (%d): %s\n%s"
            % (proc.returncode, " ".join(argv),
               proc.stderr[:OUTPUT_LIMIT_BYTES].decode("utf-8", "replace")))
    return proc


def _cnf(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _flip_one_byte(src, dst, offset):
    """Copy `src` to `dst` with exactly one byte changed.

    The number of differing bytes is asserted, because a mutation control that
    mutated nothing is a measurement error, not a passing test.
    """
    with open(src, "rb") as fh:
        data = bytearray(fh.read())
    if offset >= len(data):
        raise FixtureError("mutation offset beyond end of file")
    original = data[offset]
    data[offset] = (original + 1) % 256
    with open(dst, "wb") as fh:
        fh.write(bytes(data))
    with open(src, "rb") as a, open(dst, "rb") as b:
        left, right = a.read(), b.read()
    if len(left) != len(right):
        raise FixtureError("mutation changed the file length")
    changed = sum(1 for x, y in zip(left, right) if x != y)
    if changed != 1:
        raise FixtureError(
            "mutation must change exactly one byte, changed %d" % changed)
    return {"offset": offset, "from": original, "to": data[offset],
            "changed_bytes": changed}


def _pem_safe_mutation_offset(path):
    """An offset inside the base64 body of a PEM certificate.

    Mutating the header would produce a file OpenSSL cannot parse, which fails
    for the wrong reason. The body is where a real alteration would sit.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    start = data.index(b"-----BEGIN CERTIFICATE-----")
    body = data.index(b"\n", start) + 1
    end = data.index(b"-----END CERTIFICATE-----")
    offset = body + (end - body) // 2
    while data[offset:offset + 1] in (b"\n", b"\r"):
        offset += 1
    return offset


def build(root_dir):
    """Create the fixture set under `root_dir`. Returns a path dictionary."""
    os.makedirs(root_dir, exist_ok=True)
    d = root_dir

    def p(name):
        return os.path.join(d, name)

    _cnf(p("root.cnf"),
         "[req]\ndistinguished_name=dn\nx509_extensions=v3\nprompt=no\n"
         "[dn]\nC=ZZ\nO=WPNO R5 Synthetic Control\nCN=R5 Synthetic Root\n"
         "[v3]\nbasicConstraints=critical,CA:TRUE\n"
         "keyUsage=critical,keyCertSign,cRLSign\n"
         "subjectKeyIdentifier=hash\n")
    _cnf(p("other_root.cnf"),
         "[req]\ndistinguished_name=dn\nx509_extensions=v3\nprompt=no\n"
         "[dn]\nC=ZZ\nO=WPNO R5 Synthetic Control\nCN=R5 Unrelated Root\n"
         "[v3]\nbasicConstraints=critical,CA:TRUE\n"
         "keyUsage=critical,keyCertSign,cRLSign\n"
         "subjectKeyIdentifier=hash\n")
    _cnf(p("int_req.cnf"),
         "[req]\ndistinguished_name=dn\nprompt=no\n"
         "[dn]\nC=ZZ\nO=WPNO R5 Synthetic Control\n"
         "CN=R5 Synthetic Intermediate\n")
    _cnf(p("int_ext.cnf"),
         "basicConstraints=critical,CA:TRUE,pathlen:0\n"
         "keyUsage=critical,keyCertSign,cRLSign\n"
         "subjectKeyIdentifier=hash\n"
         "authorityKeyIdentifier=keyid,issuer\n")
    _cnf(p("leaf_req.cnf"),
         "[req]\ndistinguished_name=dn\nprompt=no\n"
         "[dn]\nC=ZZ\nO=WPNO R5 Synthetic Control\nCN=R5 Synthetic Signer\n")
    _cnf(p("leaf_ext.cnf"),
         "basicConstraints=critical,CA:FALSE\n"
         "keyUsage=critical,digitalSignature,nonRepudiation\n"
         "extendedKeyUsage=emailProtection\n"
         "subjectKeyIdentifier=hash\n"
         "authorityKeyIdentifier=keyid,issuer\n")

    # --- root and an unrelated root -----------------------------------------
    for stem, cnf in (("root", "root.cnf"), ("other_root", "other_root.cnf")):
        _run([OPENSSL, "req", "-x509", "-newkey", "rsa:" + KEY_BITS,
              "-keyout", p(stem + ".key"), "-out", p(stem + ".pem"),
              "-days", "3650", "-nodes", "-sha256",
              "-config", p(cnf)], cwd=d)

    # --- intermediate --------------------------------------------------------
    _run([OPENSSL, "req", "-new", "-newkey", "rsa:" + KEY_BITS,
          "-keyout", p("intermediate.key"), "-out", p("intermediate.csr"),
          "-nodes", "-sha256", "-config", p("int_req.cnf")], cwd=d)
    _run([OPENSSL, "x509", "-req", "-in", p("intermediate.csr"),
          "-CA", p("root.pem"), "-CAkey", p("root.key"), "-CAcreateserial",
          "-out", p("intermediate.pem"), "-days", "1825", "-sha256",
          "-extfile", p("int_ext.cnf")], cwd=d)

    # --- leaf ----------------------------------------------------------------
    _run([OPENSSL, "req", "-new", "-newkey", "rsa:" + KEY_BITS,
          "-keyout", p("leaf.key"), "-out", p("leaf.csr"),
          "-nodes", "-sha256", "-config", p("leaf_req.cnf")], cwd=d)
    _run([OPENSSL, "x509", "-req", "-in", p("leaf.csr"),
          "-CA", p("intermediate.pem"), "-CAkey", p("intermediate.key"),
          "-CAcreateserial", "-out", p("leaf.pem"), "-days", "825",
          "-sha256", "-extfile", p("leaf_ext.cnf")], cwd=d)

    # --- content and a detached CMS over it ---------------------------------
    with open(p("content.bin"), "wb") as fh:
        fh.write(b"WPNO R5 synthetic detached content\n" * 8)
    with open(p("wrong_content.bin"), "wb") as fh:
        fh.write(b"WPNO R5 synthetic UNRELATED content\n" * 8)

    # `cms -sign` is detached by default; `-nodetach` is what would embed the
    # content. There is no `-detach` option, and asking for one is an error.
    _run([OPENSSL, "cms", "-sign", "-binary", "-in", p("content.bin"),
          "-signer", p("leaf.pem"), "-inkey", p("leaf.key"),
          "-certfile", p("intermediate.pem"),
          "-outform", "DER", "-out", p("content.p7s")], cwd=d)

    # --- mutations -----------------------------------------------------------
    content_mutation = _flip_one_byte(
        p("content.bin"), p("content_one_byte_mutated.bin"), 4)
    cert_mutation = _flip_one_byte(
        p("leaf.pem"), p("leaf_one_byte_mutated.pem"),
        _pem_safe_mutation_offset(p("leaf.pem")))

    # The DER trust anchor the A34 staging path needs.
    _run([OPENSSL, "x509", "-in", p("root.pem"), "-outform", "DER",
          "-out", p("root.der")], cwd=d)

    # A validation time inside the window of the certificates just issued.
    # `notBefore` is the moment of generation, so a fixed constant would fall
    # outside it and every positive control would fail with "certificate is
    # not yet valid" — a control failing for a reason that has nothing to do
    # with what it is testing.
    validation_time = int(time.time()) + 3600

    return {
        "dir": d,
        "validation_time": validation_time,
        "root_pem": p("root.pem"),
        "root_der": p("root.der"),
        "other_root_pem": p("other_root.pem"),
        "intermediate_pem": p("intermediate.pem"),
        "leaf_pem": p("leaf.pem"),
        "leaf_mutated_pem": p("leaf_one_byte_mutated.pem"),
        "content": p("content.bin"),
        "wrong_content": p("wrong_content.bin"),
        "content_mutated": p("content_one_byte_mutated.bin"),
        "cms_detached": p("content.p7s"),
        "content_mutation": content_mutation,
        "cert_mutation": cert_mutation,
    }
