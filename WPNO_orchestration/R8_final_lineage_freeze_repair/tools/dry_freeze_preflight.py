#!/usr/bin/env python3
"""Run the controller's ENTIRE pre-write freeze sequence against real R8.

`cmd_freeze_level1` states where its write boundary is: "nothing above this
line writes". Everything above it is steps 1 to 9. This executes those nine
steps, in order, against the real package, using the controller's own module
functions — and stops at the boundary.

This is the check whose absence let a plan be built, a token be issued and a
human be asked for a freeze the controller could never grant. The step that
refused was step 9, and no test and no verification item reached it.

The token is derived here to run steps 1 and 5, and is neither printed nor
written to disk.

Usage: dry_freeze_preflight.py <r8> <plan_rel> <out.json>
Exit 0 only when all nine steps pass and R8 is byte-identical afterwards.
"""

import hashlib
import io
import json
import os
import stat
import sys


def inventory(root):
    rows = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            st = os.lstat(full)
            rows[os.path.relpath(full, root)] = (
                st.st_size, st.st_mtime_ns, oct(stat.S_IMODE(st.st_mode)),
                st.st_uid, st.st_gid)
    return rows


def main():
    r8, plan_rel, out_path = os.path.realpath(sys.argv[1]), sys.argv[2], sys.argv[3]
    sys.path.insert(0, r8)
    from automation import controller, freeze, policy

    before = inventory(r8)
    steps = []

    def step(number, name, fn):
        try:
            value = fn()
            steps.append({"step": number, "name": name, "PASS": True,
                          "measured": value})
            return value
        except Exception as exc:                            # noqa: BLE001
            steps.append({"step": number, "name": name, "PASS": False,
                          "error": "%s: %s" % (type(exc).__name__, exc)})
            raise

    plan_path = os.path.join(r8, plan_rel)
    with open(plan_path, "rb") as fh:
        raw = fh.read()
    plan = json.loads(raw.decode("utf-8"))
    plan_sha = hashlib.sha256(raw).hexdigest()
    token = freeze.token_for(plan["package_sha256"],
                             plan["verification_result_sha256"], plan_sha)

    ok = True
    try:
        parsed = step(1, "parse_freeze_token",
                      lambda: {"fields": len(token.split()),
                               "grammar": "accepted"} if
                      freeze.parse_freeze_token(token) else None)
        parsed = freeze.parse_freeze_token(token)

        step(2, "assert_no_freeze_artefact + MODE is GENERATED_UNVERIFIED",
             lambda: (freeze.assert_no_freeze_artefact(r8),
                      io.open(os.path.join(r8, "MODE"),
                              encoding="utf-8").read().strip())[1])
        mode = io.open(os.path.join(r8, "MODE"), encoding="utf-8").read().strip()
        if mode != policy.MODE_GENERATED:
            raise AssertionError("MODE is %r" % mode)

        def phases():
            with io.open(os.path.join(r8, "state", "progress.json"),
                         encoding="utf-8") as fh:
                progress = json.load(fh)
            started = ["%s/%s" % (a, p)
                       for a, audit in sorted(progress["audits"].items())
                       for p, node in sorted(audit.items())
                       if node.get("state") != "NOT_STARTED"]
            if started:
                raise AssertionError("phases started: %s" % started[:5])
            approvals = os.path.join(r8, "state", "approvals.jsonl")
            if os.path.exists(approvals) and os.path.getsize(approvals):
                raise AssertionError("approvals recorded")
            return {"phase_records": sum(len(a) for a in
                                         progress["audits"].values()),
                    "started": 0, "approvals_bytes": 0}
        step(3, "no audit phase started, no approval recorded", phases)

        step(4, "plan resolves, loads strict and shape-checks",
             lambda: {"path": os.path.relpath(
                 freeze.confined_path(r8, plan_rel), r8),
                 "sha256": freeze.load_package_freeze_plan(plan_path)[1]})
        loaded, loaded_sha = freeze.load_package_freeze_plan(plan_path)

        step(5, "assert_token_binds_plan",
             lambda: bool(freeze.assert_token_binds_plan(parsed, loaded,
                                                         loaded_sha)))
        step(6, "assert_plan_matches_disk",
             lambda: {"bound_artifacts": len(loaded["bound_artifacts"]),
                      "all_matched": bool(
                          freeze.assert_plan_matches_disk(loaded, r8))})

        def baseline():
            b, prov = freeze.build_baseline_from_predecessor(
                r8, loaded["predecessor_baseline_manifest_sha256"])
            freeze.assert_baseline_matches_plan(b, loaded)
            return {"project_members": prov["project_members"],
                    "discovery_members": prov["discovery_members"],
                    "preview_sha256": freeze.sha256_text(
                        freeze.serialize_baseline(b))}
        step(7, "Ubuntu baseline built and matches the plan", baseline)

        step(8, "assert_not_replayed",
             lambda: {"ledger": "state/freeze_attempts.jsonl",
                      "recorded_attempts": len(freeze.recorded_attempts(
                          os.path.join(r8, "state", "freeze_attempts.jsonl"))),
                      "accepted": bool(freeze.assert_not_replayed(
                          token, loaded,
                          os.path.join(r8, "state",
                                       "freeze_attempts.jsonl")) is None
                          or True)})

        # step 9 -- the one that refused the real freeze
        step(9, "predecessor lineage bound, present and unaltered",
             lambda: {"required": list(
                 freeze.required_predecessor_lineage_artifacts()),
                 "checked": list(freeze.assert_lineage_bound(loaded, r8))})
    except Exception:                                       # noqa: BLE001
        ok = False

    after = inventory(r8)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after)
                     if before[p] != after[p])
    wrote_nothing = not (added or removed or changed)

    doc = {
        "schema": "wpno.r8.dry-freeze-preflight/1",
        "r8_root": r8, "plan": plan_rel, "plan_sha256": plan_sha,
        "boundary": ("stopped at cmd_freeze_level1's stated write boundary: "
                     "'nothing above this line writes'"),
        "steps": steps,
        "steps_passed": sum(1 for s in steps if s["PASS"]),
        "steps_total": len(steps),
        "token_derived_here": True,
        "token_printed_or_written": False,
        "r8_paths_added": added, "r8_paths_removed": removed,
        "r8_paths_changed": changed,
        "R8_WROTE_NOTHING": wrote_nothing,
        "PREFLIGHT_PASS": ok and len(steps) == 9 and wrote_nothing
        and all(s["PASS"] for s in steps),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in
                      ("steps_passed", "steps_total", "R8_WROTE_NOTHING",
                       "r8_paths_added", "r8_paths_removed",
                       "r8_paths_changed", "PREFLIGHT_PASS")},
                     indent=1, sort_keys=True))
    for s in steps:
        print("  step %d %-55s %s" % (s["step"], s["name"],
                                      "PASS" if s["PASS"] else
                                      "FAIL " + s.get("error", "")))
    return 0 if doc["PREFLIGHT_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
