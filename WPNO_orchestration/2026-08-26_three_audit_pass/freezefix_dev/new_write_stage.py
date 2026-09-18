        # =============== nothing above this line writes =================
        #
        # Staging. Every byte this freeze will publish is computed before
        # anything is published, so the control manifest can be built against
        # the package's final state rather than its current one. That is what
        # lets MODE be published last and still be recorded correctly - the
        # two requirements R5 could not hold at the same time.
        baseline_text = freeze.serialize_baseline(baseline)
        mode_text = policy.MODE_FROZEN + "\n"

        staged = {"BASELINE_MANIFEST.json": baseline_text, "MODE": mode_text}
        manifest = freeze.final_state_manifest(root, staged)
        manifest_text = freeze.serialize_manifest(manifest)
        staged[freeze.CONTROL_MANIFEST_REL] = manifest_text

        if freeze.sha256_text(mode_text) != manifest.get("MODE"):
            raise ControllerError(
                "FREEZE_STAGING_INCONSISTENT: the manifest does not record the "
                "final MODE bytes. This is the R5 regression and the freeze "
                "stops here rather than publishing a package that fails its "
                "own manifest.")

        verified = {
            "schema": "wpno.level1.package-verified/1",
            "revision": freeze.R5_REVISION,
            "platform": freeze.R5_PLATFORM,
            "attempt_number": plan["attempt_number"],
            "frozen_at_utc": stamp,
            "freeze_plan_sha256": plan_sha256,
            "package_sha256": plan["package_sha256"],
            "verification_result_sha256": plan["verification_result_sha256"],
            "baseline_preview_sha256": plan["baseline_preview_sha256"],
            "baseline_provenance": provenance,
            "control_manifest_entries": len(manifest),
            "control_manifest_covers_mode": True,
            "manifest_generation": "FINAL_STATE_STAGED_BYTES",
            "publication_order": ["BASELINE_MANIFEST.json",
                                  "CONTROL_MANIFEST.sha256",
                                  "state/PACKAGE_VERIFIED.json",
                                  "MODE"],
            "independence_limitation": plan.get("independence_limitation"),
        }
        verified_text = json.dumps(verified, indent=2, sort_keys=True) + "\n"
        staged["state/PACKAGE_VERIFIED.json"] = verified_text

        # The attempt is recorded as started before the first byte is
        # published. It burns the token either way: an attempt that got as far
        # as writing must not be retried under the same approval, whatever
        # happens next. Nothing is recorded as successful yet.
        freeze.append_attempt(FREEZE_LEDGER_PATH, args.token, plan,
                              plan_sha256, "PUBLISH_STARTED", stamp)

        # Publication, MODE last. Until MODE lands the package still reads
        # GENERATED_UNVERIFIED, so a failure part way through leaves a package
        # that is visibly unfinished rather than one that falsely claims to be
        # frozen.
        order = ("BASELINE_MANIFEST.json", freeze.CONTROL_MANIFEST_REL,
                 "state/PACKAGE_VERIFIED.json", "MODE")
        written = {}
        try:
            for rel in order:
                destination = (mode_path if rel == "MODE"
                               else os.path.join(root, *rel.split("/")))
                _, written[rel] = _freeze_write(destination, staged[rel])
        except Exception as exc:
            freeze.append_attempt(
                FREEZE_LEDGER_PATH, args.token, plan, plan_sha256,
                "FAILED_DURING_PUBLICATION", stamp)
            raise ControllerError(
                "FREEZE_PUBLICATION_FAILED after %r: %s. MODE is %r. The "
                "attempt is recorded as failed and this approval is spent; a "
                "further attempt needs a new plan and a new token."
                % (sorted(written), exc, _read_mode()))

        # --- post-publication verification, against the real package -----
        #
        # Not a re-read of what was just written - that only proves the write
        # landed, which is what R5 checked and why R5 reported a frozen
        # package that was not one. This verifies the published manifest
        # against the published files, the same question `sha256sum -c` asks.
        report = freeze.verify_manifest_from_disk(root)
        current_mode = _read_mode()
        healthy = (report["failed_count"] == 0
                   and report["missing_count"] == 0
                   and report["unlisted_count"] == 0
                   and report["mode_entry_ok"]
                   and current_mode == policy.MODE_FROZEN)
        if not healthy:
            freeze.append_attempt(
                FREEZE_LEDGER_PATH, args.token, plan, plan_sha256,
                "FAILED_POST_PUBLICATION_VERIFICATION", stamp)
            raise ControllerError(
                "FREEZE_POST_VERIFICATION_FAILED: %s. The package is NOT "
                "valid frozen evidence and is not reported as frozen. It is "
                "preserved as it stands for root-cause work; a repair belongs "
                "in a successor revision, never in this one."
                % json.dumps({"failed": report["failed"][:5],
                              "missing": report["missing"][:5],
                              "unlisted": report["unlisted"][:5],
                              "mode_entry_ok": report["mode_entry_ok"],
                              "mode": current_mode}, sort_keys=True))

        freeze.append_attempt(FREEZE_LEDGER_PATH, args.token, plan,
                              plan_sha256, "FROZEN", stamp)

        print(json.dumps({
            "frozen": True,
            "revision": freeze.R5_REVISION,
            "attempt_number": plan["attempt_number"],
            "freeze_plan_sha256": plan_sha256,
            "artefacts": written,
            "project_baseline_count": len(baseline["project_files"]),
            "discovery_baseline_count": len(baseline["discovery_files"]),
            "control_manifest_verified_from_disk": {
                "entries": report["entries"],
                "ok": report["ok"],
                "failed": report["failed_count"],
                "missing": report["missing_count"],
                "unlisted": report["unlisted_count"],
                "mode_entry_ok": report["mode_entry_ok"],
            },
        }, indent=2, sort_keys=True))
        return 0
