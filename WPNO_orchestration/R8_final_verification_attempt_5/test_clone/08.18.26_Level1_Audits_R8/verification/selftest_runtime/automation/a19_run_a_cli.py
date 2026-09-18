"""Command-line entry for L1-A19 RUN-A. Frozen code, run as a subprocess.

A module rather than a script under `work/`, for the reason the operation
catalogue records: `PYTHON_SCRIPT_RUN_SANDBOX` requires its script to live
under `work/`, which is outside the control manifest, and a frozen package
that runs unfrozen code is not frozen. L1-A18 RUN-A is arranged the same way.

The sabotage control lives here rather than in a second copy of the validator.
CLAUDE.md section 10 records the same file in several places as a cause, not
an inconvenience: one implementation, one switch, and the switch is visible in
the argv.
"""

import argparse
import json
import sys

from . import a19_run_a, hashing, path_policy


def _sabotaged_check_digit(first_ten):
    """A deliberately wrong modulus. Must change the answers, and be seen to."""
    p = 10
    for ch in first_ten:
        m = (int(ch) + p) % 10
        if m == 0:
            m = 10
        p = (2 * m) % 10                      # 10, not 11
    return (11 - p) % 10


def _sabotaged_repetition(first_ten):
    """A structural rule that accepts everything. Must change the answers."""
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(prog="a19-run-a")
    parser.add_argument("--vectors", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sabotage", choices=["mod_11_10", "repetition"],
                        default=None,
                        help="run the sabotage control instead of the method")
    args = parser.parse_args(argv)

    vectors_path = path_policy.assert_readable(args.vectors)
    out_path = path_policy.assert_writable(args.out)

    vectors = []
    with open(vectors_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                vectors.append(json.loads(line))

    restore = None
    restore_name = None
    if args.sabotage == "mod_11_10":
        restore_name = "mod_11_10_check_digit"
        restore = a19_run_a.mod_11_10_check_digit
        a19_run_a.mod_11_10_check_digit = _sabotaged_check_digit
    elif args.sabotage == "repetition":
        restore_name = "repetition_rule_satisfied"
        restore = a19_run_a.repetition_rule_satisfied
        a19_run_a.repetition_rule_satisfied = _sabotaged_repetition

    try:
        results = []
        for vector in vectors:
            raw = vector["raw"]
            outcome = a19_run_a.validate(raw)
            results.append({
                "raw": raw,
                "scope": vector["scope"],
                "expected_result": vector["expected_result"],
                "expected_result_provenance":
                    vector["expected_result_provenance"],
                "actual": outcome,
                "agrees": outcome["result"] == vector["expected_result"],
            })
    finally:
        if restore is not None:
            setattr(a19_run_a, restore_name, restore)

    agreeing = sum(1 for r in results if r["agrees"])
    payload = {
        "schema": "wpno.level1.a19-run-a/1",
        "method": ("python ISO/IEC 7064 MOD 11,10 generation form: fold the "
                   "first ten digits, produce the eleventh, compare"),
        "formula_source": ("REF-03 official ELSTER specification; the REF-03 "
                           "ISO item is an eleven-page preview without the "
                           "operational clauses and is not the source of the "
                           "calculation"),
        "sabotage": args.sabotage,
        "vectors_path": vectors_path,
        "vectors_sha256": hashing.sha256_file(vectors_path),
        "total_inputs_answered": len(results),
        "agreeing_with_reference": agreeing,
        "disagreeing_with_reference": len(results) - agreeing,
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "total_inputs_answered": len(results),
        "agreeing_with_reference": agreeing,
        "disagreeing_with_reference": len(results) - agreeing,
        "sabotage": args.sabotage,
        "out": out_path,
        "out_sha256": hashing.sha256_file(out_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
