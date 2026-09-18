"""Per-audit, per-phase context.

Builds the exact input a Planner or a Reviewer receives. RUN-B isolation is
enforced here, by construction: the context is assembled from a fixed literal,
so there is no path by which a RUN-A conclusion reaches it, and the assembled
structure is then checked twice over.

What the two checks look at, and why they are two:

* **Forbidden keys.** A conclusion arrives named. `verdict`, `findings`,
  `self_critique`, `disproof`, `expected_conclusion` and their neighbours are
  refused as dictionary keys, at any depth, in any list.
* **Forbidden result paths.** A conclusion can also arrive as a pointer. Any
  string value that names another phase's results or evidence directory is
  refused.

What they deliberately do NOT look at is the phase label. The predecessor
package serialised the whole context to JSON and searched the text for the
forbidden names. `RUN-A` is one of those names, and `run_phase` legitimately
holds the value `"RUN-A"`, so every valid RUN-A context was rejected by the
control meant to protect RUN-B from it. The phase label is metadata. Metadata
that says which run this is cannot be the leak, because both runs are told
which run they are.

The two control-plane documents — the common rules and the audit specification
— are excluded from the result-path scan. They are the package's own text and
they name those paths on purpose, in the OUTPUT FILES section. Scanning them
would reject every replicated audit for quoting its own file layout, which is
the same mistake in a different place.
"""

import json
import os
import posixpath
import unicodedata
import urllib.parse

from . import hashing, path_policy, policy, redaction


class ContextError(Exception):
    pass


PLANNER_KEYS = (
    "common_rules",
    "audit_prompt",
    "binding",
    "discovery_facts",
    "target_static_content",
    "operation_catalog",
)

REVIEWER_KEYS = (
    "target_identity",
    "target_sha256_before",
    "target_sha256_after",
    "evidence",
    "command_logs",
    "positive_control_result",
    "negative_control_result",
    "mutation_result",
    "independent_oracle",
    "runtime_outputs",
)

# What a Reviewer must never see. A Reviewer told what the Planner expected
# will find it, and the second opinion collapses into the first.
REVIEWER_FORBIDDEN_KEYS = (
    "planner_conclusion",
    "predicted_conclusion",
    "expected_verdict",
    "plan_rationale",
)

# The identical key set both replicated phases receive. RUN-A and RUN-B differ
# in exactly one value — the phase label — and in nothing else.
REPLICATION_KEYS = (
    "common_rules",
    "audit_specification",
    "target_identity",
    "target_sha256",
    "minimal_discovery_evidence",
    "independent_oracle_material",
    "run_phase",
)

# Control-plane documents. Excluded from the result-path scan because they are
# this package's own specification text and name the layout deliberately.
CONTROL_PLANE_KEYS = ("common_rules", "audit_specification")


def _read_text(path):
    canonical = path_policy.assert_readable(path)
    with open(canonical, encoding="utf-8") as fh:
        return fh.read()


def load_registry():
    path = os.path.join(path_policy.LEVEL1_ROOT, "audit_registry.json")
    return json.loads(_read_text(path))


def registry_entry(audit_id):
    for entry in load_registry()["audits"]:
        if entry["audit_id"] == audit_id:
            return entry
    raise ContextError("audit not in registry: %s" % audit_id)


def load_binding(audit_id):
    path = os.path.join(path_policy.LEVEL1_ROOT, "bindings",
                        "%s.binding.json" % audit_id)
    return json.loads(_read_text(path))


