#!/usr/bin/env python3
"""Verify a revision's CONTROL_MANIFEST.sha256 against the bytes on disk.

Read-only. Reports counts, never repairs, and never writes into the tree it
is checking.
"""
import hashlib
import os
import sys


def main():
    root = os.path.abspath(sys.argv[1])
    manifest = os.path.join(root, "CONTROL_MANIFEST.sha256")
    ok = miss = bad = 0
    problems = []
    with open(manifest, "rb") as fh:
        for raw in fh:
            line = raw.decode("utf-8").rstrip("\n")
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                miss += 1
                problems.append(("MISSING", rel))
                continue
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() == digest:
                ok += 1
            else:
                bad += 1
                problems.append(("MISMATCH", rel))
    print("%s ok=%d missing=%d mismatch=%d" % (root, ok, miss, bad))
    for kind, rel in problems[:25]:
        print("   ", kind, rel)
    return 0 if (miss == 0 and bad == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
