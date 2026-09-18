# Final independent pre-freeze verification of R8 — after the lineage repair

You are an independent verifier. Measure; do not trust this prompt's numbers.
Where a claim here and the bytes disagree, the bytes win and it is a finding.

## What changed, and why there is a new verification at all

A previous verification of this package passed on 35 items and the human
supplied a valid freeze token. The controller then REFUSED the freeze, above
its own write boundary, publishing nothing and consuming nothing:

    FREEZE_LINEAGE_UNBOUND: the plan does not bind
    lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256

`cmd_freeze_level1` derived the artefact it required by string surgery on a
module constant — `"lineage/%s_MANIFEST.sha256" %
PREDECESSOR_BASELINE_REL.split(os.sep)[1]`. That gives a directory name only
when the constant points INSIDE a lineage directory, as it did in R7, which
carried a physical copy of R6. R8 inherits its predecessor by digest, so the
constant names a FILE, element [1] is a FILENAME, and the gate demanded a path
that cannot exist and that no plan could bind.

Nothing caught it because the end-to-end freeze test built its fixture by
COPYING the same expression: it created a file with that impossible name,
bound it, and the gate found what it had asked for. The test and the code
shared one wrong assumption.

The repair removes the string surgery. The required artefacts are declared as
data in `automation/freeze.py`, and the controller, the freeze-plan builder and
the freeze-plan validator read one declaration. Your job is to verify the
repaired package end to end, on its own bytes.

**The previous verification is NOT evidence for you.** It attests a manifest
that no longer describes this package. Re-measure everything.

## The two roots

    ORIGINAL = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8
    CLONE    = /home/ubuntu/project/WPNO/.r8_lineage_verify_clone_711053
    OUT      = /home/ubuntu/project/WPNO_orchestration/R8_final_lineage_freeze_repair/codex_output
    WORKSPACE= /home/ubuntu/project/WPNO_orchestration/R8_final_lineage_freeze_repair

ORIGINAL is READ-ONLY to you — enforced by the sandbox, not by permission bits.
CLONE is a `cp -a` copy placed as a DIRECT SIBLING of ORIGINAL, so that
`paths.json`'s location-relative roots (`..`, `../08.18.26_Discovery`, `.`)
resolve to the real project root, the real Discovery root and the real
predecessor siblings, while every write is absorbed by the clone. Confirm it is
byte- and metadata-identical at `WORKSPACE/preflight/COMPARE_ORIGINAL_VS_CLONE_INITIAL.json`,
and check the eight preflight conditions at `WORKSPACE/preflight/PREFLIGHT.json`.

Every check that only reads runs against ORIGINAL. Every check that writes runs
in CLONE. State which root you used for each item.

## Hard rules

- Write ONLY inside OUT and CLONE.
- No network. No git. No installation. No repair of R8. No live audit phase. Do
  not apply the migration. Do not freeze ORIGINAL. **Do not compute the real
  freeze token.** Do not create `08.18.26_Level1_Audits_R9`.
- `/usr/bin/python3`. `PYTHONDONTWRITEBYTECODE=1` and the temp/cache redirects
  are exported already. Do not unset them.
- **Never index a JSON object with a key you have not proved present.**
  `WORKSPACE/VERIFIER_SCHEMA_MAP.json` lists every key any check here names,
  with its real type and a sample, measured from the bytes. A previous attempt
  was lost to `IN_PROCESS_HANDLER_INVOCATIONS` on a record holding
  `R8_IN_PROCESS_HANDLER_INVOCATIONS`. There are no aliases and no fallbacks.
- Record each item to `OUT/ITEM_RESULTS.jsonl` the moment it finishes, before
  starting the next. Assemble the final files from that file, never from
  memory: an earlier attempt held twelve completed measurements in memory and
  lost them all to a later crash.
