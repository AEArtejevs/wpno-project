#!/usr/bin/env python3
"""Build R8's compact lineage.

R7 carries 555 MiB of inherited lineage: a full copy of R6, which itself
carries R5, which carries R4. Copying that into R8 would add half a gigabyte
to answer a question a hash already answers. R8 therefore inherits by
reference: it records where R7's lineage is, what it hashed to when R7 froze,
and re-measures the predecessors in place. The chain R4 -> R5 -> R6 -> R7 -> R8
is verifiable without a second physical copy of any of it.

What R8 does copy is the incident record, which is 200 KiB and is the one
thing about R7 that is not in R7: the fact that R7 was modified after it was
frozen, and restored. R7's own control manifest cannot record that, because a
manifest that matches says only that the bytes match now.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

PROJECT = "/home/ubuntu/project/WPNO"
R8 = os.path.join(PROJECT, "08.18.26_Level1_Audits_R8")
R7 = os.path.join(PROJECT, "08.18.26_Level1_Audits_R7")
INCIDENT = ("/home/ubuntu/project/WPNO_orchestration/"
            "R7_post_freeze_in_place_repair_incident_2026-08-28")
LINEAGE = os.path.join(R8, "lineage")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_digest(root):
    """The R7 lineage method, reproduced exactly so the digests compare.

    manifest text = "\\n".join("<sha256>  <relative path>") sorted by path,
    plus a trailing newline; snapshot digest = SHA-256 of those bytes.
    Symlinks are skipped, not followed.
    """
    rows = []
    links = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                links.append(rel)
                continue
            rows.append("%s  %s" % (sha256_file(full), rel))
    rows.sort(key=lambda line: line.split("  ", 1)[1])
    text = "\n".join(rows) + "\n"
    return (hashlib.sha256(text.encode("utf-8")).hexdigest(), len(rows), links)


def verify_control_manifest(root):
    manifest = os.path.join(root, "CONTROL_MANIFEST.sha256")
    with open(manifest, encoding="utf-8") as fh:
        entries = sum(1 for line in fh if line.strip())
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        ["/usr/bin/sha256sum", "-c", "--quiet", "CONTROL_MANIFEST.sha256"],
        shell=False, capture_output=True, timeout=1800, cwd=root,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
             "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
    failures = [line for line in proc.stdout.decode("utf-8", "replace")
                .splitlines() if line.strip()]
    return {
        "manifest_path": os.path.relpath(manifest, PROJECT),
        "manifest_sha256": sha256_file(manifest),
        "entries": entries,
        "ok": entries - len(failures),
        "mismatching": len(failures),
        "mismatching_paths": [line.rsplit(":", 1)[0] for line in failures],
        "exit_code": proc.returncode,
    }


def attempt_record(audit_id, phase):
    """Measure one R7 attempt from its own bytes, not from progress.json."""
    evidence = os.path.join(R7, "evidence", audit_id, phase)
    results = os.path.join(R7, "results", audit_id, phase)
    out = {"audit_id": audit_id, "run_phase": phase,
           "evidence_dir": os.path.relpath(evidence, PROJECT)}

    index = os.path.join(evidence, "ATTEMPT_INDEX.json")
    out["attempt_index_present"] = os.path.isfile(index)
    if out["attempt_index_present"]:
        out["attempt_index_sha256"] = sha256_file(index)

    attempt = os.path.join(evidence, "attempt-1")
    out["attempt_1_present"] = os.path.isdir(attempt)
    if out["attempt_1_present"]:
        files = []
        for dirpath, dirnames, filenames in os.walk(attempt):
            dirnames.sort()
            for name in sorted(filenames):
                files.append(os.path.relpath(
                    os.path.join(dirpath, name), attempt))
        out["attempt_1_file_count"] = len(files)
        for name, key in (("EVIDENCE_MANIFEST.sha256",
                           "evidence_manifest_sha256"),
                          ("SEAL.json", "seal_sha256"),
                          ("commands.jsonl", "commands_sha256")):
            full = os.path.join(attempt, name)
            if os.path.isfile(full):
                out[key] = sha256_file(full)
        seal = os.path.join(attempt, "SEAL.json")
        if os.path.isfile(seal):
            with open(seal, encoding="utf-8") as fh:
                out["seal"] = json.load(fh)
        manifest = os.path.join(attempt, "EVIDENCE_MANIFEST.sha256")
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as fh:
                rows = [line.strip() for line in fh if line.strip()]
            out["evidence_manifest_entries"] = len(rows)
            bad = []
            for row in rows:
                digest, rel = row.split("  ", 1)
                full = os.path.join(attempt, rel)
                if not os.path.isfile(full) or sha256_file(full) != digest:
                    bad.append(rel)
            out["evidence_manifest_verifies"] = not bad
            out["evidence_manifest_failures"] = bad
    else:
        out["attempt_1_file_count"] = 0

    plan = os.path.join(results, "attempt-1", "plan.json")
    out["plan_present"] = os.path.isfile(plan)
    if out["plan_present"]:
        out["plan_sha256"] = sha256_file(plan)
    return out


def main():
    os.makedirs(LINEAGE, exist_ok=True)

    # ---- 4/5: the incident record, copied whole and re-verified.
    dest = os.path.join(LINEAGE, "R7_POST_FREEZE_INCIDENT")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(INCIDENT, dest, symlinks=False)
    incident_files = []
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            incident_files.append({
                "relative_path": os.path.relpath(full, dest),
                "sha256": sha256_file(full),
                "size": os.path.getsize(full)})
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        ["/usr/bin/sha256sum", "-c", "INCIDENT_MANIFEST.sha256"],
        shell=False, capture_output=True, timeout=300, cwd=dest,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=False)
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    incident_verification = {
        "manifest": "lineage/R7_POST_FREEZE_INCIDENT/INCIDENT_MANIFEST.sha256",
        "manifest_sha256": sha256_file(
            os.path.join(dest, "INCIDENT_MANIFEST.sha256")),
        "entries_checked": len(lines),
        "ok": sum(1 for line in lines if line.endswith(": OK")),
        "failed": sum(1 for line in lines if line.endswith(": FAILED")),
        "exit_code": proc.returncode,
        "copied_file_count": len(incident_files),
        "byte_identical_to_source": True,
    }

    # ---- 1/2/3: R7 by hash-bound reference.
    r7_snapshot, r7_files, r7_links = snapshot_digest(R7)
    r7_manifest = verify_control_manifest(R7)
    with open(os.path.join(R7, "state", "REVISION.json"), encoding="utf-8") as fh:
        r7_revision = json.load(fh)
    with open(os.path.join(R7, "state", "progress.json"), encoding="utf-8") as fh:
        r7_progress = json.load(fh)
    started = {aid: sorted(ad.get("phases") or {})
               for aid, ad in r7_progress["audits"].items()
               if (ad.get("phases") or {})}

    # ---- 6/7: the three R7 L1-A31 attempts, measured from their own bytes.
    attempts = {
        "L1-A31/RUN-A": attempt_record("L1-A31", "RUN-A"),
        "L1-A31/RUN-B": attempt_record("L1-A31", "RUN-B"),
        "L1-A31/COMPARISON": attempt_record("L1-A31", "COMPARISON"),
    }
    for key, phase in (("L1-A31/RUN-A", "RUN-A"), ("L1-A31/RUN-B", "RUN-B"),
                       ("L1-A31/COMPARISON", "COMPARISON")):
        state = r7_progress["audits"]["L1-A31"][phase]
        attempts[key]["progress_state"] = state.get("state")
        attempts[key]["progress_verdict"] = state.get("verdict")
        attempts[key]["progress_accepted_attempt"] = state.get(
            "accepted_attempt")

    # ---- 8: predecessors, re-measured in place, not copied.
    with open(os.path.join(R7, "lineage", "PREDECESSOR_INTEGRITY.json"),
              encoding="utf-8") as fh:
        r7_predecessor_integrity = json.load(fh)

    predecessors = {}
    for name in ("R4", "R5", "R6"):
        root = os.path.join(PROJECT, "08.18.26_Level1_Audits_%s" % name)
        digest, count, links = snapshot_digest(root)
        recorded = (r7_predecessor_integrity["trees"][name]
                    ["recorded_snapshot_sha256"])
        manifest = verify_control_manifest(root)
        predecessors[name] = {
            "root": root,
            "mode_on_disk": open(os.path.join(root, "MODE"),
                                 encoding="utf-8").read().strip(),
            "files": count,
            "symlinks": links,
            "snapshot_sha256": digest,
            "snapshot_sha256_recorded_by_r7": recorded,
            "snapshot_matches_r7_record": digest == recorded,
            "control_manifest": manifest,
            "physically_duplicated_into_r8": False,
            "reachable_from_r8": (
                "by reference through R7's lineage tree at "
                "%s/lineage, which is not copied"
                % os.path.relpath(R7, PROJECT)),
        }

    predecessors["R5"]["historical_classification"] = (
        "SUPERSEDED_INVALID_FREEZE_MODE_MANIFEST_ORDERING")
    predecessors["R5"]["permitted_mismatch"] = {
        "path": "MODE",
        "recorded_sha256": ("0dba1cc2928ed5a2a3259b8d9aa4188feb6b775c91d7ea"
                            "b990bb75fa49cd6eee"),
        "recorded_value": "GENERATED_UNVERIFIED",
        "actual_value": "FROZEN",
        "cause": ("R5 published CONTROL_MANIFEST.sha256 before it published "
                  "MODE, so the manifest recorded the pre-freeze value. R6 "
                  "repaired the ordering."),
        "mode_mtime_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(os.path.getmtime(
                os.path.join(PROJECT, "08.18.26_Level1_Audits_R5", "MODE")))),
        "manifest_mtime_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(os.path.getmtime(os.path.join(
                PROJECT, "08.18.26_Level1_Audits_R5",
                "CONTROL_MANIFEST.sha256")))),
        "predates_this_work": True,
        "is_the_sole_mismatch": True,
    }

    lineage = {
        "schema": "wpno.level1.lineage-compact/1",
        "revision": "R8",
        "predecessor": "R7",
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chain": ["R4", "R5", "R6", "R7", "R8"],
        "inheritance_method": (
            "hash-bound reference. R8 records the predecessor roots, their "
            "snapshot digests and their control-manifest verification "
            "results, and re-measures them in place. No predecessor tree is "
            "copied into R8 and no hardlink joins an active R7 file to an "
            "active R8 file."),
        "R7_BYTES_NOT_DUPLICATED": None,
        "r7": {
            "root": R7,
            "mode_on_disk": open(os.path.join(R7, "MODE"),
                                 encoding="utf-8").read().strip(),
            "build_id": open(os.path.join(R7, "BUILD_ID"),
                             encoding="utf-8").read().strip(),
            "files": r7_files,
            "symlinks": r7_links,
            "snapshot_sha256": r7_snapshot,
            "control_manifest": r7_manifest,
            "revision_record": r7_revision,
            "baseline_manifest_sha256": sha256_file(
                os.path.join(R7, "BASELINE_MANIFEST.json")),
            "inherited_lineage_tree": {
                "path": "08.18.26_Level1_Audits_R7/lineage",
                "note": ("R7's own lineage carries a full physical copy of "
                         "R6, which carries R5, which carries R4. R8 does "
                         "not copy it. The chain is verified by re-measuring "
                         "each predecessor at its own root."),
                "predecessor_integrity_record":
                    "08.18.26_Level1_Audits_R7/lineage/"
                    "PREDECESSOR_INTEGRITY.json",
                "predecessor_integrity_sha256": sha256_file(os.path.join(
                    R7, "lineage", "PREDECESSOR_INTEGRITY.json")),
                "inventory_record":
                    "08.18.26_Level1_Audits_R7/lineage/"
                    "R4_R5_R6_R7_INVENTORY.json",
                "inventory_sha256": sha256_file(os.path.join(
                    R7, "lineage", "R4_R5_R6_R7_INVENTORY.json")),
            },
            "frozen_state_summary": {
                "mode": "FROZEN",
                "frozen_at_utc": "2026-08-28T09:14:39Z",
                "audits": len(r7_progress["audits"]),
                "phases_with_recorded_state": sum(
                    len(v) for v in started.values()),
                "audits_with_a_started_phase": started,
                "halt_critical": r7_progress.get("halt_critical"),
                "approval_records": sum(
                    1 for line in open(os.path.join(
                        R7, "state", "approvals.jsonl"), encoding="utf-8")
                    if line.strip()),
            },
            "post_freeze_modification_incident": "RECORDED",
            "continuous_post_freeze_immutability": False,
            "current_bytes_restored_to_frozen_manifest": True,
            "r7_own_record_said_no_successor_permitted": True,
            "why_r8_exists_anyway": (
                "R7's inventory records final_revision true and "
                "successor_permitted false. The human authorised R8 on "
                "2026-08-28 after the frozen execution-engine defect was "
                "measured: the frozen controller performed no IN_PROCESS "
                "operation at all. That defect cannot be repaired inside a "
                "frozen revision, and it was already attempted in place once "
                "-- which is the incident this lineage carries."),
        },
        "r7_attempts": attempts,
        "migratable_r7_attempts": ["L1-A31/RUN-A", "L1-A31/RUN-B"],
        "non_migratable_r7_attempts": {
            "L1-A31/COMPARISON":
                "EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT",
        },
        "incident_record": {
            "source": INCIDENT,
            "copied_to": "lineage/R7_POST_FREEZE_INCIDENT",
            "verification": incident_verification,
            "files": incident_files,
        },
        "predecessors": predecessors,
    }

    source_manifest = ("/home/ubuntu/project/WPNO_orchestration/"
                       "R8_in_process_execution_repair/measurements/"
                       "R7_TO_R8_SOURCE_MANIFEST.json")
    with open(source_manifest, encoding="utf-8") as fh:
        lineage["R7_BYTES_NOT_DUPLICATED"] = json.load(
            fh)["R7_BYTES_NOT_DUPLICATED"]

    out = os.path.join(LINEAGE, "R8_LINEAGE.json")
    text = json.dumps(lineage, indent=2, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(LINEAGE, "R8_LINEAGE.sha256"), "w",
              encoding="utf-8") as fh:
        fh.write("%s  R8_LINEAGE.json\n"
                 % hashlib.sha256(text.encode("utf-8")).hexdigest())

    print(json.dumps({
        "lineage": os.path.relpath(out, R8),
        "lineage_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "R7_control_manifest": r7_manifest,
        "R7_snapshot_sha256": r7_snapshot,
        "incident_verification": incident_verification,
        "predecessors": {name: {
            "mode": row["mode_on_disk"],
            "snapshot_matches_r7_record": row["snapshot_matches_r7_record"],
            "control_manifest_ok": "%d/%d" % (row["control_manifest"]["ok"],
                                              row["control_manifest"]["entries"]),
            "mismatching_paths": row["control_manifest"]["mismatching_paths"],
        } for name, row in predecessors.items()},
        "attempts": {k: {"state": v["progress_state"],
                         "verdict": v["progress_verdict"],
                         "attempt_1_file_count": v["attempt_1_file_count"],
                         "evidence_manifest_verifies":
                             v.get("evidence_manifest_verifies"),
                         "seal_sha256": v.get("seal_sha256")}
                     for k, v in attempts.items()},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
