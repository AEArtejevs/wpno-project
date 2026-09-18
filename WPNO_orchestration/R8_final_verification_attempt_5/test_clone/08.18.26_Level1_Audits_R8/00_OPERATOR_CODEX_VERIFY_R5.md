# OPERATOR — RUNNING THE INDEPENDENT R5 VERIFICATION

This is the human-facing companion to
`00_CODEX_VERIFY_R5_PASS_READINESS.md`. It is written for the person at the
keyboard, not for the verifier.

## Where things stand

The R5 build is complete for everything that could be built offline on this
machine. Four defects are fixed and each has regression tests behind it. Three
inputs are missing and nothing can substitute for them.

| Item | State |
|---|---|
| R4 unchanged | verified, 2238 files, all three checkpoint hashes match |
| R4-to-R5 lineage | byte-for-byte, 2238 files |
| Migrated evidence | 236 records, all equal |
| R5 active state | fresh, all 43 phases NOT_STARTED |
| L1-A31 harness fix | done, tested |
| L1-A34 DER staging fix | done, tested |
| RUN-B isolation fix | done, tested |
| Complete test cycle | 456 tests, 0 failures, 0 errors, 0 skips |
| Static safety review | 0 findings |
| REF-01 | **absent** |
| REF-02 | **absent** |
| Bouncy Castle JARs | **absent** |
| Independent CMS verifier | **not built** — no JARs |
| L1-A18 validators | **not implemented** — no REF-01/REF-02 |

## Why the verification has not been run

Two independent reasons, either of which is sufficient.

**Codex is not authenticated on this machine.** `codex-cli 0.149.1` is
installed at `/home/ubuntu/.npm-global/bin/codex`, but `~/.codex/auth.json`
does not exist. Note that a version string is not evidence that a session
works — CLAUDE.md § 3 records the day `claude doctor` reported no issues while
nothing could run because the login had expired. Authentication has to be
demonstrated by a task that completes, not by a version number.

**Three blockers remain**, so the verification could not return
`VERIFICATION_PASS_PRE_FREEZE` even if it ran. Running it now would spend a
verification pass on a foregone conclusion.

## What is needed

Place these seven files anywhere under `/home/ubuntu/project`. Do not rename
them and do not modify their bytes.

    REF-01_SWIFT_IBAN_Registry_Release_102.pdf
    REF-01_SWIFT_IBAN_Registry_Release_102.txt
    python-stdnum-2.2.zip
    bcprov-jdk18on-1.85.2.jar
    bcpkix-jdk18on-1.85.jar
    bcutil-jdk18on-1.85.jar
    CHECKSUMS-1.85.csv

Three of them have operator-recorded hashes that will be checked
independently on arrival:

    REF-01 PDF   e5b0e447e91db94259c5222caa3f9b7f45db4dcbbe61fb99a09cb331a1cb4675
    REF-01 TXT   a98aae4d7b59544973415491accb1345cb449bfd75a67c8bc704fbe6e161c303
    stdnum ZIP   12b08a74c96478fa3c86c63721d531b3e07d233a2dd27ebea9c8df38f841622e

`CHECKSUMS-1.85.csv` may be Windows-1252 or ISO-8859-1. Its exact bytes will
be preserved and it will be decoded read-only. A genuine checksum mismatch on
a matching row is a stop condition. A JAR that is simply not listed in the CSV
is a provenance limitation, not automatically a failure.

## Order of work once the files are present

1. Accept REF-01 from content, not filename, and bind it into the references
   manifest.
2. Accept REF-02 by static inspection and build the normalized vector corpus.
   No vector may be invented and no valid vector may be mutated into an
   invalid one.
3. Validate the three JARs against the CSV, copy them into the R5 tool area
   and build the bounded Bouncy Castle CMS verifier. It must not call OpenSSL
   and must not use the network.
4. Implement the two independent L1-A18 validators.
5. Re-run `build/run_r5_selftest.py` and `build/r5_pass_readiness.py`.
6. Authenticate Codex, then run the verification.

## Authenticating Codex

Run this yourself in the terminal; it is interactive and an agent must not
enter credentials on your behalf:

    codex login

Then confirm it works by giving it a task that completes and produces output.
An exit code alone is not evidence.

## Running the verification

    cd /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    codex exec --cd . "$(cat 00_CODEX_VERIFY_R5_PASS_READINESS.md)" \
      2>&1 | tee build/INDEPENDENT_CODEX_VERIFICATION_OUTPUT.txt

Run it exactly once. Keep the transcript — it is the evidence that the
verification happened and what it said.

## After the verification passes

Only then is a freeze plan created, and the freeze itself still waits for your
token. Nothing freezes automatically.

## What must not happen

- Nothing is written into `08.18.26_Level1_Audits_R4`.
- Nothing in `references/` is modified, converted in place or renamed.
- Nothing is downloaded.
- No live audit is executed as part of verification.
- A frozen Ubuntu R5 is not run unchanged on the Mac. See
  `transfer/R5_UBUNTU_TO_MAC_PORTING_PLAN.md`.
