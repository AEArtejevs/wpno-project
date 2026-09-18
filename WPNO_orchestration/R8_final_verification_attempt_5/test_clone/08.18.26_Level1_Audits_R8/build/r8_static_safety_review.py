"""Static safety review of every Python file R5 changed or added.

An AST review, not a text search. A grep is defeated by a line break; the tree
is not. Where a property is genuinely textual — a forbidden token, a literal
that must be present — the check says so and looks at the source deliberately.

R5 differs from R4's review in one way that matters. R4's review asserted that
the control modules were byte-identical to R3's. R5 changes four of them on
purpose, so the assertion is inverted: the modules R5 was permitted to change
are listed by name with the defect each change repairs, and every other module
must still be byte-identical to R4. A change outside that list is a finding.
"""

import ast
import hashlib
import io
import argparse
import json
import os
import re
import sys
import time

R5 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The names R5 and R4 are kept because every reference below uses them.
# What they point at is this package and its predecessor: in R7 that is
# R7 itself and the complete R6 lineage copy inside it. Comparing against
# the sibling R6 directory would work today and would silently start
# comparing against something else the moment that directory moved; the
# lineage copy is proved byte-identical to R6 and cannot.
# R8: the predecessor is R7, and R8 carries no physical copy of it. The
# reference is the sibling root recorded in R8's own lineage record, and the
# checkpoints below are re-measured against it. Pointing at a copy that does
# not exist would have made this check unrunnable; pointing at the sibling
# without a recorded digest would make it trust a path. The digests are the
# binding, and they are R7's.
R4 = os.path.join(os.path.dirname(R5), "08.18.26_Level1_Audits_R7")

sys.path.insert(0, R5)
from automation import policy  # noqa: E402

# The modules R5 is permitted to change, and the defect each change repairs.
# A change to anything else is a finding, not a judgement call.
PERMITTED_CHANGES = {
    "automation/state_machine.py":
        "R7 section 7: two aggregate states added, RETRYABLE_INTERNAL_ERROR "
        "and BLOCKED_FOR_EXTERNAL_MATERIAL, so that sealing an attempt no "
        "longer necessarily seals the phase. Nothing was removed and no "
        "terminal state gained an exit.",
    "automation/policy.py":
        "R7 section 4: the attempt ceilings — MAX_ATTEMPTS_PER_PHASE, "
        "MAX_REPAIRS_PER_ROOT_CAUSE, MAX_DISTINCT_INTERNAL_REPAIRS, "
        "MAX_REVISION_ESCALATIONS_AFTER_R7 — and FINAL_REVISION.",
    "automation/path_policy.py":
        "R7 section 7: attempt-scoped results, work and evidence directories, "
        "constructed in one place so a plan, its work and its seal cannot "
        "drift apart.",
    "automation/evidence.py":
        "R7 section 7: the recorder is addressed by attempt, and an evidence "
        "id carries the attempt number so two attempts cannot produce the "
        "same id in two sealed manifests. The sealing logic is unchanged.",
    "automation/controller.py":
        "R7 section 7: the phase-attempt model — prepare-retry, "
        "show-attempts, comparison-inputs, attempt-aware execution, and a "
        "finalize-current that classifies the attempt and places the phase. "
        "Section 8: the freeze route's predecessor-lineage binding key is "
        "derived from the freeze module's own constant instead of the literal "
        "lineage/R5_EXECUTION_MANIFEST.sha256, which had gone stale twice.",
    "automation/freeze.py":
        "R7: PACKAGE_REVISION and PREDECESSOR_BASELINE_REL re-pinned from R6 "
        "to R7 and from lineage/R5_EXECUTION to lineage/R6_EXECUTION.",
    "automation/operation_catalog.py":
        "R7 section 9: AUDIT_MODULE_RUN, so a phase can run a frozen second "
        "implementation without executing code from work/, which the freeze "
        "does not cover.",
    "automation/tests/test_prepare_execution.py":
        "R7: the fixture writes its plan at the attempt-1 path the controller "
        "now owns. Every assertion is unchanged.",
    "automation/tests/test_evidence_sealing.py":
        "R7: the isolated-replica guard its sibling module has carried since "
        "R4. Without it these tests created and deleted evidence directories "
        "in whatever package they were run from.",
    "automation/package_tests/__init__.py":
        "R7: generation_root, which resolves a revision's own package root "
        "through the lineage chain by reading state/REVISION.json rather than "
        "by assuming a directory name.",
    "automation/package_tests/test_r5_initialisation.py":
        "R7: R5's assertions are made at R5's generation root, and R5's "
        "identity is read from its own revision record instead of from its "
        "directory name.",
    "automation/package_tests/test_r6_initialisation.py":
        "R7: four assertions describing a freshly initialised revision moved "
        "to test_r7_initialisation.py, where they are true; what replaces "
        "them pins R6's actual history — one phase prepared, approved, "
        "executed and sealed ERROR, with the three wrong parameters still "
        "legible in its plan.",
    "automation/package_tests/test_freeze_order_regression.py":
        "R7 C9: the module's two subprocess.run calls now state shell=False, "
        "a bounded timeout, an explicit environment and a fixed cwd, and the "
        "external sha256sum -c check runs the absolute binary instead of "
        "whatever PATH resolved. A SubprocessDisciplineOfThisModule class "
        "asserts the four requirements about the module's own source. No "
        "assertion, fixture, expected exit code or freeze behaviour changed.",
    "automation/package_tests/test_r5_freeze_repair.py":
        "R7: three cases that had been unreachable since R5 — they reached "
        "FREEZE_REVISION_MISMATCH on a hardcoded \"R5\" before exercising the "
        "rule each was written for. Revision, platform and the predecessor "
        "lineage directory now come from the freeze module's own constants, "
        "and the attempt-1 supersession case, which was R5-specific and no "
        "longer exists in the code, is replaced by the freeze-ledger replay "
        "rule that does.",
}

