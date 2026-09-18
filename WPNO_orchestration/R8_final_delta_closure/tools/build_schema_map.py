#!/usr/bin/env python3
"""Enumerate the real keys of every source the verifiers will read.

Attempt 8 died because a predicate asked a JSON object for
`IN_PROCESS_HANDLER_INVOCATIONS` when the object holds
`R8_IN_PROCESS_HANDLER_INVOCATIONS`. The lookup was a guess, the guess was
wrong, and nothing between the guess and the verdict could tell.

So no predicate in this closure names a key that has not first been proved to
exist here, by opening the file and listing what is in it. There are no
fallbacks and no unprefixed aliases: a fallback would let a wrong name pass by
finding something else, which is the same defect with a softer landing.

Usage: build_schema_map.py <r8> <attempt8_root> <out.json>
"""

import hashlib
import json
import os
import sys


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def kind(value):
    return type(value).__name__


def sample(value):
    if isinstance(value, (dict, list)):
        return "<%s len %d>" % (kind(value), len(value))
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def field(source, json_path, key, container, notes=None):
    present = isinstance(container, dict) and key in container
    row = {
        "SOURCE_FILE": source,
        "JSON_PATH": json_path,
        "KEY_NAME": key,
        "VALUE_TYPE": kind(container[key]) if present else None,
        "VALUE_PRESENT": present,
        "SAMPLE_VALUE": sample(container[key]) if present else None,
    }
    if notes:
        row["NOTE"] = notes
    return row


