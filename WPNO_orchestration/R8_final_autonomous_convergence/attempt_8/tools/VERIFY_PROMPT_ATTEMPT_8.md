# Independent pre-freeze verification of R8 — attempt 8 (final)

You are an independent verifier. Measure; do not trust this prompt's numbers.
Check every claim against bytes on disk. Where a claim and the bytes disagree,
the bytes win and it is a finding.

## What this attempt is

Attempt 5 did not fail on R8. It failed on its own instructions. Its
disposable clone was placed at `ATTEMPT5_ROOT/test_clone/…`, outside the
package's required sibling layout. `paths.json` is location-relative —
`project_root ".."`, `discovery_root "../08.18.26_Discovery"`,
`level1_root "."` — so the package carries its roots with it. From that
location `project_root` resolved to a directory holding only the clone,
`discovery_root` did not exist, and R4–R7 were not siblings. The package suite
reported 343 tests, 1 failure and 47 errors, and stopped the attempt; 31 of 34
items were never measured. Those 31 are NOT VERIFIED, which is not FAILED.

Attempt 5 also recorded one item on the wrong file: it stat-ed a relative path
that resolved to a different file from the one it had measured before, and
wrote an "after" mtime EARLIER than its "before". Section "The absolute-path
rule" below exists to make that impossible here.

Neither defect is in R8, and R8 has not been modified to record them.

Attempt 6 ran under the corrected sibling placement and got much further:
items 1–8, 27, 31 and 32 passed on measurement, R8 was provably unwritten, and
the 47 errors were gone. It stopped at item 9, and again the defect was in the
instruction. Item 9's exclusion rule was written in terms of PATHS, so it could
not dispose of the self-test replica's byte-identical copies of four modules,
nor of two earlier verifiers' own scripts that merely search for the phrase.
Codex's own conclusion was "No R8 defect has been established by this attempt."
Item 9's content-based rule then worked. Attempt 7 got past it and was ended at
item 13 by a `KeyError('step_id')` in its own scratch code: the instructions had
described `test_matrix` as though every entry carried a `step_id`, and 110 of
its 295 entries do not. Attempt 7 also lost twelve completed measurements,
because the instructions told it to write its results only at the end. Both are
repaired below — the structure is stated as it is, results are recorded as they
are made, and a crash in your own scratch code is separated from an adverse
measurement. Attempts 1-7 remain not evidence for you.

Attempts 1–5 are NOT evidence for you. Their outputs may be read for
comparison only. Re-measure everything yourself. Where your measurement
differs from an earlier attempt's, yours is the one that counts and the
difference is worth stating.

This is VERIFICATION ONLY. You may not repair, edit, delete, move, rename,
regenerate or reformat anything in R8, and you may not change any test.

**A measurement that COMPLETES and returns an adverse result is a finding.**
Any defect, inconsistency, missing evidence, package mutation, manifest
mismatch, test failure, or unenforced control: STOP, record it, and finish. Do
not repair it, do not work around it, and do not re-run it to see whether it
clears.

**A crash in your own throwaway measurement code is not that.** A `KeyError`, a
`TypeError`, a mistyped path in a scratch script you wrote measures nothing
about R8 in either direction, and letting a typo end the audit would be the
instrument deciding the outcome. When your own code raises before it has
measured anything: fix that code, re-run THAT measurement, and record in
`OUT/VERIFICATION_REPORT.md` the traceback, what you changed, and both runs.
This applies only to code you wrote in this session. It does not extend to any
file in R8, to any test, or to any helper supplied to you — a defect in one of
those is a finding and you stop.

The line between the two is whether a measurement was actually made. If your
code ran to completion and told you something adverse about R8, that stands and
you stop. If it fell over before it could tell you anything, it is not evidence
and you repair your own instrument.

If you find a defect in these INSTRUCTIONS — a claim here that the bytes
contradict — record it as a finding against the instructions, say what the
bytes actually are, and continue with the corrected understanding if you can do
so without weakening the check. Say clearly that you did.

## The two roots, and which one each check uses

    ORIGINAL = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8
    CLONE    = /home/ubuntu/project/WPNO/.r8_verify_clone_attempt_8_667636
    OUT      = /home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_8/codex_output
    WORKSPACE= /home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_8

