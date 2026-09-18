#!/usr/bin/env python3
"""Prove the delta verifier before a Codex attempt is spent on it.

Eight things must hold. Each is a run, not an assertion in prose.

  1 the correct prefixed keys are accepted
  2 a missing key is rejected
  3 a wrong key name is rejected
  4 a wrong type is rejected
  5 168 against an expected 169 is rejected
  6 169 against an expected 169 is accepted
  7 no KeyError can abort the verifier
  8 every predicate is evaluated once against a schema-valid fixture

(7) is the one attempt 8 needed. Its lookup raised `KeyError` and the process
died with twelve measurements unrecorded. Here every predicate is fed an empty
object and must raise `SchemaError` -- one controlled type the runner turns
into a recorded INVALID verdict. A `KeyError`, `TypeError` or `IndexError`
escaping any predicate fails this self-test and no Codex process is launched.

Usage:
  selftest_delta_verifier.py <r8> <clone> <schema_map> <tool_inventory>
                             <writer_inspection> <out.json>

The tool inventory and the writer inspection are passed in rather than
defaulted, because five predicates read them and a predicate evaluated against
an absent document has not been evaluated -- it has only been shown to notice
that the document is absent.
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import delta_context                                       # noqa: E402
import delta_predicates as dp                              # noqa: E402


def _sha256(path):
    if not path or not os.path.isfile(path):
        return None
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def run_predicate(name, docs):
    """The runner. A schema failure becomes a verdict, never a crash."""
    try:
        row = dp.PREDICATES[name](docs)
        row["OUTCOME"] = "PASS" if row["PASS"] else "FAIL"
        return row
    except dp.SchemaError as exc:
        return {"predicate": name, "OUTCOME": "INVALID_EVIDENCE",
                "PASS": False, "error": str(exc)}


def main():
    (r8, clone, schema_map_path, tool_inventory_path,
     writers_path, out_path) = (sys.argv[1], sys.argv[2], sys.argv[3],
                                sys.argv[4], sys.argv[5], sys.argv[6])
    with open(schema_map_path, encoding="utf-8") as fh:
        schema_map = json.load(fh)
    proved_keys = {f["KEY_NAME"] for f in schema_map["fields"]
                   if f["VALUE_PRESENT"]}

    docs = delta_context.build(r8, clone,
                               tool_inventory_path=tool_inventory_path,
                               writers_path=writers_path)
    cases = []

    def case(number, name, expectation, observed, ok, detail=None):
        row = {"case": number, "name": name, "expected": expectation,
               "observed": observed, "PASS": bool(ok)}
        if detail:
            row["detail"] = detail
        cases.append(row)

    # -- 1 / 6: the correct prefixed keys, correct values -------------------
    good = {"recon": {"R8_IN_PROCESS_HANDLER_INVOCATIONS": 169,
                      "R8_UNIQUE_IN_PROCESS_PLAN_STEPS": 169}}
    v = run_predicate("p_recon_handler_invocations", good)
    case(1, "correct prefixed key accepted", "PASS", v["OUTCOME"],
         v["OUTCOME"] == "PASS")
    case(6, "169 against expected 169 accepted", "PASS", v["OUTCOME"],
         v["OUTCOME"] == "PASS")
    v = run_predicate("p_recon_unique_steps", good)
    case("1b", "second prefixed key accepted", "PASS", v["OUTCOME"],
         v["OUTCOME"] == "PASS")

    # -- 2: a missing key -----------------------------------------------------
    v = run_predicate("p_recon_handler_invocations", {"recon": {}})
    case(2, "missing key rejected as INVALID_EVIDENCE", "INVALID_EVIDENCE",
         v["OUTCOME"], v["OUTCOME"] == "INVALID_EVIDENCE", v.get("error"))

    # -- 3: the wrong name -- attempt 8's exact defect ------------------------
    v = run_predicate("p_recon_handler_invocations",
                      {"recon": {"IN_PROCESS_HANDLER_INVOCATIONS": 169}})
    case(3, "attempt 8's unprefixed key name rejected", "INVALID_EVIDENCE",
         v["OUTCOME"], v["OUTCOME"] == "INVALID_EVIDENCE", v.get("error"))

    # -- 4: the wrong type ----------------------------------------------------
    v = run_predicate("p_recon_handler_invocations",
                      {"recon": {"R8_IN_PROCESS_HANDLER_INVOCATIONS": "169"}})
    case(4, "string where an int is required is rejected", "INVALID_EVIDENCE",
         v["OUTCOME"], v["OUTCOME"] == "INVALID_EVIDENCE", v.get("error"))
    v = run_predicate("p_recon_handler_invocations",
                      {"recon": {"R8_IN_PROCESS_HANDLER_INVOCATIONS": True}})
    case("4b", "bool where an int is required is rejected",
         "INVALID_EVIDENCE", v["OUTCOME"],
         v["OUTCOME"] == "INVALID_EVIDENCE", v.get("error"))
    v = run_predicate("p_recon_handler_invocations", {"recon": "not an object"})
    case("4c", "a string where an object is required is rejected",
         "INVALID_EVIDENCE", v["OUTCOME"],
         v["OUTCOME"] == "INVALID_EVIDENCE", v.get("error"))

    # -- 5: the wrong value ---------------------------------------------------
    v = run_predicate("p_recon_handler_invocations",
                      {"recon": {"R8_IN_PROCESS_HANDLER_INVOCATIONS": 168}})
    case(5, "168 against expected 169 rejected", "FAIL", v["OUTCOME"],
         v["OUTCOME"] == "FAIL",
         {"expected": v.get("expected"), "measured": v.get("measured")})

    # -- 7: nothing may escape as KeyError ------------------------------------
    escapes = []
    empty = {k: {} for k in ("recon", "rehearsal", "tool_inventory",
                             "writers", "lineage")}
    empty.update({"plans": [], "in_process_operations": set(),
                  "handlers": set(), "transitions": [],
                  "freeze_revision": None, "freeze_platform": None,
                  "lineage_baseline_sha256": None,
                  "baseline_file_sha256": None, "baseline_raised": True,
                  "baseline_project_members": 0,
                  "baseline_discovery_members": 0,
                  "token_roundtrip_ok": False, "token_field_count": 0,
                  "token_trailing_newline": True, "freeze_attempts": 0,
                  "mode": None, "r9_exists": False,
                  "tool_digest_mismatches": []})
    for name in sorted(dp.PREDICATES):
        try:
            run_predicate(name, empty)
        except Exception as exc:                            # noqa: BLE001
            escapes.append({"predicate": name,
                            "exception": type(exc).__name__, "message": str(exc)})
    case(7, "predicates raising an uncontrolled exception on an empty "
            "document", [], escapes, not escapes)

    # also feed a document of the wrong SHAPE entirely
    escapes_shape = []
    wrong = dict(empty)
    wrong.update({k: [] for k in ("recon", "rehearsal", "tool_inventory",
                                  "writers", "lineage")})
    for name in sorted(dp.PREDICATES):
        try:
            run_predicate(name, wrong)
        except Exception as exc:                            # noqa: BLE001
            escapes_shape.append({"predicate": name,
                                  "exception": type(exc).__name__})
    case("7b", "predicates raising an uncontrolled exception on a list where "
               "an object belongs", [], escapes_shape, not escapes_shape)

    # -- 8: every predicate once, against schema-valid real documents --------
    live = []
    for name in sorted(dp.PREDICATES):
        live.append(run_predicate(name, docs))
    evaluated = len(live)
    invalid = [r for r in live if r["OUTCOME"] == "INVALID_EVIDENCE"]
    case(8, "every predicate evaluated once against a schema-valid fixture",
         len(dp.PREDICATES), evaluated, evaluated == len(dp.PREDICATES))
    case("8b", "predicates returning INVALID_EVIDENCE on the real documents",
         [], [r["predicate"] for r in invalid], not invalid,
         [r.get("error") for r in invalid])

    # -- every key any predicate names must be in the schema map -------------
    unproved = sorted(k for k in ("R8_IN_PROCESS_HANDLER_INVOCATIONS",
                                  "R8_UNIQUE_IN_PROCESS_PLAN_STEPS",
                                  "R8_TOTAL_PLAN_STEPS",
                                  "IN_PROCESS_HANDLER_INVOCATIONS",
                                  "IN_PROCESS_STEP_COUNT",
                                  "NOTE_ONLY_IN_PROCESS_STEPS",
                                  "REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE",
                                  "HOLLOW_PHASES")
                      if k not in proved_keys)
    case("9", "keys named by predicates that the schema map does not prove "
              "present", [], unproved, not unproved)

    failed = [c for c in cases if not c["PASS"]]
    doc = {
        "schema": "wpno.r8.delta-verifier-selftest/1",
        "schema_map": schema_map_path,
        "schema_map_sha256": _sha256(schema_map_path),
        "tool_inventory": tool_inventory_path,
        "tool_inventory_sha256": _sha256(tool_inventory_path),
        "writer_inspection": writers_path,
        "writer_inspection_sha256": _sha256(writers_path),
        "cases": cases,
        "case_count": len(cases),
        "cases_passed": len(cases) - len(failed),
        "live_predicate_results": live,
        "PREDICATES_TESTED": "%d/%d" % (evaluated, len(dp.PREDICATES)),
        "UNRESOLVED_KEY_LOOKUPS": len(invalid),
        "DELTA_VERIFIER_SELF_TEST": "PASS" if not failed else "FAIL",
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "case_count", "cases_passed", "PREDICATES_TESTED",
        "UNRESOLVED_KEY_LOOKUPS", "DELTA_VERIFIER_SELF_TEST")}, indent=1,
        sort_keys=True))
    for c in failed:
        print("  FAILED CASE", c["case"], c["name"], "->", c["observed"])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
