"""Command-line entry for L1-A19 RUN-B. Frozen code, run as a subprocess.

Contains no validation logic, exactly as `a19_run_b` contains none: it hands
the values to the Java validator and writes back what the Java validator said.
It imports `a19_run_a` nowhere, and the import list below is the evidence.

A non-string input has no representation on the Java boundary. It is recorded
as NOT_A_STRING here, before the boundary, rather than silently dropped - an
input that disappears is an input the run did not answer, and RUN-A and RUN-B
must answer the same number of inputs for the comparison to mean anything.
"""

import argparse
import json
import sys

from . import a19_run_b, hashing, path_policy


def main(argv=None):
    parser = argparse.ArgumentParser(prog="a19-run-b")
    parser.add_argument("--vectors", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    vectors_path = path_policy.assert_readable(args.vectors)
    out_path = path_policy.assert_writable(args.out)

    vectors = []
    with open(vectors_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                vectors.append(json.loads(line))

    passable = [v for v in vectors if isinstance(v["raw"], str)]
    non_strings = [v for v in vectors if not isinstance(v["raw"], str)]

    java_results, argv_used = a19_run_b.validate_all(
        [v["raw"] for v in passable], args.work_dir)

    results = []
    for vector, outcome in zip(passable, java_results):
        results.append({
            "raw": vector["raw"],
            "scope": vector["scope"],
            "expected_result": vector["expected_result"],
            "expected_result_provenance": vector["expected_result_provenance"],
            "actual": outcome,
            "agrees": outcome["result"] == vector["expected_result"],
        })
    for vector in non_strings:
        outcome = {"raw": None, "compacted": None, "final_intermediate": -1,
                   "result": "INVALID_NOT_A_STRING",
                   "decided": "BEFORE_THE_JAVA_BOUNDARY"}
        results.append({
            "raw": vector["raw"],
            "scope": vector["scope"],
            "expected_result": vector["expected_result"],
            "expected_result_provenance": vector["expected_result_provenance"],
            "actual": outcome,
            "agrees": outcome["result"] == vector["expected_result"],
        })

    agreeing = sum(1 for r in results if r["agrees"])
    payload = {
        "schema": "wpno.level1.a19-run-b/1",
        "method": ("Java ISO/IEC 7064 MOD 11,10 verification form: fold all "
                   "eleven digits, require the final intermediate to be 1"),
        "argv": argv_used,
        "vectors_path": vectors_path,
        "vectors_sha256": hashing.sha256_file(vectors_path),
        "inputs_passed_to_java": len(passable),
        "inputs_decided_before_the_boundary": len(non_strings),
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
        "inputs_passed_to_java": len(passable),
        "inputs_decided_before_the_boundary": len(non_strings),
        "agreeing_with_reference": agreeing,
        "disagreeing_with_reference": len(results) - agreeing,
        "out": out_path,
        "out_sha256": hashing.sha256_file(out_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
