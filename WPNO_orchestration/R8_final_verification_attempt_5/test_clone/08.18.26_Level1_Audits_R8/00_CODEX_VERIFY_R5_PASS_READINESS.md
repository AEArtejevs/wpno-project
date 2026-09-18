# CODEX — INDEPENDENT VERIFICATION OF R5 PASS-READINESS

You are the independent verifier. You did not build this package and you do
not take its build report as evidence. Re-measure everything you assert.

    R5_ROOT = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    R4_ROOT = /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4

## Rules for this verification

1. **Do not write inside `R4_ROOT`.** R4 is frozen historical evidence. If any
   step would write there, stop and report it.
2. **Do not modify `R5_ROOT/references/`.** Reference bytes are immutable.
3. **Do not use the network.** Nothing may be downloaded.
4. **Do not execute a live audit.** No phase is advanced, no verdict recorded,
   no evidence sealed.
5. **A filename is not evidence.** Verify content and hashes.
6. **`NOT VERIFIED` is not `FAIL`.** "Not found" is not "does not exist".
7. Report each item below as one of: `VERIFIED`, `NOT VERIFIED`, `CONFLICT`,
   `NOT TESTABLE`, `UNKNOWN`.

## V-01 · R4 is unchanged

Measure, do not assume:

    find "$R4_ROOT" -type f | wc -l                  # expect 2238
    sha256sum "$R4_ROOT/CONTROL_MANIFEST.sha256"
    sha256sum "$R4_ROOT/BASELINE_MANIFEST.json"
    sha256sum "$R4_ROOT/state/PACKAGE_VERIFIED.json"

Expected:

    CONTROL_MANIFEST.sha256      4b9d44f256975f7211dc37dbd382d8c3737b02abd1211fec3ea1fe78a1f1cb9f
    BASELINE_MANIFEST.json       0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d
    state/PACKAGE_VERIFIED.json  52254365d8bdb53688ab0e0c9752db29a7f856018baf005d76b4cdf99f6b5caf

Then verify the control manifest completely:

    cd "$R4_ROOT" && sha256sum -c CONTROL_MANIFEST.sha256

Expect 1915 entries, 0 failures. Confirm all seven R4 evidence seals are still
intact and still carry the verdicts R4 recorded:
L1-A31 RUN-A ERROR, RUN-B BLOCKED, COMPARISON ERROR;
L1-A34 RUN-A ERROR, RUN-B BLOCKED, COMPARISON UNVERIFIED;
L1-A18 RUN-A BLOCKED, and no RUN-B or COMPARISON evidence directory at all.

## V-02 · R4-to-R5 lineage

`R5_ROOT/lineage/R4_EXECUTION` must be a byte-for-byte copy of R4.

    cd "$R5_ROOT/lineage/R4_EXECUTION" && sha256sum -c ../R4_EXECUTION_MANIFEST.sha256

Expect 2238 entries, 0 failures. Confirm
`lineage/R4_LINEAGE_CLASSIFICATION.json` classifies it as
`HISTORICAL_R4_EXECUTION_SUPERSEDED_BY_R5_REMEDIATION`, and that the historical
evidence still contains its original macOS paths — it must **not** have been
rewritten to look Ubuntu-native.

## V-03 · Migrated evidence equality

`lineage/R4_TO_R5_MIGRATION_INVENTORY.jsonl` has one record per migrated file.
For each record independently recompute both hashes and confirm
`r4_sha256 == r5_sha256` and `equality == "EQUAL"`. Confirm the inventory
covers REF-08, REF-09, REF-11, the references manifest, the mail/ZIP
provenance evidence, the source-hash inventory, the P7S/CMS parse evidence,
the certificate material and the target bindings.

Confirm nothing in the reuse list was re-acquired: no case discovery, no
`/Volumes` access, no re-hashing of case files, no mail re-extraction, no
certificate re-acquisition, no re-import of REF-08/09/11, no re-parse of the
P7S structures.

