"""Codex capability detection and worker isolation.

The controller does not assume a Codex CLI version. It records what the
installed binary reports and refuses to plan an operation the installed
version cannot perform in isolation.

Isolation preference order:
  1. a Codex subagent with bounded context;
  2. `codex exec --ephemeral`;
  3. stop — there is no third option, and running without isolation is not
     one of them.
"""

import json
import os
import subprocess
import time

from . import hashing, path_policy, policy


class CodexError(Exception):
    pass


class UnsupportedCapability(CodexError):
    pass


ISOLATION_SUBAGENT = "SUBAGENT_BOUNDED_CONTEXT"
ISOLATION_EPHEMERAL = "EXEC_EPHEMERAL"
ISOLATION_NONE = "NONE"


def _run_readonly(argv, timeout):
    """Run a capability-probe command.

    argv is a literal list. shell interpretation is off — there is no shell in
    this call path at all. The environment is the policy allowlist, and PATH is
    the fixed absolute value so a prepended directory cannot substitute the
    binary.
    """
    started = time.time()
    proc = subprocess.run(  # noqa: S603 - argv list, no shell
        argv,
        shell=False,
        capture_output=True,
        timeout=timeout,
        env=policy.base_environment(),
        cwd=path_policy.LEVEL1_ROOT,
        check=False,
    )
    return {
        "argv": list(argv),
        "exit_code": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", "replace"),
        "stderr": proc.stderr.decode("utf-8", "replace"),
        "started": started,
        "finished": time.time(),
    }


def probe(codex_executable):
    """Record the installed Codex CLI's self-description.

    Three probes, verbatim, stored as evidence. Only options that appear in
    this output may be used later.
    """
    if not os.path.isabs(codex_executable):
        raise CodexError("codex executable must be an absolute path")
    results = []
    for args in (["--version"], ["--help"], ["exec", "--help"]):
        results.append(_run_readonly([codex_executable] + args,
                                     policy.DEFAULT_TIMEOUT_SECONDS))
    return {
        "executable": codex_executable,
        "probes": results,
        "probe_sha256": hashing.sha256_text(
            json.dumps(results, sort_keys=True, ensure_ascii=False)),
    }


def detect_isolation(probe_result):
    """Choose an isolation mode from what the probes actually showed.

    Absence of evidence for a mode is treated as absence of the mode. Guessing
    that an option probably exists is how a worker ends up running with the
    full session context.
    """
    help_text = "\n".join(p["stdout"] + p["stderr"] for p in probe_result["probes"])
    if "subagent" in help_text.lower():
        return ISOLATION_SUBAGENT
    if "--ephemeral" in help_text:
        return ISOLATION_EPHEMERAL
    return ISOLATION_NONE


def assert_isolation_available(mode):
    if mode == ISOLATION_NONE:
        raise UnsupportedCapability(
            "no safe Codex isolation method is available. Stop. Do not run a "
            "Level-1 phase in a shared session: a Planner and a Reviewer that "
            "share context are one opinion, not two.")
    return mode


def write_capability_record(probe_result, mode, out_dir):
    out_dir = path_policy.ensure_dir(out_dir)
    record = {
        "executable": probe_result["executable"],
        "isolation_mode": mode,
        "probe_sha256": probe_result["probe_sha256"],
        "probes": probe_result["probes"],
        "recorded_at": time.time(),
    }
    path = os.path.join(out_dir, "codex_capabilities.json")
    canonical = path_policy.assert_writable(path)
    with open(canonical, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    return canonical


def assert_plan_supported(plan, mode):
    """Refuse a plan the installed Codex cannot run in isolation."""
    assert_isolation_available(mode)
    from . import operation_catalog
    operation_catalog.validate_plan_operations(plan)
    return True
