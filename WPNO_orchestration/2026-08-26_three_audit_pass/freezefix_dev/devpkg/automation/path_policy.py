"""Path admission control.

Every path the controller reads or writes passes through here. The rule set
lives in exactly one place so it cannot drift between call sites.

Three roots exist. Two are read-only. One is writable. Nothing else is either.

The roots come from `paths.json` beside this package. A value there may be
absolute, or relative to the directory holding `paths.json`. The relative form
is what this package ships, so no user name is written into the control plane
and an isolated self-test replica can declare its own roots without editing a
single line of code.
"""

import json
import os
import unicodedata

from . import policy


class PathPolicyError(Exception):
    """A path was rejected. The message names the rule that rejected it."""


def _load_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    package_root = os.path.dirname(here)
    config_path = os.path.join(package_root, "paths.json")
    with open(config_path, encoding="utf-8") as fh:
        data = json.load(fh)

    base = os.path.dirname(os.path.abspath(config_path))

    def resolve(key):
        value = data[key]
        if not isinstance(value, str) or value == "":
            raise PathPolicyError("paths.json %s must be a non-empty string" % key)
        if "\x00" in value:
            raise PathPolicyError("paths.json %s contains a null byte" % key)
        if not os.path.isabs(value):
            value = os.path.join(base, value)
        return os.path.realpath(value)

    return resolve("project_root"), resolve("discovery_root"), resolve("level1_root")


PROJECT_ROOT, DISCOVERY_ROOT, LEVEL1_ROOT = _load_paths()

READ_ROOTS = (PROJECT_ROOT, DISCOVERY_ROOT, LEVEL1_ROOT)
WRITE_ROOTS = (LEVEL1_ROOT,)

# Runtime directories under LEVEL1_ROOT. Everything else there is control
# plane and is covered by the frozen manifests.
MUTABLE_SUBDIRS = ("state", "results", "evidence", "work", "logs", "verification")


def _reject_malformed(path):
    """The checks that must happen before the string touches the filesystem."""
    if path is None:
        raise PathPolicyError("path is None")
    if not isinstance(path, str):
        raise PathPolicyError("path is not a string: %r" % type(path))
    if path == "":
        raise PathPolicyError("path is empty")
    if "\x00" in path:
        raise PathPolicyError("path contains a null byte")
    return path


def lexical_absolute(path):
    """Canonicalize the *string* only. No symlink is followed here.

    This is the form the symlink guard needs: `..` is collapsed so traversal
    expressed in the string cannot survive, while every component the caller
    actually named is still present and can be inspected.
    """
    path = _reject_malformed(path)

    # macOS filesystems normalize to NFD on disk while an argument may arrive
    # as NFC. Comparing unnormalized strings makes two names for one file look
    # like two files.
    path = unicodedata.normalize("NFC", path)

    if not os.path.isabs(path):
        raise PathPolicyError("path is not absolute: %s" % path)

    return unicodedata.normalize("NFC", os.path.abspath(path))


def normalize(path):
    """Canonicalize fully, resolving symlinks.

    Rejections happen here rather than at the call site so that a caller
    cannot forget one of them.

    abspath collapses '..' lexically. realpath resolves symlinks. Both are
    needed: the first stops traversal expressed in the string, the second
    answers where the path finally lands. What realpath cannot answer is
    whether an intermediate component was a link — that question belongs to
    `assert_no_symlink_escape`, which must therefore run before this.
    """
    collapsed = lexical_absolute(path)
    resolved = os.path.realpath(collapsed)
    return unicodedata.normalize("NFC", resolved)


def _is_within(candidate, root):
    root = unicodedata.normalize("NFC", os.path.realpath(root))
    if candidate == root:
        return True
    return candidate.startswith(root + os.sep)


def _within_any_read_root(candidate):
    return any(_is_within(candidate, root) for root in READ_ROOTS)


def _case_insensitive_collision(candidate, root):
    """True when candidate escapes root only under case-sensitive comparison.

    macOS is case-insensitive by default. A path that differs from an allowed
    root only in case refers to the same directory on this machine but fails a
    case-sensitive prefix test. Treating that as 'outside' would be wrong, and
    treating it as 'inside' without saying so would hide the ambiguity.
    """
    return (
        candidate.lower() == root.lower()
        or candidate.lower().startswith(root.lower() + os.sep)
    )


def assert_readable(path):
    """Admit a path for reading. Returns the canonical path."""
    canonical = normalize(path)
    for root in READ_ROOTS:
        if _is_within(canonical, root):
            return canonical
    for root in READ_ROOTS:
        if _case_insensitive_collision(canonical, root):
            raise PathPolicyError(
                "path matches allowed root %s only case-insensitively; "
                "resolve the exact case before use: %s" % (root, canonical))
    raise PathPolicyError("read outside allowed roots: %s" % canonical)


