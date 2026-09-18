# Substantive findings preserved from the R7 repair attempt

## A · Frozen execution-engine defect

The frozen controller never performed IN_PROCESS operations.

- Controller: automation/controller.py appended the note 'in-process; performed by the worker' and executed `continue`. No worker exists; the only non-test occurrence of the word in automation/*.py was that note.
- Rehearsal: build/rehearse_candidate_plans.py recorded executed=false together with ok=true, so an unexecuted step counted as a passing step.
- Affected steps: **165 of 307**
- Fully hollow phases: **12**
- Partially skipped phases: **26**
- Observed: L1-A31 COMPARISON reported executed=3 and entered state EXECUTED with zero evidence files.
- Why invisible: The pre-freeze rehearsal shared the blind spot, so the 43/43 PASS_READY result never exercised these steps; six Codex verification attempts did not detect it.

Fully hollow phases: `L1-A03/RUN-A`, `L1-A10/RUN-A`, `L1-A17/RUN-A`, `L1-A18/COMPARISON`, `L1-A19/COMPARISON`, `L1-A20/RUN-A`, `L1-A21/RUN-A`, `L1-A23/RUN-A`, `L1-A24/RUN-A`, `L1-A31/COMPARISON`, `L1-A33/RUN-A`, `L1-A34/COMPARISON`

## B · Candidate repair (preserved for R8, reverted out of R7)

- Status: **BUILT, PROVEN, THEN REVERTED OUT OF R7. Preserved for R8.**
- Shared implementation: `automation/in_process_ops.py`, 16 operations
- Focused tests passed: **26** (`automation/package_tests/test_r7_in_process_ops.py`)
- Sabotage proof: test_the_guard_rejects_the_original_defective_branch reconstructs the defective branch verbatim and requires the guard to reject it
- In-process steps executed: **187** (before repair: 0)

## C · L1-A21 plan defect — fix in R8 only

`negative_control_export_is_not_another_project` applies `PARSE_JSON_READONLY` to `references/REF-13_all_containers.txt`.
Measured file type: Docker tabular ASCII text (docker ps output), 5449 bytes; not JSON.
Consequence: The JSON parser refuses before the expect_absent assertion is evaluated. The negative control never tested anything.

Authorised correction: R8 ONLY: use the plan-appropriate text operation, such as COUNT_TEXT_MATCHES, to measure the intended pattern and assert zero matches.

## D · L1-A33 plan defect — fix in R8 only

`parse_container_xml_safely` applies `XML_PARSE_SANDBOX` (expected exit 0) to `references/REF-11-563203462.xml`.
Measured file type: MIME multipart entity wrapping XML parts; 'MIME-Version: 1.0' at byte zero, Content-Type Multipart/Related.
Consequence: The XML parser correctly refuses at line 1 column 0. The step is a load-bearing MEASUREMENT, not a control.
Root cause: The operation was chosen from the .xml extension. CLAUDE.md section 4: a filename is not evidence of content.

Authorised correction: R8 ONLY: safely extract the intended XML MIME part into an R8 mutable work location, then parse the extracted XML, leaving the accepted reference unchanged.

## E · Control-expectation weakness — R8 review required

**55 of 307** steps carry a control role with no declared `expected_exit_code`: MUTATION 20, NEGATIVE 14, ORACLE 12, POSITIVE 9.

NOT ADJUDICATED. These are not assumed all defective and not assumed all benign.

With no declared expectation the harness scores a step ok only when it exits 0, which is the wrong polarity for a control built to fail.

R8 requirement: R8 must require an explicit machine-checkable expected outcome for every control step, using an exit code, expected status, expected count, expected hash or another operation-appropriate assertion.