## V-04 · Fresh R5 active state

`state/REVISION.json` must record revision R5, predecessor R4, platform
UBUNTU, and must state that no R4 approval authorises an R5 phase.

In `state/progress.json`, every phase of every audit must be `NOT_STARTED`,
and in particular all nine phases of L1-A18, L1-A31 and L1-A34. No node may
carry a `verdict`.

`state/approvals.jsonl` must be zero bytes. `state/transitions.jsonl` must
contain exactly one record, whose `route` is `init-revision`.

Confirm the state was produced by a controller route and not hand-edited:
`automation/controller.py` must define `cmd_init_revision`, and re-running it
must refuse rather than reinitialise.

## V-05 · REF-01

Expected outcome at the time of writing: **NOT ACCEPTED, ABSENT.**

Search only under `/home/ubuntu/project` for exactly
`REF-01_SWIFT_IBAN_Registry_Release_102.pdf` and `...txt`. If they are still
absent, confirm `references/_intake_status/R5_REQUIRED_OFFLINE_INPUTS_STATUS.json`
records that honestly and that nothing was invented in their place.

If they are now present: independently compute both SHA-256 values and compare
against the operator-recorded
`e5b0e447e91db94259c5222caa3f9b7f45db4dcbbe61fb99a09cb331a1cb4675` (PDF) and
`a98aae4d7b59544973415491accb1345cb449bfd75a67c8bc704fbe6e161c303` (TXT), then
verify from content — not filename — that they carry the country registry,
IBAN lengths, IBAN structures, the MOD97-10 rule and official country
examples.

## V-06 · REF-02

Expected outcome at the time of writing: **NOT ACCEPTED, ABSENT.**

If `python-stdnum-2.2.zip` is present, verify SHA-256
`12b08a74c96478fa3c86c63721d531b3e07d233a2dd27ebea9c8df38f841622e`, inspect it
statically without executing any archive code, and confirm it contains the
python-stdnum project identity, version 2.2, a licence, `stdnum/iban.py` and
`tests/test_iban.doctest`, with explicit valid and invalid expected outcomes
covering at least six countries.

Confirm no vector was invented and no valid vector was mutated to manufacture
an invalid one.

## V-07 · Bouncy Castle provenance and the independent verifier

Expected outcome: **BUILT AND TESTED, ALL THREE JARS PRESENT AND ACCEPTED.**

Superseded expectation, retained as history: this section originally read
"NOT BUILT, JARS ABSENT", which was true until the operator supplied the
material on 2026-08-26. The JARs were accepted at 13:53 and the verifier was
compiled at 13:55.

`tools/R5_INDEPENDENT_VERIFIER_TOOLCHAIN.json` records the installed JDK 21
toolchain with absolute paths and versions, the three accepted JARs with their
SHA-1 and SHA-256 and their `CHECKSUMS-1.85.csv` status, and the independent
verifier's source and compiled hashes. Re-measure all of them. Confirm the
three JARs and `CHECKSUMS-1.85.csv` are present and that no substitute library
was downloaded or vendored in their place.

## V-08 · L1-A31 harness fix (known cause 1)

Read the sealed R4 evidence at
`lineage/R4_EXECUTION/evidence/L1-A31/RUN-A/` and confirm for yourself that
evidence ids E0007, E0008, E0009, E0010 and E0013 each exited 1 with the
`openssl verify` usage block as stderr, and that E0008 is the positive
synthetic-chain control.

Then confirm in `automation/operation_catalog.py`:

* neither `OPENSSL_VERIFY_CERT_CHAIN` nor `OPENSSL_VERIFY_CMS` emits `--`;
* root, intermediate, leaf and detached content are all explicit;
* `-attime` is required and rejects a non-integer, a bool, zero and a negative;
* `-no-CAfile`, `-no-CApath` and `-no-CAstore` are always emitted, so no
  system or default trust can be consulted;