ORIGINAL is the package being frozen. It is READ-ONLY to you — not by
permission bits, nothing has touched its modes, but because the sandbox denies
every write outside your writable roots. Do not route around that. If a write
outside OUT or CLONE is refused, record it as a finding; do not retry it
another way.

CLONE is a `cp -a --reflink=auto` copy made before you started, placed as a
DIRECT SIBLING of ORIGINAL under `/home/ubuntu/project/WPNO/`. That placement
is the whole correction of attempt 5. From there:

    project_root    -> /home/ubuntu/project/WPNO          (the real one)
    discovery_root  -> /home/ubuntu/project/WPNO/08.18.26_Discovery (exists)
    level1_root     -> CLONE

R4, R5, R6 and R7 are siblings of CLONE, and `PROJECT_ROOT/.gitignore` is
present — so predecessor and path-policy checks measure the real architecture,
while `WRITE_ROOTS = (LEVEL1_ROOT,)` still confines every test write to CLONE.

The clone's name is hidden and does not match the revision glob
`08.18.26_Level1_Audits*`, so nothing that enumerates revisions can mistake it
for one. Confirm that yourself.

Verify the preflight record at `WORKSPACE/preflight/PREFLIGHT.json` — eight
checks, all of which must pass — and satisfy yourself it measures what this
section claims before you rely on the clone.

**Every check that only reads runs against ORIGINAL.**
**Every check that writes runs in CLONE.**

State, for every item, which root you measured.

## The absolute-path rule

Every measurement uses an absolute canonical path. Never stat, hash or compare
a relative path without first recording the absolute path it resolved to.

For every before/after file check record all of:

    requested path
    resolved absolute path
    the root it belongs to
    before mtime_ns / after mtime_ns
    before SHA-256 / after SHA-256

If `after_mtime_ns < before_mtime_ns`, that check is INVALID EVIDENCE. Stop
it. Do not report it as a pass. An mtime cannot run backwards for one file
across one interval; a backwards mtime proves the two observations addressed
two different files.

`WORKSPACE/tools/measure_path.py` does exactly this and refuses such a pair.
You may use it — read it first and satisfy yourself — or write your own. Say
which, and hash what you ran.

## Hard rules

- Write ONLY inside OUT and CLONE. CLONE is disposable and may receive
  test-generated output.
- No network. No git. No installation. No package repair. No live audit phase.
  Do not apply the migration. Do not freeze. Do not create a token. Do not
  create `08.18.26_Level1_Audits_R9`.
- `/usr/bin/python3` for everything. `PYTHONDONTWRITEBYTECODE=1` is already
  exported, and `PYTHONPYCACHEPREFIX`, `TMPDIR`, `TEMP`, `TMP`,
  `PYTEST_ADDOPTS` and `COVERAGE_FILE` are already redirected out of both
  packages. Do not unset them. No `.pyc` inside either root.
- Run the suites with `python -m unittest` directly. Do NOT use
  `build/run_test_suites.py`; it writes into `build/`.
- Do not modify anything in R4, R5, R6 or R7. Read them only.
- Log every command you run, with its exit status, to `OUT/COMMAND_LOG.jsonl`,
  one JSON object per line, as you go.
- **Record each item the moment it finishes, before you start the next.**
  Append one JSON object per item to `OUT/ITEM_RESULTS.jsonl`:

      {"id": 9, "root": "ORIGINAL", "claim": "...", "measured": {...},
       "pass": true, "finished_utc": "..."}

  Attempt 7 held items 1-12 in memory, hit a crash at item 13, and lost all
  twelve — they were then reported `pass: false` with the note "measurement
  process aborted before durable result capture", which is not what had been
  measured. A measurement that is not written down is not evidence. Assemble
  the final `VERIFICATION_RESULT.json` from this file, not from memory, so a
  later stop leaves earlier measurements intact and correctly labelled.

## Predecessor roots

    R7 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R7
    R6 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6
    R5 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    R4 = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4

## The manifest this attempt verifies

    6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a

with 724 entries. Confirm that digest and that count yourself before you begin.
Earlier manifests in `build/` carry `SUPERSEDED` in their names and are not
evidence about the current bytes.

