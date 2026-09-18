#!/usr/bin/env python3
"""Derive the actual 35-audit Level-1 scope from the package's own sources.

Section 5. The scope is not authored here; it is read. Four sources, each of
which can contradict the others, and a contradiction is the finding:

  audit_registry.json   the controller-owned execution order and replications
  bindings/*.json       the target, its digest and the external evidence
  prompts/*.md          the written specification of each audit
  automation/           the phase rules the controller actually applies

The phase list per audit comes from `state_machine.phase_order`, the function
the controller calls, not from a rule restated here. A rule restated is a rule
that can drift; R6 lost an audit to exactly that class of error.

Every extracted field records where it came from. Where the prompt says one
thing and the registry another, both values are kept and the audit is marked
contradictory rather than reconciled silently.
"""

import ast
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from automation import state_machine  # noqa: E402

OUT_DIR = os.path.join(ROOT, "build", "all_level1_scope")

EXPECTED_AUDIT_COUNT = 35

# The bindings were written on the operator's Mac. This package runs on
# Ubuntu. The prefix is data, not a guess: paths.json resolves PROJECT_ROOT,
# and every binding path begins with the Mac spelling of it.
MAC_PROJECT_ROOT = "/Users/martinotten/WPNO"

# Supplied and accepted at intake. references/manifest.json is the authority;
# this list is checked against it rather than trusted.
REFERENCE_MANIFEST = os.path.join(ROOT, "references", "manifest.json")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_root():
    with open(os.path.join(ROOT, "paths.json"), encoding="utf-8") as fh:
        paths = json.load(fh)
    value = paths["project_root"]
    if value.startswith("/"):
        return os.path.realpath(value)
    return os.path.realpath(os.path.join(ROOT, value))


PROJECT_ROOT = project_root()


def localise(mac_path):
    """A binding path, spelled for this machine. Never invented."""
    if mac_path.startswith(MAC_PROJECT_ROOT):
        return os.path.join(PROJECT_ROOT,
                            mac_path[len(MAC_PROJECT_ROOT):].lstrip("/"))
    return mac_path


def sections(text):
    """The prompt's `## HEADING` sections, in order, as {heading: body}."""
    out = {}
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    for i in range(1, len(parts), 2):
        out[parts[i].strip()] = parts[i + 1].strip()
    return out


def fenced(body):
    """The first ```text fence in a section body, stripped."""
    match = re.search(r"```text\n(.*?)\n```", body, re.S)
    return match.group(1).strip() if match else None


