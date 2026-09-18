"""Freeze mechanism for the R4 revision.

R3 froze against a two-digest human token:

    FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> VERIFICATION-SHA256=<64hex> RUN-ONCE

That grammar has a property nobody noticed until a freeze had to be repeated.
Both digests describe the package, and neither describes the *attempt*. So when
the first R4 freeze was rolled back for a defect in an artefact it produced —
the package itself being untouched — the token required for the second attempt
was, character for character, the token already spent on the first. A RUN-ONCE
token that cannot be told apart from its own replay is not one-time; it only
looks it.

R4 therefore binds the approval to a freeze plan as well:

    FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> VERIFICATION-SHA256=<64hex>
                  FREEZE-PLAN-SHA256=<64hex> RUN-ONCE

Exactly five fields. The plan records the attempt number, the digests it
expects to find, the digest of the previous attempt's evidence, and what the
attempt is for. Two attempts therefore never share a plan digest, and an
attempt-1 token — which has four fields and no plan binding — cannot authorise
attempt 2 at all. It is refused on its shape, before any value is compared.

Nothing here writes a freeze artefact until every binding has been checked
against the files on disk. The order is deliberate: a partially frozen package
is worse than an unfrozen one, because it looks finished.
"""

import hashlib
import io
import json
import os

from . import policy

# The runtime directories. Their contents are the audit's record rather than
# the control plane, and they change while the package is in use.
MUTABLE_SUBDIRS = ("state", "results", "evidence", "work", "logs")

FREEZE_FIELD_COUNT = 5
PACKAGE_FIELD = "PACKAGE-SHA256="
VERIFICATION_FIELD = "VERIFICATION-SHA256="
PLAN_FIELD = "FREEZE-PLAN-SHA256="

TOKEN_GRAMMAR = (
    "%s PACKAGE-SHA256=<64hex> VERIFICATION-SHA256=<64hex> "
    "FREEZE-PLAN-SHA256=<64hex> %s"
    % (policy.FREEZE_PREFIX, policy.APPROVAL_SUFFIX))

# The grammar R3 used and R4 no longer accepts. Named so the rejection can say
# what it recognised rather than only that something was wrong.
LEGACY_FIELD_COUNT = 4


class FreezeError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_hex64(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value.lower())


# ------------------------------------------------------------------- token
def parse_freeze_token(token):
    """Parse and structurally validate a freeze token.

    Shape first, values later. A token of the wrong shape is refused without
    any digest being computed, so a stale token cannot be probed against the
    package by watching which error it produces.
    """
    if not isinstance(token, str):
        raise FreezeError("freeze token must be a string")
    parts = token.split()
    if len(parts) == LEGACY_FIELD_COUNT and parts[0] == policy.FREEZE_PREFIX:
        raise FreezeError(
            "this is the R3 four-field freeze token, which carries no "
            "freeze-plan binding and cannot authorise an R4 freeze. R4 "
            "requires: %s" % TOKEN_GRAMMAR)
    if len(parts) != FREEZE_FIELD_COUNT:
        raise FreezeError(
            "freeze token must have exactly %d fields, got %d. Required: %s"
            % (FREEZE_FIELD_COUNT, len(parts), TOKEN_GRAMMAR))
    if parts[0] != policy.FREEZE_PREFIX:
        raise FreezeError("freeze token must begin with %s"
                          % policy.FREEZE_PREFIX)
    if parts[4] != policy.APPROVAL_SUFFIX:
        raise FreezeError("freeze token must end with %s"
                          % policy.APPROVAL_SUFFIX)
    for index, prefix, name in ((1, PACKAGE_FIELD, "second"),
                                (2, VERIFICATION_FIELD, "third"),
                                (3, PLAN_FIELD, "fourth")):
        if not parts[index].startswith(prefix):
            raise FreezeError("%s field must be %s<64hex>" % (name, prefix))
    package = parts[1][len(PACKAGE_FIELD):].lower()
    verification = parts[2][len(VERIFICATION_FIELD):].lower()
    plan = parts[3][len(PLAN_FIELD):].lower()
    for value, name in ((package, "PACKAGE-SHA256"),
                        (verification, "VERIFICATION-SHA256"),
                        (plan, "FREEZE-PLAN-SHA256")):
        if not is_hex64(value):
            raise FreezeError("%s is not 64 hex characters" % name)
    return {"package_sha256": package,
            "verification_sha256": verification,
            "freeze_plan_sha256": plan}


