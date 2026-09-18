"""Hashing and manifests."""

import hashlib
import os

from . import path_policy, policy

CHUNK = 1024 * 1024


class HashError(Exception):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    """SHA-256 of a file's raw bytes.

    Streamed. Never decoded, never normalized, never rewritten first — a hash
    of a reconstruction is a hash of a different file.

    The symlink guard runs on the caller's path, before anything canonicalises
    it. Running it afterwards would hand it a path with every link already
    resolved away, which is exactly the defect the predecessor package shipped.
    """
    path_policy.assert_no_symlink_escape(path)
    canonical = path_policy.assert_readable(path)
    size = os.path.getsize(canonical)
    if size > policy.MAX_EVIDENCE_FILE_BYTES:
        raise HashError("file exceeds MAX_EVIDENCE_FILE_BYTES: %s (%d)" % (canonical, size))
    digest = hashlib.sha256()
    with open(canonical, "rb") as fh:
        while True:
            block = fh.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text):
    return sha256_bytes(text.encode("utf-8"))


def is_hex64(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value.lower())


def manifest_for(paths, root):
    """Build {relative_path: sha256} for a list of files."""
    root = path_policy.normalize(root)
    out = {}
    for p in sorted(paths):
        canonical = path_policy.assert_readable(p)
        rel = os.path.relpath(canonical, root)
        out[rel] = sha256_file(p)
    return out


def write_manifest(manifest, out_path):
    """Write a shasum-compatible manifest: '<sha256>  <relative path>'."""
    canonical = path_policy.assert_writable(out_path)
    lines = ["%s  %s" % (manifest[k], k) for k in sorted(manifest)]
    with open(canonical, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")
    return canonical


def read_manifest(path):
    canonical = path_policy.assert_readable(path)
    out = {}
    with open(canonical, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line:
                continue
            if "  " not in line:
                raise HashError("malformed manifest line: %r" % line)
            digest, rel = line.split("  ", 1)
            if not is_hex64(digest):
                raise HashError("malformed digest in manifest: %r" % digest)
            out[rel] = digest.lower()
    return out


def verify_manifest(path, root):
    """Return (ok, differences). Never raises on a mismatch — a mismatch is
    the answer, not an error."""
    expected = read_manifest(path)
    root = path_policy.normalize(root)
    differences = []
    for rel in sorted(expected):
        target = os.path.join(root, rel)
        if not os.path.exists(target):
            differences.append({"path": rel, "expected": expected[rel], "actual": None,
                                "reason": "MISSING"})
            continue
        actual = sha256_file(target)
        if actual != expected[rel]:
            differences.append({"path": rel, "expected": expected[rel], "actual": actual,
                                "reason": "CHANGED"})
    return (not differences), differences
