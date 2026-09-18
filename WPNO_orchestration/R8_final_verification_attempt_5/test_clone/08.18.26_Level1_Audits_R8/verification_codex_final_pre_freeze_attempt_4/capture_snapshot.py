#!/usr/bin/python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "build/R8_BUILD_MANIFEST.sha256"


def main():
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        data = (ROOT / rel).read_bytes()
        rows.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest()})
    folded = hashlib.sha256()
    for row in sorted(rows, key=lambda x: x["path"]):
        folded.update(row["path"].encode("utf-8"))
        folded.update(b"\0")
        folded.update(row["sha256"].encode("ascii"))
        folded.update(b"\n")
    out = {"algorithm": "sha256(path_utf8 + NUL + lowercase_sha256 + LF), path-sorted", "count": len(rows), "folded_sha256": folded.hexdigest(), "files": rows}
    (Path(__file__).resolve().parent / "PRE_SNAPSHOT.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(out["count"], out["folded_sha256"])


if __name__ == "__main__":
    main()
