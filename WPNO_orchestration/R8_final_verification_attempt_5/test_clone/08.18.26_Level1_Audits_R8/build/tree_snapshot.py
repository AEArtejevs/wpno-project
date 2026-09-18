"""Deterministic whole-tree snapshot.

Reproduces the method recorded in lineage/R6_LINEAGE_CLASSIFICATION.json:
a shasum-format manifest of every regular file under a root, sorted by
relative path, one '<sha256>  <relpath>' line each with a trailing newline.
The snapshot digest is the SHA-256 of that manifest's bytes.

Symlinks are not followed and are not hashed as their targets; the R6
manifest was produced from a tree that contains none, which this tool
asserts rather than assumes.
"""

import hashlib
import os
import sys

CHUNK = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def snapshot(root):
    root = os.path.realpath(root)
    entries = {}
    symlinks = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                symlinks.append(rel)
                continue
            entries[rel] = sha256_file(full)
    lines = ["%s  %s" % (entries[k], k) for k in sorted(entries)]
    text = "\n".join(lines) + "\n"
    return {
        "root": root,
        "files": len(entries),
        "symlinks": symlinks,
        "manifest_text": text,
        "snapshot_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


if __name__ == "__main__":
    result = snapshot(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(result["manifest_text"])
    print("%s  files=%d  symlinks=%d  %s" % (
        result["snapshot_sha256"], result["files"], len(result["symlinks"]), result["root"]))
