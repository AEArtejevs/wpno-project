#!/usr/bin/env python3
"""Deterministic per-file SHA-256 snapshot of a tree.

Output: one line per regular file, "<sha256>  <relpath>", sorted by relpath
with a byte-wise sort so the digest of the manifest itself is stable across
machines and locales. Symlinks are recorded as their link target, never
followed, because following one would silently hash a file outside the tree.
"""
import hashlib
import os
import sys


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root):
    root = os.path.abspath(root)
    rows = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                target = os.readlink(full)
                digest = "SYMLINK:" + hashlib.sha256(
                    target.encode("utf-8")).hexdigest()
            elif os.path.isfile(full):
                digest = sha256_file(full)
            else:
                digest = "NONREGULAR"
            rows.append((rel.encode("utf-8"), digest))
    rows.sort(key=lambda r: r[0])
    return rows


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: snapshot_tree.py <root> <out>\n")
        return 2
    root, out = sys.argv[1], sys.argv[2]
    rows = snapshot(root)
    with open(out, "wb") as fh:
        for rel, digest in rows:
            fh.write(digest.encode("ascii") + b"  " + rel + b"\n")
    print("%s files=%d manifest=%s" % (root, len(rows), sha256_file(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
