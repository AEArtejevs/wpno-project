# R8 lineage-binding repair — record

    MODE:   R8_FINAL_LINEAGE_FREEZE_REPAIR_NO_R9
    R9:     NOT CREATED
    STATUS: VERIFICATION_PASS_PRE_FREEZE_R8_FINAL, plan and token ready

## The defect

`cmd_freeze_level1` step 9 derived the artefact it required by string surgery:

    lineage_key = "lineage/%s_MANIFEST.sha256" % (
        PREDECESSOR_BASELINE_REL.split(os.sep)[1],)

Element [1] is a directory name only when the constant points INSIDE a lineage
directory. R7 carried a physical copy of R6, so it did. R8 inherits by digest —
`R7_BYTES_NOT_DUPLICATED`, 555 MiB not copied — so the constant names a FILE,
element [1] is a FILENAME, and the gate demanded

    lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256

`_MANIFEST.sha256` glued onto a name already ending in `.json`. No such file
exists, none can, and no plan could bind it: the key came from a constant and
never looked at the plan. The authorised freeze refused there, above its write
boundary, publishing nothing and consuming nothing.

## Why the suites were green while the package could not be frozen

`test_freeze_order_regression` runs the real freeze route end to end — the
right shape of test — but built its fixture by COPYING that same expression. It
created a file with the impossible name, bound it, and the gate found exactly
what it had asked for. The test and the code shared one wrong assumption, so
the test could not see it. A test that re-derives the implementation's answer
is asking the implementation whether it agrees with itself.

## The repair

All lineage-path string surgery is gone. `automation/freeze.py` declares the
artefacts as DATA:

    PACKAGE_LINEAGE_MODEL           kind COMPACT_DIRECT_FILE, predecessor R7
      lineage/R7_BASELINE_MANIFEST.json   role PREDECESSOR_BASELINE
      lineage/R8_LINEAGE.sha256           role LINEAGE_ATTESTATION

each with a stated reason, and both architectures representable —
`LEGACY_DIRECTORY_MANIFEST` for R7's shape, `COMPACT_DIRECT_FILE` for R8's.
Three consumers read one function, `required_predecessor_lineage_artifacts()`:
the controller gate, the freeze-plan builder and the freeze-plan validator. The
declared baseline is cross-checked against the constant the freeze route itself
reads, so the rule and the route cannot come to require different files.

`assert_lineage_bound` checks six things per artefact: bound by the plan;
confined below the package root; no component a symlink; present as a regular
file; bytes hashing to the digest the plan bound; and the baseline entry being
the path the route reads.

## The regression that was missing

`automation/package_tests/test_r8_freeze_lineage.py`, 44 tests. The load-bearing
one invokes the ACTUAL command that refused the real freeze —
`python3 -m automation.controller freeze-level1 --token … --plan …` — in a
disposable R8-shaped package, and takes it PAST the write boundary. It proves
the gate is reached and passed, MODE becomes FROZEN, the control manifest
verifies from disk, its MODE entry matches FROZEN, both baselines are nonempty,
the verified record names the lineage artefacts required, the token is consumed
exactly once, replay is refused, no phase is started, and the original package
is not written.

It also proves the old expression is refused, that no executable statement in
the package computes it, and that the two places where it still appears are
inert: the named constant that exists to be proved impossible, and
`lineage/R7_POST_FREEZE_INCIDENT/dirty_repair_files/` — the R7-era files as
they stood during the incident. That exclusion is not asserted but measured:
every carrier is listed in `INCIDENT_MANIFEST.sha256`, that manifest verifies,
and nothing under `automation/` or `build/` loads code from `lineage/`.

## Plans and rehearsals were not regenerated, and that was checked

Neither the 43 candidate plans nor the rehearsal report references or binds
`automation/controller.py` or `automation/freeze.py`, and
`build/rehearse_candidate_plans.py` never enters the freeze branch. A first
pass reported a dependency: it matched the bare substring
`automation/freeze.py` and hit absolute paths into R4's tree from an audit
step's scan results. Anchored to R8-relative or R8-absolute references, the
answer is NO_DEPENDENCY. Rerunning 43 substantive rehearsals to reassure about
a branch they never execute would be repetition, not evidence.

## Measured

    unit / controller suite     503 / 0 failures / 0 errors / 0 skips
    package suite               405 / 0 failures / 0 errors / 0 skips
                                (361 before; the rise is the lineage module)
    static safety               0 findings, 53 files including the excluded
                                freeze-plan and verifier executables
    build manifest              728 entries, f7e181a2…95bb, 728/728 valid,
                                exact reconciliation with physical scope
    plans                       43/43            rehearsals 43/43 PASS_READY
    in-process                  169 = 169        note-only 0
    without evidence            0                hollow phases 0
    controls                    122/122          unenforced 0
    live state                  43/43 NOT_STARTED, 0 approvals/results/evidence
    migration packet            valid, bound, unconsumed
    R4 / R5 / R6 / R7           0 / ['MODE'] only / 0 / 15804 with 0 mismatching
    independent verification    38/38 items, 0 unresolved findings
    write isolation             0 paths written across every measured category

## Three literals that had outlived their subjects

Found and replaced during this repair, each the same failure mode as the one
being fixed:

- the freeze gate's derived lineage key — the defect itself;
- `fixed_target_check.py`'s hardcoded manifest digest and 724-entry count,
  which reported the package changed when the checker had gone stale;
- the freeze-plan validator's literal `724`, which failed a manifest that was
  entirely correct.

The first is now data, the second an argument, the third a measurement.

## Still true, and deliberately so

The attempt-2 freeze plan is preserved unchanged as
SUPERSEDED_UNCONSUMED_AFTER_CONTROLLER_REFUSAL, together with attempt 1. No
R4–R7 byte was modified. R9 does not exist. No live audit phase has run. The
migration packet is prepared and unconsumed. The token is not recorded on disk.
