#!/usr/bin/env python3
"""Report declared payload-scanner copies without conflating their roles."""

import argparse
import hashlib
import json
import os
from pathlib import Path


DECLARED = (
    ("anonymization/payload_scan.py", "active_canonical", True),
    ("docker/litellm/payload_scan.py", "active_alias", True),
    ("anonymization/golden/payload_scan.py", "golden_test_asset", True),
    ("anonymization/payload_scan.py.ALT.2026-08-05.bak",
     "backup_anonymization", False),
    ("docker/litellm/payload_scan.py.ALT.2026-08-05.bak",
     "backup_docker", False),
    ("docs/Test_07.28.26/AP-03/logs/payload_scan.py.before_F-AP03",
     "historical_before_fix", False),
)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(root):
    root = root.resolve()
    canonical = root / DECLARED[0][0]
    canonical_hash = _sha256(canonical) if canonical.is_file() else None
    copies = []
    failures = []

    for relative, role, required in DECLARED:
        path = root / relative
        item = {
            "path": relative,
            "role": role,
            "required": required,
            "present": path.is_file(),
            "symlink": path.is_symlink(),
            "sha256": None,
            "status": None,
        }
        if not path.is_file():
            item["status"] = ("MISSING_REQUIRED" if required else
                              "ABSENT_DECLARED_NON_ACTIVE")
            if required:
                failures.append(f"missing required {relative}")
        else:
            item["sha256"] = _sha256(path)
            if role == "active_canonical":
                item["status"] = "ACTIVE_CANONICAL"
            elif role == "active_alias":
                same_target = (path.is_symlink() and
                               path.resolve() == canonical.resolve())
                same_content = item["sha256"] == canonical_hash
                item["status"] = ("ACTIVE_ALIAS_OK" if same_target and same_content
                                  else "ACTIVE_ALIAS_DRIFT")
                if item["status"] != "ACTIVE_ALIAS_OK":
                    failures.append(f"active alias drift {relative}")
            else:
                item["status"] = (
                    "INTENTIONAL_NON_ACTIVE_SAME_CONTENT"
                    if item["sha256"] == canonical_hash else
                    "INTENTIONAL_NON_ACTIVE_DIFFERENCE"
                )
        copies.append(item)

    declared_paths = {item[0] for item in DECLARED}
    discovered = set()
    excluded = {".git", "__pycache__", ".pytest_cache"}
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames
                       if name not in excluded and "_Level1_Audits_" not in name]
        for name in filenames:
            if (name.startswith("payload_scan.py") or
                    name == "payload_scan.py.before_F-AP03"):
                path = Path(directory) / name
                discovered.add(path.relative_to(root).as_posix())
    unexpected = sorted(discovered - declared_paths)
    if unexpected:
        failures.append("undeclared scanner copies: " + ", ".join(unexpected))

    return {
        "ok": not failures,
        "canonical": DECLARED[0][0],
        "copies": copies,
        "unexpected": unexpected,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
