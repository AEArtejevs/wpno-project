"""Command-line entry for L1-A18 RUN-A. Frozen code, run as a subprocess.

Why a module and not a script under `work/`. A plan step that runs a script
must name a path, and `PYTHON_SCRIPT_RUN_SANDBOX` requires that path to be
under `work/` — which is deliberately outside the control manifest, because
it is where runs write. A script living only there would be executable code
the freeze does not cover: the package would be frozen and the thing it runs
would not be. Running a frozen module by name instead keeps the code inside
the manifest and still produces a real subprocess with a real argv, real
stdout and real stderr in the evidence.

The sabotage control is here rather than in a separate copy of the validator,
for the reason CLAUDE.md § 10 records last: the same file in several places is
not an inconvenience, it is the cause. One implementation, one switch, and the
switch is recorded in the argv.
"""

import argparse
import json
import sys

from . import a18_run_a, hashing, path_policy


def _sabotaged_mod97(value):
    """A deliberately wrong modulus. Must change the answers, and be seen to."""
    total = 0
    for ch in value:
        if ch.isdigit():
            total = (total * 10 + int(ch)) % 96          # 96, not 97
        elif ch.isalpha():
            total = (total * 100 + (ord(ch.upper()) - 55)) % 96
        else:
            return None
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(prog="a18-run-a")
    parser.add_argument("--vectors", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sabotage", choices=["mod97"], default=None,
                        help="run the sabotage control instead of the method")
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

    rules = a18_run_a.load_rules(rules_path)

    restore = None
    if args.sabotage == "mod97":
        restore = a18_run_a.mod97_10_streaming
        a18_run_a.mod97_10_streaming = _sabotaged_mod97
    try:
        results = []
        for vector in applicable:
            outcome = a18_run_a.validate(vector["iban_raw"], rules)
            results.append({
                "iban_raw": vector["iban_raw"],
                "country": vector["country"],
                "expected_result": vector["expected_result"],
                "scope": vector["scope"],
                "actual": outcome,
            })
        # The empty string is an input with an answer, and it is counted as
        # one. R5 recorded 216 of 217 because an empty line looked like the
        # file's own line structure rather than like a value.
        empty = {"iban_raw": "", "country": None,
                 "expected_result": "INVALID", "scope": "EMPTY_INPUT",
                 "actual": a18_run_a.validate("", rules)}
    finally:
        if restore is not None:
            a18_run_a.mod97_10_streaming = restore

    payload = {
        "schema": "wpno.level1.a18-run-a/1",
        "method": "python streaming ISO/IEC 7064 MOD97-10 fold",
        "sabotage": args.sabotage,
        "vectors_path": vectors_path,
        "vectors_sha256": hashing.sha256_file(vectors_path),
        "rules_path": rules_path,
        "rules_sha256": hashing.sha256_file(rules_path),
        "applicable_vector_count": len(applicable),
        "empty_input_result": empty,
        "total_inputs_answered": len(results) + 1,
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "applicable_vector_count": len(applicable),
        "total_inputs_answered": len(results) + 1,
        "empty_input_counted": True,
        "sabotage": args.sabotage,
        "out": out_path,
        "out_sha256": hashing.sha256_file(out_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
