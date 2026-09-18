"""Command-line entry for L1-A18 RUN-B. Frozen code, run as a subprocess.

Contains no validation logic, exactly as `a18_run_b` contains none: it hands
the values to the Java validator and writes back what the Java validator said.
It imports `a18_run_a` nowhere, and the import list below is the evidence.
"""

import argparse
import json
import sys

from . import a18_run_b, hashing, path_policy


def main(argv=None):
    parser = argparse.ArgumentParser(prog="a18-run-b")
    parser.add_argument("--vectors", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    vectors_path = path_policy.assert_readable(args.vectors)
    rules_path = path_policy.assert_readable(args.rules)
    out_path = path_policy.assert_writable(args.out)

    vectors = []
    with open(vectors_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                vectors.append(json.loads(line))
    applicable = [v for v in vectors
                  if v.get("applicable_to_iso13616_validator")]

    # The empty string is appended as a value, not omitted, so RUN-B answers
    # the same number of inputs RUN-A does and the two are comparable.
    values = [v["iban_raw"] for v in applicable] + [""]

    results, argv_used = a18_run_b.validate_all(values, args.work_dir,
                                                rules_path)

    payload = {
        "schema": "wpno.level1.a18-run-b/1",
        "method": "Java 21 expanded-digit-string big-integer modulus",
        "argv": argv_used,
        "vectors_path": vectors_path,
        "vectors_sha256": hashing.sha256_file(vectors_path),
        "rules_path": rules_path,
        "rules_sha256": hashing.sha256_file(rules_path),
        "applicable_vector_count": len(applicable),
        "total_inputs_answered": len(results),
        "empty_input_result": results[-1] if results else None,
        "results": [
            {"iban_raw": value, "actual": result}
            for value, result in zip(values, results)
        ],
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "applicable_vector_count": len(applicable),
        "total_inputs_answered": len(results),
        "empty_input_counted": True,
        "out": out_path,
        "out_sha256": hashing.sha256_file(out_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