- Log every command to `OUT/COMMAND_LOG.jsonl` as you go.
- A measurement that COMPLETES and returns an adverse result is a finding:
  stop, record it, finish. A crash in your own scratch code measures nothing —
  fix it, rerun that measurement, and record the traceback, the fix and both
  runs.

## The package under verification

    build manifest SHA-256 : f7e181a21c902a401c55cd9f97d50c55711fbcef6c5fdf16845ab94bc8db95bb
    entries                : 728

Confirm both yourself. Every earlier manifest — `6dfd1af6…5b945a` with 724 entries among them — is
SUPERSEDED and preserved in `build/` under a `SUPERSEDED_` name. None is
evidence about these bytes.

## Where things actually live

- Phase state: `state/progress.json`, `audits[<AUDIT>][<PHASE>]["state"]`.
- Transitions: `state/transitions.jsonl`, each row has `route`.
- `test_matrix` is heterogeneous: of 295 entries across the 43 plans, 185 carry
  `step_id`, 84 carry `check_id`, and 26 carry neither. `entry["step_id"]`
  raises on 110 of them. Use `.get`.
- The predecessor disclosure is under the `r7` key of `lineage/R8_LINEAGE.json`.
- Import `automation` from CLONE so no `__pycache__` can land in ORIGINAL.

## Verify these items

### A — the repair itself

A1. `automation/freeze.py` declares `PACKAGE_LINEAGE_MODEL` and
    `required_predecessor_lineage_artifacts()` returns exactly

        ("lineage/R7_BASELINE_MANIFEST.json", "lineage/R8_LINEAGE.sha256")

    Both files exist in ORIGINAL, are regular files, and are not symlinks.
A2. The declared PREDECESSOR_BASELINE artefact equals
    `freeze.PREDECESSOR_BASELINE_REL` — the path `load_predecessor_baseline`
    actually reads. Bind one file and read another and the binding attests
    nothing.
A3. **The defective derivation is gone from every live path.** Parse every
    `.py` under ORIGINAL and find every EXECUTABLE statement computing
    `PREDECESSOR_BASELINE_REL.split(os.sep)[1]`. A comment may quote the
    defect; no live statement may compute it. Report every occurrence and how
    you classified it. Exactly two classes are permitted:

    a. the constant named `DEFECTIVE_DERIVATION` in
       `automation/package_tests/test_r8_freeze_lineage.py`, which exists to be
       proved impossible two tests later. Keyed on the assignment's target
       NAME, not on a filename.

    b. anything under `lineage/`. That directory holds
       `R7_POST_FREEZE_INCIDENT/dirty_repair_files/`, the R7-era files exactly
       as they stood during the incident -- including the original defective
       derivation at `dirty_repair_files/automation/controller.py`. It is the
       evidence the incident record exists to preserve, and editing it to
       satisfy a rule about live code would falsify the record of what went
       wrong.

    **Do not take (b) on trust -- prove it inert, and say how.** For every
    `lineage/` file that carries the derivation, confirm: it is listed in
    `lineage/R7_POST_FREEZE_INCIDENT/INCIDENT_MANIFEST.sha256`; that manifest
    verifies against the bytes on disk; and no module under `automation/` or
    `build/` loads code from `lineage/` — check `sys.path` manipulation and
    `importlib` loads by file location, with `lineage` appearing as a PATH
    SEGMENT. Do not match the bare word: `inherited_lineage_root` is a helper's
    name, not a directory, and a boundary-less match reports it.

    `verification/` is NOT exempt. The self-test replica is a copy of this
    package's own `automation/`, so the repair must be present there too; an
    earlier scan caught exactly that before the replica was rebuilt.

    `automation/package_tests/test_r8_freeze_lineage.py` performs this whole
    check itself, including the inertness proof. Read it, then measure
    independently and compare.
A4. `automation/controller.py` calls `freeze.assert_lineage_bound(plan, root)`
    at its step 9 and contains no lineage path arithmetic.
