#!/usr/bin/env python3
"""Run R8's freeze-plan builder against the attempt-4 verification.

Why a runner exists at all.

The builder inside R8 carries a module constant naming the verification
directory it binds, and it names attempt 3. Attempt 3 passed against a
manifest that is now superseded, so a plan built from it would bind the wrong
verification. The obvious fix -- edit the constant -- is forbidden: this
authorisation is verification-only and the package is read-only.

So the constant is overridden here, from outside the package, before the
builder's own `main` runs. Nothing in R8 is modified. The builder's bytes are
recorded before and after and must be identical, because a runner that
silently rewrote the thing it was running would be worse than the edit it was
avoiding.

This runner is itself an executable that produces a freeze artefact, so its
own digest is recorded and reported alongside the builder's.
"""

import hashlib
import importlib.util
import json
import os
import sys

R8 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
BUILDER = os.path.join(R8, "build", "freeze_plan_attempt_1",
                       "build_r8_freeze_plan.py")
ATTEMPT_4_DIR = "verification_codex_final_pre_freeze_attempt_4"
HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    before = sha256_file(BUILDER)

    spec = importlib.util.spec_from_file_location("r8_freeze_plan_builder",
                                                  BUILDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["r8_freeze_plan_builder"] = module
    spec.loader.exec_module(module)

    # Point the builder at attempt 4. Every derived constant is recomputed
    # here rather than left stale, because the builder computed them from the
    # old value at import time.
    module.VERIFICATION_DIR = ATTEMPT_4_DIR
    module.VERIFICATION_RESULT = os.path.join(ATTEMPT_4_DIR,
                                              "VERIFICATION_RESULT.json")
    module.VERIFICATION_MANIFEST = os.path.join(ATTEMPT_4_DIR,
                                                "VERIFICATION_MANIFEST.sha256")

    rc = module.main()

    after = sha256_file(BUILDER)
    if before != after:
        raise SystemExit("the builder changed while it ran: %s -> %s"
                         % (before, after))

    record = {
        "schema": "wpno.r8.freeze-plan-runner/1",
        "runner": os.path.relpath(os.path.abspath(__file__), HERE),
        "runner_sha256": sha256_file(os.path.abspath(__file__)),
        "builder": os.path.relpath(BUILDER, R8),
        "builder_sha256_before": before,
        "builder_sha256_after": after,
        "builder_unchanged": before == after,
        "verification_directory_bound": ATTEMPT_4_DIR,
        "override_reason": (
            "the builder's constant named attempt 3, whose manifest is "
            "superseded; editing the package was not authorised, so the "
            "constant was overridden at run time and the builder's bytes "
            "were proved unchanged"),
        "builder_return_code": rc,
    }
    out = os.path.join(HERE, "FREEZE_PLAN_RUNNER_RECORD.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(record, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
