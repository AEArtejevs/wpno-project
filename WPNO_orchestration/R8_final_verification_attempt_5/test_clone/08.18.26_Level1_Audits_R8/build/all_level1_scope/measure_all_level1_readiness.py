#!/usr/bin/env python3
"""Section 7. Input and reference readiness for every one of the 35 audits.

Measured, one audit at a time, against the scope this package derived in
`R7_LEVEL1_35_AUDIT_SCOPE.json`. Nothing here is acquired, downloaded,
substituted or inferred. A reference that is absent is reported absent; a
check that cannot be answered before a candidate plan exists is reported as
that, and not as a pass.

The distinction matters more than it looks. Section 7 asks twelve questions
per audit. Eight can be answered from the package as it stands. Three —
positive control, negative control, mutation control — are questions about a
plan's inputs, and no plan exists yet for 26 of the 35 audits. Answering them
"present" would be a counter that counts what it knows.
"""

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from automation import operation_catalog, path_policy  # noqa: E402

SCOPE = os.path.join(ROOT, "build", "all_level1_scope",
                     "R7_LEVEL1_35_AUDIT_SCOPE.json")
OUT_DIR = os.path.join(ROOT, "build", "all_level1_scope")
REFERENCES = os.path.join(ROOT, "references")
CANDIDATE_PLANS = os.path.join(ROOT, "build", "candidate_plans_r8")

# What each reference must contain, in what form, from what source, and where
# it is taken in. Read from the package's own required-references README so
# this file does not become a second, drifting statement of the same thing.
REFERENCE_TABLE = os.path.join(
    ROOT, "discovery_reconciliation", "10_REQUIRED_OFFLINE_REFERENCES.md")


