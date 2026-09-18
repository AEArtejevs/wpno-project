"""Pre-write snapshots of R4/R5/R6/R7 + verification of the current R7 build manifest.

Snapshot method is the one lineage/R6_LINEAGE_CLASSIFICATION.json records and
build/resume_r7/tree_snapshot.py implements: a shasum-format manifest of every
regular file under a root, sorted by relative path, digest = SHA-256 of the
manifest bytes. Nothing is copied; only digests are written here.
"""
import hashlib, json, os, sys

CHUNK = 1 << 20
BASE = "/home/ubuntu/project/WPNO"
ROOTS = {
    "R4": os.path.join(BASE, "08.18.26_Level1_Audits_R4"),
    "R5": os.path.join(BASE, "08.18.26_Level1_Audits_R5"),
    "R6": os.path.join(BASE, "08.18.26_Level1_Audits_R6"),
    "R7": os.path.join(BASE, "08.18.26_Level1_Audits_R7"),
}
OUT = os.path.dirname(os.path.abspath(__file__))

def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            d.update(b)
    return d.hexdigest()

def snapshot(root):
    root = os.path.realpath(root)
    entries, symlinks = {}, []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                symlinks.append(rel)
                continue
            entries[rel] = sha256_file(full)
    text = "\n".join("%s  %s" % (entries[k], k) for k in sorted(entries)) + "\n"
    return {"root": root, "files": len(entries), "symlinks": symlinks,
            "manifest_text": text,
            "snapshot_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}

def main():
    out = {}
    for name, root in ROOTS.items():
        s = snapshot(root)
        with open(os.path.join(OUT, "snapshots", "%s_POST.sha256" % name), "w",
                  encoding="utf-8") as fh:
            fh.write(s["manifest_text"])
        out[name] = {"root": s["root"], "files": s["files"],
                     "symlinks": s["symlinks"],
                     "snapshot_sha256": s["snapshot_sha256"]}
        print("%-3s %s files=%d symlinks=%d" % (name, s["snapshot_sha256"],
                                                s["files"], len(s["symlinks"])))
    with open(os.path.join(OUT, "POST_CHECK_SNAPSHOTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0

sys.exit(main())
