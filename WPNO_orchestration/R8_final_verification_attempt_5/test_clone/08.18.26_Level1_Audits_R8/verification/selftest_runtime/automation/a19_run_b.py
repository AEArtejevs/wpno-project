"""L1-A19 RUN-B: bounded invocation of the independent Java IdNr validator.

This module is the whole of RUN-B's Python surface and it contains no
validation logic at all. It writes the values out, launches the Java
validator, and reads back what it said. Any part of the decision taken here
would put RUN-A's runtime back inside RUN-B.

What it must not do, and does not do: import `a19_run_a`, call anything in it,
or read anything under a RUN-A results, evidence or work directory. The import
list below is the evidence for the first two.
"""

import json
import os
import subprocess

from . import hashing, path_policy, policy

JAVA = "/usr/bin/java"
CLASSES_DIR = os.path.join(path_policy.LEVEL1_ROOT, "tools", "a19_run_b",
                           "classes")
MAIN_CLASS = "WpnoIdnrValidateRunB"

# Prefixed to every input line so an empty identifier is still one input.
INPUT_MARKER = ">"

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
    return True, "JDK present, RUN-B validator compiled"


def validate_all(values, work_dir):
    """Validate every value in one bounded Java process.

    `work_dir` must be under `work/`: the input and output files are written
    there and kept as evidence of exactly what RUN-B was asked.
    """
    candidate = path_policy.assert_writable(work_dir)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not (candidate == work_root or candidate.startswith(work_root + os.sep)):
        raise RunBError("RUN-B may only write under work/: %s" % candidate)
    work = path_policy.ensure_dir(candidate)

    in_path = os.path.join(work, "run_b_values.txt")
    out_path = os.path.join(work, "run_b_results.jsonl")
    with open(path_policy.assert_writable(in_path), "w",
              encoding="utf-8") as fh:
        for value in values:
            if value is None:
                raise RunBError(
                    "a non-string input cannot be handed to the Java "
                    "validator; it is answered as NOT_A_STRING before the "
                    "boundary and recorded as such")
            if "\n" in value or "\r" in value:
                raise RunBError("an identifier may not contain a line break")
            fh.write(INPUT_MARKER + value + "\n")

    argv = [JAVA, "-cp", CLASSES_DIR, MAIN_CLASS,
            "--values", path_policy.assert_readable(in_path),
            "--out", path_policy.assert_writable(out_path)]

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
               proc.stderr[:OUTPUT_LIMIT_BYTES]
               .decode("utf-8", "replace")[:500]))

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