A5. Both lineage architectures are representable: `freeze.lineage_artifacts`
    accepts a synthetic LEGACY_DIRECTORY_MANIFEST model and the live
    COMPACT_DIRECT_FILE model, and refuses an unknown kind, an absolute path, a
    traversal path, a model with no baseline role, and a model with no
    attestation.

### B — the regression that was missing

B1. **CLONE.** Run
    `/usr/bin/python3 -B -m unittest automation.package_tests.test_r8_freeze_lineage`
    at the CLONE root. Report tests run, failures, errors, skips. Read the
    module first and confirm it does what B2–B4 say.
B2. It contains an end-to-end test that invokes the ACTUAL controller command —
    `python3 -m automation.controller freeze-level1 --token … --plan …` — in a
    disposable R8-shaped package, not `token_for`, not `parse_freeze_token`,
    not `build_baseline_from_predecessor`, not a lineage-path helper.
B3. That test proves, in the disposable package: the lineage gate is reached
    and passed; MODE becomes FROZEN; the control manifest verifies from disk;
    the manifest's MODE entry matches FROZEN; both baselines are nonempty; the
    verified record names the lineage artefacts required; the token is consumed
    exactly once; replay is refused; no audit phase is started; and the
    original package is not written.
B4. It also proves the old expression is refused: a plan binding only
    `lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256` is rejected with
    `FREEZE_LINEAGE_UNBOUND`.
B5. **CLONE.** Run
    `/usr/bin/python3 -B -m unittest automation.package_tests.test_freeze_order_regression`
    and confirm its fixture now derives its lineage paths from
    `freeze.required_predecessor_lineage_artifacts()` and no longer constructs
    the impossible filename.
B6. **A dry pre-write check against ORIGINAL.** Build a plan object binding the
    two declared artefacts at their real ORIGINAL digests and call
    `freeze.assert_lineage_bound(plan, ORIGINAL)`. It must return both paths.
    Then confirm, by digest and mtime_ns before and after, that the call wrote
    nothing. This is the check that would have caught the defect before a human
    was asked for a token.

### C — the suites, static safety, and the package

C1. **CLONE.** Controller/unit suite: `/usr/bin/python3 -B -m unittest discover
    -s . -t .` inside `CLONE/verification/selftest_runtime`. Expect 503 tests,
    0 failures, 0 errors, 0 skips. Report what you measure.
C2. **CLONE, then ORIGINAL for any location-bound failure.** Package suite:
    `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .`
    at the CLONE root. Report tests run, failures, errors, skips.

    Expect 405 tests, 0 errors, 0 skips, and exactly ONE failure:

        automation.package_tests.test_r7_rehearsal_output_paths
          .OutputsStayInsideTheWorkArea
          .test_no_plan_in_the_package_names_an_unconfined_output

    That test computes the permitted work area as
    `path_policy.LEVEL1_ROOT + "/work"`, which follows the package, while 34
    plan files hold 357 output paths written as absolute strings naming the
    ORIGINAL root. In situ the two agree and every path is confined; in any
    copy `LEVEL1_ROOT` moves and the baked strings do not. Confirm that
    diagnosis yourself — count the plan files and the baked paths — do not take
    it from this prompt.

    A clone failure is admitted as a relocation artefact ONLY when BOTH of
    these are measured, and you measure them:

      a. the failing test method, run UNMODIFIED in situ at the ORIGINAL root,
         changes nothing — a full inventory of every ORIGINAL path before and
         after, equal on type, size, SHA-256, symlink target, mode, uid, gid
         AND mtime_ns; and
      b. run unmodified in situ, it passes.

    If either does not hold, or if any OTHER test fails in the clone, that is
    an R8 defect: report it and stop.

    Nothing is skipped, disabled or exempted. All 405 must pass somewhere, and
    the location is chosen so each assertion means what it says. Report the
    effective totals: tests run, passing in CLONE, passing only in situ,
    unresolved. Unresolved must be 0.

    The count rose from 361 because the lineage regressions were added; confirm
    the rise is accounted for by the new module and the tests it adds.

    `WORKSPACE/tools/run_package_suite.py` implements exactly this two-pass
    procedure. You may use it — read it first and satisfy yourself it does what
    this item says — or do it by hand. Say which, and hash what you ran.
