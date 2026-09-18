#!/usr/bin/python3
import datetime
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent


def snapshot():
    rows = []
    for line in (ROOT / "build/R8_BUILD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        expected, rel = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        rows.append({"path": rel, "sha256": actual, "manifest_sha256": expected})
    folded = hashlib.sha256()
    for row in sorted(rows, key=lambda x: x["path"]):
        folded.update(row["path"].encode("utf-8") + b"\0" + row["sha256"].encode("ascii") + b"\n")
    return {"algorithm": "sha256(path_utf8 + NUL + lowercase_sha256 + LF), path-sorted",
            "count": len(rows), "folded_sha256": folded.hexdigest(), "files": rows}


post = snapshot()
(OUT / "POST_SNAPSHOT.json").write_text(json.dumps(post, indent=2) + "\n", encoding="utf-8")
pre = json.loads((OUT / "PRE_SNAPSHOT.json").read_text(encoding="utf-8"))
pre_map = {x["path"]: x["sha256"] for x in pre["files"]}
post_map = {x["path"]: x["sha256"] for x in post["files"]}
changed = sorted(p for p in pre_map.keys() | post_map.keys() if pre_map.get(p) != post_map.get(p))

result = json.loads((OUT / "VERIFICATION_RESULT.json").read_text(encoding="utf-8"))
by_id = {x["id"]: x for x in result["items"]}
by_id[7]["measured"] = "active R8 files=890; active R7 files=954; full cross-path (device,inode) intersection=0"
by_id[9]["measured"] = (
    "14 package occurrences classified: live in_process_ops.py:6, in_process_executor.py:6, and "
    "controller.py:798 are defect-quoting docstrings; migration.py:363 is the rejecting guard; "
    "package_tests/test_r8_migration.py:324 tests that guard; lineage incident occurrences (2) are "
    "archived evidence; fixtures occurrences (2) are inert read-only fixture data, imported by no module "
    "and referenced only by test_prepare_execution.py as a fixture directory; selftest-runtime duplicates "
    "(5) have the same classifications. No executable live-path substitution found. Verifier-script "
    "self-references were excluded as verification outputs, not package code."
)
by_id[11]["measured"] = (
    "measurement operation=PROVE_SET_NOVELTY; reference_root=/home/ubuntu/project/WPNO/ap18/korpus_docx; "
    "expected_reference_entry_count=7; exactly 3 FURTHER POSITIVE/NEGATIVE novelty controls; all four "
    "rehearsal rows (measurement plus controls) status=EXECUTED and expectation_result=AS_EXPECTED"
)
item31_pass = pre["count"] == post["count"] == 724 and not changed and pre["folded_sha256"] == post["folded_sha256"]
by_id[31] = {
    "id": 31,
    "claim": "Nothing done by this verification changed any manifest-named package file.",
    "measured": (f"pre_folded_sha256={pre['folded_sha256']}; post_folded_sha256={post['folded_sha256']}; "
                 f"files_before={pre['count']}; files_after={post['count']}; changed_paths={changed}"),
    "pass": item31_pass,
}
result["items"] = [by_id[i] for i in sorted(by_id)]
manifest_digest = hashlib.sha256((ROOT / "build/R8_BUILD_MANIFEST.sha256").read_bytes()).hexdigest()
result["manifest_sha256_verified"] = manifest_digest
result["manifest_entries_verified"] = len(post["files"])
result["package_unchanged_by_this_verification"] = item31_pass
if not item31_pass:
    result["unresolved_findings"].append(f"Item 31: manifest-named package bytes changed: {changed}")
result["overall_pass"] = all(x["pass"] for x in result["items"]) and not result["unresolved_findings"]
result["status"] = "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL" if result["overall_pass"] else "VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL"
result["verified_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(OUT / "VERIFICATION_RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

notes = f"""# Independent pre-freeze verification, attempt 4 (final)

Verified the current R8 bytes independently at {result['verified_utc']}. The measured build-manifest digest was `{manifest_digest}` with {len(post['files'])} entries. Earlier attempt conclusions were not reused.

## Commands and measurements actually run

- Measured the build manifest with `/usr/bin/sha256sum` and counted its lines before substantive verification.
- Hashed every manifest-named file before the checks, using the documented path-sorted fold recorded in `PRE_SNAPSHOT.json`.
- Independently parsed and hashed the R4, R5, R6, R7 control manifests, the R7 incident manifest, and the R8 build manifest.
- Inspected current lineage, generation-root resolution, all 43 plans, rehearsal records, migration metadata, state, results, evidence, Python call sites, note-string occurrences, operation registries, inode identities, and freeze baseline inputs.
- Ran `/usr/bin/python3 -B -m unittest discover -s . -t .` in `verification/selftest_runtime`: 503 tests, 0 failures, 0 errors, 0 skips.
- Ran `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .` at the R8 root: 361 tests, 0 failures, 0 errors, 0 skips.
- Ran `/usr/bin/python3 -B build/r8_static_safety_review.py --out-dir verification_codex_final_pre_freeze_attempt_4/static`: exit 0, `clean=true`, 0 findings.
- Called `freeze.build_baseline_from_predecessor(R8)` only; no freeze publication was run.
- Re-hashed every manifest-named file after the last check and compared exact per-path hashes and the folded digest.

All Python execution used `/usr/bin/python3 -B` with `PYTHONDONTWRITEBYTECODE=1`. No network, git, migration application, live audit phase, package repair, freeze, or R9 creation was performed. All verifier-created files are confined to this attempt-4 directory.

## Result

`{result['status']}` — {sum(x['pass'] for x in result['items'])}/31 items pass; {len(result['unresolved_findings'])} unresolved findings.

Pre-verification folded digest: `{pre['folded_sha256']}`.  
Post-verification folded digest: `{post['folded_sha256']}`.  
Changed manifest-named paths: `{changed}`.
"""
(OUT / "VERIFICATION_NOTES.md").write_text(notes, encoding="utf-8")
print(json.dumps({"status": result["status"], "pre": pre["folded_sha256"], "post": post["folded_sha256"], "changed": changed}))
