"""L1-A18 RUN-B: bounded invocation of the independent Java validator.

This module is the whole of RUN-B's Python surface, and it deliberately
contains no validation logic. It launches the Java validator and reads back
what it said. Putting any part of the decision here would put RUN-A's runtime
back inside RUN-B.

What it must not do, and does not do: import `a18_run_a`, call anything in it,
or read anything under a RUN-A results, evidence or work directory. The import
list below is the evidence for the first two, and `audit_context` enforces the
third.
"""

import json
import os
import subprocess

from . import hashing, path_policy, policy

JAVA = "/usr/bin/java"
CLASSES_DIR = os.path.join(path_policy.LEVEL1_ROOT, "tools", "a18_run_b",
                           "classes")
MAIN_CLASS = "WpnoIbanValidateRunB"

# Prefixed to every input line so an empty IBAN is still one input.
INPUT_MARKER = ">"

RULES_PATH = os.path.join(path_policy.LEVEL1_ROOT, "corpora",
                          "R5_REF01_COUNTRY_RULES.jsonl")

TIMEOUT_SECONDS = 300
OUTPUT_LIMIT_BYTES = 16 * 1024 * 1024


class RunBError(Exception):
    pass


def available():
    if not os.path.exists(JAVA):
        return False, "java is not installed at %s" % JAVA
    target = os.path.join(CLASSES_DIR, MAIN_CLASS + ".class")
    if not os.path.exists(target):
        return False, "the RUN-B validator is not compiled: %s" % target
    if not os.path.exists(RULES_PATH):
        return False, "the REF-01 rule corpus is absent: %s" % RULES_PATH
    return True, "JDK 21, compiled, REF-01 corpus present"


def validate_all(values, work_dir, rules_path=None):
    """Validate every value in one bounded Java process.

    `work_dir` must be under `work/`: the input and output files are written
    there and kept as evidence of exactly what RUN-B was asked.
    """
    rules = path_policy.assert_readable(rules_path or RULES_PATH)

    # The scratch area must be under work/. RUN-B writes its own input and
    # output files there and they are kept as evidence of exactly what it was
    # asked; anywhere else would be either the control plane or another
    # phase's territory.
    candidate = path_policy.assert_writable(work_dir)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not (candidate == work_root or candidate.startswith(work_root + os.sep)):
        raise RunBError("RUN-B may only write under work/: %s" % candidate)
    work = path_policy.ensure_dir(candidate)

    in_path = os.path.join(work, "run_b_inputs.txt")
    out_path = os.path.join(work, "run_b_results.jsonl")
    # Each input is written with a leading marker character. Without it an
    # empty IBAN would be an empty line, indistinguishable from the file's
    # own line structure, and RUN-B would answer fewer inputs than it was
    # given - which it did, until a test asked it about the empty string.
    with open(path_policy.assert_writable(in_path), "w", encoding="utf-8") as fh:
        for value in values:
            if "\n" in value or "\r" in value:
                raise RunBError("an IBAN may not contain a line break")
            fh.write(INPUT_MARKER + value + "\n")

    argv = [JAVA, "-cp", CLASSES_DIR, MAIN_CLASS,
            "--rules", rules,
            "--ibans", path_policy.assert_readable(in_path),
            "--out", path_policy.assert_writable(out_path)]

    rules_before = hashing.sha256_file(rules)

    try:
        proc = subprocess.run(  # noqa: S603 - argv list, shell=False
            argv, shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
            env=policy.base_environment(), cwd=path_policy.LEVEL1_ROOT,
            check=False)
    except subprocess.TimeoutExpired:
        raise RunBError("RUN-B validator timed out after %ds" % TIMEOUT_SECONDS)

    if proc.returncode != 0:
        raise RunBError(
            "RUN-B validator exited %d: %s"
            % (proc.returncode,
               proc.stderr[:OUTPUT_LIMIT_BYTES].decode("utf-8", "replace")[:500]))

    if hashing.sha256_file(rules) != rules_before:
        raise RunBError("RUN-B changed the REF-01 rule corpus")

    size = os.path.getsize(out_path)
    if size > OUTPUT_LIMIT_BYTES:
        raise RunBError("RUN-B output exceeds its bound: %d bytes" % size)

    results = []
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    if len(results) != len(values):
        raise RunBError("RUN-B returned %d results for %d inputs"
                        % (len(results), len(values)))
    return results, argv
