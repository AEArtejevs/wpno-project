"""Verify build/R7_BUILD_MANIFEST.sha256 entry by entry against R7 on disk,
and reconcile it against the package's own exclusion policy."""
import hashlib, json, os, sys

R7 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7"
MAN = os.path.join(R7, "build", "R7_BUILD_MANIFEST.sha256")
EXCLUDED_DIR_NAMES = {"__pycache__"}
EXCLUDED_TOP_LEVEL = {"work", "state", "results", "evidence", "logs"}
EXCLUDED_RELS = {os.path.join("build", "R7_BUILD_MANIFEST.sha256")}

def sha256_file(p):
    d = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()

rows, dup, malformed = {}, [], []
with open(MAN, encoding="utf-8") as fh:
    for n, line in enumerate(fh, 1):
        line = line.rstrip("\n")
        if not line:
            continue
        if "  " not in line:
            malformed.append((n, line[:80])); continue
        digest, rel = line.split("  ", 1)
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            malformed.append((n, line[:80])); continue
        if rel in rows:
            dup.append(rel)
        rows[rel] = digest

# what the policy says should be in scope, measured now
on_disk = {}
for dirpath, dirnames, filenames in os.walk(R7, followlinks=False):
    dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIR_NAMES)
    for name in sorted(filenames):
        full = os.path.join(dirpath, name)
        rel = os.path.relpath(full, R7)
        if os.path.islink(full):
            print("SYMLINK:", rel); continue
        if rel.split(os.sep)[0] in EXCLUDED_TOP_LEVEL or rel in EXCLUDED_RELS:
            continue
        on_disk[rel] = full

missing = sorted(set(rows) - set(on_disk))
unlisted = sorted(set(on_disk) - set(rows))
mismatch = []
for rel in sorted(set(rows) & set(on_disk)):
    if sha256_file(on_disk[rel]) != rows[rel]:
        mismatch.append(rel)

# physical reconciliation
phys = sum(len(f) for _, _, f in os.walk(R7, followlinks=False))
pyc = 0
for dp, dn, fn in os.walk(R7, followlinks=False):
    if os.path.basename(dp) == "__pycache__":
        pyc += len(fn)
excl_top = 0
for top in EXCLUDED_TOP_LEVEL:
    p = os.path.join(R7, top)
    if os.path.isdir(p):
        for dp, dn, fn in os.walk(p, followlinks=False):
            excl_top += len(fn)

res = {
    "manifest_path": os.path.relpath(MAN, R7),
    "manifest_sha256": sha256_file(MAN),
    "entry_count": len(rows),
    "duplicate_paths": dup,
    "malformed_rows": malformed,
    "manifest_lists_itself": os.path.relpath(MAN, R7) in rows,
    "missing_on_disk": missing,
    "on_disk_not_listed": unlisted,
    "hash_mismatch": mismatch,
    "physical_files_total": phys,
    "excluded_pycache_files": pyc,
    "excluded_top_level_files": excl_top,
    "manifest_self_excluded": 1,
}
res["reconciles"] = (phys == len(rows) + pyc + excl_top + 1)
res["reconcile_arithmetic"] = "%d physical = %d listed + %d pycache + %d excluded-top + 1 manifest" % (
    phys, len(rows), pyc, excl_top)
res["VERIFIED"] = not (missing or unlisted or mismatch or dup or malformed) and res["reconciles"]
print(json.dumps(res, indent=2)[:6000])
with open("MANIFEST_VERIFY_PRE.json", "w", encoding="utf-8") as fh:
    json.dump(res, fh, indent=2, sort_keys=True); fh.write("\n")
