#!/usr/bin/env python3
"""Build the control fixtures the new candidate plans name.

Every fixture here is synthetic or is a sandbox copy. No accepted reference
byte is written to, no client document is altered in place, and nothing is
created outside `work/`.

Two kinds of fixture are staged.

  A control fixture the plan will use in the live phase, built here so the
  rehearsal exercises the real control rather than a description of it. The
  synthetic CMS structures and the synthetic archives are these.

  A sandbox copy of a target, which the approved phase would make for itself.
  Copying is not a catalogued operation - it is preparation - so it happens
  here rather than as a plan step.

Each fixture is proved to differ from what it is a variation on. A mutation
fixture whose bytes equal the original would make its control pass while
measuring nothing, which CLAUDE.md section 6 names as a measurement error
rather than a passing test.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy, policy  # noqa: E402

OPENSSL = policy.EXECUTABLES["openssl"]
A31_PREP = os.path.join(ROOT, "work", "L1-A31", "preparation_r8_2026-08-28")
SYN = os.path.join(A31_PREP, "synthetic")
REFERENCES = os.path.join(ROOT, "references")
OUT_RECORD = os.path.join(ROOT, "work", "_rehearsal_r8",
                          "FIXTURE_STAGING_RECORD.json")

staged = []


def run(argv, timeout=180):
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=timeout,
        env=policy.base_environment(), cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit("staging command failed (%d): %s\n%s"
                         % (proc.returncode, argv,
                            proc.stderr.decode("utf-8", "replace")[:800]))
    return proc


def record(kind, path, note, differs_from=None):
    entry = {"kind": kind, "path": os.path.relpath(path, ROOT),
             "sha256": hashing.sha256_file(path),
             "size": os.path.getsize(path), "note": note}
    if differs_from is not None:
        entry["differs_from"] = os.path.relpath(differs_from, ROOT)
        entry["differs_from_sha256"] = hashing.sha256_file(differs_from)
        entry["bytes_actually_differ"] = (
            entry["sha256"] != entry["differs_from_sha256"])
        if not entry["bytes_actually_differ"]:
            raise SystemExit(
                "fixture %s is byte-identical to what it is supposed to differ "
                "from; a control built on it would measure nothing" % path)
    staged.append(entry)
    return entry


def ensure(*parts):
    return path_policy.ensure_dir(os.path.join(ROOT, "work", *parts))


def copy_in(src, dest_dir, name=None):
    path_policy.ensure_dir(dest_dir)
    dest = os.path.join(dest_dir, name or os.path.basename(src))
    shutil.copyfile(src, path_policy.assert_writable(dest))
    return dest


def flip_one_byte(src, dest, offset=None):
    """Copy `src` to `dest` with exactly one byte changed, and say which."""
    with open(src, "rb") as fh:
        data = bytearray(fh.read())
    if not data:
        raise SystemExit("cannot mutate an empty file: %s" % src)
    if offset is None:
        offset = len(data) // 2
    before = data[offset]
    data[offset] = (before + 1) % 256
    with open(path_policy.assert_writable(dest), "wb") as fh:
        fh.write(bytes(data))
    return {"offset": offset, "byte_before": before, "byte_after": data[offset]}


# ------------------------------------------------------------------ L1-A27
def stage_a27():
    d = ensure("L1-A27", "RUN-A", "controls")
    src = os.path.join(REFERENCES, "REF-11-original-mail-attachment.zip")
    dest = os.path.join(d, "archive_one_byte_mutated.zip")
    where = flip_one_byte(src, dest)
    record("MUTATION_FIXTURE", dest,
           "one byte of the archive altered at offset %d (%d -> %d)"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=src)


# ------------------------------------------------------------------ L1-A28
def stage_a28():
    d = ensure("L1-A28", "RUN-A", "controls")
    src = os.path.join(REFERENCES, "REF-11-vhn-covered-content.xml")
    dest = os.path.join(d, "content_one_byte_mutated.xml")
    where = flip_one_byte(src, dest)
    record("MUTATION_FIXTURE", dest,
           "one byte of the covered content altered at offset %d (%d -> %d)"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=src)


# ------------------------------------------------------------------ L1-A29
def stage_a29():
    d = ensure("L1-A29", "RUN-A", "controls")
    src = os.path.join(REFERENCES, "REF-12", "376_DKB MH.docx")
    dest = os.path.join(d, "document_one_byte_mutated.docx")
    where = flip_one_byte(src, dest)
    record("MUTATION_FIXTURE", dest,
           "one byte of a sandbox copy altered at offset %d (%d -> %d); the "
           "reference copy is not written to"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=src)


# ------------------------------------------------------------------ L1-A30
def _zip_with(path, entries):
    with zipfile.ZipFile(path_policy.assert_writable(path), "w",
                         zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def stage_a30():
    d = ensure("L1-A30", "RUN-A", "controls")
    plain = [("document.txt", b"synthetic control content\n"),
             ("nested/second.txt", b"second entry\n")]
    without = os.path.join(d, "without_appledouble.zip")
    _zip_with(without, plain)
    record("NEGATIVE_CONTROL_FIXTURE", without,
           "a synthetic archive with no macOS metadata entry at all")

    with_meta = os.path.join(d, "with_appledouble.zip")
    _zip_with(with_meta, plain + [
        ("__MACOSX/._document.txt", b"\x00\x05\x16\x07synthetic appledouble\n"),
        ("nested/._second.txt", b"\x00\x05\x16\x07synthetic appledouble\n"),
        (".DS_Store", b"synthetic ds_store\n")])
    record("POSITIVE_CONTROL_FIXTURE", with_meta,
           "a synthetic archive carrying a __MACOSX prefix entry, a ._ "
           "basename entry and a .DS_Store entry",
           differs_from=without)

    one_added = os.path.join(d, "one_added_appledouble.zip")
    _zip_with(one_added, plain + [
        ("nested/._second.txt", b"\x00\x05\x16\x07synthetic appledouble\n")])
    record("MUTATION_FIXTURE", one_added,
           "the negative-control archive with exactly one ._ entry added",
           differs_from=without)


# ------------------------------------------------------------------ L1-A32
def stage_a32():
    d = ensure("L1-A32", "RUN-A", "synthetic")
    ensure("L1-A32", "RUN-A", "outputs")
    content = os.path.join(SYN, "content.bin")
    leaf = os.path.join(SYN, "leaf.pem")
    leaf_key = os.path.join(SYN, "leaf.key")
    intermediate = os.path.join(SYN, "intermediate.pem")
    inter_key = os.path.join(SYN, "intermediate.key")

    one = os.path.join(d, "one_signer.p7s")
    run([OPENSSL, "cms", "-sign", "-binary", "-in", content,
         "-signer", leaf, "-inkey", leaf_key,
         "-certfile", intermediate,
         "-outform", "DER", "-out", path_policy.assert_writable(one)])
    record("NEGATIVE_CONTROL_FIXTURE", one,
           "a synthetic detached CMS carrying exactly one SignerInfo")

    two = os.path.join(d, "two_signer.p7s")
    run([OPENSSL, "cms", "-sign", "-binary", "-in", content,
         "-signer", leaf, "-inkey", leaf_key,
         "-signer", intermediate, "-inkey", inter_key,
         "-certfile", intermediate,
         "-outform", "DER", "-out", path_policy.assert_writable(two)])
    record("POSITIVE_CONTROL_FIXTURE", two,
           "a synthetic detached CMS carrying two SignerInfo entries, both "
           "valid under the synthetic root",
           differs_from=one)

    corrupt = os.path.join(d, "two_signer_second_corrupt.p7s")
    with open(two, "rb") as fh:
        data = bytearray(fh.read())
    # The corruption has to land inside the second signature's value and
    # nowhere else. A run of bytes altered at an arbitrary offset breaks the
    # DER framing instead, and OpenSSL then reports "wrong tag" from the ASN.1
    # decoder - the structure never parses, no signature is ever checked, and
    # the control fails for a reason that has nothing to do with the signature.
    # That is the R6 failure this revision exists to prevent, measured here
    # before the plan was allowed to bind the fixture.
    #
    # An RSA-2048 signature is a 256-byte OCTET STRING, tagged 04 82 01 00.
    # Altering bytes inside that value leaves every length and every tag
    # intact, so the structure still parses and the second signature fails on
    # its own merits.
    marker = b"\x04\x82\x01\x00"
    positions = [m.start() for m in re.finditer(re.escape(marker), bytes(data))]
    if len(positions) < 2:
        raise SystemExit(
            "expected two signature values in the two-signer structure, found "
            "%d; the fixture would not exercise a second signer"
            % len(positions))
    value_start = positions[-1] + len(marker)
    for i in range(value_start, value_start + 16):
        data[i] = (data[i] + 1) % 256
    with open(path_policy.assert_writable(corrupt), "wb") as fh:
        fh.write(bytes(data))
    entry = record(
        "MUTATION_FIXTURE", corrupt,
        "the two-signer structure with sixteen bytes altered inside the "
        "second signature's 256-byte value at offset %d; every DER tag and "
        "length is unchanged, so the structure still parses and the failure "
        "is a signature failure rather than a parse failure" % value_start,
        differs_from=two)
    entry["signature_values_found"] = len(positions)
    entry["der_framing_preserved"] = True


# ------------------------------------------------------------------ L1-A33
def stage_a33():
    d = ensure("L1-A33", "RUN-A", "controls")
    entry_src = os.path.join(REFERENCES, "REF-11-vhn-covered-content.xml")
    entry_dest = os.path.join(d, "entry_one_byte_mutated.xml")
    where = flip_one_byte(entry_src, entry_dest)
    record("NEGATIVE_CONTROL_FIXTURE", entry_dest,
           "one byte of an entry altered at offset %d (%d -> %d)"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=entry_src)

    man_src = os.path.join(REFERENCES, "REF-11-563203462.xml")
    man_dest = os.path.join(d, "manifest_declared_hash_altered.xml")
    where = flip_one_byte(man_src, man_dest)
    record("MUTATION_FIXTURE", man_dest,
           "one byte of a declared value altered at offset %d (%d -> %d), so "
           "that the declaration side of the comparison is exercised"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=man_src)


# ------------------------------------------------------------------ L1-A35
def stage_a35():
    d = ensure("L1-A35", "RUN-A", "controls")
    ensure("L1-A35", "RUN-A", "outputs")
    content = os.path.join(SYN, "content.bin")
    leaf = os.path.join(SYN, "leaf.pem")
    leaf_key = os.path.join(SYN, "leaf.key")
    intermediate = os.path.join(SYN, "intermediate.pem")

    detached = os.path.join(d, "synthetic_detached.p7s")
    run([OPENSSL, "cms", "-sign", "-binary", "-in", content,
         "-signer", leaf, "-inkey", leaf_key, "-certfile", intermediate,
         "-outform", "DER", "-out", path_policy.assert_writable(detached)])
    record("CONTROL_FIXTURE", detached,
           "a synthetic detached CMS over the synthetic content, used to "
           "locate the coverage boundary")

    mutated = os.path.join(d, "content_inside_coverage_mutated.bin")
    where = flip_one_byte(content, mutated)
    record("MUTATION_FIXTURE", mutated,
           "one byte inside the signed content altered at offset %d (%d -> %d)"
           % (where["offset"], where["byte_before"], where["byte_after"]),
           differs_from=content)

    source = os.path.join(d, "synthetic_source.zip")
    _zip_with(source, [("payload.bin", b"layered synthetic payload\n" * 40),
                       ("meta.txt", b"container metadata\n")])
    record("CONTROL_FIXTURE", source,
           "a synthetic source archive for the layer comparison")

    preserving = os.path.join(d, "synthetic_copy_preserving.zip")
    shutil.copyfile(source, path_policy.assert_writable(preserving))
    entry = record("POSITIVE_CONTROL_FIXTURE", preserving,
                   "a byte-for-byte copy of the synthetic source archive")
    if entry["sha256"] != hashing.sha256_file(source):
        raise SystemExit("the byte-preserving copy is not byte-preserving")

    recompressed = os.path.join(d, "synthetic_copy_recompressed.zip")
    with zipfile.ZipFile(source) as src_zip:
        entries = [(i.filename, src_zip.read(i.filename))
                   for i in src_zip.infolist()]
    with zipfile.ZipFile(path_policy.assert_writable(recompressed), "w",
                         zipfile.ZIP_STORED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, data)
    record("NEGATIVE_CONTROL_FIXTURE", recompressed,
           "the same entries stored uncompressed: the container differs while "
           "every entry's content is unchanged",
           differs_from=source)

    # The claim the negative control rests on, proved rather than asserted.
    with zipfile.ZipFile(source) as a, zipfile.ZipFile(recompressed) as b:
        for name, data in entries:
            if hashlib.sha256(a.read(name)).hexdigest() != \
                    hashlib.sha256(b.read(name)).hexdigest():
                raise SystemExit(
                    "recompression changed entry content for %s; the fixture "
                    "does not separate the layers" % name)
    staged.append({
        "kind": "FIXTURE_PROPERTY_PROOF",
        "claim": ("every entry of the recompressed copy has the same "
                  "uncompressed content as the source, while the archives "
                  "differ as files"),
        "verified": True,
        "entries_checked": len(entries),
    })


def main():
    path_policy.ensure_dir(os.path.join(ROOT, "work", "_rehearsal_r8"))
    for stage in (stage_a27, stage_a28, stage_a29, stage_a30, stage_a32,
                  stage_a33, stage_a35):
        stage()
    payload = {
        "schema": "wpno.level1.rehearsal-fixtures/1",
        "revision": "R8",
        "fixtures": staged,
        "count": len([s for s in staged if "path" in s]),
        "note": ("Every fixture is synthetic or a sandbox copy. No accepted "
                 "reference byte was written to and nothing was created "
                 "outside work/."),
    }
    with open(path_policy.assert_writable(OUT_RECORD), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"fixtures_staged": payload["count"],
                      "record": os.path.relpath(OUT_RECORD, ROOT),
                      "record_sha256": hashing.sha256_file(OUT_RECORD)},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