def operation_tokens(body):
    """Operation names from a section. Only backticked UPPER_SNAKE tokens and
    the contents of a text fence count; prose naming an operation does not."""
    tokens = set(re.findall(r"`([A-Z][A-Z0-9_]{3,})`", body))
    fence = fenced(body)
    if fence:
        # Operation names only. The GATED OPERATIONS section also carries the
        # approval-token template in a fence, and taking every fence line
        # reported "APPROVE-EXECUTION L1-Axx RUN=..." as an operation missing
        # from the catalogue - in all 35 audits at once, which is the shape of
        # a measuring error rather than a finding.
        tokens |= {line.strip() for line in fence.splitlines()
                   if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", line.strip())}
    return sorted(tokens)


def reference_ids(*bodies):
    found = set()
    for body in bodies:
        found |= set(re.findall(r"\bREF-\d{2}\b", body or ""))
    return sorted(found)


def declared_replication(body):
    """The prompt's own REPLICATION REQUIREMENT, parsed from its fence."""
    fence = fenced(body) or ""
    reps = re.search(r"replications\s*=\s*(\d+)", fence)
    phases = re.search(r"phases:\s*(.+)", fence)
    return (
        int(reps.group(1)) if reps else None,
        # The prompts separate phase names with a middle dot, not a comma.
        # Splitting on the comma alone produced one element, "RUN-A \u00b7 RUN-B
        # \u00b7 COMPARISON", and reported four audits as contradicting a rule
        # they state exactly.
        tuple(p for p in re.split(r"[,\u00b7]", phases.group(1))
              for p in [p.strip()] if p) if phases else None,
    )


def dependencies(audit_id, binding, prompt_text):
    """Audits this one depends on, named by whoever names them."""
    found = {}
    for question in binding.get("unresolved_questions") or []:
        for other in re.findall(r"\bL1-A\d{2}\b", str(question)):
            if other != audit_id:
                found.setdefault(other, []).append(
                    {"source": "binding.unresolved_questions",
                     "text": str(question)})
    for line in prompt_text.splitlines():
        if "depends" not in line.lower() and "after" not in line.lower():
            continue
        for other in re.findall(r"\bL1-A\d{2}\b", line):
            if other != audit_id:
                found.setdefault(other, []).append(
                    {"source": "prompt", "text": line.strip()})
    return {k: found[k] for k in sorted(found)}


def measure_target(binding):
    """The target as it is on this machine, now."""
    declared = binding.get("productive_target")
    expected = binding.get("productive_target_sha256")
    if not declared:
        return {
            "declared_productive_target": None,
            "binding_status": binding.get("binding_status"),
            "candidate_paths": binding.get("candidate_paths") or [],
            "state": "NO_PRODUCTIVE_TARGET_IN_BINDING",
        }
    local = localise(declared)
    record = {
        "declared_productive_target": declared,
        "binding_status": binding.get("binding_status"),
        "local_path": local,
        "expected_sha256": expected,
        "candidate_paths": binding.get("candidate_paths") or [],
    }
    if not os.path.isfile(local):
        record["state"] = "TARGET_ABSENT_ON_THIS_MACHINE"
        record["measured_sha256"] = None
        return record
    measured = sha256_file(local)
    record["measured_sha256"] = measured
    record["state"] = ("TARGET_PRESENT_HASH_MATCHES" if measured == expected
                       else "TARGET_PRESENT_HASH_DIFFERS")
    return record


def supplied_reference_ids():
    with open(REFERENCE_MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    return sorted(manifest.get("ref_ids") or [])


def build():
    with open(os.path.join(ROOT, "audit_registry.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    entries = registry["audits"]

    supplied = supplied_reference_ids()
    audits = []
    problems = []
    seen_ids = {}

    for entry in sorted(entries, key=lambda e: e["execution_order"]):
        audit_id = entry["audit_id"]
        seen_ids[audit_id] = seen_ids.get(audit_id, 0) + 1

        binding_path = os.path.join(ROOT, entry["binding_file"])
        prompt_path = os.path.join(ROOT, entry["prompt_file"])
        if not os.path.isfile(binding_path):
            problems.append("%s: binding file absent: %s" % (audit_id, entry["binding_file"]))
            continue
        if not os.path.isfile(prompt_path):
            problems.append("%s: prompt file absent: %s" % (audit_id, entry["prompt_file"]))
            continue

        with open(binding_path, encoding="utf-8") as fh:
            binding = json.load(fh)
        with open(prompt_path, encoding="utf-8") as fh:
            prompt_text = fh.read()
        sect = sections(prompt_text)

        phases = list(state_machine.phase_order(entry["replications"]))
        prompt_reps, prompt_phases = declared_replication(
            sect.get("REPLICATION REQUIREMENT", ""))

        conflicts = []
        if prompt_reps is not None and prompt_reps != entry["replications"]:
            conflicts.append({
                "field": "replications",
                "registry": entry["replications"],
                "prompt": prompt_reps})
        if prompt_phases is not None and list(prompt_phases) != phases:
            conflicts.append({
                "field": "phases",
                "controller_derived": phases,
                "prompt": list(prompt_phases)})
        if binding.get("execution_order") != entry["execution_order"]:
            conflicts.append({
                "field": "execution_order",
                "registry": entry["execution_order"],
                "binding": binding.get("execution_order")})
        if binding.get("replications") != entry["replications"]:
            conflicts.append({
                "field": "replications",
                "registry": entry["replications"],
                "binding": binding.get("replications")})
        prompt_id = fenced(sect.get("AUDIT ID", "") or "")
        if prompt_id and prompt_id != audit_id:
            conflicts.append({"field": "audit_id", "registry": audit_id,
                              "prompt": prompt_id})

        binding_refs = list(binding.get("external_evidence_required") or [])
        prompt_refs = reference_ids(prompt_text)
        required_refs = sorted(set(binding_refs) | set(prompt_refs))

        audits.append({
            "audit_id": audit_id,
            "controller_order": entry["execution_order"],
            "title": entry["title"],
            "risk": entry["risk"],
            "source_point": entry["source_point"],
            "source_group": entry["source_group"],

            "required_phases": phases,
            "required_phase_count": len(phases),
            "phase_rule_source": ("automation.state_machine.phase_order(%d)"
                                  % entry["replications"]),
            "replications": entry["replications"],

            "target": measure_target(binding),

            "required_references": [
                {"ref_id": ref,
                 "named_by": sorted(
                     ([] if ref not in binding_refs else ["binding"])
                     + ([] if ref not in prompt_refs else ["prompt"])),
                 "supplied_at_intake": ref in supplied}
                for ref in required_refs],

            "required_method": {
                "allowed_operations": operation_tokens(
                    sect.get("ALLOWED OPERATIONS", "")),
                "gated_operations": operation_tokens(
                    sect.get("GATED OPERATIONS", "")),
                "forbidden_operations": operation_tokens(
                    sect.get("FORBIDDEN OPERATIONS", "")),
                "independent_oracle": sect.get("INDEPENDENT ORACLE", "").strip(),
                "static_analysis_required": bool(sect.get("STATIC ANALYSIS")),
                "runtime_matrix_required": bool(sect.get("RUNTIME TEST MATRIX")),
            },

            "required_controls": {
                "positive": sect.get("POSITIVE CONTROL", "").strip(),
                "negative": sect.get("NEGATIVE CONTROL", "").strip(),
                "mutation": sect.get("MUTATION CONTROL", "").strip(),
            },

            "required_comparison": {
                "comparison_phase_required": "COMPARISON" in phases,
                "why": ("replications=%d, so state_machine.phase_order returns "
                        "%s" % (entry["replications"], phases)),
            },

            "required_final_verdict": {
                "pass_criteria": sect.get("PASS CRITERIA", "").strip(),
                "pass_with_warnings_criteria":
                    sect.get("PASS_WITH_WARNINGS CRITERIA", "").strip(),
                "fail_criteria": sect.get("FAIL CRITERIA", "").strip(),
                "blocked_criteria": sect.get("BLOCKED CRITERIA", "").strip(),
                "unverified_criteria": sect.get("UNVERIFIED CRITERIA", "").strip(),
            },

            "dependencies": dependencies(audit_id, binding, prompt_text),

            "final_completion_rule": {
                "rule": ("The audit counts as complete only when every phase in "
                         "required_phases is sealed and the audit's final "
                         "verdict is exactly PASS."),
                "phases_that_must_seal": phases,
                "verdicts_that_do_not_complete": [
                    "PASS_WITH_WARNINGS", "FAIL", "BLOCKED", "UNVERIFIED",
                    "ERROR", "CONTAMINATED"],
                "source": "operator instruction Section 17; prompt PASS CRITERIA",
            },

            "unresolved_questions": binding.get("unresolved_questions") or [],
            "specification_conflicts": conflicts,
            "prompt_file": entry["prompt_file"],
            "prompt_sha256": sha256_file(prompt_path),
            "binding_file": entry["binding_file"],
            "binding_sha256": sha256_file(binding_path),
        })

    duplicates = sorted(k for k, v in seen_ids.items() if v > 1)
    known = {a["audit_id"] for a in audits}
    unknown = sorted(k for k in seen_ids if not re.fullmatch(r"L1-A\d{2}", k))
    orders = [a["controller_order"] for a in audits]

    counts = {
        "EXPECTED_AUDIT_COUNT": EXPECTED_AUDIT_COUNT,
        "DISCOVERED_AUDIT_COUNT": len(audits),
        "DUPLICATE_AUDIT_IDS": len(duplicates),
        "UNKNOWN_AUDIT_IDS": len(unknown),
        "MISSING_SPECIFICATIONS": sum(1 for p in problems if "prompt file absent" in p),
        "MISSING_BINDINGS": sum(1 for p in problems if "binding file absent" in p),
    }

    contradictions = [
        {"audit_id": a["audit_id"], "conflicts": a["specification_conflicts"]}
        for a in audits if a["specification_conflicts"]]

    phase_total = sum(a["required_phase_count"] for a in audits)

    report = {
        "schema": "wpno.level1.all35-scope/1",
        "revision": "R8",
        "platform": "UBUNTU",
        "level1_root": ROOT,
        "project_root": PROJECT_ROOT,
        "sources": {
            "registry": "audit_registry.json",
            "registry_sha256": sha256_file(os.path.join(ROOT, "audit_registry.json")),
            "phase_rule": "automation/state_machine.py::phase_order",
            "phase_rule_sha256": sha256_file(
                os.path.join(ROOT, "automation", "state_machine.py")),
            "references_manifest_sha256": sha256_file(REFERENCE_MANIFEST),
        },
        "counts": counts,
        "order_is_unique_1_to_n": orders == list(range(1, len(orders) + 1)),
        "required_phase_total": phase_total,
        "phase_totals_by_kind": {
            kind: sum(1 for a in audits for p in a["required_phases"] if p == kind)
            for kind in ("RUN-A", "RUN-B", "COMPARISON")},
        "supplied_reference_ids": supplied,
        "problems": problems,
        "specification_contradictions": contradictions,
        "audits": audits,
    }
    report["scope_contradiction"] = bool(contradictions) or bool(problems)
    return report


def markdown(report):
    lines = []
    add = lines.append
    add("# R7 — the actual Level-1 scope, all 35 audits")
    add("")
    add("Derived, not authored. Every column below is read from the package's "
        "own registry, bindings, prompts and phase rules; the generator is "
        "`build/all_level1_scope/build_all_level1_scope.py`.")
    add("")
    counts = report["counts"]
    for key in ("EXPECTED_AUDIT_COUNT", "DISCOVERED_AUDIT_COUNT",
                "DUPLICATE_AUDIT_IDS", "UNKNOWN_AUDIT_IDS",
                "MISSING_SPECIFICATIONS", "MISSING_BINDINGS"):
        add("    %s=%d" % (key, counts[key]))
    add("")
    add("Required phases in total: **%d** — %d RUN-A, %d RUN-B, %d COMPARISON."
        % (report["required_phase_total"],
           report["phase_totals_by_kind"]["RUN-A"],
           report["phase_totals_by_kind"]["RUN-B"],
           report["phase_totals_by_kind"]["COMPARISON"]))
    add("")
    add("Execution order is a unique 1..N sequence: %s."
        % report["order_is_unique_1_to_n"])
    add("")
    if report["specification_contradictions"]:
        add("## Specification contradictions")
        add("")
        for row in report["specification_contradictions"]:
            add("- **%s**: %s" % (row["audit_id"], json.dumps(row["conflicts"])))
        add("")
    else:
        add("No audit's written specification contradicts the controller-owned "
            "order, replication count or phase rule.")
        add("")

    add("## Per audit")
    add("")
    add("| # | audit | phases | target state | refs required | refs missing | deps |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    for a in report["audits"]:
        missing = [r["ref_id"] for r in a["required_references"]
                   if not r["supplied_at_intake"]]
        add("| %d | %s | %s | %s | %s | %s | %s |" % (
            a["controller_order"], a["audit_id"], " ".join(a["required_phases"]),
            a["target"]["state"],
            " ".join(r["ref_id"] for r in a["required_references"]) or "—",
            " ".join(missing) or "—",
            " ".join(a["dependencies"]) or "—"))
    add("")
    add("`target state` is measured on this machine at generation time, not "
        "copied from the binding. `refs missing` names a reference the audit "
        "requires that intake has not accepted; it is a statement about this "
        "package's contents, not about whether the material exists.")
    add("")
    return "\n".join(lines) + "\n"


def main():
    report = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    json_path = os.path.join(OUT_DIR, "R7_LEVEL1_35_AUDIT_SCOPE.json")
    md_path = os.path.join(OUT_DIR, "R7_LEVEL1_35_AUDIT_SCOPE.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(markdown(report))

    counts = report["counts"]
    for key in ("EXPECTED_AUDIT_COUNT", "DISCOVERED_AUDIT_COUNT",
                "DUPLICATE_AUDIT_IDS", "UNKNOWN_AUDIT_IDS",
                "MISSING_SPECIFICATIONS", "MISSING_BINDINGS"):
        print("%s=%d" % (key, counts[key]))
    print("REQUIRED_PHASE_TOTAL=%d" % report["required_phase_total"])
    print("SPECIFICATION_CONTRADICTIONS=%d"
          % len(report["specification_contradictions"]))
    for row in report["specification_contradictions"]:
        print("  %s %s" % (row["audit_id"], json.dumps(row["conflicts"])))
    if report["scope_contradiction"]:
        print("STOP_LEVEL1_SCOPE_CONTRADICTION")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
