#!/usr/bin/env python3
"""Build an isolated fixture package that can execute the real freeze route.

Small and synthetic on purpose. The point is not to copy R5 but to give the
actual controller-owned freeze driver everything it demands - a predecessor
baseline whose members really exist and really hash as declared, a bound
lineage manifest, an initialised state, a plan and a token - so the route runs
to completion and the CONTROL_MANIFEST it produces can be checked from disk.
"""
import hashlib, io, json, os, shutil, subprocess, sys

R5 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R5"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def build(base, automation_src):
    """Create <base>/pkg with sibling project and discovery roots."""
    if os.path.isdir(base):
        shutil.rmtree(base)
    pkg = os.path.join(base, "pkg")
    project = os.path.join(base, "project_root")
    discovery = os.path.join(base, "discovery_root")
    for d in (pkg, project, discovery):
        os.makedirs(d)

    # --- control plane carried from R5, plus the automation under test ----
    shutil.copytree(automation_src, os.path.join(pkg, "automation"))
    shutil.rmtree(os.path.join(pkg, "automation", "package_tests"),
                  ignore_errors=True)
    for d in ("bindings", "prompts", "discovery_reconciliation"):
        shutil.copytree(os.path.join(R5, d), os.path.join(pkg, d))
    for f in ("audit_registry.json", "AGENTS.md", "00_COMMON_RULES.md"):
        shutil.copy2(os.path.join(R5, f), os.path.join(pkg, f))
    for dirpath, dirnames, _ in os.walk(pkg):
        for name in list(dirnames):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, name), ignore_errors=True)
                dirnames.remove(name)

    with io.open(os.path.join(pkg, "paths.json"), "w", encoding="utf-8") as fh:
        json.dump({"schema": "wpno.level1.paths/2",
                   "note": "Isolated freeze-order fixture.",
                   "project_root": "../project_root",
                   "discovery_root": "../discovery_root",
                   "level1_root": "."}, fh, indent=2, sort_keys=True)
        fh.write("\n")

    for d in ("state", "results", "evidence", "work", "logs"):
        os.makedirs(os.path.join(pkg, d))

    # --- the synthetic audited sources -----------------------------------
    project_files, discovery_files = [], []
    for i in range(3):
        rel = "src_%d.txt" % i
        p = os.path.join(project, rel)
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write("audited project source %d\n" % i)
        project_files.append({"path": rel, "sha256": sha256_file(p),
                              "state": "FILE"})
    for i in range(2):
        rel = "disc_%d.txt" % i
        p = os.path.join(discovery, rel)
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write("discovery member %d\n" % i)
        discovery_files.append({"path": rel, "sha256": sha256_file(p)})

    # --- the predecessor baseline the freeze reads from lineage -----------
    lineage = os.path.join(pkg, "lineage", "R4_EXECUTION")
    os.makedirs(lineage)
    baseline = {
        "schema": "wpno.level1.baseline-manifest/1",
        "scope": {"audited_sources": "fixture", "discovery": "fixture"},
        "project_files": project_files,
        "discovery_files": discovery_files,
    }
    bpath = os.path.join(lineage, "BASELINE_MANIFEST.json")
    with io.open(bpath, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(baseline, indent=2, sort_keys=True,
                            ensure_ascii=False) + "\n")
    with io.open(os.path.join(lineage, "MODE"), "w", encoding="utf-8") as fh:
        fh.write("FROZEN\n")

    lin_manifest = os.path.join(pkg, "lineage", "R4_EXECUTION_MANIFEST.sha256")
    rows = []
    for dirpath, dirnames, filenames in os.walk(lineage):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rows.append((sha256_file(full),
                         os.path.relpath(full, os.path.join(pkg, "lineage"))))
    with io.open(lin_manifest, "w", encoding="utf-8") as fh:
        fh.write("".join("%s  %s\n" % r for r in sorted(rows, key=lambda x: x[1])))

    # --- pre-freeze MODE ---------------------------------------------------
    with io.open(os.path.join(pkg, "MODE"), "w", encoding="utf-8") as fh:
        fh.write("GENERATED_UNVERIFIED\n")
    return pkg, bpath, lin_manifest


def run(pkg, args, env_extra=None):
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "en_US.UTF-8",
           "PYTHONPATH": pkg, "HOME": os.environ.get("HOME", "/home/ubuntu")}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "automation.controller"] + args,
                          cwd=pkg, env=env, capture_output=True, text=True)


def make_plan(pkg, bpath, lin_manifest, attempt, plan_dir):
    """Build a plan the driver will accept, with a real baseline preview."""
    sys.path.insert(0, pkg)
    for mod in [m for m in list(sys.modules) if m.startswith("automation")]:
        del sys.modules[mod]
    os.chdir(pkg)
    from automation import freeze as fz
    baseline, _prov = fz.build_baseline_from_predecessor(pkg, sha256_file(bpath))
    preview = fz.sha256_text(fz.serialize_baseline(baseline))

    bound = {
        "lineage/R4_EXECUTION_MANIFEST.sha256": sha256_file(lin_manifest),
        "lineage/R4_EXECUTION/BASELINE_MANIFEST.json": sha256_file(bpath),
        "audit_registry.json": sha256_file(os.path.join(pkg,
                                                        "audit_registry.json")),
    }
    plan = {
        "schema": "wpno.level1.freeze-plan/2",
        "revision": "R5",
        "platform": "UBUNTU",
        "attempt_number": attempt,
        "package_sha256": sha256_file(lin_manifest),
        "verification_result_sha256": sha256_file(bpath),
        "baseline_preview_sha256": preview,
        "expected_project_baseline_count": len(baseline["project_files"]),
        "expected_discovery_baseline_count": len(baseline["discovery_files"]),
        "bound_artifacts": bound,
        "predecessor_baseline_manifest_sha256": sha256_file(bpath),
        "predecessor_baseline_manifest_path":
            "lineage/R4_EXECUTION/BASELINE_MANIFEST.json",
        "independence_limitation": "FIXTURE",
    }
    os.makedirs(os.path.join(pkg, plan_dir), exist_ok=True)
    rel = os.path.join(plan_dir, "FREEZE_PLAN.json")
    raw = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with io.open(os.path.join(pkg, rel), "w", encoding="utf-8") as fh:
        fh.write(raw)
    plan_sha = fz.sha256_text(raw)
    token = fz.token_for(plan["package_sha256"],
                         plan["verification_result_sha256"], plan_sha)
    return rel, plan_sha, token
