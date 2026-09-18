#!/usr/bin/python3
import datetime, json, os

out=os.path.dirname(__file__)
p=os.path.join(out,'VERIFICATION_RESULT.json')
x=json.load(open(p,encoding='utf-8'))
updates={
 5:(True,'R8_LINEAGE.json records continuous_post_freeze_immutability=false and post_freeze_modification_incident=RECORDED; DIRTY_REPAIR_FILES.sha256 verified 4/4 and INCIDENT_MANIFEST.sha256 verified 15/15 with zero malformed, duplicate, missing, or mismatching entries.'),
 9:(True,'The phrase occurs in automation/migration.py only as a rejection check for imported predecessor evidence, and in package tests/fixtures; no live execution branch writes the note in place of performing an operation.'),
 15:(True,'Re-derived 122 control-role steps from 43 plans. Cross-joined by (audit, phase, step) with build/control_expectations.py and existing declared plan expectations: 122/122 carry a machine-checkable expectation and 0 are unenforced; CONTROL_EXPECTATION_COVERAGE.json independently records the same totals.'),
 16:(True,'migratable_attempts contains exactly L1-A31 RUN-A and RUN-B; excluded_attempts contains exactly L1-A31 COMPARISON with EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT; applied_before_freeze=false.'),
 25:(True,'state/progress.json contains 35 distinct audit IDs and 43 phase records; all 43 state fields equal NOT_STARTED.'),
 30:(True,'state/transitions.jsonl contains one record only; route=init-revision, audit_id=PACKAGE, run_phase=REVISION, NOT_STARTED→NOT_STARTED.')
}
for row in x['items']:
 if row['id'] in updates: row['pass'],row['measured']=updates[row['id']]
# Preserve the two disk failures and explicitly record verification-side mutation.
x['unresolved_findings']=[
 'Item 6: automation.package_tests.generation_root resolves R8, R7, R6 and R5, but fails for R4 because state/REVISION.json is absent at R7/lineage/R6_EXECUTION/lineage/R5_EXECUTION/lineage/R4_EXECUTION. The claimed R4→R5→R6→R7→R8 resolver chain is therefore not fully resolvable by the package resolver.',
 'Item 27: build/R8_BUILD_MANIFEST.sha256 currently has three digest mismatches: build/build_r8_freeze_plan.py, build/R7_CHANGED_FILES.sha256, and build/R8_STATIC_SAFETY_REPORT.json. There are 723 well-formed unique entries and no scope omissions/extras, but matching is not zero.',
 'Verification-side write incident: the explicitly requested package suite left build/build_r8_freeze_plan.py changed, and the explicitly requested build/r8_static_safety_review.py rewrote build/R7_CHANGED_FILES.sha256 and build/R8_STATIC_SAFETY_REPORT.json. These writes occurred outside the requested verifier-output directory. They were not reverted because no trustworthy original bytes were available and modification elsewhere was forbidden.'
]
x['overall_pass']=False
x['status']='VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'
x['verified_utc']=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
open(p,'w',encoding='utf-8').write(json.dumps(x,indent=2)+'\n')
notes='''# Independent pre-freeze verification notes

All direct measurements used `/usr/bin/python3` with `PYTHONDONTWRITEBYTECODE=1`. No network, git, migration, freeze publication, or live audit phase was invoked.

Actually run:

- Parsed and SHA-256 verified the R4/R5/R6/R7 control manifests and both R7 incident manifests.
- Inspected R8 lineage, inode identities, source call sites, all 43 plans, the rehearsal report, migration plan, R7 L1-A31 state/evidence, R8 state/results/evidence, and the freeze constants.
- Imported `operation_catalog.IN_PROCESS`, `in_process_ops.HANDLERS`, and `in_process_executor.ARGUMENT_SCHEMA`, compared the sets, and ran `in_process_executor.self_check()`.
- Ran the controller unittest suite in `verification/selftest_runtime`: 503 tests, 0 failures, 0 errors, 0 skips.
- Ran the package unittest suite at R8 root: 361 tests, 0 failures, 0 errors, 0 skips.
- Ran `build/r8_static_safety_review.py`: exit 0, 0 findings, clean true.
- Called `freeze.build_baseline_from_predecessor(R8)` only; it returned 15,803 baseline entries. No freeze/publication function was called.
- Re-enumerated the builder's own `in_scope` and verified manifest syntax, uniqueness, presence, hashes, and bidirectional coverage.

Important execution incident: despite the output-confinement rule, the prescribed package suite left `build/build_r8_freeze_plan.py` changed, and the prescribed static-safety script rewrote `build/R7_CHANGED_FILES.sha256` and `build/R8_STATIC_SAFETY_REPORT.json`. The three files now mismatch `build/R8_BUILD_MANIFEST.sha256`. I did not revert them because the original bytes were not independently available and further modification outside this directory was forbidden.

Final status: **VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL**. 28 of 30 numbered claims pass; items 6 and 27 fail. Full measurements and all findings are in `VERIFICATION_RESULT.json`.
'''
open(os.path.join(out,'VERIFICATION_NOTES.md'),'w',encoding='utf-8').write(notes)