PERMITTED_ADDITIONS = {
    "automation/attempts.py":
        "R7 section 7: the phase-attempt model — classification, "
        "immutability, retry admission and comparison inputs.",
    "automation/mutation_fixtures.py":
        "R7 section 8 (F3): mutation and negative-control fixtures built at "
        "the layer each claims, and proved before they are returned.",
    "automation/a18_run_a_cli.py":
        "R7: frozen command-line entry for L1-A18 RUN-A, including the "
        "sabotage control, so the plan runs frozen code rather than a script "
        "under work/.",
    "automation/a18_run_b_cli.py":
        "R7: frozen command-line entry for L1-A18 RUN-B. No validation logic.",
    "automation/independent_cms_cli.py":
        "R7: frozen command-line entry for the independent CMS verifier.",
    "run_audit_module.py":
        "R7: the launcher AUDIT_MODULE_RUN invokes, at the package root so "
        "that -I isolation and a frozen import path hold at once. Static "
        "imports and a literal dispatch table; no dynamic module loading.",
    "automation/tests/test_attempt_model.py":
        "R7 section 7: attempt transitions, replay, immutability, "
        "substantive-fail terminality, external-material resumption, limits.",
    "automation/tests/test_l1a31_plan_correction.py":
        "R7 section 8: F1 purpose, F2 epoch, F3 mutation fixture and F4 "
        "controls-fail-for-the-stated-reason, each reproduced then repaired.",
    "automation/package_tests/test_r7_initialisation.py":
        "R7 sections 5 and 6: predecessor integrity, lineage, fresh active "
        "state, and the preservation of R6's failed attempt.",
    "build/build_r8_selftest_replica.py": "rebuilds the isolated test replica",
    "build/stage_l1a31_material.py":
        "R7 section 8: carries R6's staged certificates forward by digest, "
        "cross-checks each against the operator-supplied official material, "
        "and rebuilds the control fixtures.",
    "build/build_candidate_plans.py":
        "R7 section 9: the exact candidate live plans for all nine phases.",
    "build/rehearse_candidate_plans.py":
        "R7 section 9: runs those plans through the exact argv builder and "
        "checks every control against its stated failure reason.",
    "build/r8_static_safety_review.py": "this review",
    "build/resume_r7/tree_snapshot.py":
        "R7 Section 1: the deterministic whole-tree snapshot used to re-measure "
        "R4, R5 and R6 against the digests lineage recorded, before and after "
        "this revision wrote anything.",
    "build/resume_r7/build_r7_build_manifest.py":
        "R7 Section 3: regenerates R7_BUILD_MANIFEST.sha256 in its established "
        "scope, preserves the prior manifest as superseded evidence, and "
        "accounts for every added, removed and changed entry.",
    "build/all_level1_scope/build_all_level1_scope.py":
        "R7 Section 5: derives the 35-audit scope from the registry, bindings, "
        "prompts and the controller's own phase rule, and reports any "
        "contradiction between them rather than reconciling it.",
    "build/all_level1_scope/measure_all_level1_readiness.py":
        "R7 Section 7: measures target and reference readiness for all 35 "
        "audits and names every missing item a human must supply.",
}