## Where things actually live — read this before writing a check

Structural facts, given so your checks address the right bytes. The values are
still yours to measure.

- Phase state is in `state/progress.json`, under
  `audits[<AUDIT>][<PHASE>]["state"]`. There is no `state/phase_status.json`.
- Transition records are in `state/transitions.jsonl`. Each row has a `route`
  key. There is no `event` key.
- A step's expectation lives in the plan's `test_matrix`, in the entry whose
  `step_id` equals the step's — **but `test_matrix` is heterogeneous and most
  of its entries are not step expectations at all.** Measured across all 43
  plans:

      test_matrix entries        295
        carrying `step_id`       185
        carrying `check_id`       84   (34 of them PLAN_BINDING)
        carrying neither          26   (free-form prose keys such as
                                        `compared`, `refusal`, `independence`)

  So `entry["step_id"]` raises `KeyError` on 110 of 295 entries. Attempt 7 was
  ended by exactly that. Use `entry.get("step_id")` and skip an entry that has
  none; do not index it, and do not treat its absence as a defect.

  The 43 plans hold 311 steps, and every step does carry `step_id`,
  `operation`, `params`, `purpose`, `control_role` and `timeout_seconds`.
  Confirm these counts yourself.

  The expectation vocabulary is wider than exit codes:
  `expected_exit_code`, `expected_status`, `expected_count`,
  `expected_minimum_count`, `expected_hash_relation`, `expected_boolean`,
  `expected_difference_count`, `expected_failure_reason_canonical`,
  `expected_parse_result`, `expected_validation_result`. The authoritative list
  is `automation.in_process_executor.EXPECTATION_KEYS` and
  `expectation_keys_present(entry)` is the function that reads it. Use them.
- R8's predecessor disclosure is nested under the `r7` key of
  `lineage/R8_LINEAGE.json`, not at the top level.
- R4 predates `state/REVISION.json` and is reachable as `lineage/R4_EXECUTION`
  inside R5. `automation.package_tests.generation_root` handles this; use it
  rather than reimplementing the walk.
- Importing R8's `automation` package requires its root on `sys.path`. Import
  from CLONE, so no `__pycache__` can land in ORIGINAL even if the bytecode
  redirect were to fail. The two trees are byte-identical and you re-prove that
  in item 32.

## Verify these thirty-five items

1.  R4's `CONTROL_MANIFEST.sha256` verifies with 0 mismatching.
2.  R5's control manifest has exactly ONE mismatching entry and it is `MODE`.
    More than one, or a different path, is a finding.
3.  R6's control manifest verifies with 0 mismatching.
4.  R7's control manifest verifies: 15804 entries, 0 mismatching.
5.  R8 carries R7's post-freeze incident record under
    `lineage/R7_POST_FREEZE_INCIDENT/`; its `INCIDENT_MANIFEST.sha256`
    verifies; and `lineage/R8_LINEAGE.json` has
    `r7.continuous_post_freeze_immutability == false` and
    `r7.current_bytes_restored_to_frozen_manifest == true`. R8 must nowhere
    claim R7 was continuously immutable after its freeze.
6.  R8 contains no directory `lineage/R6_EXECUTION` and no full copy of any
    predecessor package, and `generation_root` resolves all of R4, R5, R6, R7
    and R8.
7.  No active R8 file shares an inode with an active R7 file. Measure by
    device+inode, not by path.
8.  `in_process_executor.execute` is called from BOTH `automation/controller.py`
    and `build/rehearse_candidate_plans.py`.
