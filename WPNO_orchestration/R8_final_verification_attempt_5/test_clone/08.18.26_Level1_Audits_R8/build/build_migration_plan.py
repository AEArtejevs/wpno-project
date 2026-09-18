#!/usr/bin/env python3
"""Prepare, but do not apply, the R7-to-R8 migration packet.

The packet is prepared before the freeze so that the freeze plan can bind it,
and applied only after the freeze so that R8's pre-freeze state stays 43/43
NOT_STARTED. Every digest in it is measured from the predecessor here and now;
none is copied from a report.

Two attempts are included and one is excluded, and the exclusion is by measured
reason rather than by name: R7's L1-A31 COMPARISON is EXECUTED, unsealed, and
has zero evidence files, because all three of its steps were IN_PROCESS and the
frozen controller performed none of them.
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, migration, path_policy  # noqa: E402

R7 = os.path.join(os.path.dirname(ROOT), "08.18.26_Level1_Audits_R7")
INCIDENT = os.path.join(ROOT, "lineage", "R7_POST_FREEZE_INCIDENT",
                        "INCIDENT_MANIFEST.sha256")
OUT_DIR = os.path.join(ROOT, "build", "migration_plan_r7_to_r8")

MIGRATABLE = (("L1-A31", "RUN-A"), ("L1-A31", "RUN-B"))
EXCLUDED = {
    ("L1-A31", "COMPARISON"):
        "EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT",
}


REFERENCES_DIR = os.path.join(R7, "references") + os.sep


def source_reference_hashes(plan):
    """Every accepted reference the attempt's steps actually read.

    Taken from the step parameters rather than from a `references` list in
    the test matrix: the nine plans written before the shared plan library
    existed -- L1-A31's among them -- carry no such list, so reading one
    would bind nothing for exactly the attempts being migrated. What the
    steps name is what the attempt was bound to.
    """
    found = {}

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.startswith(REFERENCES_DIR):
            if os.path.isfile(node):
                found[node] = hashing.sha256_file(node)

    walk(plan.get("steps", []))
    walk(plan.get("target", {}))
    return [{"path": path, "sha256": found[path]} for path in sorted(found)]


def build_packet(audit_id, phase, control_entries, control_sha):
    progress = json.load(open(os.path.join(R7, "state", "progress.json"),
                              encoding="utf-8"))
    node = progress["audits"][audit_id][phase]
    attempt = node["accepted_attempt"]
    row = node["attempts"][str(attempt)]
    plan_path = os.path.join(R7, "results", audit_id, phase,
                             "attempt-%d" % attempt, "plan.json")
    plan = json.load(open(plan_path, encoding="utf-8"))

    packet = {
        "schema": migration.PACKET_SCHEMA,
        "prepared_by": "build/build_migration_plan.py",
        "applied": False,
        "apply_only_after": "R8 MODE == FROZEN",
        "source_revision": "R7",
        "source_root": R7,
        "source_audit_id": audit_id,
        "source_run_phase": phase,
        "source_attempt_number": attempt,
        "source_attempt_id": row["attempt_id"],
        "source_plan_sha256": row["plan_sha256"],
        "source_target_path": row["target_path"],
        "source_target_sha256": row["target_sha256"],
        "source_evidence_manifest_sha256": row["evidence_manifest_sha256"],
        "source_seal_sha256": row["seal_sha256"],
        "source_verdict": row["verdict"],
        "source_classification": row["classification"],
        "source_evidence_file_count": row["evidence_file_count"],
        "source_reference_hashes": source_reference_hashes(plan),
        "source_control_manifest_sha256": control_sha,
        "source_control_manifest_entries": control_entries,
        "source_incident_manifest_path": INCIDENT,
        "source_incident_manifest_sha256": hashing.sha256_file(INCIDENT),
        "predecessor_incident_disclosed": True,
        "predecessor_incident_summary": (
            "R7 was modified after it was frozen and restored to its frozen "
            "bytes. Its control manifest verifies now; it did not "
            "continuously. The incident record is carried in R8's lineage."),
        "destination_revision": "R8",
        "destination_audit_id": audit_id,
        "destination_run_phase": phase,
        "approval_token_imported": False,
        "approval_authority": (
            "NONE. A token authorises one execution of one plan in one "
            "revision. R8's own gated phases require fresh human tokens."),
    }
    packet["migration_packet_sha256"] = migration.packet_digest(packet)
    return packet


def main():
    control_manifest = os.path.join(R7, "CONTROL_MANIFEST.sha256")
    control_sha = hashing.sha256_file(control_manifest)
    with open(control_manifest, encoding="utf-8") as handle:
        control_entries = sum(1 for line in handle if line.strip())

    packets = [build_packet(a, p, control_entries, control_sha)
               for a, p in MIGRATABLE]

    progress = json.load(open(os.path.join(R7, "state", "progress.json"),
                              encoding="utf-8"))
    excluded = []
    for (audit_id, phase), reason in sorted(EXCLUDED.items()):
        node = progress["audits"][audit_id][phase]
        directory = os.path.join(R7, "evidence", audit_id, phase)
        files = sum(len(f) for _, _, f in os.walk(directory))
        excluded.append({
            "audit_id": audit_id, "run_phase": phase,
            "state": node.get("state"),
            "sealed": False,
            "evidence_file_count": files,
            "exclusion_reason": reason,
            "measured": ("state is %s, no seal exists, and the phase produced "
                         "%d evidence files" % (node.get("state"), files)),
        })

    plan = {
        "schema": "wpno.level1.migration-plan/1",
        "revision": "R8",
        "predecessor": "R7",
        "prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "applied_before_freeze": False,
        "route": "import-sealed-predecessor-attempt",
        "route_module": "automation/migration.py",
        "route_module_sha256": hashing.sha256_file(
            os.path.join(ROOT, "automation", "migration.py")),
        "post_freeze_resume_sequence": [
            "freeze R8",
            "verify the R8 frozen control manifest",
            "apply this migration packet once, through the controller route",
            "verify the imported RUN-A and RUN-B",
            "require L1-A31 RUN-A SEALED / UNVERIFIED",
            "require L1-A31 RUN-B SEALED / UNVERIFIED",
            "require L1-A31 COMPARISON NOT_STARTED",
            "prepare L1-A31 COMPARISON",
            "request a new R8 phase approval token",
            "execute the comparison through the repaired controller",
        ],
        "migratable_attempts": packets,
        "excluded_attempts": excluded,
        "r8_lineage_record_sha256": hashing.sha256_file(
            os.path.join(ROOT, "lineage", "R8_LINEAGE.json")),
    }

    path_policy.ensure_dir(OUT_DIR)
    out = os.path.join(OUT_DIR, "MIGRATION_PLAN.json")
    text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(out), "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashing.sha256_text(text)
    with open(path_policy.assert_writable(
            os.path.join(OUT_DIR, "MIGRATION_PLAN.sha256")), "w",
            encoding="utf-8") as fh:
        fh.write("%s  MIGRATION_PLAN.json\n" % digest)

    # Each packet also written alone, because the route takes one packet.
    for packet in packets:
        name = "PACKET_%s_%s.json" % (packet["source_audit_id"],
                                      packet["source_run_phase"])
        body = json.dumps({k: v for k, v in packet.items()
                           if k != "migration_packet_sha256"},
                          indent=2, sort_keys=True) + "\n"
        payload = json.loads(body)
        payload["migration_packet_sha256"] = packet["migration_packet_sha256"]
        with open(path_policy.assert_writable(os.path.join(OUT_DIR, name)),
                  "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")

    print(json.dumps({
        "migration_plan": os.path.relpath(out, ROOT),
        "migration_plan_sha256": digest,
        "migratable": ["%s/%s" % (p["source_audit_id"], p["source_run_phase"])
                       for p in packets],
        "packet_digests": {p["source_attempt_id"]:
                           p["migration_packet_sha256"] for p in packets},
        "excluded": {"%s/%s" % (e["audit_id"], e["run_phase"]):
                     e["exclusion_reason"] for e in excluded},
        "applied_before_freeze": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
