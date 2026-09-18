#!/usr/bin/env python3
"""Rebuild the controller's required isolated self-test runtime."""

import json
import os
import shutil


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY = os.path.join(ROOT, "verification")
RUNTIME = os.path.join(VERIFY, "selftest_runtime")
PROJECT = os.path.join(VERIFY, "selftest_project_root")
DISCOVERY = os.path.join(VERIFY, "selftest_discovery_root")


def main():
    for path in (RUNTIME, PROJECT, DISCOVERY):
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)
    # `run_audit_module.py` is the frozen launcher AUDIT_MODULE_RUN names, so
    # the replica needs it to build that operation's argv at all.
    for name in ("00_COMMON_RULES.md", "AGENTS.md", "audit_registry.json",
                 "run_audit_module.py"):
        shutil.copy2(os.path.join(ROOT, name), os.path.join(RUNTIME, name))
    # The candidate live plans, so the tests that read the real plan read the
    # real plan rather than skipping. A skipped assertion about the live plan
    # is the shape of gap that let R6 freeze with three wrong parameters.
    shutil.copytree(os.path.join(ROOT, "build", "candidate_plans_r8"),
                    os.path.join(RUNTIME, "build", "candidate_plans_r8"))
    for name in ("automation", "bindings", "discovery_reconciliation",
                 "prompts"):
        shutil.copytree(os.path.join(ROOT, name), os.path.join(RUNTIME, name))
    shutil.rmtree(os.path.join(RUNTIME, "automation", "package_tests"),
                  ignore_errors=True)
    for directory, dirnames, _ in os.walk(RUNTIME):
        for name in list(dirnames):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(directory, name))
                dirnames.remove(name)
    for name in ("state", "results", "evidence", "work"):
        os.makedirs(os.path.join(RUNTIME, name))
    paths = {
        "schema": "wpno.level1.paths/2",
        "note": "Isolated R8 shared-controller self-test replica.",
        "project_root": "../selftest_project_root",
        "discovery_root": "../selftest_discovery_root",
        "level1_root": ".",
    }
    with open(os.path.join(RUNTIME, "paths.json"), "w",
              encoding="utf-8") as handle:
        json.dump(paths, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"runtime": RUNTIME, "rebuilt": True}, sort_keys=True))


if __name__ == "__main__":
    main()