9.  No LIVE code path writes a note instead of performing an in-process
    operation.

    Find every occurrence of the string "performed by the worker" in every
    `.py` under R8, then classify EVERY ONE and report your classification of
    all of them. Attempt 6 found 16; measure the number yourself.

    **A FINDING is an executable statement on a live controller or rehearsal
    path that assigns that note as a step's outcome instead of performing the
    operation.** That definition is what you are testing against. Nothing below
    relaxes it; the rules below only say how to recognise an occurrence that
    does not meet it.

    Classify by CONTENT, not by filename. Attempt 6's rule was written in terms
    of paths and reported five occurrences as findings that the definition
    above does not reach — the self-test replica's byte-identical copies of
    four modules, and two earlier verifiers' own scripts. That was a defect in
    the instruction, and this is its repair.

    An occurrence is NOT a finding when any of these holds, and you say which:

      a. **Quoted text.** It lies inside a docstring, a comment, or a string
         literal that quotes or describes the defect rather than performing it.
         Decide this from the syntax tree, not from the file's name. Example:
         `automation/controller.py:798` sits inside the docstring of
         `_run_in_process_operation`, which reproduces the old defective branch
         in order to say what was repaired.

      b. **A guard that refuses the note.** Code whose effect is to REJECT a
         record carrying that note — for instance
         `if "performed by the worker" in note: raise ...` in
         `automation/migration.py` — together with any test that exercises that
         guard. Refusing the note is the opposite of assigning it. Show the
         refusal: name the exception raised or the assertion made.

      c. **A byte-identical duplicate of a file already classified.** If a
         file's SHA-256 equals that of a file you have already classified as
         not-a-finding, it holds the same bytes and therefore the same
         statements, and it inherits that classification. **Record both paths
         and the shared digest.** This is how the self-test replica under
         `verification/selftest_runtime/` is disposed of: it duplicates the
         package, so `verification/selftest_runtime/automation/controller.py`
         is the same file as `automation/controller.py`. Do not take that on
         trust — measure the digests. If a replica file is NOT byte-identical
         to its original, this rule does not apply to it and you classify it on
         its own content.

         Additionally show the replica is not a live path: confirm that no
         module reached from `automation/controller.py` or
         `build/rehearse_candidate_plans.py` imports anything from
         `verification/selftest_runtime/`.

      d. **A verifier's own script.** A file under a
         `verification_codex_final_pre_freeze_attempt_*` directory that
         SEARCHES for the phrase — `if "performed by the worker" in src`, a
         grep pattern, an AST scan. A script that looks for a string does not
         assign it. These directories are excluded from the build manifest and
         are not on any controller or rehearsal path; confirm that.

      e. **Read-only fixture or lineage data.** Any path SEGMENT is `fixtures`
         or `lineage`, at any depth — a segment test, not a prefix test. For
         any file excluded this way, show it is inert rather than assuming it:
         confirm no module imports it and that it is referenced only as a
         directory of read-only data.

    Report, for every occurrence: path, line, the matched text, which rule
    disposed of it, and the evidence for that rule (the AST node kind, the
    exception raised, the shared digest, the import check). If any occurrence
    is disposed of by none of them, it is a FINDING and you stop.

10. Every operation in `operation_catalog.IN_PROCESS` has a handler in
    `in_process_ops.HANDLERS` and a schema in
    `in_process_executor.ARGUMENT_SCHEMA`; the three sets are equal.
11. L1-A16's novelty measurement and its controls. Passes when a, b and c hold.

    a. In `build/candidate_plans_r8/L1-A16/RUN-A/plan.json`, step
       `prove_cases_are_novel` has operation `PROVE_SET_NOVELTY`,
       `reference_root` `/home/ubuntu/project/WPNO/ap18/korpus_docx` (not
       `ap18`), and `expected_reference_entry_count` 7.
    b. That plan has exactly three FURTHER steps whose operation is
       `PROVE_SET_NOVELTY` and whose `control_role` is POSITIVE or NEGATIVE.
    c. In `work/_rehearsal_r8/REHEARSAL_REPORT.json`, every step of
       L1-A16/RUN-A whose operation is `PROVE_SET_NOVELTY` has `status`
       EXECUTED and `expectation_result` AS_EXPECTED. There are FOUR such
       steps: the measurement from (a) and the three controls from (b). Four
       AS_EXPECTED results is the expected outcome, not an excess.
12. In all 43 plans: no `COMPARE_HASHES` step has `left == right` without an
    `expected_sha256`; and no rehearsal step recorded a non-empty
    `reads_outside_declared_allowance`. Report the count of steps carrying that
    key and the count that were non-empty. The second count must be 0.
13. L1-A21 `negative_control_export_is_not_another_project` uses
    `COUNT_TEXT_MATCHES`, `word_boundary` true, expected count 0.
