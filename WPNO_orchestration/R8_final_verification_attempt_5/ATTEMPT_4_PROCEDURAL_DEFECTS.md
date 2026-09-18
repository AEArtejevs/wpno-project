# Attempt-4 procedural defect record

Recorded outside R8, under
`/home/ubuntu/project/WPNO_orchestration/R8_final_verification_attempt_5/`.
R8 is not edited to carry this record.

Classification of attempt 4:

    SUBSTANTIVE_CHECKS_PASS_BUT_PROCEDURAL_WRITE_ISOLATION_NOT_PROVEN

Attempt-4 evidence is preserved, not deleted. It remains at
`08.18.26_Level1_Audits_R8/verification_codex_final_pre_freeze_attempt_4/`
and at
`WPNO_orchestration/R8_in_process_execution_repair/attempt_4/`.

The attempt-4 token is NOT consumed and NOT recorded.

---

## D1 — the reported token SHA-256 was incorrect

Stated by the human decision and accepted. The value reported at the end of
attempt 4 did not equal the digest of the token bytes attempt 4 emitted.

## D2 — the correct digest of the exact visible attempt-4 token

    47cf40be29089257bd08dfef738fdb966009c46c7cd21add5c5400167d9c0d44

hashed over the exact token bytes with NO trailing newline.

Independently reconstructed in attempt 5 rather than copied. The attempt-4
token is a pure function of three digests measured from disk:

    PACKAGE-SHA256      = 6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a
                          (build/R8_BUILD_MANIFEST.sha256)
    VERIFICATION-SHA256 = 9bdb04d6326c3d6974c5c709a79100e31d493f6e953358d85e66c8412a8171eb
                          (verification_codex_final_pre_freeze_attempt_4/VERIFICATION_RESULT.json)
    FREEZE-PLAN-SHA256  = f71be8dde0464dca92a0776f6a5cea6b7e39818d34f8bb357109439647560a09
                          (build/freeze_plan_attempt_1/FREEZE_PLAN_R8_ATTEMPT_1.json)

assembled by `automation.freeze.token_for` with
`policy.FREEZE_PREFIX = "FREEZE-LEVEL1"` and
`policy.APPROVAL_SUFFIX = "RUN-ONCE"`. Hashing that assembled string without
a trailing newline yields exactly 47cf40be…0d44. The stated digest is
therefore CONFIRMED by measurement, not adopted on assertion.

## D3 — a manifest-covered file was rewritten during the test suite

    verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt

The attempt-4 prompt left this one file writable on purpose so the controller
suite could run, and relied on a post-run byte comparison. The final bytes did
match, so the manifest still verified 724/724. A write nevertheless occurred
inside R8 during verification.

Final bytes matching is not the same claim as no write occurred. Under §6 of
the project rules a measurement that changes what it measures is not a
measurement, and R8 was changed — reopened and rewritten — during the run.

## D4 — attempt 4 therefore did not meet the human no-project-write condition

Consequence of D3, plus the mode changes attempt 4 applied to the package:
the attempt-4 prompt records that 723 of 724 manifest-covered files had their
write bits removed for the duration and restored afterwards. Mode is package
metadata; removing and restoring it is a write to the package.

Attempt 4's substantive result (31/31 items, `overall_pass` true,
`unresolved_findings` empty) is not disputed here. What was not proven is the
procedural condition. Attempt 4 is superseded on procedure alone.

## D5 — verifier and verification result were not clearly distinguished

`VERIFICATION_RESULT.json` is the OUTPUT of the verification. It was not
separated in the attempt-4 record from the two things that are the verifier:
the instructions (`VERIFY_PROMPT.md`) and the runner that executed them.
Attempt 5 hashes instructions, runner, helpers and result as distinct roles in
a machine-readable tool inventory, and never labels the result as the verifier.

## D6 — the separate plan runner must be explicitly bound if used

Attempt 4 used
`WPNO_orchestration/R8_in_process_execution_repair/attempt_4/run_freeze_plan_builder.py`
to override the builder's stale `VERIFICATION_DIR = "…attempt_3"` constant at
run time. That runner is a tool that materially determined the plan's content:
it decided which verification directory the plan bound. It sits outside R8,
outside the build manifest, and was not bound into the plan.

A tool that changes what a plan says, and is not bound by the plan, is an
unbound input to the freeze.

## D7 — additional finding raised by attempt 5, not by the human

The builder `build/freeze_plan_attempt_1/build_r8_freeze_plan.py` carries a
stale `attempt_purpose` string that it writes verbatim into the plan:

    "First and only freeze attempt for R7 … R7 is the final revision;
     there is no R8."

It appears in `FREEZE_PLAN_R8_ATTEMPT_1.json` as written. It is prose, not a
digest, and no check reads it — which is exactly why it survived. The attempt-5
plan does not inherit it.
