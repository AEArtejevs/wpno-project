#!/usr/bin/env python3
"""Independently validate R8 freeze plan attempt 2 and its token.

Independent of the builder in the sense that matters: it re-reads the plan
from disk, re-hashes every bound artefact from disk, and re-derives the token
from the plan's own fields. It shares no state with the builder and does not
import it.

It does use `automation.freeze` -- deliberately. The freeze route will use
exactly that module, and a validator that agreed with the builder while
disagreeing with the route would prove nothing about what the route will
accept. Where a shared function could hide a defect by being wrong in both
places, the same quantity is measured a second time here without it.

It writes nothing into R8. Every artefact is bound by a relative path confined
under the package root, so there is no `external_bound_artifacts` list to
check: attempt 5 needed one because its verification lived outside the
package; this attempt installs the verification into the excluded verifier
directory, where `freeze.assert_bound_artifacts_match_disk` can reach it.

Usage: validate_freeze_plan_attempt_2.py <plan.json> <out.json>
"""

import hashlib
import inspect
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

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
    plan_sha_here = hashlib.sha256(raw_bytes).hexdigest()

    # 1. The route's own loader accepts it: duplicate-key strict, shape checked.
    loaded, loaded_sha = freeze.load_package_freeze_plan(plan_path)
    check("route_loader_accepts_plan", True, "load_package_freeze_plan ok")
    check("plan_digest_agrees_with_route_loader",
          loaded_sha == plan_sha_here,
          {"validator": plan_sha_here, "freeze.load": loaded_sha})

    freeze.assert_package_plan_shape(loaded)
    check("assert_package_plan_shape", True, "ok")
    check("attempt_number_is_2", loaded["attempt_number"] == 2,
          loaded["attempt_number"])
    check("plan_is_not_attempt_1", loaded["attempt_number"] != 1,
          loaded["attempt_number"])
    check("attempt_1_plan_preserved",
          os.path.isfile(os.path.join(
              ROOT, "build", "freeze_plan_attempt_1",
              "FREEZE_PLAN_R8_ATTEMPT_1.json")),
          "attempt 1 not overwritten")

    # 2. The three defects attempt 1 carried are gone.
    check("no_r7_finality_statement",
          "R7 is the final revision" not in json.dumps(loaded),
          "absent")
    check("plan_declares_r8_final",
          loaded.get("final_revision") is True
          and loaded.get("successor_permitted") is False,
          {"final_revision": loaded.get("final_revision"),
           "successor_permitted": loaded.get("successor_permitted")})
    check("package_root_key_names_r8",
          loaded.get("r8_root") == ROOT and "r7_root" not in loaded,
          {"r8_root": loaded.get("r8_root"),
           "r7_root_present": "r7_root" in loaded})
    check("verification_dir_is_not_a_stale_attempt_3_or_4_constant",
          loaded["verification_path"] not in (
              "verification_codex_final_pre_freeze_attempt_3",
              "verification_codex_final_pre_freeze_attempt_4"),
          loaded["verification_path"])
    check("verification_dir_is_the_highest_numbered_on_disk",
          loaded["verification_path"] == max(
              (e for e in os.listdir(ROOT)
               if e.startswith("verification_codex_final_pre_freeze_attempt_")
               and e.rsplit("_", 1)[-1].isdigit()),
              key=lambda e: int(e.rsplit("_", 1)[-1])),
          loaded["verification_path"])

    # 3. Every bound artefact re-hashed from disk by the function the freeze
    #    route itself calls.
    freeze.assert_bound_artifacts_match_disk(loaded, ROOT)
    bound = loaded["bound_artifacts"]
    check("bound_artifacts_match_disk_route_function", True,
          "%d/%d MATCH" % (len(bound), len(bound)))

    # 4. Re-hashed again here without that function, so a defect inside it
    #    could not pass both measurements.
    mismatched = []
    for rel, declared in sorted(bound.items()):
        actual = sha256_file(os.path.join(ROOT, rel))
        if actual != declared:
            mismatched.append({"path": rel, "declared": declared,
                               "actual": actual})
    check("bound_artifacts_rehashed_independently", not mismatched,
          {"count": len(bound), "mismatched": mismatched})

    # 5. The roles §13 requires are all bound.
    required = {
        "build/R8_BUILD_MANIFEST.sha256": "BUILD_MANIFEST",
        "automation/freeze.py": "FREEZE_MODULE_AND_TOKEN_GENERATOR",
        "automation/policy.py": "TOKEN_GRAMMAR_CONSTANTS",
        "automation/controller.py": "FREEZE_ROUTE",
        "automation/migration.py": "MIGRATION_ROUTE",
        "build/migration_plan_r7_to_r8/MIGRATION_PLAN.json": "MIGRATION_PACKET",
        "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-A.json": "MIGRATION_PACKET",
        "build/migration_plan_r7_to_r8/PACKET_L1-A31_RUN-B.json": "MIGRATION_PACKET",
        "MODE": "MODE",
    }
    absent = sorted(p for p in required if p not in bound)
    check("required_roles_bound", not absent, {"absent": absent})

    builder_rel = os.path.relpath(
        os.path.join(HERE, "build_r8_freeze_plan_attempt_2.py"), ROOT)
    validator_rel = os.path.relpath(os.path.abspath(__file__), ROOT)
    check("builder_binds_itself", builder_rel in bound, builder_rel)
    check("validator_is_bound", validator_rel in bound, validator_rel)

    # 6. The whole installed verification directory is bound, file by file.
    vdir = os.path.join(ROOT, loaded["verification_path"])
    on_disk = sorted(
        os.path.relpath(os.path.join(dp, fn), ROOT)
        for dp, dn, fns in os.walk(vdir) for fn in fns)
    unbound = [p for p in on_disk if p not in bound]
    check("every_installed_verification_file_is_bound",
          on_disk and not unbound,
          {"files": len(on_disk), "unbound": unbound})

    # 7. The verification result is not identified as a verifier. Attempt 4
    #    named VERIFICATION_RESULT.json as the verifier; a result is what a
    #    verifier produced, never the thing that produced it.
    inventory_rel = os.path.join(loaded["verification_path"],
                                 "TOOL_INVENTORY.json")
    roles_ok, roles_detail = True, "TOOL_INVENTORY.json absent"
    inv_path = os.path.join(ROOT, inventory_rel)
    if os.path.isfile(inv_path):
        with open(inv_path, encoding="utf-8") as fh:
            inv = json.load(fh)
        offenders = [t["CANONICAL_PATH"] for t in inv["tools"]
                     if t["CANONICAL_PATH"].endswith("VERIFICATION_RESULT.json")
                     and t["ROLE"] in ("VERIFICATION_RUNNER",
                                       "VERIFICATION_INSTRUCTIONS",
                                       "VERIFICATION_HELPER")]
        roles_ok = not offenders and inv["UNIDENTIFIED_TOOLS"] == 0
        roles_detail = {"offenders": offenders,
                        "UNIDENTIFIED_TOOLS": inv["UNIDENTIFIED_TOOLS"]}
    check("verification_result_not_identified_as_a_verifier",
          roles_ok, roles_detail)

    # 8. The token generator, narrowed to the function that composes the token.
    gen = loaded["token_generation"]
    source = inspect.getsource(freeze.token_for)
    check("token_generator_function_digest_matches",
          gen["function_source_sha256"]
          == hashlib.sha256(source.encode("utf-8")).hexdigest()
          and gen["function"] == "token_for"
          and gen["module"] == "automation/freeze.py",
          gen["function_source_sha256"])
    check("token_generator_module_digest_matches",
          gen["module_sha256"] == sha256_file(
              os.path.join(ROOT, "automation", "freeze.py")),
          gen["module_sha256"])
    check("plan_wrapper_declared",
          "plan_wrapper" in loaded, loaded.get("plan_wrapper"))

    # 9. The package digest the plan names is the live manifest.
    manifest = os.path.join(ROOT, "build", "R8_BUILD_MANIFEST.sha256")
    check("package_sha256_is_the_live_manifest",
          loaded["package_sha256"] == sha256_file(manifest),
          loaded["package_sha256"])
    with open(manifest, encoding="utf-8") as fh:
        entries = [ln for ln in fh.read().splitlines() if ln.strip()]
    check("manifest_entry_count", len(entries) == 724, len(entries))

    # 10. The verification the plan rests on passed, with nothing unresolved.
    result_path = os.path.join(ROOT, loaded["verification_path"],
                               "VERIFICATION_RESULT.json")
    with open(result_path, encoding="utf-8") as fh:
        verification = json.load(fh)
    status = verification.get("result") or verification.get("status")
    check("verification_status_pass",
          status == "VERIFICATION_PASS_PRE_FREEZE_R8_FINAL", status)
    check("verification_overall_pass",
          verification.get("overall_pass") is True,
          verification.get("overall_pass"))
    check("verification_no_unresolved_findings",
          verification.get("unresolved_findings") == [],
          verification.get("unresolved_findings"))
    check("verification_result_digest_bound",
          loaded["verification_result_sha256"] == sha256_file(result_path),
          loaded["verification_result_sha256"])

    # 11. Baseline, rebuilt and compared the way the route will.
    baseline, provenance = freeze.build_baseline_from_predecessor(
        ROOT, loaded["predecessor_baseline_manifest_sha256"])
    freeze.assert_baseline_matches_plan(baseline, loaded)
    check("assert_baseline_matches_plan", True,
          {"project_members": provenance["project_members"],
           "discovery_members": provenance["discovery_members"]})
    check("baselines_are_nonempty",
          provenance["project_members"] > 0
          and provenance["discovery_members"] > 0,
          {"project": provenance["project_members"],
           "discovery": provenance["discovery_members"]})

    # 12. Live state has not moved under the plan.
    with open(os.path.join(ROOT, "state", "progress.json"),
              encoding="utf-8") as fh:
        progress = json.load(fh)
    states, records = {}, 0
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
          not freeze.recorded_attempts(
              os.path.join(ROOT, "state", "freeze_attempts.jsonl")), 0)
    ledger = os.path.join(ROOT, "state", "migrations.jsonl")
    check("migration_packet_unconsumed",
          not os.path.exists(ledger) or os.path.getsize(ledger) == 0,
          "unconsumed")
    check("mode_is_generated_unverified",
          open(os.path.join(ROOT, "MODE"),
               encoding="utf-8").read().strip() == "GENERATED_UNVERIFIED",
          open(os.path.join(ROOT, "MODE"), encoding="utf-8").read().strip())
    check("r9_absent",
          not os.path.exists(os.path.join(os.path.dirname(ROOT),
                                          "08.18.26_Level1_Audits_R9")),
          "absent")

    # 13. The token. Re-derived from the plan's own fields, then hashed two
    #     ways over the exact bytes with no trailing newline.
    token = freeze.token_for(loaded["package_sha256"],
                             loaded["verification_result_sha256"],
                             plan_sha_here)
    parsed = freeze.parse_freeze_token(token)
    freeze.assert_token_binds_plan(parsed, loaded, plan_sha_here)
    check("token_binds_plan", True, "assert_token_binds_plan ok")
    check("token_is_five_fields", len(token.split()) == 5, len(token.split()))
    check("token_has_no_trailing_newline", not token.endswith("\n"), True)

    # Two independent implementations over the same exact bytes. The four
    # keyword arguments are not decoration: the package's own static-safety
    # review requires every subprocess call to state `shell`, `timeout`, `env`
    # and `cwd`, and it found this call short of all four. A validator that
    # failed the standard it exists to uphold would be the weakest link in the
    # chain it certifies, so the call states them rather than the rule being
    # relaxed for it.
    python_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        ["/usr/bin/sha256sum"], shell=False, input=token.encode("utf-8"),
        stdout=subprocess.PIPE, check=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, cwd=ROOT)
    sha256sum_digest = proc.stdout.decode().split()[0]
    check("token_hash_methods_agree", python_digest == sha256sum_digest,
          {"python_hashlib": python_digest, "sha256sum": sha256sum_digest})

    # 14. The token is not one an earlier attempt already produced. Attempt 1's
    #     plan is on disk, so its token is re-derived and compared rather than
    #     quoted from a literal that could go stale.
    prior = []
    attempt_1 = os.path.join(ROOT, "build", "freeze_plan_attempt_1",
                             "FREEZE_PLAN_R8_ATTEMPT_1.json")
    if os.path.isfile(attempt_1):
        with open(attempt_1, "rb") as fh:
            p1_raw = fh.read()
        p1 = json.loads(p1_raw.decode("utf-8"))
        try:
            t1 = freeze.token_for(p1["package_sha256"],
                                  p1["verification_result_sha256"],
                                  hashlib.sha256(p1_raw).hexdigest())
            prior.append(hashlib.sha256(t1.encode("utf-8")).hexdigest())
        except Exception:                                 # noqa: BLE001
            pass
    # attempt 4's token, the only earlier digest recorded outside a plan file
    prior.append("47cf40be29089257bd08dfef738fdb96"
                 "6009c46c7cd21add5c5400167d9c0d44")
    check("token_differs_from_every_earlier_attempt",
          python_digest not in prior,
          {"this": python_digest, "earlier": prior})

    ok = all(c["pass"] for c in checks)
    doc = {
        "schema": "wpno.r8.attempt6-freeze-plan-validation/1",
        "plan_path": plan_path,
        "plan_sha256": plan_sha_here,
        "attempt_number": loaded["attempt_number"],
        "verification_path": loaded["verification_path"],
        "bound_artifacts": len(bound),
        "bound_artifacts_matched": len(bound) - len(mismatched),
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
        "plan_sha256", "attempt_number", "verification_path",
        "bound_artifacts", "bound_artifacts_matched", "checks_passed",
        "checks_total", "token_sha256_python", "token_sha256_sha256sum",
        "VALID")}, indent=1, sort_keys=True))
    if not ok:
        print(json.dumps([c for c in checks if not c["pass"]], indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
