#!/usr/bin/env python3
"""Refuse to proceed while another process holds a writable fd below a root.

The authoritative evidence is the kernel's own view: /proc/<pid>/fd for the
open descriptors, /proc/<pid>/fdinfo/<fd> for the access mode, and
/proc/<pid>/exe for what the process actually is. `pgrep -f` is not used and
is not accepted here: it matches a command line, and a command line is a
label, not a handle -- it matches this checker's own argv, it misses a process
that has execed something else, and it cannot say whether a descriptor is open
for writing.

Nothing is killed. A process that holds a writable descriptor is reported and
the caller stops.

What this cannot see is recorded rather than assumed: descriptors of processes
owned by another uid are not readable without privilege. Those pids are
counted and their uids listed, so the limit of the measurement is visible.

Usage: inspect_writers.py <root> <out.json>
Exit 0 when no other process holds a writable descriptor below <root>.
"""

import json
import os
import sys


def flags_of(pid, fd):
    try:
        with open("/proc/%s/fdinfo/%s" % (pid, fd), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("flags:"):
                    return int(line.split()[1], 8)
    except OSError:
        return None
    return None


def link(path):
    try:
        return os.readlink(path)
    except OSError:
        return None


def status_of(pid):
    uid = name = None
    try:
        with open("/proc/%s/status" % pid, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("Uid:"):
                    uid = int(line.split()[1])
                elif line.startswith("Name:"):
                    name = line.split(None, 1)[1].strip()
    except OSError:
        pass
    return uid, name


def main():
    root = os.path.realpath(sys.argv[1])
    out_path = sys.argv[2]
    me = os.getpid()
    my_uid = os.getuid()

    holders = []
    scanned = []
    unreadable = []
    for entry in sorted(os.listdir("/proc"), key=lambda s: (not s.isdigit(), s)):
        if not entry.isdigit():
            continue
        uid, name = status_of(entry)
        fd_dir = "/proc/%s/fd" % entry
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            unreadable.append({"pid": int(entry), "uid": uid, "name": name})
            continue
        scanned.append(int(entry))
        for fd in fds:
            target = link(os.path.join(fd_dir, fd))
            if target is None:
                continue
            if not (target == root or target.startswith(root + os.sep)):
                continue
            flags = flags_of(entry, fd)
            access = None if flags is None else flags & 3
            holders.append({
                "pid": int(entry),
                "uid": uid,
                "name": name,
                "exe": link("/proc/%s/exe" % entry),
                "cwd": link("/proc/%s/cwd" % entry),
                "fd": int(fd),
                "target": target,
                "flags_octal": None if flags is None else oct(flags),
                "access": {0: "O_RDONLY", 1: "O_WRONLY", 2: "O_RDWR"}.get(access),
                "writable": access in (1, 2),
                "is_this_process": int(entry) == me,
            })

    blocking = [h for h in holders
                if h["writable"] and not h["is_this_process"]]
    doc = {
        "schema": "wpno.r8.lineage-writer-inspection/1",
        "root": root,
        "this_pid": me,
        "this_uid": my_uid,
        "method": "/proc/<pid>/fd + /proc/<pid>/fdinfo + /proc/<pid>/exe",
        "pgrep_used": False,
        "pids_with_readable_fd_table": len(scanned),
        "pids_with_unreadable_fd_table": len(unreadable),
        "unreadable_pids_by_uid": sorted({u["uid"] for u in unreadable
                                          if u["uid"] is not None}),
        "unreadable_same_uid": [u for u in unreadable if u["uid"] == my_uid],
        "measurement_limit": (
            "Descriptors held by processes of another uid are not readable "
            "without privilege. Those pids are counted above, not assumed "
            "empty. The pre/post inventory of the root is the independent "
            "check that closes this gap after the fact."),
        "open_descriptors_below_root": holders,
        "blocking_writable_descriptors": blocking,
        "BLOCKING_COUNT": len(blocking),
        "NO_CONCURRENT_WRITER": not blocking,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "root", "pids_with_readable_fd_table", "pids_with_unreadable_fd_table",
        "unreadable_pids_by_uid", "BLOCKING_COUNT", "NO_CONCURRENT_WRITER")},
        indent=1, sort_keys=True))
    return 0 if not blocking else 1


if __name__ == "__main__":
    sys.exit(main())