def assert_writable(path):
    """Admit a path for writing. Returns the canonical path.

    Writing is permitted below LEVEL1_ROOT and nowhere else. PROJECT_ROOT and
    DISCOVERY_ROOT are rejected explicitly and by name so the error is
    unambiguous.
    """
    canonical = normalize(path)

    home = os.path.realpath(os.path.expanduser("~"))
    for name in policy.NEVER_WRITE_HOME_SUBDIRS:
        forbidden = os.path.join(home, name)
        if _is_within(canonical, forbidden):
            raise PathPolicyError("write into protected home directory: %s" % canonical)
    for prefix in policy.NEVER_WRITE_PREFIXES:
        if canonical == prefix or canonical.startswith(prefix + os.sep):
            raise PathPolicyError("write into protected system path: %s" % canonical)

    if _is_within(canonical, PROJECT_ROOT) and not _is_within(canonical, LEVEL1_ROOT):
        raise PathPolicyError("write into PROJECT_ROOT is forbidden: %s" % canonical)
    if _is_within(canonical, DISCOVERY_ROOT):
        raise PathPolicyError("write into DISCOVERY_ROOT is forbidden: %s" % canonical)

    for root in WRITE_ROOTS:
        if _is_within(canonical, root):
            return canonical
    raise PathPolicyError("write outside LEVEL1_ROOT: %s" % canonical)


def _link_target_of(component):
    """The absolute, NFC-normalized target of one symlink component.

    `os.readlink` returns the link's literal text, which may be relative. It is
    joined against the link's own directory, exactly as the kernel would, and
    collapsed lexically. It is deliberately NOT passed through realpath: the
    next turn of the loop inspects it, and realpath here would resolve away the
    very component the next check needs to see.
    """
    raw = os.readlink(component)
    if not os.path.isabs(raw):
        raw = os.path.join(os.path.dirname(component), raw)
    return unicodedata.normalize("NFC", os.path.abspath(raw))


def assert_no_symlink_escape(path):
    """Reject a path any of whose components links outside the allowed roots.

    The predecessor package canonicalized the input first and then walked the
    result. Canonicalization is precisely what removes a symlink, so the walk
    inspected a path with no links left in it and never rejected anything. The
    order here is the other way round, and it is the whole point of the
    function:

      1. validate and lexically canonicalize the string, without following
         anything;
      2. walk the components from the filesystem root outwards;
      3. at each component, ask `os.path.islink` — which uses lstat and does
         not follow — before the component can disappear;
      4. resolve each link's own target separately and check that target
         against the allowed roots;
      5. continue the walk from the resolved location, because that is where
         the remaining components actually live;
      6. bound the number of links followed and remember the ones already
         seen, so a cycle ends in a rejection rather than in a hang;
      7. finally, confirm the fully resolved destination is still inside an
         allowed root.

    A symlink that stays entirely inside an allowed root is permitted, and the
    canonical destination is returned — that behaviour is relied on by the
    evidence and hashing paths and is covered by its own test.
    """
    lexical = lexical_absolute(path)

    walked = os.sep
    followed = 0
    seen = set()

    for part in lexical.split(os.sep):
        if not part:
            continue
        walked = os.path.join(walked, part)

        while os.path.islink(walked):
            followed += 1
            if followed > policy.MAX_SYMLINK_DEPTH:
                raise PathPolicyError(
                    "symlink chain exceeds the permitted depth of %d at %s"
                    % (policy.MAX_SYMLINK_DEPTH, walked))
            if walked in seen:
                raise PathPolicyError("symlink loop detected at %s" % walked)
            seen.add(walked)

            target = _link_target_of(walked)
            if not _within_any_read_root(target):
                raise PathPolicyError(
                    "symlink component %s escapes allowed roots to %s"
                    % (walked, target))
            walked = target

    canonical = normalize(lexical)
    if not _within_any_read_root(canonical):
        raise PathPolicyError(
            "resolved target leaves allowed roots: %s" % canonical)
    return canonical


def audit_work_dir(audit_id, run_phase):
    return assert_writable(
        os.path.join(LEVEL1_ROOT, "work", audit_id, run_phase))


def audit_results_dir(audit_id, run_phase):
    return assert_writable(
        os.path.join(LEVEL1_ROOT, "results", audit_id, run_phase))


def audit_evidence_dir(audit_id, run_phase):
    return assert_writable(
        os.path.join(LEVEL1_ROOT, "evidence", audit_id, run_phase))


def ensure_dir(path):
    canonical = assert_writable(path)
    os.makedirs(canonical, exist_ok=True)
    return canonical
