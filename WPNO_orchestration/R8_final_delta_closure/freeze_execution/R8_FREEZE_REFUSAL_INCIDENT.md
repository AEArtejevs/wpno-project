# R8 freeze refused — genuine internal package defect

    GATE:            HUMAN_GATE: GENUINE_R8_PACKAGE_DEFECT_FOUND
    CLASSIFICATION:  R8_INTERNAL_PREFREEZE_DEFECT
    NOT:             VERIFIER_HARNESS_DEFECT
    R8 MODIFIED:     NO
    R9 CREATED:      NO
    TOKEN CONSUMED:  NO

## What happened

The human's token was validated character-exactly — 271 bytes, byte-identical
to the expected token, SHA-256 `176f6fbb…733560` by both methods,
`parse_freeze_token` and `assert_token_binds_plan` both accepting it.

The controller-owned route was then invoked exactly once:

    python3 -m automation.controller freeze-level1 --token <token> \
      --plan build/freeze_plan_attempt_2/FREEZE_PLAN_R8_ATTEMPT_2.json

It refused at its own step 9, above its stated write boundary:

    ControllerError
    FREEZE_LINEAGE_UNBOUND: the plan does not bind
    lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256

## The defect

`automation/controller.py`, in `cmd_freeze_level1`:

    lineage_key = "lineage/%s_MANIFEST.sha256" % (
        freeze.PREDECESSOR_BASELINE_REL.split(os.sep)[1],)

`PREDECESSOR_BASELINE_REL` in `automation/freeze.py` is

    lineage/R7_BASELINE_MANIFEST.json

so `split(os.sep)[1]` is `R7_BASELINE_MANIFEST.json`, and the required key is

    lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256

`_MANIFEST.sha256` appended to a name that already ends in `.json`. No such
file exists, none can, and **no freeze plan can satisfy the check** — the key
is derived from a module constant and does not depend on the plan at all. The
freeze route as shipped cannot freeze R8.

## Why the derivation is wrong here and was right in R7

The expression assumes `PREDECESSOR_BASELINE_REL` names a path *inside a
lineage directory*, so that element [1] is that directory's name. That held in
R7, which carried a full physical copy of R6:

    R7:  lineage/R6_EXECUTION/...        -> split[1] = "R6_EXECUTION"
         -> lineage/R6_EXECUTION_MANIFEST.sha256   (exists; R7's own plan
                                                    binds exactly this)

R8 deliberately does not duplicate its predecessor — `R8_LINEAGE.json` records
`R7_BYTES_NOT_DUPLICATED`, because R7's inherited lineage is 555 MiB and a
digest carries the same guarantee. So R8's baseline is a single FILE directly
under `lineage/`, and element [1] is a filename rather than a directory name.

The comment above the line says the key is derived "so the artefact this rule
requires and the artefact the freeze actually reads cannot disagree". The
derivation was made dynamic; the *shape assumption* underneath it stayed
static. This is CLAUDE.md §10's recurring pattern — a rule written for one
shape carried unchanged to another — and it is the same failure mode as the
R7-era stale literal the comment describes fixing.

## Why the verification did not catch it

Item 28 measured the freeze mechanism's *capability*: `PACKAGE_REVISION`,
`PACKAGE_PLATFORM`, the predecessor baseline digest against the lineage
record, `build_baseline_from_predecessor` returning without raising, and
`token_for`/`parse_freeze_token` round-tripping on dummy digests. Every one of
those passed and every one is still true. None of them enters
`cmd_freeze_level1`, where the defect lives.

Nor do the suites. `grep` over `automation/tests/` and
`automation/package_tests/` finds no mention of `FREEZE_LINEAGE_UNBOUND` or
`lineage_key`: neither the 503-test controller suite nor the 361-test package
suite exercises this branch. Those results stand; they simply do not reach
here.

A green suite proves something about what it looks at. This branch was looked
at by nothing until the freeze itself ran.

## Nothing was published

Measured, not asserted. Full inventory of all 1449 R8 paths before and after
the refusal:

    paths added                0
    paths removed              0
    contents changed           0
    modes changed              0
    uid / gid changed          0
    symlink targets changed    0
    mtimes changed             1   -- `state/`, the directory, because
                                     ControllerLock created and removed its
                                     lock file there. No file under it changed.

    MODE                       GENERATED_UNVERIFIED   (unchanged)
    CONTROL_MANIFEST.sha256    absent
    BASELINE_MANIFEST.json     absent
    PACKAGE_VERIFIED.json      absent
    state/freeze_attempts.jsonl absent  -> the token was NOT consumed
    state/migrations.jsonl     absent  -> the packet was NOT applied
    active phases              43/43 NOT_STARTED
    approvals / results / evidence  0 / 0 / 0
    build manifest             724/724 valid, 6dfd1af6…5b945a
    R9                         absent

The freeze plan re-validates unchanged: 236/236 bound artefacts, 42/42 checks.

The route's own design is what made this safe: "no artefact is created until
the token, the plan, every bound digest, the Ubuntu baseline, the replay state
and the R5 lineage have all been checked. Any failure before the write stage
leaves MODE at GENERATED_UNVERIFIED, writes nothing, and does not consume the
token." That is exactly what happened.

## The repair is small, but it is a specification decision

The rule's intent is that a freeze plan must bind the predecessor's lineage
evidence. What that artefact IS differs between a predecessor carried by copy
and one inherited by digest, and choosing is an audit-standard judgement, not
a code edit. Two candidate readings:

  (a) Bind the predecessor baseline itself — `freeze.PREDECESSOR_BASELINE_REL`,
      i.e. `lineage/R7_BASELINE_MANIFEST.json`. It is the artefact the freeze
      actually reads, which is what the comment says the rule is for. The
      current plan already binds it.

  (b) Bind the revision's own lineage integrity record —
      `lineage/R8_LINEAGE.sha256` — on the view that the rule guards the
      lineage *claim* rather than the baseline input. The current plan already
      binds this too.

Either is satisfied by freeze plan attempt 2 as it stands; the choice changes
what the rule means, not whether this plan passes. My recommendation is (a)
with (b) added, and the derivation replaced by a direct reference to the
constant rather than string surgery on it — string surgery on a path is what
failed twice now.

Whichever is chosen, the repair must come with the regression test this branch
has never had: a test that runs `cmd_freeze_level1` far enough to evaluate the
lineage rule against R8's actual lineage shape.

## What this changes about the verification

Nothing already measured becomes false. All 35 items stand on their evidence;
the suites, static safety, the manifest, the plans, the rehearsals, the
control expectations and the write isolation are unaffected. What this shows
is a gap in item 28's *scope* — it verified that the freeze module could
produce a plan and a token, not that the freeze route would accept one.

If the defect is repaired, `automation/controller.py` changes. That is a
manifest-covered file, so the build manifest must be regenerated, the affected
suites re-run, and the verification and freeze plan rebuilt against the new
manifest digest. The current token dies with the current plan.