14. `references/REF-11-563203462.xml` still begins `MIME-Version:` and has the
    same sha256 as R7's copy; L1-A33 extracts the part into `work/` and parses
    the extraction, not the reference.
15. Every control-role step (POSITIVE/NEGATIVE/MUTATION/ORACLE/SABOTAGE) in all
    43 plans carries at least one expectation from `EXPECTATION_KEYS`.
    Re-derive the count and the unenforced list yourself and compare with
    `build/CONTROL_EXPECTATION_COVERAGE.json`. Report both your count and the
    record's. The unenforced count must be 0.
16. `build/migration_plan_r7_to_r8/MIGRATION_PLAN.json`: `migratable_attempts`
    is exactly L1-A31 RUN-A and RUN-B; `excluded_attempts` is exactly L1-A31
    COMPARISON with reason
    `EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT`;
    `applied_before_freeze` is false; and its `route_module_sha256` equals the
    digest of `automation/migration.py`. Confirm also that
    `state/migrations.jsonl` is absent or empty, i.e. the packet is unconsumed.
17. In R7, L1-A31 COMPARISON is EXECUTED, has no SEAL.json, and has zero
    evidence files.
18. **CLONE.** Controller suite passes with 0 failures, 0 errors, 0 skips. Run
    `/usr/bin/python3 -B -m unittest discover -s . -t .` inside
    `CLONE/verification/selftest_runtime`. Report the number of tests run.
19. **CLONE, then ORIGINAL for any location-bound failure.** The package suite.

    Run `/usr/bin/python3 -B -m unittest discover -s automation/package_tests
    -t .` at the CLONE root. Report tests run, failures, errors, skips.

    Expect 361 tests, 0 errors, 0 skips, and exactly ONE failure:

        automation.package_tests.test_r7_rehearsal_output_paths
          .OutputsStayInsideTheWorkArea
          .test_no_plan_in_the_package_names_an_unconfined_output

    That test computes the permitted work area as
    `path_policy.LEVEL1_ROOT + "/work"`, which follows the package, while 34
    plan files hold 357 output paths written as absolute strings naming the
    ORIGINAL root. In situ the two agree and every path is confined; in any
    copy `LEVEL1_ROOT` moves and the baked strings do not. Confirm that
    diagnosis yourself — count the plan files and the baked paths — do not
    take it from this prompt.

    A clone failure is admitted as a relocation artefact ONLY when BOTH of
    these are measured, and you measure them:

      a. the failing test method, run UNMODIFIED in situ at the ORIGINAL root,
         changes nothing — a full inventory of all 1362 ORIGINAL paths before
         and after, equal on type, size, SHA-256, symlink target, mode, uid,
         gid AND mtime_ns; and
      b. run unmodified in situ, it passes.

    If either does not hold, or if any OTHER test fails in the clone, that is
    an R8 internal defect and you report it as one and stop.

    Nothing is skipped, disabled or exempted: all 361 must pass somewhere, and
    the location is chosen so each assertion means what it says. Report the
    effective totals: tests run, tests passing in CLONE, tests passing only in
    situ, tests unresolved. Unresolved must be 0.

    `WORKSPACE/tools/run_package_suite.py` implements exactly this two-pass
    procedure. You may use it — read it first and satisfy yourself it does what
    this item says — or do it by hand. Say which, and hash what you ran.
20. **CLONE.** Static safety reports 0 findings and `clean` true. Run
    `/usr/bin/python3 -B build/r8_static_safety_review.py --out-dir
    CLONE/logs/attempt6_static` from the CLONE root, then copy the output files
    into OUT. The script refuses an out-dir outside its own package; that
    refusal is by design and is why this item runs in CLONE. Confirm its
    `predecessor_root` resolved to the real R7 sibling, and compare its every
    field with `build/R8_STATIC_SAFETY_REPORT.json` in ORIGINAL: they must
    agree on everything except `package_root` and `reviewed_at_utc`.
21. 43/43 plans exist and the coverage manifest reports 0 missing, 0 duplicate,
    0 unknown.
22. `work/_rehearsal_r8/REHEARSAL_REPORT.json` reports 43 of 43 phases
    PASS_READY.