def token_for(package_sha256, verification_sha256, freeze_plan_sha256):
    """The exact token a human must supply for this plan."""
    for value in (package_sha256, verification_sha256, freeze_plan_sha256):
        if not is_hex64(value):
            raise FreezeError("digest is not 64 hex characters: %r" % value)
    return "%s %s%s %s%s %s%s %s" % (
        policy.FREEZE_PREFIX,
        PACKAGE_FIELD, package_sha256,
        VERIFICATION_FIELD, verification_sha256,
        PLAN_FIELD, freeze_plan_sha256,
        policy.APPROVAL_SUFFIX)


# -------------------------------------------------------------------- plan
REQUIRED_PLAN_FIELDS = (
    "schema",
    "attempt_number",
    "package_sha256",
    "verification_result_sha256",
    "verification_manifest_sha256",
    "baseline_preview_sha256",
    "expected_project_baseline_count",
    "expected_discovery_baseline_count",
    "prior_freeze_attempt_manifest_sha256",
    "excluded_paths",
    "r3_root",
    "r3_expected_aggregate",
    "r3_expected_file_count",
)


def load_freeze_plan(path):
    """Read a freeze plan and check it is structurally complete."""
    with io.open(path, encoding="utf-8") as handle:
        raw = handle.read()
    plan = json.loads(raw)
    if not isinstance(plan, dict):
        raise FreezeError("freeze plan must be a JSON object")
    missing = [f for f in REQUIRED_PLAN_FIELDS if f not in plan]
    if missing:
        raise FreezeError("freeze plan is missing %r" % missing)
    if not isinstance(plan["attempt_number"], int) or plan["attempt_number"] < 1:
        raise FreezeError("attempt_number must be a positive integer")
    for field in ("package_sha256", "verification_result_sha256",
                  "verification_manifest_sha256", "baseline_preview_sha256",
                  "prior_freeze_attempt_manifest_sha256",
                  "r3_expected_aggregate"):
        if not is_hex64(plan[field]):
            raise FreezeError("%s is not 64 hex characters" % field)
    return plan, sha256_text(raw)


def assert_token_binds_plan(parsed, plan, plan_sha256):
    """Every binding checked separately, so the error names which one failed."""
    if parsed["freeze_plan_sha256"] != plan_sha256:
        raise FreezeError(
            "FREEZE_PLAN_MISMATCH: the token authorises plan %s but the plan "
            "on disk is %s. A freeze approval is bound to one plan and one "
            "attempt."
            % (parsed["freeze_plan_sha256"], plan_sha256))
    if parsed["package_sha256"] != plan["package_sha256"]:
        raise FreezeError(
            "FREEZE_PACKAGE_MISMATCH: token %s, plan %s"
            % (parsed["package_sha256"], plan["package_sha256"]))
    if parsed["verification_sha256"] != plan["verification_result_sha256"]:
        raise FreezeError(
            "FREEZE_VERIFICATION_MISMATCH: token %s, plan %s"
            % (parsed["verification_sha256"], plan["verification_result_sha256"]))
    return True


def assert_plan_matches_disk(plan, level1_root):
    """The plan must describe the package as it is now, not as it was.

    Revision-aware. A plan that carries `bound_artifacts` names the files it
    binds itself, so nothing here is hard-coded to one revision's filenames;
    that is the R5 route. A plan without it is an R4-era plan and is checked
    against R4's four fixed paths, unchanged, so R4 lineage plans still verify.

    R4's list was the defect: it named `build/R4_BUILD_MANIFEST.sha256` and
    three other R4-only files, none of which exists in R5, so an R5 plan was
    refused before a single digest was compared.
    """
    if "bound_artifacts" in plan:
        return assert_bound_artifacts_match_disk(plan, level1_root)
    checks = (
        ("package_sha256", os.path.join(level1_root, "build",
                                        "R4_BUILD_MANIFEST.sha256")),
        ("verification_result_sha256", os.path.join(level1_root, "verification",
                                                    "VERIFICATION_RESULT.json")),
        ("verification_manifest_sha256",
         os.path.join(level1_root, "verification",
                      "VERIFICATION_MANIFEST.sha256")),
        ("prior_freeze_attempt_manifest_sha256",
         os.path.join(level1_root, "build", "freeze_attempt_1",
                      "FREEZE_ATTEMPT_1_MANIFEST.sha256")),
    )
    for field, path in checks:
        if not os.path.isfile(path):
            raise FreezeError("freeze plan names a missing file: %s" % path)
        actual = sha256_file(path)
        if actual != plan[field]:
            raise FreezeError(
                "FREEZE_PLAN_STALE: %s says %s, %s is %s"
                % (field, plan[field], path, actual))
    return True