SCAN_SCOPES = ("automation", "build", "tools", ".")
SKIP_DIRS = ("__pycache__", "selftest_runtime", "fixtures", "lineage",
             "verification", "work", "state", "results", "evidence",
             "logs", "verification_codex_pre_freeze")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def python_files(root, base):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.relpath(os.path.join(dirpath, name), base))
    return sorted(out)


def _scope_files(scope):
    """The Python files a scope contributes, each file exactly once.

    The "." scope contributes the package root's own files only. Walking it
    recursively would enumerate automation/, build/ and tools/ a second time
    and report every changed file twice — a counter that counts what it
    already counted.
    """
    root = os.path.join(R5, scope)
    if not os.path.isdir(root):
        return []
    if scope == ".":
        return sorted(name for name in os.listdir(root)
                      if name.endswith(".py")
                      and os.path.isfile(os.path.join(root, name)))
    return python_files(root, R5)


def classify():
    changed, added, identical = [], [], []
    for scope in SCAN_SCOPES:
        for rel in _scope_files(scope):
            new, old = os.path.join(R5, rel), os.path.join(R4, rel)
            if not os.path.exists(old):
                added.append(rel)
            elif sha(new) != sha(old):
                changed.append(rel)
            else:
                identical.append(rel)
    return sorted(changed), sorted(added), sorted(identical)


# ------------------------------------------------------------------ checks
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_ATTR_CALLS = {("os", "system"), ("os", "popen"),
                        ("runpy", "run_module"), ("runpy", "run_path"),
                        ("importlib", "__import__"),
                        ("subprocess", "getoutput"),
                        ("subprocess", "getstatusoutput"),
                        ("importlib", "import_module"),
                        ("pickle", "loads"), ("pickle", "load")}
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}

# Anything that would reach the network. None of these may be imported or
# called by a file R5 changed or added.
# Modules that can open a connection. `urllib.parse` is deliberately absent:
# it is string manipulation and cannot reach the network, and the isolation
# check needs it to decode a percent-encoded path. Matching on the top-level
# package would have banned it along with `urllib.request`, which is why the
# match below is on the full dotted name.
NETWORK_MODULES = frozenset((
    "socket", "ssl", "http", "http.client", "urllib.request", "urllib3",
    "ftplib", "smtplib", "telnetlib", "requests", "httpx", "aiohttp",
))
def _network_binaries():
    """Network-reaching commands, assembled from fragments.

    Two lessons from this package's own history are applied here at once.

    The fragments exist so the review does not report itself: a check that has
    to be exempted from its own rule is a check nobody trusts.

    The word boundary exists because the short tokens are substrings of
    ordinary words. `nc` sits inside `rsync` and `since`; `scp` inside no
    English word but plenty of identifiers. CLAUDE.md records exactly this
    failure — `*bea*` matching `Bearbeitung` — and the second version of this
    review reproduced it, flagging its own `rsync` fragment as an `nc` call.
    Matching is therefore anchored on both sides.
    """
    return (
        "cu" + "rl", "wg" + "et", "n" + "c", "ss" + "h", "sc" + "p",
        "rs" + "ync", "pip in" + "stall", "mv" + "n", "grad" + "le",
    )


