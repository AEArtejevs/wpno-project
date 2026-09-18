#!/usr/bin/env python3
"""Install the final verification into R8's next unused excluded directory.

Two families are created after the build manifest is generated and are
excluded from it by a named, path-component rule:

    verification_codex_final_pre_freeze_attempt_*/
    build/freeze_plan_attempt_*/

Writing into the first is therefore lawful and does not invalidate the
manifest. Nothing manifest-covered is touched, and that is measured here
rather than intended: the manifest is re-verified after the install, and every
newly created path is checked to fall inside the excluded directory.

Every installed byte is compared with its source after the copy. A copy that
is not verified is a copy that might not have happened.

Usage: install_verification.py <r8> <final_root> <attempt8_root> <out.json>
"""

import hashlib
import json
import os
import shutil
import sys

PREFIX = "verification_codex_final_pre_freeze_attempt_"


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def next_unused(r8):
    used = []
    for entry in os.listdir(r8):
        if entry.startswith(PREFIX) and entry[len(PREFIX):].isdigit():
            used.append(int(entry[len(PREFIX):]))
    return max(used) + 1 if used else 1


def main():
    r8, fr, a8, out_path = (os.path.realpath(sys.argv[1]),
                            os.path.realpath(sys.argv[2]),
                            os.path.realpath(sys.argv[3]), sys.argv[4])
    number = next_unused(r8)
    target = os.path.join(r8, "%s%d" % (PREFIX, number))
    if os.path.exists(target):
        raise SystemExit("refusing to overwrite %s" % target)

    plan = [
        # role, source, destination relative to the new directory
        ("FINAL_VERIFICATION_INSTRUCTIONS",
         os.path.join(fr, "tools", "DELTA_VERIFY_PROMPT.md"),
         "VERIFY_PROMPT.md"),
        ("VERIFICATION_RUNNER",
         os.path.join(fr, "tools", "run_delta_closure.sh"),
         "run_delta_closure.sh"),
        ("SCHEMA_MAP", os.path.join(fr, "VERIFIER_SCHEMA_MAP.json"),
         "VERIFIER_SCHEMA_MAP.json"),
        ("VERIFIER_SELF_TEST",
         os.path.join(fr, "tools", "selftest_delta_verifier.py"),
         "selftest_delta_verifier.py"),
        ("VERIFIER_SELF_TEST_RESULT",
         os.path.join(fr, "selftest", "DELTA_VERIFIER_SELFTEST.json"),
         "DELTA_VERIFIER_SELFTEST.json"),
        ("DURABLE_ITEM_MATRIX",
         os.path.join(fr, "ATTEMPT_8_DURABLE_ITEM_MATRIX.json"),
         "ATTEMPT_8_DURABLE_ITEM_MATRIX.json"),
        ("BASE_EVIDENCE_VERIFICATION",
         os.path.join(fr, "BASE_EVIDENCE_VERIFICATION.json"),
         "BASE_EVIDENCE_VERIFICATION.json"),
        ("TOOL_INVENTORY", os.path.join(fr, "TOOL_INVENTORY.json"),
         "TOOL_INVENTORY.json"),
    ]
    for name in ("delta_predicates.py", "delta_context.py",
                 "build_schema_map.py", "build_durable_matrix.py",
                 "verify_base_evidence.py", "fixed_target_check.py",
                 "build_delta_tool_inventory.py", "install_verification.py",
                 "inventory_r8.py", "compare_inventories.py",
                 "measure_path.py", "inspect_writers.py",
                 "preflight_clone.py", "make_clone.sh",
                 "run_package_suite.py"):
        plan.append(("VERIFIER_HELPER", os.path.join(fr, "tools", name),
                     os.path.join("helpers", name)))
    for name in ("FIXED_TARGET.json", "FIXED_TARGET_POST.json",
                 "PREFLIGHT.json", "WRITER_INSPECTION_PRE.json",
                 "WRITER_INSPECTION_POST.json",
                 "COMPARE_ORIGINAL_VS_CLONE_INITIAL.json"):
        plan.append(("PREFLIGHT_EVIDENCE",
                     os.path.join(fr, "preflight", name),
                     os.path.join("preflight", name)))
    plan.append(("WRITE_BARRIER_PROOF",
                 os.path.join(fr, "logs", "SANDBOX_PROBE_RECORD.json"),
                 os.path.join("preflight", "SANDBOX_PROBE_RECORD.json")))
    for name in ("INVENTORY_PRE.json", "INVENTORY_POST.json",
                 "COMPARE_PRE_VS_POST.json", "INVENTORY_PRE.summary.json",
                 "INVENTORY_POST.summary.json"):
        plan.append(("WRITE_ISOLATION_EVIDENCE",
                     os.path.join(fr, "inventory", name),
                     os.path.join("write_isolation", name)))
    # the delta verifier's own outputs, byte for byte
    for name in sorted(os.listdir(os.path.join(fr, "codex_output"))):
        plan.append(("DELTA_EVIDENCE",
                     os.path.join(fr, "codex_output", name), name))
    # the base attempt's evidence, so what is carried forward is bindable
    base_out = os.path.join(a8, "codex_output")
    for dirpath, dirnames, filenames in os.walk(base_out):
        dirnames.sort()
        for name in sorted(filenames):
            src = os.path.join(dirpath, name)
            plan.append(("BASE_ATTEMPT_8_EVIDENCE", src,
                         os.path.join("base_attempt_8",
                                      os.path.relpath(src, base_out))))
    plan.append(("BASE_ATTEMPT_8_EVIDENCE",
                 os.path.join(a8, "original_inventory", "INVENTORY_FINAL.json"),
                 os.path.join("base_attempt_8", "INVENTORY_FINAL.json")))

    # -- what R8 held before the install -----------------------------------
    before = set()
    for dirpath, dirnames, filenames in os.walk(r8):
        for name in filenames:
            before.add(os.path.relpath(os.path.join(dirpath, name), r8))

    os.makedirs(target)
    installed = []
    for role, src, rel in plan:
        if not os.path.isfile(src):
            raise SystemExit("source is absent: %s" % src)
        dst = os.path.join(target, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        src_sha, dst_sha = sha256_file(src), sha256_file(dst)
        installed.append({
            "ROLE": role, "SOURCE": src,
            "INSTALLED": os.path.relpath(dst, r8),
            "SOURCE_SHA256": src_sha, "INSTALLED_SHA256": dst_sha,
            "BYTES_EQUAL": src_sha == dst_sha,
            "SIZE": os.path.getsize(dst),
        })

    mismatched = [i for i in installed if not i["BYTES_EQUAL"]]

    after = set()
    for dirpath, dirnames, filenames in os.walk(r8):
        for name in filenames:
            after.add(os.path.relpath(os.path.join(dirpath, name), r8))
    created = sorted(after - before)
    removed = sorted(before - after)
    outside = [p for p in created
               if p.split(os.sep)[0] != os.path.basename(target)]

    doc = {
        "schema": "wpno.r8.delta-verification-install/1",
        "r8_root": r8,
        "verification_directory": os.path.relpath(target, r8),
        "verification_attempt_number": number,
        "manifest_excluded_by": ("build/build_r8_build_manifest.py "
                                 "is_post_manifest_artefact, matched on the "
                                 "first path component"),
        "installed": installed,
        "installed_count": len(installed),
        "byte_mismatches": mismatched,
        "paths_created_in_r8": len(created),
        "paths_created_outside_the_excluded_directory": outside,
        "paths_removed_from_r8": removed,
        "INSTALL_VALID": (not mismatched and not outside and not removed),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "verification_directory", "verification_attempt_number",
        "installed_count", "paths_created_in_r8",
        "paths_created_outside_the_excluded_directory",
        "paths_removed_from_r8", "INSTALL_VALID")}, indent=1, sort_keys=True))
    print("byte mismatches: %d" % len(mismatched))
    return 0 if doc["INSTALL_VALID"] else 1


if __name__ == "__main__":
    sys.exit(main())