23. That report has `REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE` 0 and
    `NOTE_ONLY_IN_PROCESS_STEPS` 0, and
    `IN_PROCESS_HANDLER_INVOCATIONS == IN_PROCESS_STEP_COUNT`. Report both
    numbers. Compare them with `build/IN_PROCESS_COUNT_RECONCILIATION.json`.
24. That report has `HOLLOW_PHASES` empty and `LIVE_STATE_UNCHANGED` true.
25. `state/progress.json` holds 35 audits and 43 phase records, and every one is
    `NOT_STARTED`.
26. `state/approvals.jsonl` is empty; `results/` and `evidence/` contain zero
    files; and no approval token text (`APPROVE-EXECUTION`, `RUN-ONCE`) appears
    anywhere under `state/`.
27. `build/R8_BUILD_MANIFEST.sha256` verifies: every entry present and
    matching, no duplicates, no malformed lines, and the set of listed paths
    equals the set of physical files for which the builder's own `in_scope`
    returns true.
28. **The freeze mechanism is capable of producing the plan and the token.**

    a. `automation/freeze.py` has `PACKAGE_REVISION` "R8" and
       `PACKAGE_PLATFORM` "UBUNTU".
    b. Its `PREDECESSOR_BASELINE_REL` resolves to a file inside R8 whose digest
       equals `lineage/R8_LINEAGE.json`'s `r7.baseline_manifest_sha256`.
    c. `freeze.build_baseline_from_predecessor(CLONE)` returns without raising,
       and both baseline member counts are greater than zero. Report them.
    d. `freeze.token_for` composes a well-formed token and
       `freeze.parse_freeze_token` accepts it: call `token_for` with THREE
       DUMMY 64-hex digests of your own choosing — for example the SHA-256 of
       the strings "a", "b" and "c" — never with the package's real digests.
       Confirm five whitespace-separated fields, no trailing newline, and that
       `parse_freeze_token` round-trips them. **You must not compute the real
       token.** Producing it is not yours to do and would be a finding against
       this attempt.
    e. `state/freeze_attempts.jsonl` records no consumed attempt, and MODE
       reads `GENERATED_UNVERIFIED`.
29. No `08.18.26_Level1_Audits_R9` exists beside the package.
30. `state/transitions.jsonl` contains exactly one row and its `route` is
    `init-revision`.
31. Nothing you did changed ORIGINAL. Before your first measurement and after
    your last, compute the SHA-256 of every file under ORIGINAL whose path the
    build manifest names, fold those 724 digests into one digest, and compare
    the two. They must be identical. Report both. If they differ, name every
    path that changed; that is a VERIFICATION_FAIL and you must not attempt to
    restore anything.
32. **Write isolation, stated as a metadata claim and not only a byte claim.**
    Before your first measurement and after your last, record for EVERY path
    under ORIGINAL — all 1362, not only the 724 the manifest covers, and
    directories as well as files — its size, mode, uid, gid, symlink target and
    mtime in nanoseconds. Compare the two records. Report, as measured
    integers:

        R8 paths written              (expect 0)
        R8 mtimes changed             (expect 0)
        R8 modes changed              (expect 0)
        R8 symlink targets changed    (expect 0)
        R8 contents changed           (expect 0)
        R8 paths added                (expect 0)
        R8 paths removed              (expect 0)

    Exempt nothing. In particular do not exempt
    `verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt`,
    the file attempt 4 allowed to be rewritten. Its mtime must be unchanged,
    not merely its bytes.

    Note that item 19(a) runs one test method in situ at ORIGINAL. That is
    inside this window and is not exempt from it: if it wrote anything, this
    item must show it.

    `WORKSPACE/tools/inventory_r8.py` and
    `WORKSPACE/tools/compare_inventories.py` exist and do this. You may use
    them, and if you do you must first read both and satisfy yourself they
    measure what this item says. You may write your own instead. Either way say
    which you did, and hash what you ran.