# ------------------------------------------------------------------ replay
def recorded_attempts(ledger_path):
    if not os.path.exists(ledger_path):
        return []
    out = []
    with io.open(ledger_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def assert_not_replayed(token, plan, ledger_path):
    """A freeze approval is one-time, by token and by attempt alike.

    Two independent refusals. The token digest catches the same token offered
    twice. The attempt number catches a second token minted for an attempt that
    has already consumed one — which is the case a digest comparison alone
    would let through.
    """
    digest = sha256_text(token)
    for prior in recorded_attempts(ledger_path):
        if prior.get("token_sha256") == digest:
            raise FreezeError(
                "FREEZE_TOKEN_REPLAY: this exact freeze token was already "
                "consumed at %s for attempt %s. Produce a new freeze plan and "
                "obtain a new approval."
                % (prior.get("consumed_at_utc"), prior.get("attempt_number")))
        if prior.get("attempt_number") == plan["attempt_number"]:
            raise FreezeError(
                "FREEZE_ATTEMPT_REPLAY: attempt %s already consumed an "
                "approval at %s. A repeat freeze needs a new attempt number "
                "and a new plan."
                % (plan["attempt_number"], prior.get("consumed_at_utc")))
    return True


def append_attempt(ledger_path, token, plan, plan_sha256, outcome, when):
    record = {
        "schema": "wpno.level1.freeze-attempt/1",
        "attempt_number": plan["attempt_number"],
        "token_sha256": sha256_text(token),
        "freeze_plan_sha256": plan_sha256,
        "package_sha256": plan["package_sha256"],
        "verification_result_sha256": plan["verification_result_sha256"],
        "outcome": outcome,
        "consumed_at_utc": when,
    }
    directory = os.path.dirname(ledger_path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    handle = os.open(ledger_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    try:
        os.write(handle, line.encode("utf-8"))
        os.fsync(handle)
    finally:
        os.close(handle)
    return record


# --------------------------------------------------------------- artefacts
def assert_no_freeze_artefact(level1_root):
    """Refuse to start if any part of a previous freeze is still present."""
    mode_path = os.path.join(level1_root, "MODE")
    if os.path.isfile(mode_path):
        with io.open(mode_path, encoding="utf-8") as handle:
            if handle.read().strip() == policy.MODE_FROZEN:
                raise FreezeError("FREEZE_ALREADY_DONE: MODE is %s"
                                  % policy.MODE_FROZEN)
    for rel in ("CONTROL_MANIFEST.sha256", "BASELINE_MANIFEST.json",
                os.path.join("state", "PACKAGE_VERIFIED.json")):
        if os.path.exists(os.path.join(level1_root, rel)):
            raise FreezeError("FREEZE_ARTEFACT_PRESENT: %s" % rel)
    return True


def control_plane_files(level1_root):
    """Every regular file except the runtime directories and the manifest."""
    out = []
    for dirpath, dirnames, filenames in os.walk(level1_root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        relative = os.path.relpath(dirpath, level1_root)
        top = relative.split(os.sep)[0] if relative != "." else ""
        if top in MUTABLE_SUBDIRS:
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, level1_root)
            if rel.split(os.sep)[0] in MUTABLE_SUBDIRS:
                continue
            if rel == "CONTROL_MANIFEST.sha256":
                continue
            if os.path.islink(full):
                raise FreezeError("symlink in control plane: %s" % rel)
            out.append(rel)
    return sorted(out)



# ------------------------------------------------- final-state manifesting
#
# R5 froze a package that failed its own control manifest on exactly one
# entry. The manifest was generated by hashing every control-plane file from
# disk, and MODE was published afterwards, so the manifest recorded the
# pre-freeze `GENERATED_UNVERIFIED` digest for a file the same freeze went on
# to set to `FROZEN`.
#
# The obvious repair is R4's order - publish MODE first, hash afterwards - and
# it is the wrong one. Publishing MODE first opens a window in which the
# package says FROZEN while its manifest and baseline do not yet exist, and a
# package that claims to be finished before it is, is worse than one that
# claims nothing. R5 moved MODE last deliberately and that instinct was right.
#
# What was missing is that the manifest does not have to describe the package
# as it is at the moment it is written. It has to describe the package as it
# will be when the freeze is complete. Staging the final bytes first and
# hashing those keeps MODE last and makes the manifest self-consistent, which
# are not competing requirements once the digest stops coming from disk.

CONTROL_MANIFEST_REL = "CONTROL_MANIFEST.sha256"


def in_manifest_scope(relative):
    """Is `relative` covered by the control manifest?

    Two things sit outside it. The manifest cannot carry its own digest: a
    file whose content includes a hash of itself has no fixed point. And the
    runtime directories are the audit's record rather than its control plane -
    they change while the package is in use, so a frozen digest of them would
    be wrong the moment a phase ran.

    Everything else is inside, MODE included. MODE is the entry R5 got wrong,
    and it is in scope here for the same reason it was in scope there: a MODE
    that could be edited without the manifest noticing would let a frozen
    package be talked back into an unfrozen one.
    """
    if relative == CONTROL_MANIFEST_REL:
        return False
    return relative.split(os.sep)[0] not in MUTABLE_SUBDIRS


def final_state_manifest(level1_root, staged):
    """Digest the control plane as it will be once this freeze is published.

    `staged` maps a relative path to the exact final bytes of a file the
    freeze generates. A staged path that is in manifest scope is hashed from
    those bytes rather than from disk, because disk still holds the pre-freeze
    content. Every other control-plane file is hashed from disk, unchanged.

    A staged path outside manifest scope - the manifest itself, and
    `state/PACKAGE_VERIFIED.json` under the runtime directory - is staged so
    that publication has its bytes, and is deliberately not recorded here.
    """
    if not isinstance(staged, dict):
        raise FreezeError("staged artefacts must be a mapping")
    manifest = {}
    for relative in control_plane_files(level1_root):
        if relative not in staged:
            manifest[relative] = sha256_file(os.path.join(level1_root, relative))
    for relative, text in staged.items():
        if in_manifest_scope(relative):
            manifest[relative] = sha256_text(text)
    if CONTROL_MANIFEST_REL in manifest:
        raise FreezeError("the control manifest cannot record itself")
    return manifest


def serialize_manifest(manifest):
    """The `sha256sum -c` format: digest, two spaces, path, sorted by path."""
    return "".join("%s  %s\n" % (manifest[r], r) for r in sorted(manifest))


def parse_manifest(text):
    """Read a `sha256sum` manifest, refusing anything ambiguous."""
    entries = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if len(line) < 67 or line[64:66] != "  ":
            raise FreezeError("CONTROL_MANIFEST line %d is malformed" % number)
        digest, relative = line[:64], line[66:]
        if not is_hex64(digest):
            raise FreezeError(
                "CONTROL_MANIFEST line %d does not begin with a digest" % number)
        if relative in entries:
            raise FreezeError(
                "CONTROL_MANIFEST names %s twice; one of them would be "
                "unchecked" % relative)
        entries[relative] = digest
    return entries


def verify_manifest_from_disk(level1_root, manifest_path=None):
    """Check every manifest entry against the file on disk.

    The in-process equivalent of `sha256sum -c CONTROL_MANIFEST.sha256`, done
    here so the result is structured rather than parsed back out of text.

    It reports three separate things, because they are three separate
    failures. `failed` is a file whose bytes are not what the manifest says.
    `missing` is a file the manifest names that is not there. `unlisted` is a
    control-plane file that exists and that the manifest does not name - not a
    mismatch, but not covered either, which means it could change and nothing
    here would notice.
    """
    if manifest_path is None:
        manifest_path = os.path.join(level1_root, CONTROL_MANIFEST_REL)
    if not os.path.isfile(manifest_path):
        raise FreezeError("control manifest is absent: %s" % manifest_path)
    with io.open(manifest_path, encoding="utf-8") as handle:
        entries = parse_manifest(handle.read())
    if not entries:
        raise FreezeError(
            "control manifest is empty; an empty manifest verifies trivially "
            "and attests to nothing")

    failed, missing = [], []
    for relative in sorted(entries):
        if relative == CONTROL_MANIFEST_REL:
            failed.append({"path": relative, "reason": "MANIFEST_NAMES_ITSELF"})
            continue
        full = os.path.join(level1_root, relative)
        if os.path.islink(full) or not os.path.isfile(full):
            missing.append(relative)
            continue
        actual = sha256_file(full)
        if actual != entries[relative]:
            failed.append({"path": relative,
                           "recorded": entries[relative],
                           "measured": actual,
                           "reason": "DIGEST_MISMATCH"})
    unlisted = [r for r in control_plane_files(level1_root) if r not in entries]
    return {
        "entries": len(entries),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "unlisted_count": len(unlisted),
        "ok": len(entries) - len(failed) - len(missing),
        "failed": failed,
        "missing": missing,
        "unlisted": unlisted,
        "mode_entry_present": "MODE" in entries,
        "mode_entry_ok": ("MODE" in entries
                          and not any(f["path"] == "MODE" for f in failed)
                          and "MODE" not in missing),
    }


def build_baseline(level1_root):
    """Audited PROJECT_ROOT sources named in bindings, plus every Discovery file.

    The scope is PROJECT_ROOT, and it is enforced rather than described. A
    binding may name a path outside it — `~/.claude/CLAUDE.md` is one — and such
    a path is discarded here. The first R4 freeze recorded it, which put a
    digest of the operator's private configuration into a permanent frozen
    artefact and made the manifest contradict the scope it declares.
    """
    with io.open(os.path.join(level1_root, "paths.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    project = os.path.realpath(os.path.join(level1_root, cfg["project_root"]))
    discovery = os.path.realpath(os.path.join(level1_root, cfg["discovery_root"]))

    named = set()
    bindings_dir = os.path.join(level1_root, "bindings")
    for name in sorted(os.listdir(bindings_dir)):
        with io.open(os.path.join(bindings_dir, name), encoding="utf-8") as fh:
            binding = json.load(fh)
        for item in binding.get("source_evidence", []):
            if item.get("path"):
                named.add(item["path"])
        for path in binding.get("candidate_paths") or []:
            named.add(path)
        if binding.get("productive_target"):
            named.add(binding["productive_target"])

    project_files = []
    excluded = []
    for path in sorted(named):
        absolute = os.path.abspath(
            path if os.path.isabs(path) else os.path.join(project, path))
        if not (absolute == project or absolute.startswith(project + os.sep)):
            excluded.append(absolute)
            continue
        rel = os.path.relpath(absolute, project)
        if os.path.islink(absolute):
            state, digest = "SYMLINK", None
        elif os.path.isfile(absolute):
            state, digest = "FILE", sha256_file(absolute)
        elif os.path.isdir(absolute):
            state, digest = "DIRECTORY", None
        else:
            state, digest = "ABSENT", None
        project_files.append({"path": rel, "sha256": digest, "state": state})

    discovery_files = []
    for dirpath, dirnames, filenames in os.walk(discovery, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            discovery_files.append({"path": os.path.relpath(full, discovery),
                                    "sha256": sha256_file(full)})
    discovery_files.sort(key=lambda d: d["path"])

    baseline = {
        "schema": "wpno.level1.baseline-manifest/1",
        "scope": {
            "audited_sources": ("All PROJECT_ROOT candidate_paths and "
                                "source_evidence source_path values named in "
                                "bindings; duplicates removed; presence state "
                                "captured at freeze time."),
            "discovery": "Every regular non-symlink file under DISCOVERY_ROOT.",
        },
        "project_files": project_files,
        "discovery_files": discovery_files,
    }
    return baseline, sorted(excluded)


def serialize_baseline(baseline):
    """The exact bytes the freeze writes, so a preview digest is meaningful."""
    return json.dumps(baseline, indent=2, sort_keys=True,
                      ensure_ascii=False) + "\n"


def assert_baseline_matches_plan(baseline, plan):
    project = len(baseline["project_files"])
    discovery = len(baseline["discovery_files"])
    if project != plan["expected_project_baseline_count"]:
        raise FreezeError(
            "BASELINE_COUNT_MISMATCH: plan expects %d project entries, built %d"
            % (plan["expected_project_baseline_count"], project))
    if discovery != plan["expected_discovery_baseline_count"]:
        raise FreezeError(
            "BASELINE_COUNT_MISMATCH: plan expects %d Discovery entries, built %d"
            % (plan["expected_discovery_baseline_count"], discovery))
    actual = sha256_text(serialize_baseline(baseline))
    if actual != plan["baseline_preview_sha256"]:
        raise FreezeError(
            "BASELINE_PREVIEW_MISMATCH: plan expects %s, built %s"
            % (plan["baseline_preview_sha256"], actual))
    return True


# ==========================================================================
# R5 REPAIR — the three blockers that stopped freeze attempt 1
# ==========================================================================
#
# A. `build_baseline` derives PROJECT_ROOT membership from absolute paths
#    embedded in the bindings. Those paths are the Mac's. On Ubuntu every one
#    of them resolves outside PROJECT_ROOT, all 34 are excluded, and
#    `project_files` comes out empty. A freeze on that preview would seal a
#    BASELINE_MANIFEST attesting to nothing while looking complete. The repair
#    is `build_baseline_from_predecessor`: membership is taken from the
#    verified R4 baseline — which is what actually declares which files belong
#    — and every member is then re-hashed from the real Ubuntu file and
#    required to equal the digest R4 recorded.
#
# B. `assert_plan_matches_disk` named four R4-only files. It is now
#    plan-driven; see above.
#
# C. There was no freeze driver. That is `controller.cmd_freeze_level1`.
#    Nothing below writes anything: this module stays a pure validator, and
#    the controller is the only thing that writes a freeze artefact.

R5_REVISION = "R5"
R5_PLATFORM = "UBUNTU"

R5_REQUIRED_PLAN_FIELDS = (
    "schema",
    "revision",
    "platform",
    "attempt_number",
    "package_sha256",
    "verification_result_sha256",
    "baseline_preview_sha256",
    "expected_project_baseline_count",
    "expected_discovery_baseline_count",
    "bound_artifacts",
    "predecessor_baseline_manifest_sha256",
    "predecessor_baseline_manifest_path",
)

# Where the predecessor's verified baseline lives inside R5. It is the lineage
# copy, not R4 itself: the freeze reads only its own package, and the copy is
# proved byte-identical to R4 by its recorded digest before it is trusted.
PREDECESSOR_BASELINE_REL = os.path.join(
    "lineage", "R4_EXECUTION", "BASELINE_MANIFEST.json")


def _reject_duplicate_keys(pairs):
    """A JSON object with a repeated key is refused, not silently last-wins.

    Two keys that disagree would let a plan say two different things and have
    the parser pick one.
    """
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise FreezeError("DUPLICATE_JSON_KEY: %r" % key)
        seen.add(key)
    return dict(pairs)


def load_json_strict(path):
    """Read JSON, refusing duplicate keys."""
    with io.open(path, encoding="utf-8") as handle:
        raw = handle.read()
    return json.loads(raw, object_pairs_hook=_reject_duplicate_keys), raw


def confined_path(root, relative):
    """Resolve `relative` under `root`, refusing traversal and symlinks.

    Checked on the resolved path, not on the string. `a/../../etc/passwd`
    and a symlink pointing out of the tree both produce a path outside the
    root, and both are refused here rather than by inspection of the text.
    """
    if not isinstance(relative, str) or not relative:
        raise FreezeError("path must be a non-empty string: %r" % relative)
    if os.path.isabs(relative):
        raise FreezeError("PATH_NOT_RELATIVE: %s" % relative)
    if relative.startswith("\\") or ":" in relative.split(os.sep)[0][1:2]:
        raise FreezeError("PATH_NOT_RELATIVE: %s" % relative)
    root_real = os.path.realpath(root)
    candidate = os.path.join(root_real, relative)
    if os.path.islink(candidate):
        raise FreezeError("SYMLINK_REFUSED: %s" % relative)
    # every intermediate component must also be a real directory, not a link
    walk = root_real
    for part in relative.split(os.sep)[:-1]:
        walk = os.path.join(walk, part)
        if os.path.islink(walk):
            raise FreezeError("SYMLINK_REFUSED: %s" % relative)
    resolved = os.path.realpath(candidate)
    if not (resolved == root_real or resolved.startswith(root_real + os.sep)):
        raise FreezeError("PATH_ESCAPES_ROOT: %s" % relative)
    return resolved


def assert_bound_artifacts_match_disk(plan, level1_root):
    """Every file the plan binds must be present and hash exactly as declared.

    The plan names its own inputs, so this works for any revision and cannot
    drift when a filename changes. Each path is confined under the package
    root, so a plan cannot bind a digest of something outside it.
    """
    bound = plan.get("bound_artifacts")
    if not isinstance(bound, dict) or not bound:
        raise FreezeError("bound_artifacts must be a non-empty object")
    for relative in sorted(bound):
        declared = bound[relative]
        if not is_hex64(declared):
            raise FreezeError(
                "bound_artifacts[%s] is not 64 hex characters" % relative)
        resolved = confined_path(level1_root, relative)
        if not os.path.isfile(resolved):
            raise FreezeError("freeze plan names a missing file: %s" % relative)
        actual = sha256_file(resolved)
        if actual != declared:
            raise FreezeError(
                "FREEZE_PLAN_STALE: %s says %s, the file is %s"
                % (relative, declared, actual))
    return True


def assert_r5_plan_shape(plan):
    """R5 plan invariants that are not digests: revision, platform, attempt."""
    missing = [f for f in R5_REQUIRED_PLAN_FIELDS if f not in plan]
    if missing:
        raise FreezeError("R5 freeze plan is missing %r" % missing)
    if plan["revision"] != R5_REVISION:
        raise FreezeError(
            "FREEZE_REVISION_MISMATCH: plan is for %r, this package is %r"
            % (plan["revision"], R5_REVISION))
    if plan["platform"] != R5_PLATFORM:
        raise FreezeError(
            "FREEZE_PLATFORM_MISMATCH: plan is for %r, this package is %r"
            % (plan["platform"], R5_PLATFORM))
    number = plan["attempt_number"]
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise FreezeError("attempt_number must be a positive integer")
    if number == 1:
        raise FreezeError(
            "FREEZE_ATTEMPT_1_SUPERSEDED: attempt 1 was created before the "
            "freeze mechanism repair and is classified "
            "SUPERSEDED_INVALID_AFTER_FREEZE_MECHANISM_REPAIR. It cannot "
            "authorise a freeze of the repaired package.")
    for field in ("package_sha256", "verification_result_sha256",
                  "baseline_preview_sha256",
                  "predecessor_baseline_manifest_sha256"):
        if not is_hex64(plan[field]):
            raise FreezeError("%s is not 64 hex characters" % field)
    for field in ("expected_project_baseline_count",
                  "expected_discovery_baseline_count"):
        value = plan[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise FreezeError(
                "%s must be a positive integer; a baseline of zero files "
                "attests to nothing" % field)
    return True


def load_r5_freeze_plan(path):
    """Read an R5 freeze plan: duplicate-key strict, shape-checked."""
    plan, raw = load_json_strict(path)
    if not isinstance(plan, dict):
        raise FreezeError("freeze plan must be a JSON object")
    assert_r5_plan_shape(plan)
    return plan, sha256_text(raw)


def load_predecessor_baseline(level1_root, expected_sha256=None):
    """The verified R4 baseline, read from the lineage copy inside R5."""
    resolved = confined_path(level1_root, PREDECESSOR_BASELINE_REL)
    if not os.path.isfile(resolved):
        raise FreezeError(
            "predecessor baseline is absent: %s" % PREDECESSOR_BASELINE_REL)
    actual = sha256_file(resolved)
    if expected_sha256 is not None and actual != expected_sha256:
        raise FreezeError(
            "PREDECESSOR_BASELINE_DRIFT: expected %s, measured %s"
            % (expected_sha256, actual))
    baseline, _ = load_json_strict(resolved)
    for key in ("project_files", "discovery_files"):
        if not isinstance(baseline.get(key), list) or not baseline[key]:
            raise FreezeError("predecessor baseline has no %s" % key)
    return baseline, actual


def build_baseline_from_predecessor(level1_root, expected_sha256=None):
    """The R5 Ubuntu baseline: R4's membership, re-measured on this machine.

    Membership is not re-derived from the bindings. The bindings carry the
    Mac's absolute paths and deriving from them on Ubuntu yields nothing. What
    declares membership is the predecessor's own verified BASELINE_MANIFEST,
    whose paths are already relative to PROJECT_ROOT and DISCOVERY_ROOT.

    Every member is then required to exist here, to be a regular file rather
    than a symlink, to sit inside its root, and to hash to exactly the digest
    R4 recorded. Nothing is substituted, nothing is skipped, and no file that
    R4 did not name is added. A missing or different file raises rather than
    being quietly dropped — a baseline that silently shrank is the failure
    this whole repair exists to prevent.
    """
    with io.open(os.path.join(level1_root, "paths.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    project = os.path.realpath(os.path.join(level1_root, cfg["project_root"]))
    discovery = os.path.realpath(os.path.join(level1_root, cfg["discovery_root"]))

    predecessor, predecessor_sha = load_predecessor_baseline(
        level1_root, expected_sha256)

    def rebuild(records, root, label, keep_state):
        out = []
        seen = set()
        for record in records:
            relative = record["path"]
            if relative in seen:
                raise FreezeError(
                    "DUPLICATE_BASELINE_MEMBER: %s %s" % (label, relative))
            seen.add(relative)
            declared = record["sha256"]
            state = record.get("state")
            if keep_state and state != "FILE":
                raise FreezeError(
                    "UNSUPPORTED_BASELINE_STATE: %s %s is %r. Only FILE is "
                    "carried forward; a symlink or absent member would have to "
                    "be recorded and permitted explicitly by the predecessor "
                    "baseline." % (label, relative, state))
            resolved = confined_path(root, relative)
            if not os.path.isfile(resolved):
                raise FreezeError(
                    "STOP_UBUNTU_SOURCE_BASELINE_NOT_EQUIVALENT: %s baseline "
                    "member is absent on this machine: %s" % (label, relative))
            actual = sha256_file(resolved)
            if actual != declared:
                raise FreezeError(
                    "STOP_UBUNTU_SOURCE_BASELINE_NOT_EQUIVALENT: %s baseline "
                    "member %s hashes %s here but the verified predecessor "
                    "baseline records %s" % (label, relative, actual, declared))
            entry = {"path": relative, "sha256": actual}
            if keep_state:
                entry["state"] = "FILE"
            out.append(entry)
        out.sort(key=lambda d: d["path"])
        return out

    project_files = rebuild(predecessor["project_files"], project,
                            "PROJECT", True)
    discovery_files = rebuild(predecessor["discovery_files"], discovery,
                              "DISCOVERY", False)

    baseline = {
        "schema": "wpno.level1.baseline-manifest/1",
        "scope": {
            "audited_sources": ("All PROJECT_ROOT candidate_paths and "
                                "source_evidence source_path values named in "
                                "bindings; duplicates removed; presence state "
                                "captured at freeze time."),
            "discovery": "Every regular non-symlink file under DISCOVERY_ROOT.",
        },
        "project_files": project_files,
        "discovery_files": discovery_files,
    }
    provenance = {
        "membership_source": "PREDECESSOR_VERIFIED_BASELINE",
        "predecessor_baseline_path": PREDECESSOR_BASELINE_REL,
        "predecessor_baseline_sha256": predecessor_sha,
        "project_root": project,
        "discovery_root": discovery,
        "project_members": len(project_files),
        "discovery_members": len(discovery_files),
        "every_member_rehashed_on_ubuntu": True,
        "every_member_equals_predecessor_digest": True,
        "members_added_beyond_predecessor": 0,
        "members_dropped": 0,
    }
    return baseline, provenance