def planner_context(audit_id, discovery_facts, target_static_content):
    """Assemble the Planner's input. Only the six allowlisted keys."""
    from . import operation_catalog
    entry = registry_entry(audit_id)
    context = {
        "common_rules": _read_text(
            os.path.join(path_policy.LEVEL1_ROOT, "00_COMMON_RULES.md")),
        "audit_prompt": _read_text(
            os.path.join(path_policy.LEVEL1_ROOT, entry["prompt_file"])),
        "binding": load_binding(audit_id),
        "discovery_facts": discovery_facts,
        "target_static_content": target_static_content,
        "operation_catalog": {
            "automatic": list(operation_catalog.AUTOMATIC),
            "gated": list(operation_catalog.GATED),
            "forbidden": list(operation_catalog.FORBIDDEN),
        },
    }
    _assert_keys(context, PLANNER_KEYS, "planner")
    return context


def reviewer_context(payload):
    """Assemble the Reviewer's input and strip anything predictive."""
    context = {k: payload.get(k) for k in REVIEWER_KEYS}
    for forbidden in REVIEWER_FORBIDDEN_KEYS:
        if forbidden in payload:
            raise ContextError(
                "reviewer context must not carry %r — the Reviewer produces "
                "the verdict and may not be told what was expected" % forbidden)
    _assert_keys(context, REVIEWER_KEYS, "reviewer")
    return context


def replication_context(audit_id, run_phase, target_identity, target_sha256,
                        discovery_evidence, oracle_material):
    """Assemble the context for one phase of a replicated audit.

    RUN-A and RUN-B receive the same seven items. Neither receives any output
    of the other. This is enforced by building the dictionary from a literal
    and then asserting isolation over the assembled structure — belt and
    braces, because this is the guarantee the whole replication rests on.

    Both phases are validated identically. A control that treats the two runs
    differently is a control that can be argued with.
    """
    if run_phase not in ("RUN-A", "RUN-B", "COMPARISON"):
        raise ContextError("unknown run phase: %r" % run_phase)
    if run_phase == "COMPARISON":
        raise ContextError(
            "COMPARISON is assembled by comparison_context, not here")

    entry = registry_entry(audit_id)
    context = {
        "common_rules": _read_text(
            os.path.join(path_policy.LEVEL1_ROOT, "00_COMMON_RULES.md")),
        "audit_specification": _read_text(
            os.path.join(path_policy.LEVEL1_ROOT, entry["prompt_file"])),
        "target_identity": target_identity,
        "target_sha256": target_sha256,
        "minimal_discovery_evidence": discovery_evidence,
        "independent_oracle_material": oracle_material,
        "run_phase": run_phase,
    }
    _assert_keys(context, REPLICATION_KEYS, "replication")
    assert_run_b_isolated(context)
    return context


