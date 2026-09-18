# Independent pre-freeze verification, attempt 4 (final)

Verified the current R8 bytes independently at 2026-08-28T16:49:52Z. The measured build-manifest digest was `6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a` with 724 entries. Earlier attempt conclusions were not reused.

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

`VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` — 31/31 items pass; 0 unresolved findings.

Pre-verification folded digest: `e7d3d32e70b9782c0da9d04be31ba68b4f1ace29ddae4fbbe2495b5e565b97eb`.  
Post-verification folded digest: `e7d3d32e70b9782c0da9d04be31ba68b4f1ace29ddae4fbbe2495b5e565b97eb`.  
Changed manifest-named paths: `[]`.
