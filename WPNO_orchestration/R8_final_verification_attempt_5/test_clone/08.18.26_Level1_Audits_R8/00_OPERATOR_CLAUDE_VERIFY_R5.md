# OPERATOR — RUNNING THE FRESH-CLAUDE R5 VERIFICATION

Companion to `00_CLAUDE_VERIFY_R5_PASS_READINESS.md`. Written for the person
at the keyboard.

## Where things stand

Every blocker from the previous session is cleared. The operator-supplied
material arrived, was verified, and everything that was waiting on it is
built and tested.

| Item | State |
|---|---|
| R4 unchanged | 2238 files, byte-identical to the pre-build snapshot |
| R4-to-R5 lineage | 2238/2238 verified |
| REF-01 | accepted from content, bound, 89 countries |
| REF-02 | accepted, 217 applicable vectors, none invented |
| Bouncy Castle JARs | all three match `CHECKSUMS-1.85.csv`, SHA-1 and SHA-256 |
| Independent CMS verifier | built, JDK 21 + Bouncy Castle 1.85 |
| L1-A18 validators | two, Python and Java, 217/217 agreement |
| L1-A31 harness fix | done, tested |
| L1-A34 DER staging fix | done, tested |
| RUN-B isolation fix | done, tested |
| Complete suite | 534 tests, 0 failures, 0 errors, 0 skips |
| Static safety review | 27 files, 0 findings |
| Pass-readiness | L1-A31 READY · L1-A34 READY · L1-A18 READY |

R5 is **not frozen** and **not verified**.

## What the verification is, and what it is not

Codex is unavailable, so verification falls to a second Claude session.

**This is not tool diversity.** The verifier shares a model family, training
and failure modes with the process that built R5. A defect rooted in how this
model reasons will not be caught by asking the same model again. What a fresh
session does give is a clean context: no memory of the build, no involvement
in the design choices, no commitment to defending them.

That is a real but limited form of independence, and the verifier is
instructed to say so before it gives a verdict. If it returns PASS without
that qualification, treat the report as incomplete.

If Codex or another engine becomes available later, running the same prompt
through it would add the diversity this run lacks. It is worth doing before
the freeze if you can.

## Running it

Start a **new** Claude session. It must not have access to the build
conversation — that is the whole point.

    cd /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    # then, in the fresh session:
    #   "Follow 00_CLAUDE_VERIFY_R5_PASS_READINESS.md in this directory."

Give it nothing else. Do not summarise the build for it, do not tell it what
you expect, and do not tell it the previous session's figures. A verifier told
the answer will find the answer.

## What it is allowed to touch

It writes only below `verification_claude_2/`, which is empty apart from its
README. It copies the package into a fixture there and runs the tests on the
copy, so the package itself stays byte-identical. Everything else — R4, this
package's `references/`, `corpora/`, `state/`, `work/`, `build/` — is
read-only to it.

If `verification_claude_2/` still contains only its README afterwards, the
verification did not run.

## Checking it afterwards

Two things are worth confirming yourself, because they are the ones a report
can most easily assert without doing:

    # the package was not modified by the verification
    cd /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5
    sha256sum -c BUILD_MANIFEST.sha256 | grep -c ': OK$'

    # R4 was not modified either
    cd /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R4
    find . -type f | wc -l
    sha256sum CONTROL_MANIFEST.sha256

Expect 2238 files and
`4b9d44f256975f7211dc37dbd382d8c3737b02abd1211fec3ea1fe78a1f1cb9f`.

Read the verdict for what it measured, not for what it concluded. A `PASS`
that does not name figures is not a `PASS`.

## After it passes

Only then is a freeze plan created, and the freeze itself still waits for your
token. Nothing freezes automatically, and nothing in this session froze
anything.

## What must not happen

- Nothing is written into `08.18.26_Level1_Audits_R4`.
- Nothing in `references/` or `corpora/` is modified; both are mode 0444.
- Nothing is downloaded.
- No live L1-A31, L1-A34 or L1-A18 audit is executed as part of verification.
- A frozen Ubuntu R5 is not run unchanged on the Mac. See
  `transfer/R5_UBUNTU_TO_MAC_PORTING_PLAN.md` — the openssl on macOS is
  LibreSSL, which is the program whose missing `--` support produced the
  original L1-A31 failure, and which does not support the flags R5 uses to
  refuse default trust.
