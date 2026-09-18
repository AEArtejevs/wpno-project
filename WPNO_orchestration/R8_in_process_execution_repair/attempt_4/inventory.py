#!/usr/bin/env python3
"""Complete inventory of the R8 package: what is there and exactly what it is.

Records, per file: relative path, type, size, SHA-256, symlink target,
and the permission bits. Directories are recorded too, because a permission
change on a directory is a change to the package even when no file moved.

Two digests are produced. The COMPLETE digest covers every path. The
MANIFEST-COVERED digest covers only the 724 paths the build manifest names --
which is the package in the sense the freeze binds. Both are reported, so a
difference can be located rather than merely detected.
"""

import hashlib
import json
import os
import stat
import sys

R8 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
MANIFEST = os.path.join(R8, "build", "R8_BUILD_MANIFEST.sha256")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def covered_paths():
    out = set()
    with open(MANIFEST, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                out.add(line.rstrip("\n").split("  ", 1)[1])
    return out


def collect():
    rows = []
    for dirpath, dirnames, filenames in os.walk(R8):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, R8)
        if rel_dir != ".":
            info = os.lstat(dirpath)
            rows.append({
                "path": rel_dir, "type": "dir", "size": None,
                "sha256": None, "symlink_target": None,
                "mode": oct(stat.S_IMODE(info.st_mode)),
            })
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, R8)
            info = os.lstat(full)
            if stat.S_ISLNK(info.st_mode):
                rows.append({
                    "path": rel, "type": "symlink", "size": info.st_size,
                    "sha256": None, "symlink_target": os.readlink(full),
                    "mode": oct(stat.S_IMODE(info.st_mode)),
                })
                continue
            rows.append({
                "path": rel, "type": "file", "size": info.st_size,
                "sha256": sha256_file(full), "symlink_target": None,
                "mode": oct(stat.S_IMODE(info.st_mode)),
                "executable_bit": bool(info.st_mode & stat.S_IXUSR),
            })
    rows.sort(key=lambda row: row["path"])
    return rows


def digest_of(rows):
    text = "\n".join(
        "%s|%s|%s|%s|%s|%s" % (r["path"], r["type"], r["size"], r["sha256"],
                               r["symlink_target"], r["mode"])
        for r in rows) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    out_path = sys.argv[1]
    rows = collect()
    covered = covered_paths()
    covered_rows = [r for r in rows if r["path"] in covered]
    payload = {
        "schema": "wpno.r8.inventory/1",
        "r8_root": R8,
        "manifest_path": os.path.relpath(MANIFEST, R8),
        "manifest_sha256": sha256_file(MANIFEST),
        "manifest_entries": len(covered),
        "total_paths": len(rows),
        "files": sum(1 for r in rows if r["type"] == "file"),
        "directories": sum(1 for r in rows if r["type"] == "dir"),
        "symlinks": sum(1 for r in rows if r["type"] == "symlink"),
        "COMPLETE_INVENTORY_SHA256": digest_of(rows),
        "MANIFEST_COVERED_INVENTORY_SHA256": digest_of(covered_rows),
        "manifest_covered_paths_present": len(covered_rows),
        "rows": rows,
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({k: v for k, v in payload.items() if k != "rows"},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
