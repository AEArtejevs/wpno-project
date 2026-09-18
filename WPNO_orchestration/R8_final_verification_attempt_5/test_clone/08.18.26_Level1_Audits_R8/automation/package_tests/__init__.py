"""Tests that must run against the real R5 package, not the replica.

The controller self-tests run inside `verification/selftest_runtime` because
they rewrite `state/`. These do the opposite: they assert facts about this
package — that R4 is unchanged, that the lineage copy is byte-identical, that
the migrated references are equal, that the DER anchor stages correctly. A
replica has none of that material, so asserting it there would assert nothing.

Nothing here writes outside `work/_r5_selftest/`.
"""

# --- generation roots (R7, extended in R8) ---------------------------------
# A revision's own facts are asserted against the package root at which that
# revision was the active one. R5's facts were asserted against R5 while R5
# was live; in R6 that root moved to `lineage/R5_EXECUTION`, and in R7 it
# moved again to `lineage/R6_EXECUTION/lineage/R5_EXECUTION`.
#
# Re-pointing the older tests is not a relaxation. Every assertion they make is
# unchanged and is made against the same bytes; what changes is where those
# bytes now live. Deleting them instead — the other obvious option — would
# quietly retire the regressions that R5 and R6 exist to hold in place.
#
# R8 changes how the chain is walked, not what it proves. R7 carried a
# complete physical copy of R6 and the walk descended into it. R8 carries no
# such copy: 555 MiB duplicated to answer a question a hash already answers.
# Its lineage is a hash-bound reference to the sibling R7 root instead, so the
# walk now takes whichever form a revision actually uses — descend into a
# physical `lineage_path` directory where one exists, and otherwise cross to
# the recorded `predecessor_root` beside the package.
#
# Crossing to a sibling is the step that has to be earned rather than
# assumed, so it is checked: the sibling must be the revision the record
# names as its predecessor, and it must still be FROZEN. A walk that landed
# on some other tree would assert against the wrong bytes, which is worse
# than failing.

import os

from automation import path_policy


class GenerationRootError(Exception):
    pass


def generation_root(revision, start=None):
    """The package root at which `revision` was the active revision.

    Resolved by reading `state/REVISION.json` at each step of the lineage
    chain, never by assuming a directory name. A chain that does not lead to
    the requested revision raises rather than returning the nearest match: a
    test that silently asserts against the wrong revision's bytes is worse
    than one that fails.
    """
    import json

    root = os.path.abspath(start or path_policy.LEVEL1_ROOT)
    seen = []
    for _ in range(16):
        record_path = os.path.join(root, "state", "REVISION.json")
        if not os.path.isfile(record_path):
            raise GenerationRootError(
                "no state/REVISION.json at %s; the lineage chain from %s "
                "visited %r and could not reach %s"
                % (root, start or path_policy.LEVEL1_ROOT, seen, revision))
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        here = record.get("revision")
        seen.append(here)
        if here == revision:
            return root

        # R4 predates `state/REVISION.json`. It is reachable only as the
        # `lineage/R4_EXECUTION` directory R5 carries, so the chain ends by
        # naming it rather than by reading a record it never had. The
        # directory is required to exist and to carry R4's control manifest,
        # so this is still a measurement and not an assumption.
        if revision == "R4":
            candidate = os.path.join(root, "lineage", "R4_EXECUTION")
            if os.path.isdir(candidate):
                manifest = os.path.join(candidate, "CONTROL_MANIFEST.sha256")
                if not os.path.isfile(manifest):
                    raise GenerationRootError(
                        "%s has no control manifest; it cannot be R4"
                        % candidate)
                return candidate

        # A physically copied lineage: descend into it.
        lineage = record.get("lineage_path")
        if lineage:
            candidate = os.path.join(root, lineage)
            if os.path.isdir(candidate):
                root = candidate
                continue

        # A hash-bound lineage: cross to the recorded predecessor root, and
        # only after checking it is the revision this record names and that
        # it is still frozen.
        predecessor = record.get("predecessor")
        predecessor_root = record.get("predecessor_root")
        if not (predecessor and predecessor_root):
            break
        if not os.path.isdir(predecessor_root):
            raise GenerationRootError(
                "%s records predecessor %s at %s and that root is absent"
                % (here, predecessor, predecessor_root))
        sibling_record = os.path.join(predecessor_root, "state",
                                      "REVISION.json")
        if not os.path.isfile(sibling_record):
            raise GenerationRootError(
                "%s has no state/REVISION.json; it cannot be the predecessor "
                "%s claims" % (predecessor_root, here))
        with open(sibling_record, encoding="utf-8") as handle:
            sibling = json.load(handle)
        if sibling.get("revision") != predecessor:
            raise GenerationRootError(
                "%s records predecessor %s but %s declares itself %s"
                % (here, predecessor, predecessor_root,
                   sibling.get("revision")))
        mode_path = os.path.join(predecessor_root, "MODE")
        mode = (open(mode_path, encoding="utf-8").read().strip()
                if os.path.isfile(mode_path) else None)
        if mode != "FROZEN":
            raise GenerationRootError(
                "predecessor %s at %s reads MODE %r; a lineage step may only "
                "cross into a frozen revision"
                % (predecessor, predecessor_root, mode))
        root = predecessor_root
    raise GenerationRootError(
        "revision %s is not in the lineage chain from %s; the chain is %r"
        % (revision, start or path_policy.LEVEL1_ROOT, seen))


def compact_lineage_record():
    """R8's lineage record, which replaces the physically copied tree.

    R7 answered "is the predecessor intact" by carrying a complete copy of it
    and hashing that. R8 answers the same question by recording where the
    predecessor is, what it hashed to, and re-measuring it in place. The
    record is the entry point for every test that used to read a path inside
    `lineage/R6_EXECUTION`.
    """
    import json
    path = os.path.join(path_policy.LEVEL1_ROOT, "lineage", "R8_LINEAGE.json")
    if not os.path.isfile(path):
        raise GenerationRootError("no compact lineage record at %s" % path)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def inherited_lineage_root():
    """The predecessor's own lineage directory, verified before it is used.

    R8 does not copy it. It records the path and the digest of the integrity
    record inside it, and this resolves the one against the other, so a test
    that reads through here cannot silently read a tree that has moved or
    changed. The digest check is the whole point: without it this would be a
    path constant with extra steps.
    """
    from automation import hashing

    record = compact_lineage_record()
    root = record["r7"]["root"]
    inherited = record["r7"]["inherited_lineage_tree"]
    lineage = os.path.join(root, "lineage")
    if not os.path.isdir(lineage):
        raise GenerationRootError(
            "the predecessor lineage tree is absent: %s" % lineage)
    project = os.path.dirname(path_policy.LEVEL1_ROOT)
    integrity = os.path.join(project, inherited["predecessor_integrity_record"])
    if not os.path.isfile(integrity):
        raise GenerationRootError(
            "the predecessor integrity record is absent: %s" % integrity)
    measured = hashing.sha256_file(integrity)
    if measured != inherited["predecessor_integrity_sha256"]:
        raise GenerationRootError(
            "PREDECESSOR_INTEGRITY_DRIFT: %s recorded %s, measured %s"
            % (integrity, inherited["predecessor_integrity_sha256"], measured))
    return lineage