def _walk_keys(node):
    """Yield every dictionary key in a nested structure, at every depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            for found in _walk_keys(value):
                yield found
    elif isinstance(node, (list, tuple)):
        for item in node:
            for found in _walk_keys(item):
                yield found


def _walk_strings(node):
    """Yield every string value in a nested structure, at every depth.

    Dictionary keys are yielded too: a key is a string a leak can hide in.
    """
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            for found in _walk_strings(value):
                yield found
    elif isinstance(node, (list, tuple)):
        for item in node:
            for found in _walk_strings(item):
                yield found


def assert_no_forbidden_keys(context):
    """Raise if any forbidden key name appears anywhere in the structure.

    Keys only. Never values: the phase label is a value, and rejecting it is
    how the predecessor rejected every legitimate RUN-A context.
    """
    forbidden = set(policy.RUN_B_FORBIDDEN_KEYS)
    for key in _walk_keys(context):
        if key in forbidden:
            raise ContextError(
                "RUN-B isolation violated: context contains key %r" % key)
    return True


def isolation_variants(text):
    """Every spelling of one string that could name the same location.

    A substring test over the literal string is the check R4 shipped, and a
    substring test only ever catches the spelling someone happened to think
    of. `results/L1-A31/RUN-A` is one spelling. So are

        results/L1-A31/run-a                       (case)
        results/L1-A31/RUN-B/../RUN-A              (relative traversal)
        results\\L1-A31\\RUN-A                      (separator)
        results/L1-A31/RUN%2DA                     (percent-encoding)
        results/L1-A31/RUN-A  with U+0041 decomposed neighbours  (NFC/NFD)
        work/L1-A31/RUN-A-link                     (symlink, resolved below)

    and every one of them reaches the same bytes. The variants are generated
    here, once, so that the two callers cannot disagree about what counts.
    """
    variants = []

    def add(value):
        if value and value not in variants:
            variants.append(value)

    if not isinstance(text, str):
        return variants

    nfc = unicodedata.normalize("NFC", text)
    nfd = unicodedata.normalize("NFD", text)
    for form in (nfc, nfd):
        slashed = form.replace("\\", "/")
        add(form.lower())
        add(slashed.lower())
        try:
            add(urllib.parse.unquote(slashed).lower())
        except (ValueError, UnicodeDecodeError):
            pass
        # Collapse traversal lexically. normpath is applied to the whole
        # string: a value that is not a path is unchanged by it, and a value
        # that is one loses its `..` segments.
        try:
            add(posixpath.normpath(slashed).lower())
            add(posixpath.normpath(
                urllib.parse.unquote(slashed)).lower())
        except (ValueError, UnicodeDecodeError):
            pass

    # Symlinks. A link is only visible on the filesystem, so the string is
    # resolved when — and only when — it actually names something. lexists is
    # used rather than exists so a dangling link is still resolved and still
    # checked; a link that points at RUN-A is a leak whether or not RUN-A has
    # been written yet.
    try:
        candidate = nfc.replace("\\", "/")
        if candidate.startswith("/") and os.path.lexists(candidate):
            resolved = unicodedata.normalize("NFC", os.path.realpath(candidate))
            add(resolved.lower())
            try:
                add(os.path.relpath(
                    resolved, path_policy.LEVEL1_ROOT).lower())
            except ValueError:
                pass
    except (OSError, ValueError):
        pass

    return variants


def assert_no_other_phase_result_paths(context):
    """Raise if a string value points at another phase's results or evidence.

    A conclusion does not have to be copied in to leak. A path to it is enough,
    because the worker can read a path — and a path has more than one spelling.
    Every spelling `isolation_variants` can produce is tested against every
    forbidden fragment.
    """
    scanned = {k: v for k, v in context.items()
               if k not in CONTROL_PLANE_KEYS} \
        if isinstance(context, dict) else context
    fragments = policy.RUN_B_FORBIDDEN_PATH_FRAGMENTS_NORMALIZED
    for text in _walk_strings(scanned):
        for variant in isolation_variants(text):
            for fragment in fragments:
                if fragment in variant:
                    raise ContextError(
                        "RUN-B isolation violated: context references another "
                        "phase's result path %r (matched spelling %r)"
                        % (fragment, variant[:200]))
    return True


def assert_run_b_isolated(context):
    """Both isolation checks. Neither substitutes for the other."""
    assert_no_forbidden_keys(context)
    assert_no_other_phase_result_paths(context)
    return True


def comparison_context(audit_id, run_a_result, run_b_result):
    """COMPARISON is the only phase that sees both runs."""
    return {
        "audit_id": audit_id,
        "run_a": run_a_result,
        "run_b": run_b_result,
        "instruction": (
            "Report agreement or disagreement. A disagreement between the two "
            "runs is a finding in its own right and is never resolved by "
            "preferring the run that matches expectation. A disagreement never "
            "becomes PASS automatically."),
    }


def _assert_keys(context, expected, label):
    missing = [k for k in expected if k not in context]
    if missing:
        raise ContextError("%s context missing keys: %r" % (label, missing))
    extra = [k for k in context if k not in expected]
    if extra:
        raise ContextError("%s context has unexpected keys: %r" % (label, extra))
    return True


def redacted_for_report(context):
    """A context safe to quote in a report."""
    return redaction.redact_structure(context)


def context_fingerprint(context):
    return hashing.sha256_text(
        json.dumps(context, sort_keys=True, default=str, ensure_ascii=False))


# ---------------------------------------------------------------------------
# RUN-B input packet
# ---------------------------------------------------------------------------
# R5 CHANGE (known cause 5). R4 built RUN-A and RUN-B from the same seven-key
# literal. That is symmetric, which reads well, but symmetry is not isolation:
# the seven keys included `independent_oracle_material`, and nothing bounded
# what an operator could put in it. RUN-B now receives an allowlisted packet
# whose keys are fixed by policy, whose every value is scanned, and which
# carries facts about RUN-A rather than any output of RUN-A.
#
# What RUN-B is told about RUN-A is deliberately two booleans. Whether RUN-A
# reached a terminal state and whether its seal is intact are sequencing facts
# the controller needs to order the phases. Neither discloses what RUN-A found.

def run_b_context(audit_id, target_path, target_sha256, immutable_pre_run_packet,
                  validation_time, independent_method, required_controls,
                  run_a_terminal, run_a_seal_integrity,
                  phase_sequencing=None):
    """Assemble the only structure a RUN-B worker may receive.

    Every argument is a fact about the target or about the method. None is an
    output of RUN-A. `run_a_terminal` and `run_a_seal_integrity` are booleans
    and are asserted to be booleans: a string here could carry a verdict.
    """
    if not isinstance(run_a_terminal, bool):
        raise ContextError(
            "run_a_terminal must be a bool; a non-boolean can carry a verdict")
    if not isinstance(run_a_seal_integrity, bool):
        raise ContextError(
            "run_a_seal_integrity must be a bool; a non-boolean can carry a "
            "verdict")
    if not hashing.is_hex64(target_sha256):
        raise ContextError("target_sha256 must be 64 hex characters")
    if not isinstance(validation_time, int):
        raise ContextError("validation_time must be an integer epoch second")
    if not isinstance(required_controls, (list, tuple)) or not required_controls:
        raise ContextError(
            "required_controls must be a non-empty sequence; a phase with no "
            "declared controls cannot be shown to have run any")

    context = {
        "audit_id": audit_id,
        "phase_sequencing": list(
            phase_sequencing or policy.RUN_PHASES_REPLICATED),
        "run_a_terminal": run_a_terminal,
        "run_a_seal_integrity": run_a_seal_integrity,
        "target_path": target_path,
        "target_sha256": target_sha256,
        "immutable_pre_run_packet": immutable_pre_run_packet,
        "validation_time": validation_time,
        "independent_method": independent_method,
        "required_controls": list(required_controls),
        "run_phase": "RUN-B",
    }
    _assert_keys(context, policy.RUN_B_ALLOWED_KEYS, "run-b")
    assert_run_b_isolated(context)
    return context


FORBIDDEN_READ_TREES = ("results", "evidence", "work")


def run_b_forbidden_read_roots(audit_id):
    """The absolute directories a RUN-B for this audit may not read.

    Returned as absolute paths so a caller enforcing the policy at the
    filesystem level does not have to rebuild them and get it wrong.
    """
    return tuple(
        os.path.join(path_policy.LEVEL1_ROOT, tree, audit_id, "RUN-A")
        for tree in FORBIDDEN_READ_TREES)


def assert_run_b_may_read(audit_id, path):
    """Raise unless `path` is outside every RUN-A tree for this audit.

    Applied to the resolved path, so a symlink or a `..` cannot walk in.
    """
    path_policy.assert_no_symlink_escape(path)
    resolved = path_policy.normalize(path)
    for root in run_b_forbidden_read_roots(audit_id):
        root_n = unicodedata.normalize("NFC", os.path.realpath(root))
        if resolved == root_n or resolved.startswith(root_n + os.sep):
            raise ContextError(
                "RUN-B isolation violated: RUN-B for %s may not read %s"
                % (audit_id, resolved))
    return resolved
