"""A phase-aware cross-phase-read predicate, and the self-check that fixes it.

Attempt 4 flagged L1-A19 RUN-B for a cross-phase read. The path it flagged was

    <R7>/work/L1-A19/RUN-B

which is RUN-B's own working directory. The predicate that flagged it was

    wrongb = [s for s in bs
              if '/L1-A19/' in s and '/RUN-B/' not in s
              and not s.endswith('R7_REF04_IDNR_VECTORS.jsonl')]

`'/RUN-B/' not in s` is true for that string because the path *ends* at
`RUN-B` and therefore contains no trailing separator. A bare directory path
can never satisfy a test written for a path with something after it. This is
the same defect as a search without a word boundary: the anchor is wrong, and
the wrong anchor produces a confident answer about the wrong thing.

The replacement below compares path components, is phase-aware, and is not
specific to any audit. It also encodes what the specification actually
forbids, which is not "another phase's name appears" but "this phase reads
another phase's answer".

  * A phase may read its own work, results and evidence.
  * RUN-A and RUN-B may not read each other's work, results or evidence, and
    may not read a COMPARISON result - that would be reading a conclusion
    drawn from themselves.
  * COMPARISON may read the sealed results and evidence of RUN-A and RUN-B.
    A comparison that cannot read both compares nothing. It may not read
    another audit's directories.
"""

import os

PHASE_DIRECTORIES = ("work", "results", "evidence")
PHASES = ("RUN-A", "RUN-B", "COMPARISON")


def _components(path):
    return os.path.normpath(path).split(os.sep)


def locate(path, level1_root):
    """Which audit and phase does this path belong to, if any?

    Returns (audit_id, phase) or (None, None). A path that *is* the phase
    directory counts as belonging to it, which is the case the earlier
    predicate could not express.
    """
    root = _components(os.path.normpath(level1_root))
    parts = _components(path)
    if parts[:len(root)] != root:
        return (None, None)
    rest = parts[len(root):]
    if len(rest) >= 3 and rest[0] in PHASE_DIRECTORIES and rest[2] in PHASES:
        return (rest[1], rest[2])
    return (None, None)


def is_cross_phase_read(path, audit_id, run_phase, level1_root):
    """Does `path` read another phase's territory, for this phase?

    Generic over audit and phase. Nothing here names an audit.
    """
    owner_audit, owner_phase = locate(path, level1_root)
    if owner_audit is None:
        return False                      # not a phase directory at all
    if owner_audit != audit_id:
        return True                       # another audit entirely
    if owner_phase == run_phase:
        return False                      # this phase's own territory
    if run_phase == "COMPARISON" and owner_phase in ("RUN-A", "RUN-B"):
        return False                      # what a comparison is for
    return True


def self_check(level1_root="/R7"):
    """The five cases the disposition requires, each stated and measured."""
    R = level1_root
    cases = [
        ("own-phase work path accepted",
         R + "/work/L1-A19/RUN-B", "L1-A19", "RUN-B", False),
        ("own-phase work path with a trailing file accepted",
         R + "/work/L1-A19/RUN-B/run_b_results.json", "L1-A19", "RUN-B", False),
        ("RUN-A work path rejected",
         R + "/work/L1-A19/RUN-A", "L1-A19", "RUN-B", True),
        ("RUN-A result path rejected",
         R + "/results/L1-A19/RUN-A/result.json", "L1-A19", "RUN-B", True),
        ("RUN-A evidence path rejected",
         R + "/evidence/L1-A19/RUN-A/SEAL.json", "L1-A19", "RUN-B", True),
        ("comparison-result path rejected before comparison",
         R + "/results/L1-A19/COMPARISON/result.json", "L1-A19", "RUN-B", True),
        ("comparison may read RUN-A evidence",
         R + "/evidence/L1-A19/RUN-A/SEAL.json", "L1-A19", "COMPARISON", False),
        ("comparison may read RUN-B evidence",
         R + "/evidence/L1-A19/RUN-B/SEAL.json", "L1-A19", "COMPARISON", False),
        ("another audit's evidence rejected",
         R + "/evidence/L1-A18/RUN-A/SEAL.json", "L1-A19", "RUN-B", True),
        ("a corpus path is not a phase path",
         R + "/corpora/R7_REF04_IDNR_VECTORS.jsonl", "L1-A19", "RUN-B", False),
        ("the same rule for another audit, no audit hard-coded",
         R + "/work/L1-A31/RUN-A", "L1-A31", "RUN-B", True),
        ("and its own phase accepted",
         R + "/work/L1-A31/RUN-B", "L1-A31", "RUN-B", False),
    ]
    out = []
    for label, path, audit, phase, expected in cases:
        got = is_cross_phase_read(path, audit, phase, R)
        out.append({"case": label, "path": path, "audit_id": audit,
                    "run_phase": phase, "expected_cross_phase": expected,
                    "measured_cross_phase": got, "agrees": got == expected})
    return out


if __name__ == "__main__":
    import json
    rows = self_check()
    print(json.dumps(rows, indent=2))
    bad = [r for r in rows if not r["agrees"]]
    print("cases:", len(rows), " disagreeing:", len(bad))
    raise SystemExit(1 if bad else 0)
