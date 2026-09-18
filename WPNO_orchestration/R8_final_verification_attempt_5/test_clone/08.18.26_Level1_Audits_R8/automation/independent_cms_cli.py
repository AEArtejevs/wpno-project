"""Command-line entry for the independent CMS verifier. Frozen code.

A thin wrapper over `independent_cms`, present so a plan step can name a
frozen module rather than a script under `work/`. It adds no verification
logic of its own; a wrapper that decided anything would be a third
implementation nobody reviewed.
"""

import argparse
import json
import sys

from . import hashing, independent_cms, path_policy


def main(argv=None):
    parser = argparse.ArgumentParser(prog="independent-cms-verify")
    parser.add_argument("--cms", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--leaf", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--intermediate", default=None)
    parser.add_argument("--validation-time", required=True, type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    out_path = path_policy.assert_writable(args.out)
    result, argv_used, exit_code = independent_cms.verify(
        args.cms, args.content, args.leaf, args.root,
        args.validation_time, args.intermediate)

    payload = {
        "schema": "wpno.level1.independent-cms/1",
        "argv": argv_used,
        "exit_code": exit_code,
        "validation_time": args.validation_time,
        "inputs": {
            "cms_sha256": hashing.sha256_file(args.cms),
            "content_sha256": hashing.sha256_file(args.content),
            "leaf_sha256": hashing.sha256_file(args.leaf),
            "root_sha256": hashing.sha256_file(args.root),
        },
        "result": result,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"exit_code": exit_code, "out": out_path,
                      "out_sha256": hashing.sha256_file(out_path)},
                     indent=2, sort_keys=True))
    # A nonzero verifier exit is an answer, not a harness failure: the point
    # of a verifier is to be able to say no. The wrapper exits 0 having
    # recorded what it said.
    return 0


if __name__ == "__main__":
    sys.exit(main())