* `-purpose` is restricted to a fixed allowlist;
* the suppression-flag guard rejects every flag in `SUPPRESSION_FLAGS`;
* building an argv does not alter any input file's hash.

Run the five controls yourself and confirm: positive synthetic chain passes;
invalid chain fails; wrong detached content fails; one-byte content mutation
fails; one-byte certificate mutation fails. Confirm each mutation changed
exactly one byte — a mutation control that mutated nothing has proved nothing.

## V-09 · L1-A34 DER staging fix (known cause 2)

Confirm `references/REF-08-safe-root-ca-2017.der` is unchanged
(`1abddfa573cf1dcd5a75f164bc828e6d4177c448849535912eed3c7825bfc9fc`) and that
no PEM was ever written inside `references/`.

Confirm `automation/trust_material.py`:

* refuses to write anywhere but `work/`;
* refuses to convert inside `references/`;
* refuses to overwrite an existing staged file;
* proves fingerprint, subject, issuer and public-key equality between the DER
  source and the staged PEM, and refuses to return if any differs;
* re-hashes the source after staging and refuses if it changed;
* converts in-process, with no subprocess in the conversion path;
* retains a staging evidence record.

Confirm `operation_catalog._pem_anchor` rejects a DER anchor **by content**,
not by extension, and that its message tells the caller to stage rather than
to replace the reference.

## V-10 · RUN-B isolation fix (known cause 5)

Confirm `policy.RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS` covers
`work/<audit>/RUN-A` as well as `results/` and `evidence/`, for every
replicated audit, and that the set is derived from the audit list rather than
typed out.

Confirm `audit_context.assert_no_other_phase_result_paths` refuses all of:
a direct path; a nested path; relative traversal; a symlink; case variants;
Unicode NFC and NFD variants; a backslash separator; a percent-encoded path.
Construct each spelling yourself rather than trusting the test names.

Confirm it still **permits** a legitimate RUN-B path and the phase label
`"RUN-A"` appearing as a value in `phase_sequencing` — a control that rejects
what it exists to permit is broken, not strict.

Confirm `audit_context.run_b_context` admits only the keys in
`policy.RUN_B_ALLOWED_KEYS`, and that `run_a_terminal` and
`run_a_seal_integrity` must be booleans.

Confirm the operator-intake RUN-A conclusion documents are refused while the
factual intake evidence remains available.

## V-11 · L1-A18 independent implementations

Expected outcome at the time of writing: **NOT IMPLEMENTED.** Both validators
require REF-01 and REF-02. Confirm that no validator was written against
invented data, and that no vector corpus exists in the package.

## V-12 · Complete tests

    cd "$R5_ROOT" && python3 build/run_r5_selftest.py

Require 0 failures, 0 errors, 0 skips, and confirm the run actually executed
tests rather than discovering none. Confirm the controller suite ran inside
`verification/selftest_runtime` and not against the live package.

## V-13 · Pass-readiness

    cd "$R5_ROOT" && python3 build/r5_pass_readiness.py

Confirm each criterion's status independently. At the time of writing the
harness criteria for L1-A31 and L1-A34 are satisfied and the two
missing-input criteria are not, so all three audits are `NOT_READY`.

**Do not report `VERIFICATION_PASS_PRE_FREEZE` while any audit is
`NOT_READY`.** Report the blocking criteria instead.

## V-14 · Static safety

    cd "$R5_ROOT" && python3 build/r5_static_safety_review.py

Confirm zero findings across every changed and added file: no `shell=True`,
no `os.system`, no `eval`, no `exec`, no command strings, bounded subprocess
timeout, bounded output, explicit environment, fixed cwd, no network command,
no system-trust fallback, no write to R4. Confirm the review itself detects
sabotage — introduce each violation into a scratch file and check it is
reported.

## Required outcome

Report `VERIFICATION_PASS_PRE_FREEZE` only if every item above is `VERIFIED`
and no known blocker remains. Otherwise report the exact blockers.

Freezing is a separate, human-gated step and is not part of this verification.