C3. **CLONE.** Static safety: `/usr/bin/python3 -B build/r8_static_safety_review.py
    --out-dir CLONE/logs/verify_static` from the CLONE root. Expect 0 findings
    and `clean` true. Compare every field with ORIGINAL's
    `build/R8_STATIC_SAFETY_REPORT.json`; they must agree on everything except
    `package_root` and `reviewed_at_utc`.
C4. `build/R8_BUILD_MANIFEST.sha256` verifies: 728 entries, every path present
    and matching, no duplicates, no malformed lines, and the set of listed
    paths equals the set of physical files for which the builder's own
    `in_scope` returns true.
C5. `build/R8_TEST_SUITE_RESULTS.json` records what the suites reported, and
    the digest of every test source it names matches disk.
C6. `build/R8_FINAL_PRE_FREEZE_CLOSURE.json` identifies the refused freeze
    attempt, the lineage defect, the repair, and the end-to-end regression, and
    records `live_execution` as none.

### D — plans, rehearsals, controls, migration

D1. 43/43 plans exist; the coverage manifest reports 0 missing, 0 duplicate,
    0 unknown.
D2. `work/_rehearsal_r8/REHEARSAL_REPORT.json` reports 43 of 43 PASS_READY,
    with 43 per-phase records.
D3. In-process: `R8_IN_PROCESS_HANDLER_INVOCATIONS` 169 and
    `R8_UNIQUE_IN_PROCESS_PLAN_STEPS` 169 in
    `build/IN_PROCESS_COUNT_RECONCILIATION.json` — **those exact prefixed
    names** — and the rehearsal aggregate's `IN_PROCESS_HANDLER_INVOCATIONS`
    and `IN_PROCESS_STEP_COUNT` both 169. Re-derive both from the record's own
    311 step rows and from the 43 plan files against
    `operation_catalog.IN_PROCESS`. `NOTE_ONLY_IN_PROCESS_STEPS` 0,
    `REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` 0, `HOLLOW_PHASES` empty.
D4. **The plans and rehearsals were NOT regenerated by this repair.** Confirm
    that is correct: check that neither the 43 plans nor the rehearsal report
    references or binds this package's `automation/controller.py` or
    `automation/freeze.py`, and that `build/rehearse_candidate_plans.py` never
    enters the freeze branch. Match on anchored references, not bare
    substrings — a first pass here matched absolute paths into R4's tree and
    reported a dependency that does not exist. If you find a real dependency,
    that is a finding.
D5. Controls: 122 control-role steps, 122 machine-checkable, 0 unenforced.
    Re-derive and compare with `build/CONTROL_EXPECTATION_COVERAGE.json`. Note
    that `CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION` is the STRING
    `"122/122"`, not an integer.
D6. No rehearsal step recorded a non-empty `reads_outside_declared_allowance`.
D7. The migration packet: `migratable_attempts` is exactly L1-A31 RUN-A and
    RUN-B; `excluded_attempts` is exactly L1-A31 COMPARISON with reason
    `EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`;
    `applied_before_freeze` false; `route_module_sha256` equals the digest of
    `automation/migration.py`; `state/migrations.jsonl` absent or empty.

### E — predecessors, live state, isolation

E1. R4's control manifest verifies with 0 mismatching.
E2. R5's has exactly ONE mismatching entry and it is `MODE`.
E3. R6's verifies with 0 mismatching.
E4. R7's verifies: 15804 entries, 0 mismatching.
E5. R8 carries R7's post-freeze incident under `lineage/R7_POST_FREEZE_INCIDENT/`;
    its `INCIDENT_MANIFEST.sha256` verifies; `lineage/R8_LINEAGE.json` has
    `r7.continuous_post_freeze_immutability` false and
    `r7.current_bytes_restored_to_frozen_manifest` true. R8 must nowhere claim
    R7 was continuously immutable after its freeze.
