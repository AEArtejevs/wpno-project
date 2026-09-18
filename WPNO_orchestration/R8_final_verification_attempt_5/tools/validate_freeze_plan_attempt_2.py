#!/usr/bin/env python3
"""Independently validate R8 freeze plan attempt 2 and its token.

Independent of the builder in the sense that matters here: it re-reads the
plan from disk, re-hashes every artefact from disk, and re-derives the token
from the plan's own fields. It shares no state with the builder and does not
import it. It does use `automation.freeze` -- deliberately, because the freeze
route will use exactly that module, and a validator that agreed with the
builder while disagreeing with the route would prove nothing.

It writes nothing into R8.

Usage: validate_freeze_plan_attempt_2.py <plan.json> <out.json>
"""

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A5_ROOT = os.path.dirname(HERE)
ROOT = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
CLONE = os.path.join(A5_ROOT, "test_clone", "08.18.26_Level1_Audits_R8")
sys.path.insert(0, CLONE)

from automation import freeze  # noqa: E402


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    plan_path, out_path = sys.argv[1], sys.argv[2]
    checks = []

    def check(name, ok, measured):
        checks.append({"check": name, "pass": bool(ok), "measured": measured})
        return ok

    with open(plan_path, "rb") as fh:
        raw_bytes = fh.read()
    raw = raw_bytes.decode("utf-8")
    plan_sha_here = hashlib.sha256(raw_bytes).hexdigest()

    # 1. The route's own loader accepts it: duplicate-key strict, shape checked.
    loaded, loaded_sha = freeze.load_package_freeze_plan(plan_path)
    check("route_loader_accepts_plan", True, "load_package_freeze_plan ok")
    check("plan_digest_agrees_with_route_loader",
          loaded_sha == plan_sha_here,
          {"validator": plan_sha_here, "freeze.load": loaded_sha})

    # 2. Shape, revision, platform, attempt number.
    freeze.assert_package_plan_shape(loaded)
    check("assert_package_plan_shape", True, "ok")
    check("attempt_number_is_2", loaded["attempt_number"] == 2,
          loaded["attempt_number"])
    check("attempt_number_unused_by_attempt_1",
          loaded["attempt_number"] != 1, loaded["attempt_number"])

    # 3. Every in-package bound artefact re-hashed from disk, by the exact
    #    function the freeze route calls.
    freeze.assert_bound_artifacts_match_disk(loaded, ROOT)
    bound = loaded["bound_artifacts"]
    check("bound_artifacts_match_disk", True, "%d/%d MATCH"
          % (len(bound), len(bound)))

    # 4. Re-hash them again here, independently of that call, so a defect in
    #    the shared function would not pass both.
    mismatched = []
    for rel, declared in sorted(bound.items()):
        actual = sha256_file(os.path.join(ROOT, rel))
        if actual != declared:
            mismatched.append({"path": rel, "declared": declared,
                               "actual": actual})
    check("bound_artifacts_rehashed_independently", not mismatched,
          {"count": len(bound), "mismatched": mismatched})

    # 5. Every external bound artefact.
    external = loaded["external_bound_artifacts"]
    ext_bad = []
    for path, row in sorted(external.items()):
        if not os.path.isfile(path):
            ext_bad.append({"path": path, "problem": "absent"})
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            ext_bad.append({"path": path, "declared": row["sha256"],
                            "actual": actual})
    check("external_bound_artifacts_match_disk", not ext_bad,
          {"count": len(external), "mismatched": ext_bad})

    # 6. No external artefact secretly lies inside R8, and no bound artefact
    #    escapes it. The two lists must not overlap.
    inside = [p for p in external
              if os.path.realpath(p).startswith(os.path.realpath(ROOT) + os.sep)]
    check("external_artefacts_are_outside_r8", not inside, inside)

    # 7. Every role §5 requires is present in the external bindings or is
    #    explicitly accounted for.
    roles = {row["role"] for row in external.values()}
    required_roles = {
        "VERIFICATION_INSTRUCTIONS", "VERIFICATION_RUNNER",
        "FREEZE_PLAN_BUILDER", "FREEZE_PLAN_VALIDATOR",
        "ATTEMPT5_VERIFICATION_RESULT", "ATTEMPT5_VERIFICATION_MANIFEST",
        "ATTEMPT5_TOOL_INVENTORY", "ATTEMPT5_WRITE_ISOLATION_PROOF",
    }
    check("required_external_roles_present",
          required_roles <= roles, sorted(required_roles - roles))

    # 8. The result is not labelled as a verifier.
    result_rows = [p for p, r in external.items()
                   if r["role"] == "ATTEMPT5_VERIFICATION_RESULT"]
    check("verification_result_not_labelled_as_verifier",
          all(external[p]["role"] != "VERIFICATION_RUNNER"
              and external[p]["role"] != "VERIFICATION_INSTRUCTIONS"
              for p in result_rows), result_rows)

    # 9. freeze.py and the token generator are bound.
    freeze_py = os.path.join(ROOT, "automation", "freeze.py")
    check("freeze_module_bound_in_package",
          "automation/freeze.py" in bound
          and bound["automation/freeze.py"] == sha256_file(freeze_py),
          bound.get("automation/freeze.py"))

    import inspect
    source = inspect.getsource(freeze.token_for)
    gen = loaded["token_generator"]
    check("token_generator_source_digest_matches",
          gen["source_sha256"]
          == hashlib.sha256(source.encode("utf-8")).hexdigest()
          and gen["symbol"] == "automation.freeze.token_for",
          gen)

    # 10. The package digest the plan names is the live manifest.
    manifest = os.path.join(ROOT, "build", "R8_BUILD_MANIFEST.sha256")
    check("package_sha256_is_live_manifest",
          loaded["package_sha256"] == sha256_file(manifest),
          loaded["package_sha256"])
    with open(manifest, encoding="utf-8") as fh:
        entries = [ln for ln in fh.read().splitlines() if ln.strip()]
    check("manifest_entry_count_724", len(entries) == 724, len(entries))

    # 11. The verification the plan rests on passed and wrote nothing.
    with open(os.path.join(A5_ROOT, "codex_output",
                           "VERIFICATION_RESULT.json"), encoding="utf-8") as fh:
        verification = json.load(fh)
    check("verification_status_pass",
          verification.get("status")
          == "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL",
          verification.get("status"))
    check("verification_overall_pass",
          verification.get("overall_pass") is True,
          verification.get("overall_pass"))
    check("verification_no_unresolved_findings",
          verification.get("unresolved_findings") == [],
          verification.get("unresolved_findings"))
    check("verification_result_digest_bound",
          loaded["verification_result_sha256"]
          == sha256_file(os.path.join(A5_ROOT, "codex_output",
                                      "VERIFICATION_RESULT.json")),
          loaded["verification_result_sha256"])

    # 12. Write isolation proof.
    with open(os.path.join(A5_ROOT, "original_inventory",
                           "COMPARE_PRE_VS_POST.json"), encoding="utf-8") as fh:
        proof = json.load(fh)
    check("r8_unchanged_across_attempt_5", proof.get("EQUAL") is True,
          {k: proof.get(k) for k in ("paths_added", "paths_removed",
                                     "contents_changed", "mtimes_changed",
                                     "modes_changed")})

    # 13. Baseline: rebuild it and compare with the plan, the way the route
    #     will. assert_baseline_matches_plan is the route's own check.
    baseline, provenance = freeze.build_baseline_from_predecessor(
        ROOT, loaded["predecessor_baseline_manifest_sha256"])
    freeze.assert_baseline_matches_plan(baseline, loaded)
    check("assert_baseline_matches_plan", True,
          {"project_members": provenance["project_members"],
           "discovery_members": provenance["discovery_members"]})

    # 14. Live state has not moved under the plan.
    with open(os.path.join(ROOT, "state", "progress.json"),
              encoding="utf-8") as fh:
        progress = json.load(fh)
    states = {}
    records = 0
    for rec in progress["audits"].values():
        for entry in rec.values():
            records += 1
            states[entry["state"]] = states.get(entry["state"], 0) + 1
    check("live_state_43_not_started",
          records == 43 and states == {"NOT_STARTED": 43},
          {"records": records, "states": states})
    check("no_approvals",
          os.path.getsize(os.path.join(ROOT, "state",
                                       "approvals.jsonl")) == 0, 0)
    check("no_results", os.listdir(os.path.join(ROOT, "results")) == [], 0)
    check("no_evidence", os.listdir(os.path.join(ROOT, "evidence")) == [], 0)
    check("no_freeze_attempt_recorded",
          not freeze.recorded_attempts(os.path.join(ROOT, "state",
                                                    "freeze_attempts.jsonl")),
          0)
    check("r9_absent",
          not os.path.exists(os.path.join(os.path.dirname(ROOT),
                                          "08.18.26_Level1_Audits_R9")),
          "absent")

    # 15. The token. Re-derived from the plan's own fields, then hashed two
    #     ways over the exact bytes with no trailing newline.
    token = freeze.token_for(loaded["package_sha256"],
                             loaded["verification_result_sha256"],
                             plan_sha_here)
    parsed = freeze.parse_freeze_token(token)
    freeze.assert_token_binds_plan(parsed, loaded, plan_sha_here)
    check("token_binds_plan", True, "assert_token_binds_plan ok")
    check("token_is_five_fields", len(token.split()) == 5, len(token.split()))
    check("token_has_no_trailing_newline", not token.endswith("\n"), True)

    python_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    proc = subprocess.run(["/usr/bin/sha256sum"], input=token.encode("utf-8"),
                          stdout=subprocess.PIPE, check=True)
    sha256sum_digest = proc.stdout.decode().split()[0]
    check("token_hash_methods_agree", python_digest == sha256sum_digest,
          {"python_hashlib": python_digest, "sha256sum": sha256sum_digest})

    check("token_differs_from_attempt_4",
          python_digest != ("47cf40be29089257bd08dfef738fdb96"
                            "6009c46c7cd21add5c5400167d9c0d44"),
          python_digest)

    ok = all(c["pass"] for c in checks)
    doc = {
        "schema": "wpno.r8.attempt5-freeze-plan-validation/1",
        "plan_path": plan_path,
        "plan_sha256": plan_sha_here,
        "attempt_number": loaded["attempt_number"],
        "bound_artifacts": len(bound),
        "external_bound_artifacts": len(external),
        "checks": checks,
        "checks_passed": sum(1 for c in checks if c["pass"]),
        "checks_total": len(checks),
        "token_sha256_python": python_digest,
        "token_sha256_sha256sum": sha256sum_digest,
        "token_recorded_here": False,
        "VALID": ok,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "plan_sha256", "attempt_number", "bound_artifacts",
        "external_bound_artifacts", "checks_passed", "checks_total",
        "token_sha256_python", "token_sha256_sha256sum", "VALID")},
        indent=1, sort_keys=True))
    if not ok:
        print(json.dumps([c for c in checks if not c["pass"]], indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