33. **The instrument is live: the write it must catch, it catches.**

    A zero in item 32 means nothing if the instrument is blind. So make the
    write happen where it is allowed to, and show the instrument sees it.

    In CLONE, after item 18 has run, observe

        CLONE/verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt

    **by that absolute path and no other.** Attempt 5 recorded this item by
    stat-ing the relative path `work/_selftest/unicode_fs_behaviour.txt`, which
    resolved to the clone's ROOT-LEVEL `work/_selftest/…` — a different file —
    and so reported an "after" mtime earlier than its "before". Record, for
    both observations: requested path, resolved absolute path, owning root,
    mtime_ns, SHA-256. If the two resolved paths differ, or the mtime runs
    backwards, the check is INVALID and you say so instead of passing it.

    Report the CLONE mtime before and after the suite, and whether the bytes
    still match ORIGINAL's copy. State plainly which you observed: the mtime
    moved (the instrument is live), or it did not (item 32's zero is measuring
    nothing).
34. **Every verification and freeze tool is identified and hashed by role.**
    Read `WORKSPACE/TOOL_INVENTORY.json`. For every row confirm the file exists
    and its SHA-256 matches. Confirm the inventory distinguishes:

      - the verification INSTRUCTIONS (this file);
      - the verification RUNNER (the script that launched you);
      - each verifier HELPER;
      - the clone builder and the clone preflight;
      - the inventory script and the inventory comparator;
      - the test runner;
      - the static-safety runner;
      - the freeze-plan BUILDER;
      - the plan RUNNER or wrapper, or an explicit NOT_USED;
      - `automation/freeze.py`;
      - the exact token-generation function source;
      - every executable used to create or validate freeze artefacts.

    `VERIFICATION_RESULT.json` is the RESULT of a verification and is not a
    verifier. If the inventory labels it as one, that is a finding. Confirm
    `UNIDENTIFIED_TOOLS` is 0. If any tool named there cannot be identified, or
    any row's digest does not match, stop with
    `VERIFICATION_FAIL_UNIDENTIFIED_TOOL`.
35. **No concurrent writer, and the limit of that measurement stated.**
    Confirm from `/proc/<pid>/fd` and `/proc/<pid>/fdinfo/<fd>` — not from
    `pgrep -f`, which matches a command line rather than a handle — that no
    process other than your own holds a writable descriptor below ORIGINAL.
    Report how many pids you could inspect and how many you could not, and why.
    Do not kill anything.

## Output

Write `OUT/VERIFICATION_RESULT.json`:

```json
{
  "schema": "wpno.level1.codex-verification/1",
  "revision": "R8",
  "stage": "PRE_FREEZE_FINAL",
  "attempt": 8,
  "verified_utc": "<UTC>",
  "items": [
    {"id": 1, "root": "ORIGINAL", "claim": "...", "measured": "...",
     "pass": true}
  ],
  "manifest_sha256_verified": "<the 64-hex digest you measured>",
  "manifest_entries_verified": 724,
  "package_unchanged_by_this_verification": true,
  "r8_paths_written_during_attempt_8": 0,
  "write_isolation_instrument_proven_live": true,
  "overall_pass": true,
  "unresolved_findings": [],
  "status": "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL"
}
```

`status` is `VERIFICATION_PASS_PRE_FREEZE_R8_FINAL` only when all 35 items pass
and `unresolved_findings` is empty. Otherwise
`VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL`, with every finding stated.

`write_isolation_instrument_proven_live` is true only if item 33 showed the
clone's copy of that file actually moved, measured by absolute path.

Also write:

- `OUT/ITEM_RESULTS.jsonl` — one line per item, appended as each finishes.
- `OUT/MEASUREMENTS.json` — the raw numbers behind every item: counts,
  digests, before/after pairs, suite totals. One place a reader can check your
  arithmetic without re-running anything.
- `OUT/COMMAND_LOG.jsonl` — every command you ran, one JSON object per line,
  with the command, the root it ran against, its exit status and the UTC time.
- `OUT/VERIFICATION_REPORT.md` — prose: what you actually ran, which root each
  ran against, what you read versus what you inferred, and anything you could
  not measure.
- `OUT/VERIFICATION_MANIFEST.sha256` — a plain `sha256  path` listing of every
  file you wrote into OUT, itself excluded.

`OUT/ITEM_RESULTS.jsonl` is written incrementally THROUGHOUT, one line per item
as that item finishes. The other five files are assembled from it at the end,
after every measurement is complete, and are not touched again afterwards.
Include `ITEM_RESULTS.jsonl` in `VERIFICATION_MANIFEST.sha256`.