def main():
    r8, a8, out_path = (os.path.realpath(sys.argv[1]),
                        os.path.realpath(sys.argv[2]), sys.argv[3])
    fields = []
    sources = {}

    def load(rel, root=None):
        path = os.path.join(root or r8, rel)
        sources[path] = sha256_file(path)
        with open(path, encoding="utf-8") as fh:
            return path, json.load(fh)

    # ---- the record attempt 8 got wrong ---------------------------------
    p, recon = load(os.path.join("build",
                                 "IN_PROCESS_COUNT_RECONCILIATION.json"))
    for key in sorted(recon):
        fields.append(field(p, "$", key, recon))

    # ---- the rehearsal aggregate ----------------------------------------
    p, reh = load(os.path.join("work", "_rehearsal_r8",
                               "REHEARSAL_REPORT.json"))
    for key in ("IN_PROCESS_HANDLER_INVOCATIONS", "IN_PROCESS_STEP_COUNT",
                "NOTE_ONLY_IN_PROCESS_STEPS",
                "REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE",
                "HOLLOW_PHASES", "LIVE_STATE_UNCHANGED", "phases_rehearsed",
                "phases_required", "all_pass_ready", "steps_total",
                "steps_executed", "reports"):
        fields.append(field(p, "$", key, reh))
    if isinstance(reh.get("reports"), list) and reh["reports"]:
        r0 = reh["reports"][0]
        for key in sorted(r0):
            fields.append(field(p, "$.reports[*]", key, r0))
        steps = r0.get("steps")
        if isinstance(steps, list) and steps:
            for key in sorted(steps[0]):
                fields.append(field(p, "$.reports[*].steps[*]", key, steps[0]))

    # ---- the other R8 sources the delta reads ---------------------------
    p, cov = load(os.path.join("build", "candidate_plans_r8",
                               "PLAN_COVERAGE_MANIFEST.json"))
    for key in ("REQUIRED_PLAN_COUNT", "CANDIDATE_PLAN_COUNT",
                "MISSING_PLAN_COUNT", "DUPLICATE_PLAN_COUNT",
                "UNKNOWN_PLAN_COUNT", "plans"):
        fields.append(field(p, "$", key, cov))

    p, ctrl = load(os.path.join("build", "CONTROL_EXPECTATION_COVERAGE.json"))
    for key in sorted(k for k in ctrl if not isinstance(ctrl[k], list)):
        fields.append(field(p, "$", key, ctrl))

    p, prog = load(os.path.join("state", "progress.json"))
    fields.append(field(p, "$", "audits", prog))
    fields.append(field(p, "$", "halt_critical", prog))
    first_audit = next(iter(prog["audits"].values()))
    first_phase = next(iter(first_audit.values()))
    for key in sorted(first_phase):
        fields.append(field(p, "$.audits[*][*]", key, first_phase))

    p, mig = load(os.path.join("build", "migration_plan_r7_to_r8",
                               "MIGRATION_PLAN.json"))
    for key in sorted(k for k in mig if not isinstance(mig[k], (list, dict))):
        fields.append(field(p, "$", key, mig))
    for key in ("migratable_attempts", "excluded_attempts",
                "post_freeze_resume_sequence"):
        fields.append(field(p, "$", key, mig))

    p, lin = load(os.path.join("lineage", "R8_LINEAGE.json"))
    for key in sorted(lin):
        fields.append(field(p, "$", key, lin))
    if isinstance(lin.get("r7"), dict):
        for key in sorted(lin["r7"]):
            fields.append(field(p, "$.r7", key, lin["r7"]))

    # ---- transitions: a JSONL, so the shape is per row -------------------
    tpath = os.path.join(r8, "state", "transitions.jsonl")
    sources[tpath] = sha256_file(tpath)
    rows = [json.loads(l) for l in open(tpath, encoding="utf-8") if l.strip()]
    fields.append({"SOURCE_FILE": tpath, "JSON_PATH": "$[*]",
                   "KEY_NAME": "<row count>", "VALUE_TYPE": "int",
                   "VALUE_PRESENT": True, "SAMPLE_VALUE": repr(len(rows))})
    if rows:
        for key in sorted(rows[0]):
            fields.append(field(tpath, "$[*]", key, rows[0]))

    # ---- attempt 8's durable records: the shape is NOT uniform ----------
    ipath = os.path.join(a8, "codex_output", "ITEM_RESULTS.jsonl")
    sources[ipath] = sha256_file(ipath)
    items = {}
    for line in open(ipath, encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
            items[rec["id"]] = rec
    shapes = {}
    for item_id, rec in sorted(items.items()):
        m = rec["measured"]
        shapes[item_id] = {
            "measured_type": kind(m),
            "measured_keys": sorted(m) if isinstance(m, dict) else None,
            "pass": rec["pass"],
        }
        fields.append({
            "SOURCE_FILE": ipath,
            "JSON_PATH": "$[id=%d].measured" % item_id,
            "KEY_NAME": "measured",
            "VALUE_TYPE": kind(m),
            "VALUE_PRESENT": True,
            "SAMPLE_VALUE": sample(m),
            "NOTE": ("items 1-8 and 10-17 record `measured` as a "
                     "semicolon-separated key=value STRING; items 9 and 18-35 "
                     "record it as an OBJECT. A predicate that indexes every "
                     "record as a dict raises TypeError on the strings."),
        })

    unresolved = [f for f in fields if not f["VALUE_PRESENT"]]
    doc = {
        "schema": "wpno.r8.delta-verifier-schema-map/1",
        "r8_root": r8,
        "attempt_8_root": a8,
        "rule": ("every key a predicate names must appear here with "
                 "VALUE_PRESENT true. No fallback, no unprefixed alias."),
        "source_digests": sources,
        "fields": fields,
        "field_count": len(fields),
        "attempt_8_item_shapes": shapes,
        "UNRESOLVED_KEY_LOOKUPS": len(unresolved),
        "unresolved": unresolved,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")

    required = ("R8_IN_PROCESS_HANDLER_INVOCATIONS",
                "R8_UNIQUE_IN_PROCESS_PLAN_STEPS")
    proved = {k: any(f["KEY_NAME"] == k and f["VALUE_PRESENT"] for f in fields)
              for k in required}
    print(json.dumps({"field_count": doc["field_count"],
                      "UNRESOLVED_KEY_LOOKUPS": doc["UNRESOLVED_KEY_LOOKUPS"],
                      "required_keys_proved_present": proved,
                      "measured_type_counts": {
                          t: sum(1 for s in shapes.values()
                                 if s["measured_type"] == t)
                          for t in sorted({s["measured_type"]
                                           for s in shapes.values()})}},
                     indent=1, sort_keys=True))
    if unresolved:
        for f in unresolved:
            print("  UNRESOLVED", f["SOURCE_FILE"], f["JSON_PATH"],
                  f["KEY_NAME"])
    return 0 if not unresolved and all(proved.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