NETWORK_BINARIES = _network_binaries()

# Trust that is not named explicitly. `-CAfile` alone is not enough: OpenSSL
# will still consult its default file, directory and store unless refused.
def _system_trust_tokens():
    """Also assembled from fragments, for the same reason."""
    return (
        "/etc/ssl" + "/certs", "SSL_CERT" + "_FILE", "SSL_CERT" + "_DIR",
        "default_verify" + "_paths", "load_default" + "_certs",
        "/usr/lib/ssl" + "/certs", "ca-certificates" + ".crt",
    )


SYSTEM_TRUST_TOKENS = _system_trust_tokens()


def _chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def review_file(rel, findings):
    path = os.path.join(R5, rel)
    text = io.open(path, encoding="utf-8").read()
    tree = ast.parse(text, filename=rel)

    def add(rule, detail, line):
        findings.append({"file": rel, "rule": rule, "detail": detail,
                         "line": line})

    # `policy.py` assembles the dangerous tokens from fragments so it does not
    # contain them itself; the review's own token list is likewise data.
    if rel != "automation/policy.py":
        for token in policy.DANGEROUS_TOKENS:
            if token in text:
                add("DANGEROUS_TOKEN", "source contains %r" % token, 0)

    _check_network_invocation(tree, add)

    for token in SYSTEM_TRUST_TOKENS:
        if token in text:
            add("SYSTEM_TRUST_FALLBACK", "source contains %r" % token, 0)

    # Nothing may write into R4.
    if R4 in text:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _chain(node.func)[-1:] == ("open",):
                for kw in node.keywords or []:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                            and "w" in str(kw.value.value):
                        add("WRITE_TO_R4_SUSPECTED", "open(mode=w) near an R4 "
                            "path literal", node.lineno)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("pickle", "marshal"):
                    add("RISKY_IMPORT", alias.name, node.lineno)
                if alias.name in NETWORK_MODULES:
                    add("NETWORK_IMPORT", alias.name, node.lineno)
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module in ("pickle", "marshal"):
                add("RISKY_IMPORT", node.module, node.lineno)
            if node.module in NETWORK_MODULES:
                add("NETWORK_IMPORT", node.module, node.lineno)

        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)

        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            add("DYNAMIC_EXECUTION", node.func.id, node.lineno)
        if len(chain) >= 2 and (chain[-2], chain[-1]) in FORBIDDEN_ATTR_CALLS:
            add("DYNAMIC_EXECUTION", ".".join(chain), node.lineno)

        if chain and chain[-1] in SUBPROCESS_CALLS and "subprocess" in chain:
            kwargs = {kw.arg: kw.value for kw in node.keywords or []}

            shell = kwargs.get("shell")
            if shell is None:
                add("SUBPROCESS_SHELL_UNSET", "shell not stated", node.lineno)
            elif not (isinstance(shell, ast.Constant) and shell.value is False):
                add("SUBPROCESS_SHELL", "shell is not a literal False",
                    node.lineno)

            argv = node.args[0] if node.args else kwargs.get("args")
            if isinstance(argv, ast.Constant) and isinstance(argv.value, str):
                add("SUBPROCESS_COMMAND_STRING", "argv is a command string",
                    node.lineno)

            for required, rule in (("timeout", "SUBPROCESS_NO_TIMEOUT"),
                                   ("env", "SUBPROCESS_NO_EXPLICIT_ENV"),
                                   ("cwd", "SUBPROCESS_NO_FIXED_CWD")):
                if required not in kwargs:
                    add(rule, "%s is not passed" % required, node.lineno)
    return text




# --------------------------------------------------------------------------
# Java and shell
# --------------------------------------------------------------------------
# Section 14 asks for every changed Python, Java and shell file. The Python
# review is an AST review; there is no Java or shell parser in the standard
# library, so those are reviewed against the constructs that would let them
# leave the sandbox, with comments stripped first so a file is not reported
# for describing the thing it refuses to do.

