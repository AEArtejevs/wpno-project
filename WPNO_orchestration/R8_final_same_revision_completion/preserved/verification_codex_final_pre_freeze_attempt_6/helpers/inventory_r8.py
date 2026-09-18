#!/usr/bin/env python3
"""Full metadata + content inventory of a tree, for write-isolation proof.

Records, for every path below the root: relative path, entry type, size,
SHA-256 of file content, symlink target, mode, uid, gid, and mtime in
nanoseconds. Directories and symlinks are recorded too, because a write that
adds or removes a file leaves the file untouched and moves the directory's
mtime instead.

Symlinks are never followed: os.walk(followlinks=False), and lstat throughout.
Nothing is written inside the tree being inventoried.

Usage: inventory_r8.py <root> <out.json>
"""

import hashlib
import json
import os
import stat
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify(mode):
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "device"
    return "other"


def record(root, abs_path):
    rel = os.path.relpath(abs_path, root)
    st = os.lstat(abs_path)
    kind = classify(st.st_mode)
    entry = {
        "path": rel,
        "type": kind,
        "size": st.st_size,
        "mode": oct(stat.S_IMODE(st.st_mode)),
        "uid": st.st_uid,
        "gid": st.st_gid,
        "mtime_ns": st.st_mtime_ns,
        "inode": st.st_ino,
        "nlink": st.st_nlink,
        "sha256": None,
        "symlink_target": None,
    }
    if kind == "symlink":
        entry["symlink_target"] = os.readlink(abs_path)
    elif kind == "file":
        entry["sha256"] = sha256_file(abs_path)
    return entry


def main():
    root = os.path.realpath(sys.argv[1])
    out_path = sys.argv[2]
    entries = [record(root, root)]
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in dirnames + filenames:
            entries.append(record(root, os.path.join(dirpath, name)))
    entries.sort(key=lambda e: e["path"])

    counts = {}
    for e in entries:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    doc = {
        "schema": "wpno.r8.lineage-inventory/1",
        "root": root,
        "entry_count": len(entries),
        "counts_by_type": counts,
        "total_file_bytes": sum(e["size"] for e in entries
                                if e["type"] == "file"),
        "entries": entries,
    }
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(raw)

    # A single digest over the inventory content, excluding nothing.
    print(json.dumps({
        "root": root,
        "out": out_path,
        "entry_count": len(entries),
        "counts_by_type": counts,
        "inventory_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