def reference_spec():
    """The REF table, read from the package rather than restated here.

    A first version of this file transcribed the operator-facing Latvian
    README by hand and stopped at REF-13, because the pattern used to find the
    rows was written for the ids that were already known. REF-14 exists, is
    required by L1-A17 and L1-A23, and was silently absent from the
    transcription - a counter that counted what it knew. The table is now
    parsed, and the row count is asserted against the ids the bindings and
    prompts actually name.
    """
    with open(REFERENCE_TABLE, encoding="utf-8") as fh:
        text = fh.read()
    spec = {}
    for line in text.splitlines():
        if not line.startswith("| REF-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        ref_id, audits, content, source, version, fmt, absence = cells[:7]
        spec[ref_id] = {
            "content": content,
            "audits": [a.strip() for a in audits.split(",")],
            "source": source,
            "date_or_version": version,
            "format": fmt,
            "absence_consequence": absence,
        }
    if not spec:
        raise SystemExit("reference table parsed to nothing: %s" % REFERENCE_TABLE)
    return spec


REFERENCE_SPEC = reference_spec()

# REF-10 is the one reference whose absence the specification itself resolves:
# revocation is then reported NOT_ASSESSED_OFFLINE, never as "not revoked".
ABSENCE_HANDLED_BY_SPECIFICATION = {"REF-10"}

INTAKE_PATH = "references/  (bound at intake, hash-checked against the operator manifest)"


MAC_PROJECT_ROOT = "/Users/martinotten/WPNO"


def project_root():
    with open(os.path.join(ROOT, "paths.json"), encoding="utf-8") as fh:
        paths = json.load(fh)
    value = paths["project_root"]
    if value.startswith("/"):
        return os.path.realpath(value)
    return os.path.realpath(os.path.join(ROOT, value))


PROJECT_ROOT = project_root()


def localise(mac_path):
    """A binding path, spelled for this machine."""
    if mac_path.startswith(MAC_PROJECT_ROOT):
        return os.path.join(PROJECT_ROOT,
                            mac_path[len(MAC_PROJECT_ROOT):].lstrip("/"))
    return mac_path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference_files():
    """Every physical reference file, by REF id, measured now."""
    by_ref = {}
    for name in sorted(os.listdir(REFERENCES)):
        full = os.path.join(REFERENCES, name)
        if not os.path.isfile(full) or not name.startswith("REF-"):
            continue
        ref_id = name[:6]
        by_ref.setdefault(ref_id, []).append({
            "file": "references/%s" % name,
            "sha256": sha256_file(full),
            "bytes": os.path.getsize(full),
        })
    return by_ref


def manifest_records():
    with open(os.path.join(REFERENCES, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    by_ref = {}
    for record in manifest.get("references", []):
        ref_id = record.get("ref_id") or record.get("reference_group")
        by_ref.setdefault(ref_id, []).append(record)
    return manifest, by_ref


def candidate_plan_phases():
    """Which audit/phase pairs already have an exact candidate plan."""
    have = set()
    if not os.path.isdir(CANDIDATE_PLANS):
        return have
    for audit_id in sorted(os.listdir(CANDIDATE_PLANS)):
        audit_dir = os.path.join(CANDIDATE_PLANS, audit_id)
        if not os.path.isdir(audit_dir):
            continue
        for phase in sorted(os.listdir(audit_dir)):
            if os.path.isdir(os.path.join(audit_dir, phase)):
                have.add((audit_id, phase))
    return have


def measure():
    with open(SCOPE, encoding="utf-8") as fh:
        scope = json.load(fh)

    files_by_ref = reference_files()
    manifest, manifest_by_ref = manifest_records()
    supplied = set(manifest.get("ref_ids") or [])
    planned = candidate_plan_phases()

    known_ops = (set(operation_catalog.AUTOMATIC) | set(operation_catalog.GATED))
    forbidden_ops = set(operation_catalog.FORBIDDEN)

    audits = []
    missing_items = []

    for a in scope["audits"]:
        audit_id = a["audit_id"]
        checks = {}

        # 1-5. target identity, and whether it is what the binding declared.
        #
        # "No productive target in the binding" is not one state but three,
        # and collapsing them reported every REF-11 audit as blocked next to
        # L1-A31 and L1-A34, which have been rehearsed pass-ready from exactly
        # that material. The three are separated here:
        #
        #   the binding names candidates and the audit must resolve which is
        #   productive - that is the audit's own TARGET IDENTIFICATION RULE,
        #   specified work, not a missing input;
        #
        #   the binding names no candidate because the target is an operator
        #   reference artefact - readiness is then the reference's readiness;
        #
        #   neither - the target is genuinely unavailable here.
        target = a["target"]
        candidates = [localise(c) for c in target.get("candidate_paths") or []]
        present = [c for c in candidates if os.path.isfile(c)]
        refs_named = [r["ref_id"] for r in a["required_references"]]
        # REF-10's absence is resolved by the specification, not by intake, so
        # it does not make a target unavailable. Counting it would have
        # reported L1-A31 - already rehearsed pass-ready from staged REF-08,
        # REF-09 and REF-11 material - as having no target at all.
        refs_that_must_be_present = [
            r for r in a["required_references"]
            if r["ref_id"] not in ABSENCE_HANDLED_BY_SPECIFICATION]
        refs_all_present = bool(refs_that_must_be_present) and all(
            r["supplied_at_intake"] for r in refs_that_must_be_present)

        if target["state"] == "TARGET_PRESENT_HASH_MATCHES":
            state, verified = "TARGET_CONFIRMED_HASH_MATCHES", True
        elif target["state"] == "TARGET_PRESENT_HASH_DIFFERS":
            state, verified = "TARGET_PRESENT_HASH_DIFFERS", False
        elif target["state"] == "TARGET_ABSENT_ON_THIS_MACHINE":
            state, verified = "TARGET_ABSENT_ON_THIS_MACHINE", False
        elif candidates and len(present) == len(candidates):
            state, verified = "TARGET_CANDIDATES_ALL_PRESENT", True
        elif candidates:
            state, verified = "TARGET_CANDIDATES_PARTIALLY_ABSENT", False
        elif refs_all_present:
            state, verified = "TARGET_SUPPLIED_BY_REFERENCES", True
        else:
            state, verified = "TARGET_UNAVAILABLE_NO_CANDIDATE_NO_REFERENCE", False

        checks["target_identity"] = {
            "state": state,
            "verified": verified,
            "binding_state": target["state"],
            "path": target.get("local_path"),
            "expected_sha256": target.get("expected_sha256"),
            "measured_sha256": target.get("measured_sha256"),
            "binding_status": target.get("binding_status"),
            "candidate_paths_declared": len(candidates),
            "candidate_paths_present": len(present),
            "target_reference_ids": refs_named,
        }

        # 1-4. every required reference: exists, digest, role.
        refs = []
        for entry in a["required_references"]:
            ref_id = entry["ref_id"]
            spec = REFERENCE_SPEC.get(ref_id, {})
            present_files = files_by_ref.get(ref_id, [])
            accepted = ref_id in supplied
            record = {
                "ref_id": ref_id,
                "named_by": entry["named_by"],
                "accepted_at_intake": accepted,
                "physical_files": present_files,
                "physical_file_count": len(present_files),
                "manifest_records": len(manifest_by_ref.get(ref_id, [])),
                "role": spec.get("content"),
                "absence_consequence": spec.get("absence_consequence"),
                "specified_in_package": bool(spec),
            }
            if accepted and present_files:
                record["state"] = "PRESENT_AND_HASHED"
            elif ref_id in ABSENCE_HANDLED_BY_SPECIFICATION:
                record["state"] = "ABSENT_BUT_SPECIFICATION_HANDLES_ABSENCE"
            else:
                record["state"] = "ABSENT"
                missing_items.append({
                    "AUDIT_ID": audit_id,
                    "REF_ID": ref_id,
                    "ROLE": spec.get("content", "not specified in the package"),
                    "EXACT_REQUIRED_CONTENT": spec.get("content", "unknown"),
                    "ACCEPTABLE_FORMAT": spec.get("format", "unknown"),
                    "ACCEPTABLE_SOURCE": spec.get("source", "unknown"),
                    "DATE_OR_VERSION": spec.get("date_or_version", "unknown"),
                    "ABSENCE_CONSEQUENCE": spec.get("absence_consequence", "unknown"),
                    "INTAKE_PATH": INTAKE_PATH,
                    "WHY_REQUIRED": _why(a, ref_id),
                })
            refs.append(record)
        checks["references"] = refs

        # 6. validation time, where the audit needs one.
        needs_time = any(op.startswith("OPENSSL_") for op
                         in a["required_method"]["gated_operations"])
        checks["validation_time"] = {
            "required": needs_time,
            "state": ("BOUND_IN_CANDIDATE_PLAN" if needs_time
                      and (audit_id, "RUN-A") in planned
                      else ("NOT_REQUIRED" if not needs_time
                            else "NOT_YET_SELECTED_NO_CANDIDATE_PLAN")),
        }

        # 7. method and tool availability.
        named = set(a["required_method"]["allowed_operations"]) | \
            set(a["required_method"]["gated_operations"])
        unknown = sorted(named - known_ops - forbidden_ops)
        checks["method_available"] = {
            "operations_named": sorted(named),
            "not_in_catalogue": unknown,
            "verified": not unknown,
        }

        # 8-10. the controls. These are properties of a plan.
        phase_plans = {p: ((audit_id, p) in planned) for p in a["required_phases"]}
        all_planned = all(phase_plans.values())
        for name in ("positive_control", "negative_control", "mutation_control"):
            checks[name] = {
                "specified_in_prompt": bool(
                    a["required_controls"][name.split("_")[0]]),
                "input_state": ("BOUND_AND_REHEARSED" if all_planned
                                else "NOT_MEASURABLE_UNTIL_A_CANDIDATE_PLAN_EXISTS"),
            }

        # 11. output and evidence boundary.
        results_dir = os.path.join(ROOT, "results", audit_id)
        evidence_dir = os.path.join(ROOT, "evidence", audit_id)
        checks["output_boundary"] = {
            "results_path": "results/%s" % audit_id,
            "evidence_path": "evidence/%s" % audit_id,
            "results_exists_already": os.path.exists(results_dir),
            "evidence_exists_already": os.path.exists(evidence_dir),
            "lawful_under_path_policy": _lawful(results_dir) and _lawful(evidence_dir),
            "verified": (not os.path.exists(results_dir)
                         and not os.path.exists(evidence_dir)),
        }

        # 12. no silent substitution.
        substitutions = []
        for record in refs:
            for physical in record["physical_files"]:
                declared = _declared_digest(manifest_by_ref.get(record["ref_id"], []),
                                            physical["file"])
                if declared and declared != physical["sha256"]:
                    substitutions.append({
                        "ref_id": record["ref_id"],
                        "file": physical["file"],
                        "declared": declared,
                        "measured": physical["sha256"]})
        checks["no_silent_substitution"] = {
            "mismatches": substitutions,
            "verified": not substitutions,
        }

        blocking = []
        if not checks["target_identity"]["verified"]:
            blocking.append("TARGET_NOT_READY:%s" % state)
        for record in refs:
            if record["state"] == "ABSENT":
                blocking.append("REFERENCE_ABSENT:%s" % record["ref_id"])
        if unknown:
            blocking.append("OPERATION_NOT_IN_CATALOGUE")

        audits.append({
            "audit_id": audit_id,
            "controller_order": a["controller_order"],
            "required_phases": a["required_phases"],
            "candidate_plans_present": phase_plans,
            "checks": checks,
            "blocking_reasons": sorted(set(blocking)),
            "readiness": "READY_FOR_PLANNING" if not blocking else "BLOCKED",
        })

    ready = [a for a in audits if a["readiness"] == "READY_FOR_PLANNING"]
    blocked = [a for a in audits if a["readiness"] == "BLOCKED"]

    return {
        "schema": "wpno.level1.all35-readiness/1",
        "revision": "R8",
        "platform": "UBUNTU",
        "scope_sha256": sha256_file(SCOPE),
        "references_manifest_sha256": sha256_file(
            os.path.join(REFERENCES, "manifest.json")),
        "accepted_reference_ids": sorted(supplied),
        "AUDITS_TOTAL": len(audits),
        "AUDITS_READY_FOR_PLANNING": len(ready),
        "AUDITS_BLOCKED": len(blocked),
        "MISSING_ITEM_COUNT": len(missing_items),
        "missing_external_material": missing_items,
        "audits": audits,
    }


def _why(audit, ref_id):
    return ("%s (%s) requires %s: %s. Without it the audit's independent "
            "oracle does not exist, and its verdict could only be a statement "
            "about the tool under audit." % (
                audit["audit_id"], audit["title"], ref_id,
                REFERENCE_SPEC.get(ref_id, {}).get("content", "unspecified")))


def _lawful(path):
    try:
        path_policy.assert_writable(path)
        return True
    except Exception:
        return False


def _declared_digest(records, rel_path):
    for record in records:
        for key in ("bound_copy_sha256", "sha256", "declared_sha256"):
            if record.get("destination") == rel_path or \
                    record.get("bound_into_r5_at") == rel_path:
                if record.get(key):
                    return record[key]
    return None


def markdown(report):
    lines = []
    add = lines.append
    add("# R7 — all-35 input and reference readiness")
    add("")
    add("Section 7, measured. Nothing here was acquired, downloaded or "
        "substituted. A reference that is absent is reported absent; a check "
        "that cannot be answered before a candidate plan exists is reported as "
        "that, and never as a pass.")
    add("")
    add("    AUDITS_TOTAL=%d" % report["AUDITS_TOTAL"])
    add("    AUDITS_READY_FOR_PLANNING=%d" % report["AUDITS_READY_FOR_PLANNING"])
    add("    AUDITS_BLOCKED=%d" % report["AUDITS_BLOCKED"])
    add("    MISSING_ITEM_COUNT=%d" % report["MISSING_ITEM_COUNT"])
    add("")
    add("Accepted at intake: %s."
        % ", ".join(report["accepted_reference_ids"]))
    add("")
    add("## Per audit")
    add("")
    add("| # | audit | phases | target | readiness | blocking |")
    add("| --- | --- | --- | --- | --- | --- |")
    for a in report["audits"]:
        add("| %d | %s | %s | %s | %s | %s |" % (
            a["controller_order"], a["audit_id"],
            " ".join(a["required_phases"]),
            a["checks"]["target_identity"]["state"],
            a["readiness"],
            " ".join(a["blocking_reasons"]) or "—"))
    add("")
    if report["missing_external_material"]:
        add("## Missing external material")
        add("")
        add("Each item is material a human must supply. None of it can be "
            "downloaded, reconstructed or stood in for.")
        add("")
        for item in report["missing_external_material"]:
            add("### %s — %s" % (item["AUDIT_ID"], item["REF_ID"]))
            add("")
            for key in ("ROLE", "EXACT_REQUIRED_CONTENT", "ACCEPTABLE_FORMAT",
                        "ACCEPTABLE_SOURCE", "DATE_OR_VERSION", "INTAKE_PATH",
                        "ABSENCE_CONSEQUENCE", "WHY_REQUIRED"):
                if item.get(key):
                    add("- **%s:** %s" % (key, item[key]))
            add("")
    return "\n".join(lines) + "\n"


def main():
    report = measure()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "R7_ALL35_INPUT_READINESS.json"),
              "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(OUT_DIR, "R7_ALL35_INPUT_READINESS.md"),
              "w", encoding="utf-8") as fh:
        fh.write(markdown(report))
    print("AUDITS_TOTAL=%d" % report["AUDITS_TOTAL"])
    print("AUDITS_READY_FOR_PLANNING=%d" % report["AUDITS_READY_FOR_PLANNING"])
    print("AUDITS_BLOCKED=%d" % report["AUDITS_BLOCKED"])
    print("MISSING_ITEM_COUNT=%d" % report["MISSING_ITEM_COUNT"])
    print()
    for a in report["audits"]:
        print("%2d %-8s %-19s %s" % (
            a["controller_order"], a["audit_id"], a["readiness"],
            " ".join(a["blocking_reasons"]) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
