#!/usr/bin/env python3
"""The gate that must pass before any verifier is launched.

Seven conditions, each measured, none asserted. If any fails the workspace is
wrong and Codex is not started -- attempt 5 was started against a workspace
that failed conditions 2, 3 and 4 and spent the attempt discovering it.

Usage: preflight_clone.py <clone> <r8_root> <project_root> <workspace> <out.json>
Exit 0 only when every condition holds.
"""

import hashlib
import json
import os
import subprocess
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def manifest_entries(root):
    path = os.path.join(root, "build", "R8_BUILD_MANIFEST.sha256")
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            out.append((digest, rel))
    return out


def main():
    clone, r8, project, workspace, out_path = (
        os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2]),
        os.path.realpath(sys.argv[3]), os.path.realpath(sys.argv[4]),
        sys.argv[5])
    checks = {}

    # 1 -- every manifest-covered source file in the clone matches R8.
    entries = manifest_entries(r8)
    mismatched, missing = [], []
    for digest, rel in entries:
        c = os.path.join(clone, rel)
        if not os.path.isfile(c):
            missing.append(rel)
            continue
        if sha256_file(c) != digest:
            mismatched.append(rel)
    checks["1_manifest_covered_clone_matches_r8"] = {
        "manifest_entries": len(entries),
        "missing_in_clone": missing,
        "digest_mismatched_in_clone": mismatched,
        "PASS": not missing and not mismatched,
    }

    # 2 -- paths.json in the clone resolves to the real architecture.
    with open(os.path.join(clone, "paths.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    def resolve(key):
        v = cfg[key]
        if not os.path.isabs(v):
            v = os.path.join(clone, v)
        return os.path.realpath(v)

    resolved = {k: resolve(k) for k in
                ("project_root", "discovery_root", "level1_root")}
    expected = {
        "project_root": project,
        "discovery_root": os.path.join(project, "08.18.26_Discovery"),
        "level1_root": clone,
    }
    checks["2_paths_json_resolves"] = {
        "declared": {k: cfg[k] for k in expected},
        "resolved": resolved,
        "expected": expected,
        "discovery_root_exists": os.path.isdir(resolved["discovery_root"]),
        "PASS": resolved == expected and os.path.isdir(resolved["discovery_root"]),
    }

    # 3 -- R4, R5, R6, R7 exist as siblings of the clone.
    siblings = {}
    for rev in ("R4", "R5", "R6", "R7"):
        p = os.path.join(project, "08.18.26_Level1_Audits_%s" % rev)
        siblings[rev] = {"path": p, "is_dir": os.path.isdir(p)}
    checks["3_predecessors_are_siblings"] = {
        "clone_parent": os.path.dirname(clone),
        "siblings": siblings,
        "PASS": (os.path.dirname(clone) == project
                 and all(v["is_dir"] for v in siblings.values())),
    }

    # 4 -- the project .gitignore exists where the package expects it.
    gi = os.path.join(project, ".gitignore")
    checks["4_project_gitignore_present"] = {
        "path": gi, "is_file": os.path.isfile(gi),
        "sha256": sha256_file(gi) if os.path.isfile(gi) else None,
        "PASS": os.path.isfile(gi),
    }

    # 5 -- the clone is writable. Proved by writing, not by reading a mode bit.
    #
    # Creating and removing a file at the clone root moves the clone root
    # directory's mtime. That would then show up as a difference between the
    # clone and R8 in the very comparison that is supposed to say the clone is
    # a faithful copy -- a measuring instrument changing the thing it measures.
    # So the root's mtime is read before the probe and restored after it, and
    # the restoration is recorded here rather than left silent. It is confined
    # to the disposable clone; nothing in R8 is touched by any of this.
    probe = os.path.join(clone, ".preflight_write_probe")
    writable, detail = False, None
    before_ns = os.lstat(clone).st_mtime_ns
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("probe\n")
        writable = os.path.isfile(probe)
        os.unlink(probe)
    except OSError as exc:
        detail = str(exc)
    os.utime(clone, ns=(before_ns, before_ns))
    after_ns = os.lstat(clone).st_mtime_ns
    checks["5_clone_writable"] = {
        "probe_path": probe, "wrote_and_removed": writable,
        "error": detail,
        "clone_root_mtime_ns_before_probe": before_ns,
        "clone_root_mtime_ns_after_restore": after_ns,
        "clone_root_mtime_restored": after_ns == before_ns,
        "restoration_note": (
            "the probe necessarily moves the clone root's mtime; it is put "
            "back so the clone-versus-R8 comparison measures the copy and not "
            "this check's own footprint"),
        "PASS": writable and after_ns == before_ns,
    }

    # 6 -- the original R8 lies outside the verifier's writable workspace.
    inside = (r8 == workspace or r8.startswith(workspace + os.sep)
              or r8 == clone or r8.startswith(clone + os.sep))
    checks["6_r8_outside_writable_workspace"] = {
        "r8_root": r8, "workspace": workspace, "clone": clone,
        "r8_inside_a_writable_root": inside, "PASS": not inside,
    }

    # 7 -- no active R7 or R8 file is hardlinked to the clone.
    #
    # A hardlink is not visible in a path comparison: two names, one inode. If
    # a clone file shared an inode with an R7 or R8 file, a test write to the
    # clone would land in the original and every later inventory would show it
    # as a write to R8 with no writer to blame. Measured by device+inode.
    def inodes(root):
        seen = {}
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames.sort()
            for name in sorted(filenames):
                p = os.path.join(dirpath, name)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if st.st_nlink > 1:
                    seen.setdefault((st.st_dev, st.st_ino), []).append(p)
        return seen

    clone_multi = inodes(clone)
    shared = []
    for root in (r8, os.path.join(project, "08.18.26_Level1_Audits_R7")):
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames.sort()
            for name in sorted(filenames):
                p = os.path.join(dirpath, name)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if (st.st_dev, st.st_ino) in clone_multi:
                    shared.append({"original": p,
                                   "clone_names": clone_multi[(st.st_dev, st.st_ino)]})
    checks["7_no_hardlink_between_clone_and_active_r7_r8"] = {
        "clone_files_with_nlink_gt_1": sum(len(v) for v in clone_multi.values()),
        "shared_inodes_with_r7_or_r8": shared,
        "PASS": not shared,
    }

    # The clone must not be mistakable for a revision directory.
    base = os.path.basename(clone)
    checks["8_clone_name_outside_revision_glob"] = {
        "clone_basename": base,
        "matches_revision_glob": base.startswith("08.18.26_Level1_Audits"),
        "hidden": base.startswith("."),
        "PASS": base.startswith(".") and not base.startswith("08.18.26_Level1_Audits"),
    }

    doc = {
        "schema": "wpno.r8.delta-preflight/1",
        "clone": clone, "r8_root": r8, "project_root": project,
        "workspace": workspace,
        "checks": checks,
        "failed_checks": sorted(k for k, v in checks.items() if not v["PASS"]),
        "PREFLIGHT_PASS": all(v["PASS"] for v in checks.values()),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"PREFLIGHT_PASS": doc["PREFLIGHT_PASS"],
                      "failed_checks": doc["failed_checks"],
                      "per_check": {k: v["PASS"] for k, v in checks.items()}},
                     indent=1, sort_keys=True))
    return 0 if doc["PREFLIGHT_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
