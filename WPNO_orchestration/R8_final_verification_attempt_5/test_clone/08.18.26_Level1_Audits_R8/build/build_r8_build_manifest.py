#!/usr/bin/env python3
"""Regenerate build/R8_BUILD_MANIFEST.sha256 in its established scope.

The scope is not restated from memory; it is recovered from the manifest that
already exists and then asserted. Every top-level directory the previous
manifest covers is covered; every one it omits is omitted, and the omissions
are named rather than discovered:

    __pycache__   compiled bytecode is not package content
    work/         scratch, rewritten by every rehearsal
    state/        live controller state, which changes without the package changing
    results/      written by a live phase; none has run
    evidence/     written by a live phase; none has run
    logs/         written by a live phase; none has run

and two families created after this manifest exists, which the freeze plan
binds separately:

    verification_codex_final_pre_freeze_attempt_*/
    build/freeze_plan_attempt_*/

The previous manifest is preserved beside the new one under a name that says
what it is. A superseded manifest is evidence: it is what the last independent
verification measured 15464 entries against.
"""

import hashlib
import os
import shutil
import sys
import time

# Two dirnames, not three: this file moved from build/resume_r7/ to build/
# when R8 renamed the R7-specific tooling, and the extra level would have
# resolved ROOT to the directory above the package.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MANIFEST = os.path.join(ROOT, "build", "R8_BUILD_MANIFEST.sha256")

EXCLUDED_DIR_NAMES = {"__pycache__"}
EXCLUDED_TOP_LEVEL = {"work", "state", "results", "evidence", "logs"}

# Two families of artefact are created after this manifest is generated and
# are therefore outside it by construction rather than by preference. Both are
# bound separately by the freeze plan, so nothing here goes unchecked; what
# would go wrong without these rules is that the manifest would be stale the
# moment the verifier wrote its first file.
#
#   the fresh final verifier's output directory, one per attempt
#   the freeze-plan directory, one per attempt
#
# The rules are prefix rules on a single path component and nothing wider. A
# directory whose name merely resembles one of these - the existing
# `verification_codex_pre_freeze/`, which holds the earlier independent
# verification and must stay inside the manifest - does not match, because the
# prefix is spelled out in full and the earlier directory does not begin with
# it.
FINAL_VERIFIER_PREFIX = "verification_codex_final_pre_freeze_attempt_"
FREEZE_PLAN_PREFIX = "freeze_plan_attempt_"


def is_post_manifest_artefact(rel):
    """Is `rel` one of the two families created after this manifest exists?

    Matched on path components, never on a substring of the whole path. A
    substring test would exclude `build/notes_about_freeze_plan_attempt_1.md`,
    which is an ordinary control-plane file and belongs in the manifest.
    """
    parts = rel.split(os.sep)
    if parts[0].startswith(FINAL_VERIFIER_PREFIX):
        return True
    if len(parts) >= 2 and parts[0] == "build" \
            and parts[1].startswith(FREEZE_PLAN_PREFIX):
        return True
    return False

# A manifest cannot hold its own digest. The value would be the digest of the
# file as it stood before it was rewritten, and it would fail on the first
# verification - the same shape as a grep that finds its own invocation. The
# previous manifest excluded itself; so does this one, and its superseded
# copies with it.
# Only the live manifest is excluded. A superseded copy is evidence - it is
# what the last independent verification measured its 15464 entries against -
# and evidence that no manifest covers is evidence nothing checks.
EXCLUDED_RELS = {os.path.join("build", "R8_BUILD_MANIFEST.sha256")}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def in_scope(rel):
    if rel.split(os.sep)[0] in EXCLUDED_TOP_LEVEL:
        return False
    if rel in EXCLUDED_RELS:
        return False
    if is_post_manifest_artefact(rel):
        return False
    return True


def enumerate_files():
    out = {}
    for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIR_NAMES)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                raise SystemExit("symlink in package: %s" % full)
            rel = os.path.relpath(full, ROOT)
            if in_scope(rel):
                out[rel] = full
    return out


def read_manifest(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                digest, rel = line.split("  ", 1)
                out[rel] = digest
    return out


def main():
    previous = read_manifest(MANIFEST) if os.path.isfile(MANIFEST) else {}

    # The scope assertion. Every top-level directory the previous manifest
    # covered must still be covered by the rule above; a directory that
    # silently left scope would shrink the manifest without saying so.
    previous_tops = {rel.split(os.sep)[0] for rel in previous
                     if os.sep in rel}
    leaving = sorted(previous_tops & EXCLUDED_TOP_LEVEL)
    # A previous manifest cannot have covered a post-manifest artefact: those
    # directories do not exist when a manifest is written. If one appears in
    # the previous manifest, something wrote a manifest after the verifier ran
    # and the ordering the freeze depends on has already been broken.
    stale_post = sorted(rel for rel in previous
                        if is_post_manifest_artefact(rel))
    if stale_post:
        raise SystemExit(
            "the previous manifest covers post-manifest artefacts, so it was "
            "written after the verifier or the freeze plan: %s"
            % stale_post[:5])
    if leaving:
        raise SystemExit("scope would drop directories the previous manifest "
                         "covered: %s" % leaving)

    # Preserve first, then enumerate. A superseded copy written after the walk
    # is a file the new manifest cannot cover, and an uncovered file is one
    # nothing checks.
    if previous:
        stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
        superseded = os.path.join(
            ROOT, "build", "R8_BUILD_MANIFEST.SUPERSEDED_%s.sha256" % stamp)
        shutil.copy2(MANIFEST, superseded)
        print("superseded manifest preserved: %s"
              % os.path.relpath(superseded, ROOT))
        print("superseded manifest sha256   : %s" % sha256_file(superseded))
        print("superseded manifest entries  : %d" % len(previous))

    files = enumerate_files()
    manifest = {rel: sha256_file(full) for rel, full in sorted(files.items())}

    added = sorted(set(manifest) - set(previous))
    removed = sorted(set(previous) - set(manifest))
    changed = sorted(rel for rel in set(manifest) & set(previous)
                     if manifest[rel] != previous[rel])

    lines = ["%s  %s" % (manifest[rel], rel) for rel in sorted(manifest)]
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")

    print("entries      : %d" % len(manifest))
    print("added        : %d" % len(added))
    for rel in added:
        print("    + %s" % rel)
    print("removed      : %d" % len(removed))
    for rel in removed:
        print("    - %s" % rel)
    print("changed      : %d" % len(changed))
    for rel in changed:
        print("    ~ %s" % rel)
    print("manifest sha256: %s" % sha256_file(MANIFEST))
    return 0


if __name__ == "__main__":
    sys.exit(main())