def _java_forbidden():
    """Assembled from fragments, like `policy.DANGEROUS_TOKENS`.

    A scanner that spells out the tokens it looks for matches itself. This
    file reported itself twice before the fragments went in.
    """
    return (
        "ProcessBuilder", "Runtime.getRun" + "time", "Runtime." + "exec",
        "." + "exec" + "(", "ProcessHandle",
        "System.loadLib" + "rary", "System." + "load" + "(",
        "java.net.", "Socket", "URLConnection", "HttpClient",
        "TrustManager" + "Factory", "cacer" + "ts", "setSecurity" + "Manager",
    )


def _shell_forbidden():
    return (
        "ev" + "al ", "cu" + "rl ", "wg" + "et ", "| sh", "|sh", "| bash",
        "rm -rf /", "chmod " + "777", "su" + "do ",
    )


JAVA_FORBIDDEN = _java_forbidden()

SHELL_FORBIDDEN = _shell_forbidden()


def strip_java_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif text[i] in "\"'":
            quote = text[i]
            out.append(text[i])
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i])
                    i += 1
                out.append(text[i])
                i += 1
            if i < n:
                out.append(text[i])
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def strip_shell_comments(text):
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def review_non_python(rel, findings):
    path = os.path.join(R5, rel)
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()

    def add(rule, detail):
        findings.append({"file": rel, "rule": rule, "detail": detail, "line": 0})

    if rel.endswith(".java"):
        code = strip_java_comments(text)
        for token in JAVA_FORBIDDEN:
            if token in code:
                add("JAVA_ESCAPES_THE_SANDBOX", "uses %r" % token)
        if "System.exit" not in code:
            add("JAVA_NO_EXPLICIT_EXIT",
                "the program does not set its own exit status")
    elif rel.endswith(".sh"):
        code = strip_shell_comments(text)
        for token in SHELL_FORBIDDEN:
            if token in code:
                add("SHELL_UNSAFE_CONSTRUCT", "uses %r" % token)
        if "set -e" not in code:
            add("SHELL_NO_ERROR_EXIT", "does not set -e")
    return text


def non_python_files():
    """Java and shell sources, each listed once.

    R7 note: `sorted()` on a list with repeats returns a sorted list with the
    repeats still in it. Once "." joined SCAN_SCOPES, every file under
    automation/, build/ and tools/ was enumerated twice and the report said
    "java/shell: 4" about two files. A count that counts what it already
    counted is the same defect this package has recorded twice before, and it
    would have been bound into the freeze plan as a fact.
    """
    out = set()
    for scope in SCAN_SCOPES:
        root = os.path.join(R5, scope)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if name.endswith(".java") or name.endswith(".sh"):
                    out.add(os.path.relpath(os.path.join(dirpath, name), R5))
    return sorted(out)


