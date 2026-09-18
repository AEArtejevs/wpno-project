# Independent pre-freeze verification of R8 — attempt 5

Result: `VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`.

The first substantive finding was item 19. The required package suite in CLONE ran 343 tests and ended with 1 failure and 47 errors. I did not retry it, run item 20, or continue the remaining substantive checks. This differs from attempt 4's record of 361 passing tests.

## Commands actually run

- ORIGINAL: read and SHA-256 hashed `tools/inventory_r8.py` and `tools/compare_inventories.py`, then ran `/usr/bin/python3 -B tools/inventory_r8.py ORIGINAL codex_output/original_inventory_before.json`.
- ORIGINAL: ran an independent Python manifest parser/hasher. It measured the build-manifest digest as `6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a`, 724 entries, and zero missing or mismatching entries. The raw-digest-byte fold was `c6f1ce026f0e5a1cfdb5b9e1d65d8a46ead9ee6679cba9b93a1c096d1ad2d21b`.
- CLONE/controller: ran `/usr/bin/python3 -B -m unittest discover -s . -t .` in `verification/selftest_runtime`. Result: 503 tests, 0 failures, 0 errors, 0 skips.
- CLONE/package: ran `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .` at the clone root. Result: 343 tests, 1 failure, 47 errors, 0 skips.
- ORIGINAL: after the failure, ran the required final full-tree inventory and compared it with the pre-inventory using the supplied helper. All 1,362 paths were equal on type, size, content SHA-256, symlink target, mode, uid, gid, and mtime_ns.
- ORIGINAL: recomputed the 724-file fold after the suite failure. It remained `c6f1ce026f0e5a1cfdb5b9e1d65d8a46ead9ee6679cba9b93a1c096d1ad2d21b`, with zero changed manifest paths.

The pre-mtime for the Unicode control comes from `original_inventory/INVENTORY_CLONE_INITIAL.json`, whose equality record I independently read before testing. A preliminary relative-path stat command used the package-root-relative path while already inside `verification/selftest_runtime` and therefore did not find the file; it made no write. I did not retry or rerun the suite. The already-recorded initial clone inventory supplies the required before value. After the controller suite, the clone file's mtime moved from `1787935556841911690` to `1787925319844038458` ns while its bytes matched ORIGINAL, proving the write-isolation instrument was live.

The package-suite errors were dominated by clone-location assumptions: predecessor paths were rejected as outside allowed roots, the clone did not have predecessor sibling packages under its parent, and baseline construction reported the project `.gitignore` absent. The single assertion failure classified an absolute ORIGINAL work path in L1-A01/RUN-A `run1` as outside the CLONE work root. These are measured outcomes, not inferred passes.

No network, git, installation, migration, live audit, freeze, token creation, R9 creation, repair, or test modification was performed. The static-safety command was not run because the mandatory stop had already triggered.
