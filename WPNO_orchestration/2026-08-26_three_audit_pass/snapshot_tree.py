#!/usr/bin/env python3
"""Deterministic pre/post snapshot of a package root.

Records for every entry: relative path, type, size, inode, device, symlink
target, and SHA-256 of regular files. Output is newline-delimited JSON sorted
by relative path, so two snapshots of the same tree are byte-identical and a
diff names exactly what moved.
"""
import hashlib, json, os, sys

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def walk(root):
    root = os.path.realpath(root)
    rows = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(dirnames)
        for name in sorted(dirnames) + sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            st = os.lstat(full)
            row = {"path": rel, "size": st.st_size, "inode": st.st_ino,
                   "device": st.st_dev, "mode": oct(st.st_mode)}
            if os.path.islink(full):
                row["type"] = "SYMLINK"
                row["symlink_target"] = os.readlink(full)
                row["sha256"] = None
            elif os.path.isdir(full):
                row["type"] = "DIRECTORY"
                row["sha256"] = None
            elif os.path.isfile(full):
                row["type"] = "FILE"
                row["sha256"] = sha256_file(full)
            else:
                row["type"] = "OTHER"
                row["sha256"] = None
            rows.append(row)
    rows.sort(key=lambda r: r["path"])
    return rows

if __name__ == "__main__":
    root, out = sys.argv[1], sys.argv[2]
    rows = walk(root)
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
    files = sum(1 for r in rows if r["type"] == "FILE")
    print(json.dumps({"root": os.path.realpath(root), "entries": len(rows),
                      "files": files, "out": out}, sort_keys=True))