E6. R8 carries no full copy of any predecessor package, and no active R8 file
    shares an inode with an active R7 file. Measure by device+inode.
E7. `state/progress.json`: 35 audits, 43 phase records, every one NOT_STARTED.
E8. `state/approvals.jsonl` empty; `results/` and `evidence/` hold no files;
    `state/freeze_attempts.jsonl` absent; MODE is `GENERATED_UNVERIFIED`.
E9. `state/transitions.jsonl` holds exactly one row, `route` `init-revision`.
E10. No `08.18.26_Level1_Audits_R9` exists beside the package.
E11. **Write isolation.** Before your first measurement and after your last,
     record for EVERY path under ORIGINAL — files and directories — its size,
     mode, uid, gid, symlink target and mtime_ns. Report, as measured integers:
     paths written, mtimes changed, modes changed, symlink targets changed,
     contents changed, paths added, paths removed. All must be 0. Exempt
     nothing. `WORKSPACE/tools/inventory_r8.py` and
     `WORKSPACE/tools/compare_inventories.py` do this; read them first if you
     use them, and hash what you ran.
E12. From `/proc/<pid>/fd` and `/proc/<pid>/fdinfo/<fd>` — not `pgrep -f` —
     confirm no process other than your own holds a writable descriptor below
     ORIGINAL. Report how many pids you could inspect and how many you could
     not, and why. Kill nothing.

### F — tools

F1. Read `WORKSPACE/TOOL_INVENTORY.json`. Every row's file exists and its
    SHA-256 matches disk; `UNIDENTIFIED_TOOLS` is 0; the inventory
    distinguishes the instructions, the runner, each helper, the schema map,
    the freeze-plan builder, the plan wrapper or an explicit `NOT_USED`,
    `automation/freeze.py`, the exact token-generation function source, and
    every executable used to create or validate freeze artefacts.
    `VERIFICATION_RESULT.json` is a RESULT; if any row labels it a verifier
    that is a finding.
F2. The freeze mechanism can still produce a plan and a token:
    `freeze.PACKAGE_REVISION` is "R8", `PACKAGE_PLATFORM` "UBUNTU",
    `build_baseline_from_predecessor(CLONE)` returns with both member counts
    above zero, and `token_for`/`parse_freeze_token` round-trip on THREE DUMMY
    64-hex digests of your own choosing. **Never with the real digests.**

## Output

`OUT/VERIFICATION_RESULT.json`:

```json
{
  "schema": "wpno.level1.codex-verification/3",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL_AFTER_LINEAGE_REPAIR",
  "verified_utc": "<UTC>",
  "items": [
    {"id": "A1", "root": "ORIGINAL", "claim": "...", "measured": {},
     "pass": true}
  ],
  "manifest_sha256_verified": "<the digest you measured>",
  "manifest_entries_verified": 728,
  "lineage_defect_resolved": true,
  "old_defective_derivation_present": false,
  "exact_cmd_freeze_level1_regression": "PASS",
  "disposable_clone_freeze": "PASS",
  "package_unchanged_by_this_verification": true,
  "r8_paths_written_during_this_verification": 0,
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when every item passes
and `unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`, with every finding stated.

Also write `OUT/ITEM_RESULTS.jsonl` (incrementally, one line per item),
`OUT/MEASUREMENTS.json`, `OUT/COMMAND_LOG.jsonl`, `OUT/VERIFICATION_REPORT.md`
and `OUT/VERIFICATION_MANIFEST.sha256` (a `sha256  path` listing of every file
you wrote into OUT, itself excluded). The last five are assembled after every
measurement is complete and are not touched again.
