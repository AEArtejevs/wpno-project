#!/usr/bin/env python3
"""Negative control: the fixture must reproduce the R5 defect on unmodified code.

A fixture that passes here would be measuring nothing. The R5 freeze produced a
CONTROL_MANIFEST whose MODE entry is the pre-freeze digest; this fixture has to
produce exactly that failure before it is allowed to certify a repair.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fixture as bf

BASE = sys.argv[1]
AUTOMATION = sys.argv[2]

pkg, bpath, lin = bf.build(BASE, AUTOMATION)

r = bf.run(pkg, ["init-revision", "--revision", "R5", "--predecessor", "R4",
                 "--predecessor-root", "/nonexistent",
                 "--lineage", "lineage/R4_EXECUTION", "--platform", "UBUNTU"])
print("init-revision rc=%d" % r.returncode)
if r.returncode != 0:
    print(r.stdout, r.stderr); raise SystemExit("init failed")

rel, plan_sha, token = bf.make_plan(pkg, bpath, lin, 2, "build/freeze_plan")
r = bf.run(pkg, ["freeze-level1", "--token", token, "--plan", rel])
print("freeze rc=%d" % r.returncode)
print(r.stdout[-800:])
print(r.stderr[-800:])
if r.returncode != 0:
    raise SystemExit("freeze failed - fixture cannot reach the write stage")

mode = open(os.path.join(pkg, "MODE")).read().strip()
check = subprocess.run(["sha256sum", "-c", "CONTROL_MANIFEST.sha256"],
                       cwd=pkg, capture_output=True, text=True)
bad = [l for l in check.stdout.splitlines() if not l.endswith(": OK")]
total = len(check.stdout.splitlines())
print(json.dumps({"mode_on_disk": mode, "manifest_entries": total,
                  "failed": bad}, indent=2))
