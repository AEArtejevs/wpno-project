# Attempt-4 findings V15 and V19, adjudicated

Attempt 4 returned `VERIFICATION_FAIL_PRE_FREEZE_R7_FINAL` with twenty of
twenty-two items passing and two unresolved findings. Its five outputs were
written once, at 07:44:54Z, and were not revised; the subprocess exited `rc=0`
at 07:51:11Z. They were read only after that.

This adjudication is not a verification. A fresh attempt must re-measure both
items with the corrected predicates rather than adopt anything written here.

## FPF4-V15 — L1-A19 independence

**Disposition: VERIFIER_PATH_CLASSIFICATION_FALSE_POSITIVE.**

The allegation was a cross-phase read, and the path named was

    <R7>/work/L1-A19/RUN-B

which is the phase's own working directory. The predicate was

    wrongb = [s for s in bs
              if '/L1-A19/' in s and '/RUN-B/' not in s
              and not s.endswith('R7_REF04_IDNR_VECTORS.jsonl')]

The string ends at `RUN-B`, so it contains no `/RUN-B/`. A bare directory path
cannot satisfy a test written for a path with something after the phase name.
The anchor is wrong, and a wrong anchor gives a confident answer about the
wrong thing — the same shape as a search without a word boundary.

All six required properties were measured independently and hold.

| # | requirement | how it was measured |
|---|---|---|
| 1 | no import or call into RUN-A | AST import lists of both RUN-B modules; no `a19_run_a` import, attribute or call |
| 2 | no read of RUN-A results, findings, reports, verdicts or evidence | 534 absolute step paths across all 43 plans classified; **0 cross-phase reads** |
| 3 | inputs are only the approved packet and sequencing facts | the vector corpus, its own work directory, its own output |
| 4 | mathematically distinct forms | RUN-A produces a check digit and compares it; the Java RUN-B produces none and tests a fold invariant |
| 5 | two sabotage controls, distinct and effective | modulus 11→10 changes 11 answers; repetition-always-true changes 8; the two sets are disjoint |
| 6 | comparison receives both sealed outputs after both runs | COMPARISON reads the two SEAL files and computes nothing substantive |

No R7 byte was changed for this finding. The corrected predicate is
`cross_phase_predicate.py` beside this record: it compares path components,
is phase-aware, names no audit, and passes a twelve-case self-check covering
own-phase acceptance, RUN-A work, result and evidence rejection, rejection of
a COMPARISON result before comparison, and the same behaviour for a second
audit.

## FPF4-V19 — executable test and static-safety coverage

**Disposition: SUBSTANTIVE_COVERAGE_EXISTS_BUT_MACHINE_READABLE_MAP_MISSING.**

The predicate required the literals 503 and 312 to appear under the key names
`controller_tests` and `package_tests`. The closure record stores them as
`unit_suite.ran` and `package_suite.ran`, so both lookups returned empty lists
and the conjunction failed. Every substantive sub-measurement it recorded had
already passed: no rehash failures, no malformed rows, static safety clean
with zero findings.

Adjudicated per file rather than in aggregate. All 54 reviewed entries were
enumerated with their role, current digest, reviewed digest, linked test
evidence, rehearsal execution evidence and static-safety evidence:

- 54 of 54 current digests equal the digest the static-safety record reviewed;
- 0 uncovered executables;
- 0 accepted reference inputs wrongly counted as package executables;
- 9 shared control-plane files, covered by the full controller suite that was
  rerun for exactly that reason;
- audit entry points with no importing unit test are covered by the rehearsal
  executing them through the frozen launcher, with argv, exit code and result
  recorded — stated as rehearsal execution, not described as a unit test.

The mapping did not exist in machine-readable form, so one non-executable
record was created: `build/FINAL_EXECUTABLE_TEST_SAFETY_COVERAGE.json`,
deterministically derived from `R7_CHANGED_FILES.sha256`,
`R7_STATIC_SAFETY_REPORT.json` and the closure record. No test was rerun; the
suite sizes were established by collection, not execution.

**A discrepancy found while doing this.** The closure record reports the
package suite as 281. The suite collects 312. The figure is a stale literal in
the closure record's generator, not updated when the last two test modules
were added; it understates the suite and does not describe a different run.
Correcting it would mean editing an executable, which this invocation forbids,
so it is recorded in the coverage record rather than changed.

## A separate observation, not one of attempt 4's findings

The rehearsal did not execute L1-A19's two sabotage steps. It recorded them
`LIVE_PHASE_MATERIAL_NOT_STAGED`, with `absent_inputs` naming
`sabotage_modulus.json` and `sabotage_repetition.json` — which are those
steps' own `--out` targets, not inputs. The cause is in
`build/rehearse_candidate_plans.py`, which treats every absolute string in a
step's args as an input. Two of the 96 steps recorded under that reason were
skipped only for this; the other 94 were skipped for genuine reasons.

The sabotage controls themselves are correct and demonstrably effective, and
the approved live phase executes them under the plan's own stated expectation.
Repairing the harness would require an executable change, which this
invocation forbids, so it is reported for the operator to decide rather than
made.

## What changed in R7

Executable bytes: none. Accepted reference bytes: none. Human decisions: none.
Candidate plans: none. `lineage/PREDECESSOR_INTEGRITY.json`: untouched.

Added: the coverage record and its digest file. Edited: the closure record,
by a pointer to the coverage record and this adjudication. The build manifest
was preserved as superseded evidence and regenerated once.