def _check_network_invocation(tree, add):
    """Flag a network binary that is *invoked*, not one that is mentioned.

    The two earlier versions of this check searched the source text and were
    both wrong, in opposite directions. A plain substring match reported
    `rsync` as a call to `nc`. Adding word boundaries fixed that and then
    reported `policy.py` for listing `.ssh` among the directories it forbids
    writing to — a protection rule read as a network call — and reported this
    file for the sentence explaining the first bug.

    Prose is not an invocation. Every command this package runs is built from
    string literals in an argv list, so the thing worth looking at is a string
    constant that names one of these binaries: the whole constant, its final
    path component, or the first word of a command string. A docstring that
    discusses `nc` is none of those.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value.strip()
        if not value or len(value) > 200:
            continue
        candidates = {value, value.rsplit("/", 1)[-1]}
        first = value.split(" ", 1)[0]
        candidates.add(first)
        candidates.add(first.rsplit("/", 1)[-1])
        for binary in NETWORK_BINARIES:
            if binary in candidates or value.startswith(binary + " "):
                add("NETWORK_COMMAND",
                    "string constant invokes %r" % binary, node.lineno)

def check_r5_invariants(findings):
    """Properties the R5 remediation must still have."""
    def source(rel):
        return io.open(os.path.join(R5, rel), encoding="utf-8").read()

    catalog = source("automation/operation_catalog.py")
    tree = ast.parse(catalog, filename="automation/operation_catalog.py")

    # known cause 1: the separator must not be emitted by either openssl
    # builder. `--` is legitimate for file(1), so the check is scoped to the
    # `if name == "OPENSSL_..."` blocks rather than to the whole file. The
    # first version of this check compared a line number against a character
    # offset — two different units — and so never rejected anything.
    guarded = ("OPENSSL_VERIFY_CERT_CHAIN", "OPENSSL_VERIFY_CMS")
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare)
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value in guarded):
            continue
        operation = test.comparators[0].value
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and inner.value == "--":
                findings.append({
                    "file": "automation/operation_catalog.py",
                    "rule": "END_OF_OPTIONS_SEPARATOR_PRESENT",
                    "detail": "'--' emitted by %s" % operation,
                    "line": inner.lineno})

    for token, rule in (
            ("NO_DEFAULT_TRUST_FLAGS", "DEFAULT_TRUST_NOT_REFUSED"),
            ("-no-CAfile", "DEFAULT_TRUST_NOT_REFUSED"),
            ("_attime", "VALIDATION_TIME_NOT_REQUIRED"),
            ("_pem_anchor", "DER_ANCHOR_NOT_REJECTED"),
            ("_reject_suppression", "SUPPRESSION_GUARD_MISSING")):
        if token not in catalog:
            findings.append({"file": "automation/operation_catalog.py",
                             "rule": rule, "detail": "%s absent" % token,
                             "line": 0})

    # The isolation set is asserted on the value policy actually computes.
    # Looking for the literal `work/%s/RUN-A` in the source found nothing,
    # because the fragments are built in a loop — the check was wrong, not the
    # code. Asserting the computed tuple cannot drift from what is enforced.
    for audit in policy.REPLICATED_AUDIT_IDS_FOR_ISOLATION:
        for tree_name in ("results", "evidence", "work"):
            fragment = "%s/%s/RUN-A" % (tree_name, audit)
            if fragment not in policy.RUN_B_FORBIDDEN_RESULT_PATH_FRAGMENTS:
                findings.append({
                    "file": "automation/policy.py",
                    "rule": "RUN_A_TREE_NOT_ISOLATED",
                    "detail": "%s is not forbidden to RUN-B" % fragment,
                    "line": 0})
    if not getattr(policy, "RUN_B_ALLOWED_KEYS", None):
        findings.append({"file": "automation/policy.py",
                         "rule": "RUN_B_ALLOWLIST_MISSING",
                         "detail": "RUN_B_ALLOWED_KEYS absent", "line": 0})

    ctx = source("automation/audit_context.py")
    for token, rule in (("isolation_variants", "SPELLING_NORMALISATION_MISSING"),
                        ("run_b_context", "RUN_B_PACKET_BUILDER_MISSING"),
                        ("assert_run_b_may_read", "READ_ENFORCEMENT_MISSING")):
        if token not in ctx:
            findings.append({"file": "automation/audit_context.py",
                             "rule": rule, "detail": "%s absent" % token,
                             "line": 0})

    trust = source("automation/trust_material.py")
    for token, rule in (("_assert_not_in_references", "REFERENCES_WRITABLE"),
                        ("never overwritten", "OVERWRITE_PERMITTED"),
                        ("identity_equal", "IDENTITY_NOT_PROVED")):
        if token not in trust:
            findings.append({"file": "automation/trust_material.py",
                             "rule": rule, "detail": "%s absent" % token,
                             "line": 0})

    ctrl = source("automation/controller.py")
    for name in ("cmd_prepare_execution", "cmd_init_revision",
                 "_append_transition", "parse_approval"):
        if "def %s" % name not in ctrl:
            findings.append({"file": "automation/controller.py",
                             "rule": "MISSING_CONTROL",
                             "detail": "%s is gone" % name, "line": 0})
    if "policy.MAX_OUTPUT_BYTES" not in ctrl:
        findings.append({"file": "automation/controller.py",
                         "rule": "UNBOUNDED_OUTPUT",
                         "detail": "MAX_OUTPUT_BYTES is not applied", "line": 0})
    return findings


def check_unchanged_controls(report):
    """Every control module R5 was NOT permitted to change."""
    rows = {}
    for rel in python_files(os.path.join(R5, "automation"), R5):
        if rel.startswith("automation/tests/") or \
           rel.startswith("automation/package_tests/"):
            continue
        old = os.path.join(R4, rel)
        if not os.path.exists(old):
            continue
        identical = sha(os.path.join(R5, rel)) == sha(old)
        rows[rel] = {
            "r4_sha256": sha(old),
            "r5_sha256": sha(os.path.join(R5, rel)),
            "identical": identical,
            "change_permitted": rel in PERMITTED_CHANGES,
            "reason": PERMITTED_CHANGES.get(rel),
        }
    report["control_modules"] = rows
    report["unpermitted_changes"] = sorted(
        rel for rel, r in rows.items()
        if not r["identical"] and not r["change_permitted"])
    return report


def r4_unchanged():
    """The predecessor's checkpoints, measured from R6 before R7 was created.

    R7 note: these were R4's digests and R4's file count, carried unchanged
    through R5 and R6. The predecessor of this package is R6, so they are R6's
    now. Checking R4's digests against R6's tree would report a change that is
    not a change — the same class of error as a counter that counts what it
    knows.

    R8 note: the predecessor is now R7, so these are R7's, measured from R7's
    own root. BASELINE_MANIFEST.json keeps the same digest because R7 carried
    R6's baseline unchanged, which is the chain working rather than a
    coincidence.
    """
    expected = {
        "CONTROL_MANIFEST.sha256":
            "005e3e890f7ebea0202101c918aa2dc2794b82c9ff8d8c27318ed9f9e15beb57",
        "BASELINE_MANIFEST.json":
            "0e8b18f04d55897b30a1b047cb3af2cbfe6ddbd9be0cb0e201373ddf943e0d7d",
        "state/PACKAGE_VERIFIED.json":
            "1f6f410dd93069da124566f86af6a1d58dfb949d5d2ce7f79432f9bc1e766670",
    }
    rows = {rel: {"expected": want, "actual": sha(os.path.join(R4, rel))}
            for rel, want in expected.items()}
    for row in rows.values():
        row["identical"] = row["expected"] == row["actual"]
    count = sum(len(files) for _, _, files in os.walk(R4))
    return {"checkpoints": rows, "file_count": count,
            "file_count_expected": 16153,
            "unchanged": all(r["identical"] for r in rows.values())
                          and count == 16153}


def write_manifest(paths, base, out_path):
    lines = []
    for rel in sorted(paths):
        lines.append("%s  %s" % (sha(os.path.join(base, rel)), rel))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return sha(out_path)


def review_subprocess_discipline(rel, findings):
    """The four subprocess requirements, checked in EVERY file in scope.

    R7 note, and the reason this function exists separately from
    `review_file`. That function reviews the files this revision changed or
    added, which is the right scope for "did this revision introduce
    something", and the wrong scope for "does this package still hold".

    `automation/package_tests/test_freeze_order_regression.py` was inherited
    from R6 unchanged, so it was never reviewed here, and it carried two
    `subprocess.run` calls with no timeout, no stated `shell`, and — in the
    one that runs the external `sha256sum -c` check — no explicit environment
    and a binary found through PATH. An independent verifier found them by
    reading every file rather than every changed file. It was right to, and
    this is that check, made part of the review so it is not found by luck
    next time.
    """
    path = os.path.join(R5, rel)
    text = io.open(path, encoding="utf-8").read()
    tree = ast.parse(text, filename=rel)

    def add(rule, detail, line):
        findings.append({"file": rel, "rule": rule, "detail": detail,
                         "line": line, "scope": "ALL_FILES_SWEEP"})

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if not (chain and chain[-1] in SUBPROCESS_CALLS
                and "subprocess" in chain):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords or []}
        shell = kwargs.get("shell")
        if shell is None:
            add("SUBPROCESS_SHELL_UNSET", "shell not stated", node.lineno)
        elif not (isinstance(shell, ast.Constant) and shell.value is False):
            add("SUBPROCESS_SHELL", "shell is not a literal False",
                node.lineno)
        argv = node.args[0] if node.args else kwargs.get("args")
        if isinstance(argv, ast.Constant) and isinstance(argv.value, str):
            add("SUBPROCESS_COMMAND_STRING", "argv is a command string",
                node.lineno)
        for required, rule in (("timeout", "SUBPROCESS_NO_TIMEOUT"),
                               ("env", "SUBPROCESS_NO_EXPLICIT_ENV"),
                               ("cwd", "SUBPROCESS_NO_FIXED_CWD")):
            if required not in kwargs:
                add(rule, "%s is not passed" % required, node.lineno)
    return text


def all_python_files_in_scope():
    seen = []
    for scope in SCAN_SCOPES:
        for rel in _scope_files(scope):
            if rel not in seen:
                seen.append(rel)
    return sorted(seen)


def main(argv=None):
    """Review, and write the report where the caller says.

    `--out-dir` exists for the independent verifier. Re-running this review
    into `build/` would rewrite two files the final build manifest already
    covers, and the verifier would then be reporting a manifest mismatch it
    had caused itself -- which is what happened on the first verification
    attempt. The verifier writes into its own excluded directory instead, so
    the review it runs is the same review and the package it is reviewing
    does not move underneath it.
    """
    parser = argparse.ArgumentParser(prog="r8-static-safety-review")
    parser.add_argument("--out-dir", default=os.path.join(R5, "build"),
                        help="where to write the report and the changed-file "
                             "manifest; defaults to build/")
    args = parser.parse_args(argv)
    out_dir = os.path.abspath(args.out_dir)
    if not out_dir.startswith(R5 + os.sep) and out_dir != os.path.join(R5, "build"):
        raise SystemExit("--out-dir must be inside the package: %s" % out_dir)
    os.makedirs(out_dir, exist_ok=True)

    changed, added, identical = classify()
    findings = []
    for rel in changed + added:
        review_file(rel, findings)
    for rel in all_python_files_in_scope():
        if rel not in changed and rel not in added:
            review_subprocess_discipline(rel, findings)
    non_python = non_python_files()
    for rel in non_python:
        review_non_python(rel, findings)
    check_r5_invariants(findings)

    report = {
        "schema": "wpno.level1.static-safety-report/1",
        "revision": "R8",
        "platform": "UBUNTU",
        "reviewed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "predecessor_root": R4,
        "package_root": R5,
        "changed_files": changed,
        "added_files": added,
        "identical_files": identical,
        "java_and_shell_files": non_python,
        "reviewed_file_count": len(changed) + len(added) + len(non_python),
        "subprocess_sweep_file_count": len(all_python_files_in_scope()),
        "findings": findings,
        "finding_count": len(findings),
        "permitted_changes": PERMITTED_CHANGES,
        "permitted_additions": PERMITTED_ADDITIONS,
        "predecessor_unchanged": r4_unchanged(),
        "r4_unchanged": r4_unchanged(),
    }
    check_unchanged_controls(report)

    changed_manifest = os.path.join(out_dir, "R8_CHANGED_FILES.sha256")
    report["changed_files_manifest_sha256"] = write_manifest(
        changed + added + non_python, R5, changed_manifest)

    report["clean"] = (
        not findings
        and not report["unpermitted_changes"]
        and report["r4_unchanged"]["unchanged"])

    out = os.path.join(out_dir, "R8_STATIC_SAFETY_REPORT.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("reviewed  :", report["reviewed_file_count"])
    print("changed   :", len(changed))
    print("added     :", len(added))
    print("java/shell:", len(non_python))
    print("findings  :", len(findings))
    for f in findings[:25]:
        print("   %-34s %s:%s  %s" % (f["rule"], f["file"], f["line"],
                                      f["detail"][:60]))
    print("unpermitted changes:", report["unpermitted_changes"])
    print("R4 unchanged       :", report["r4_unchanged"]["unchanged"])
    print("clean              :", report["clean"])
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
