"""The R7-to-R8 migration route: what it admits and what it refuses.

Every case here runs against a sandbox that stands in for a frozen R8, and
reads the real R7 beside it. The sandbox is necessary: the route refuses to
run at all while the active package is GENERATED_UNVERIFIED, which is the
first thing it checks and the first case below.

The refusals are the point. Two of R7's three L1-A31 attempts are worth
carrying across and one is not, and the route has to reach that answer by
measuring each attempt rather than by holding a list of two names -- otherwise
it is not a route, it is a hardcoded import with extra steps.
"""

import copy
import json
import os
import shutil
import unittest

from automation import hashing, migration, path_policy

ROOT = path_policy.LEVEL1_ROOT
R7 = os.path.join(os.path.dirname(ROOT), "08.18.26_Level1_Audits_R7")
PACKETS = os.path.join(ROOT, "build", "migration_plan_r7_to_r8")
SANDBOX = os.path.join(ROOT, "work", "_migration_selftest")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def packet_for(phase):
    return read(os.path.join(PACKETS, "PACKET_L1-A31_%s.json" % phase))


class MigrationCase(unittest.TestCase):
    """A sandbox that looks like a frozen R8 with an empty active state."""

    def setUp(self):
        shutil.rmtree(SANDBOX, ignore_errors=True)
        self.root = os.path.join(SANDBOX, "package")
        os.makedirs(os.path.join(self.root, "state"))
        os.makedirs(os.path.join(self.root, "evidence"))
        with open(os.path.join(self.root, "MODE"), "w",
                  encoding="utf-8") as handle:
            handle.write("FROZEN\n")
        shutil.copy2(os.path.join(ROOT, "state", "REVISION.json"),
                     os.path.join(self.root, "state", "REVISION.json"))
        shutil.copy2(os.path.join(ROOT, "state", "progress.json"),
                     os.path.join(self.root, "state", "progress.json"))
        self.saved = []
        self.transitions = []

    def tearDown(self):
        shutil.rmtree(SANDBOX, ignore_errors=True)

    def save_progress(self, progress):
        self.saved.append(copy.deepcopy(progress))
        with open(os.path.join(self.root, "state", "progress.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(progress, handle, indent=2, sort_keys=True)

    def append_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def write_packet(self, packet, name="packet.json"):
        """Write a packet, re-digesting it so it is internally consistent.

        A mutated packet whose digest no longer matches would be refused for
        the digest, which would hide whichever check the case is about.
        """
        body = {k: v for k, v in packet.items()
                if k != "migration_packet_sha256"}
        body["migration_packet_sha256"] = migration.packet_digest(body)
        path = os.path.join(SANDBOX, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(body, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    def apply(self, packet, name="packet.json"):
        return migration.apply(self.root, self.write_packet(packet, name),
                               save_progress=self.save_progress,
                               append_transition=self.append_transition)

    def refuses(self, packet, fragment, name="packet.json"):
        with self.assertRaises(migration.MigrationError) as ctx:
            self.apply(packet, name)
        self.assertIn(fragment, str(ctx.exception))
        return str(ctx.exception)


class ValidImports(MigrationCase):

    def test_run_a_imports(self):
        result = self.apply(packet_for("RUN-A"))
        self.assertTrue(result["imported"])
        self.assertEqual(result["ledger"]["destination"], "L1-A31/RUN-A")
        node = self.saved[-1]["audits"]["L1-A31"]["RUN-A"]
        self.assertEqual(node["state"], "SEALED")
        self.assertEqual(node["verdict"], "UNVERIFIED")
        self.assertTrue(node["imported_from_predecessor"])
        self.assertFalse(node["attempts"]["1"]["approval_token_imported"])

    def test_run_b_imports(self):
        result = self.apply(packet_for("RUN-B"))
        self.assertTrue(result["imported"])
        node = self.saved[-1]["audits"]["L1-A31"]["RUN-B"]
        self.assertEqual(node["state"], "SEALED")
        self.assertEqual(node["verdict"], "UNVERIFIED")

    def test_the_imported_evidence_verifies_against_its_seal(self):
        self.apply(packet_for("RUN-A"))
        imported = os.path.join(self.root, "evidence", "L1-A31", "RUN-A",
                                "attempt-1")
        manifest = os.path.join(imported, "EVIDENCE_MANIFEST.sha256")
        seal = read(os.path.join(imported, "SEAL.json"))
        self.assertEqual(hashing.sha256_file(manifest),
                         seal["manifest_sha256"])
        with open(manifest, encoding="utf-8") as handle:
            rows = [line.strip() for line in handle if line.strip()]
        self.assertTrue(rows)
        for row in rows:
            digest, rel = row.split("  ", 1)
            self.assertEqual(hashing.sha256_file(os.path.join(imported, rel)),
                             digest, rel)

    def test_no_raw_token_reaches_the_imported_state(self):
        self.apply(packet_for("RUN-A"))
        blob = json.dumps(self.saved[-1], sort_keys=True)
        for marker in ("APPROVE-EXECUTION", "RUN-ONCE", "PLAN-SHA256="):
            self.assertNotIn(marker, blob)

    def test_comparison_becomes_eligible_only_after_both_imports(self):
        """The comparison waits for two sealed phases, and stays NOT_STARTED."""
        self.apply(packet_for("RUN-A"), "a.json")
        after_one = self.saved[-1]["audits"]["L1-A31"]
        self.assertEqual(after_one["RUN-B"]["state"], "NOT_STARTED")
        self.assertEqual(after_one["COMPARISON"]["state"], "NOT_STARTED")

        self.apply(packet_for("RUN-B"), "b.json")
        after_two = self.saved[-1]["audits"]["L1-A31"]
        self.assertEqual(after_two["RUN-A"]["state"], "SEALED")
        self.assertEqual(after_two["RUN-B"]["state"], "SEALED")
        # The comparison is now executable and has still not been executed.
        # Importing two phases does not import a third.
        self.assertEqual(after_two["COMPARISON"]["state"], "NOT_STARTED")
        self.assertNotIn("attempts", after_two["COMPARISON"])


class Refusals(MigrationCase):

    def test_the_route_refuses_before_the_freeze(self):
        with open(os.path.join(self.root, "MODE"), "w",
                  encoding="utf-8") as handle:
            handle.write("GENERATED_UNVERIFIED\n")
        self.refuses(packet_for("RUN-A"), "ACTIVE_REVISION_NOT_FROZEN")

    def test_the_unsealed_comparison_is_refused(self):
        """R7's COMPARISON: EXECUTED, unsealed, zero evidence files."""
        packet = packet_for("RUN-A")
        packet.update({
            "source_run_phase": "COMPARISON",
            "destination_run_phase": "COMPARISON",
            "source_attempt_id": "L1-A31/COMPARISON/attempt-1",
        })
        message = self.refuses(packet, "SOURCE_PHASE_NOT_SEALED")
        self.assertIn("EXECUTED", message)

    def _synthetic_predecessor(self, operation):
        """A sealed predecessor attempt whose plan binds `operation`.

        Built rather than borrowed. R7 has no sealed attempt binding an
        in-process operation -- which is the point, and is why this refusal
        cannot be exercised against R7's real material. A synthetic
        predecessor is the only way to show the check fires rather than
        merely existing, and CLAUDE.md section 6 is explicit that a control
        which has not been shown to work has not been tested.
        """
        source = os.path.join(SANDBOX, "synthetic_predecessor")
        evidence = os.path.join(source, "evidence", "L1-A31", "RUN-A",
                                "attempt-1")
        results = os.path.join(source, "results", "L1-A31", "RUN-A",
                               "attempt-1")
        os.makedirs(evidence)
        os.makedirs(results)
        with open(os.path.join(source, "MODE"), "w", encoding="utf-8") as fh:
            fh.write("FROZEN\n")

        target = os.path.join(source, "target.bin")
        with open(target, "wb") as fh:
            fh.write(b"synthetic target\n")

        plan = {"schema": "wpno.level1.execution_plan/1",
                "audit_id": "L1-A31", "run_phase": "RUN-A",
                "steps": [{"step_id": "s1", "operation": operation,
                           "control_role": "MEASUREMENT", "params": {}}],
                "test_matrix": []}
        plan_path = os.path.join(results, "plan.json")
        with open(plan_path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=2, sort_keys=True)

        with open(os.path.join(evidence, "commands.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({"evidence_id": "E0001",
                                 "operation": operation,
                                 "argv": ["/usr/bin/true"],
                                 "exit_code": 0}) + "\n")
        rows = []
        for name in sorted(os.listdir(evidence)):
            full = os.path.join(evidence, name)
            rows.append("%s  %s" % (hashing.sha256_file(full), name))
        manifest_path = os.path.join(evidence, "EVIDENCE_MANIFEST.sha256")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        manifest_sha = hashing.sha256_file(manifest_path)
        seal_path = os.path.join(evidence, "SEAL.json")
        with open(seal_path, "w", encoding="utf-8") as fh:
            json.dump({"audit_id": "L1-A31", "run_phase": "RUN-A",
                       "attempt_number": 1,
                       "manifest_sha256": manifest_sha,
                       "verdict": "UNVERIFIED"}, fh, indent=2, sort_keys=True)

        control = os.path.join(source, "CONTROL_MANIFEST.sha256")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write("%s  results/L1-A31/RUN-A/attempt-1/plan.json\n"
                     % hashing.sha256_file(plan_path))
        os.makedirs(os.path.join(source, "state"))
        with open(os.path.join(source, "state", "progress.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"audits": {"L1-A31": {"RUN-A": {
                "state": "SEALED", "accepted_attempt": 1,
                "attempts": {"1": {
                    "attempt_id": "L1-A31/RUN-A/attempt-1",
                    "plan_sha256": hashing.sha256_file(plan_path),
                    "target_sha256": hashing.sha256_file(target),
                    "evidence_manifest_sha256": manifest_sha,
                    "seal_sha256": hashing.sha256_file(seal_path),
                    "verdict": "UNVERIFIED",
                    "classification": "SUBSTANTIVE_AUDIT_RESULT",
                    "evidence_file_count": len(rows)}}}}}}, fh)

        packet = packet_for("RUN-A")
        packet.update({
            "source_root": source,
            "source_plan_sha256": hashing.sha256_file(plan_path),
            "source_target_path": target,
            "source_target_sha256": hashing.sha256_file(target),
            "source_evidence_manifest_sha256": manifest_sha,
            "source_seal_sha256": hashing.sha256_file(seal_path),
            "source_control_manifest_sha256": hashing.sha256_file(control),
            "source_control_manifest_entries": 1,
            "source_reference_hashes": [],
        })
        return packet

    def test_a_synthetic_predecessor_without_in_process_is_admitted(self):
        """The counter-proof: the fixture is admissible when it is clean.

        Without this, the refusal below would prove only that the synthetic
        predecessor is malformed in some way, not that the in-process check
        is what rejected it.
        """
        packet = self._synthetic_predecessor("FILE_TYPE")
        result = self.apply(packet, "clean_synthetic.json")
        self.assertTrue(result["imported"])

    def test_a_source_plan_with_an_in_process_step_is_refused(self):
        """The check that makes the route generic rather than a name list."""
        packet = self._synthetic_predecessor("SHA256_FILE")
        message = self.refuses(packet, "SOURCE_PLAN_CONTAINS_IN_PROCESS",
                               "in_process_synthetic.json")
        self.assertIn("SHA256_FILE", message)

    def _reseal(self, packet):
        """Rebuild the manifest and seal after editing an attempt's evidence.

        The order matters and is the same order the recorder uses: the
        manifest covers every file except the seal, and the seal then names
        the manifest. Building them the other way round makes each cover the
        other and neither verify.
        """
        evidence = os.path.join(packet["source_root"], "evidence", "L1-A31",
                                "RUN-A", "attempt-1")
        manifest_path = os.path.join(evidence, "EVIDENCE_MANIFEST.sha256")
        seal_path = os.path.join(evidence, "SEAL.json")
        for stale in (manifest_path, seal_path):
            if os.path.isfile(stale):
                os.remove(stale)
        rows = ["%s  %s" % (hashing.sha256_file(os.path.join(evidence, name)),
                            name)
                for name in sorted(os.listdir(evidence))]
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        manifest_sha = hashing.sha256_file(manifest_path)
        with open(seal_path, "w", encoding="utf-8") as fh:
            json.dump({"audit_id": "L1-A31", "run_phase": "RUN-A",
                       "attempt_number": 1,
                       "manifest_sha256": manifest_sha,
                       "verdict": "UNVERIFIED"}, fh, indent=2, sort_keys=True)
        packet["source_evidence_manifest_sha256"] = manifest_sha
        packet["source_seal_sha256"] = hashing.sha256_file(seal_path)
        progress_path = os.path.join(packet["source_root"], "state",
                                     "progress.json")
        progress = read(progress_path)
        row = progress["audits"]["L1-A31"]["RUN-A"]["attempts"]["1"]
        row["evidence_manifest_sha256"] = manifest_sha
        row["seal_sha256"] = packet["source_seal_sha256"]
        with open(progress_path, "w", encoding="utf-8") as fh:
            json.dump(progress, fh)
        return packet

    def test_a_source_that_used_the_defective_branch_is_refused(self):
        """The note the frozen controller wrote instead of running anything."""
        packet = self._synthetic_predecessor("FILE_TYPE")
        evidence = os.path.join(packet["source_root"], "evidence", "L1-A31",
                                "RUN-A", "attempt-1")
        with open(os.path.join(evidence, "commands.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({
                "evidence_id": "E0001", "operation": "FILE_TYPE",
                "argv": [], "exit_code": 0,
                "note": "in-process; performed by the worker"}) + "\n")
        self.refuses(self._reseal(packet), "SOURCE_USED_THE_DEFECTIVE_BRANCH",
                     "defective_branch.json")

    def test_an_evidence_manifest_mismatch_is_refused(self):
        packet = packet_for("RUN-A")
        packet["source_evidence_manifest_sha256"] = "0" * 64
        self.refuses(packet, "EVIDENCE_MANIFEST_SHA256_DRIFT")

    def test_a_seal_mismatch_is_refused(self):
        packet = packet_for("RUN-A")
        packet["source_seal_sha256"] = "1" * 64
        self.refuses(packet, "SEAL_SHA256_DRIFT")

    def test_target_drift_is_refused(self):
        packet = packet_for("RUN-A")
        packet["source_target_sha256"] = "2" * 64
        self.refuses(packet, "TARGET_SHA256_DRIFT")

    def test_reference_drift_is_refused(self):
        packet = copy.deepcopy(packet_for("RUN-A"))
        self.assertTrue(packet["source_reference_hashes"],
                        "the packet binds no references to drift")
        packet["source_reference_hashes"][0]["sha256"] = "3" * 64
        self.refuses(packet, "SOURCE_REFERENCE_DRIFT")

    def test_a_wrong_predecessor_is_refused(self):
        packet = packet_for("RUN-A")
        packet["source_revision"] = "R6"
        self.refuses(packet, "WRONG_PREDECESSOR")

    def test_a_wrong_destination_revision_is_refused(self):
        packet = packet_for("RUN-A")
        packet["destination_revision"] = "R9"
        self.refuses(packet, "WRONG_DESTINATION_REVISION")

    def test_a_control_manifest_drift_in_the_source_is_refused(self):
        packet = packet_for("RUN-A")
        packet["source_control_manifest_sha256"] = "4" * 64
        self.refuses(packet, "SOURCE_CONTROL_MANIFEST_DRIFT")

    def test_an_undisclosed_incident_is_refused(self):
        packet = packet_for("RUN-A")
        packet["predecessor_incident_disclosed"] = False
        self.refuses(packet, "SOURCE_INCIDENT_NOT_DISCLOSED")

    def test_a_packet_carrying_a_token_is_refused(self):
        packet = packet_for("RUN-A")
        packet["note"] = ("APPROVE-EXECUTION L1-A31 RUN=RUN-A "
                          "PLAN-SHA256=%s RUN-ONCE" % ("a" * 64))
        self.refuses(packet, "PACKET_CARRIES_APPROVAL_MATERIAL")

    def test_a_packet_that_does_not_declare_token_exclusion_is_refused(self):
        packet = packet_for("RUN-A")
        packet["approval_token_imported"] = True
        self.refuses(packet, "PACKET_DOES_NOT_DECLARE_TOKEN_EXCLUSION")

    def test_a_tampered_packet_digest_is_refused(self):
        """The one case whose digest is deliberately left inconsistent."""
        packet = packet_for("RUN-A")
        packet["source_verdict"] = "PASS"
        path = os.path.join(SANDBOX, "tampered.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(packet, handle, indent=2, sort_keys=True)
        with self.assertRaises(migration.MigrationError) as ctx:
            migration.apply(self.root, path,
                            save_progress=self.save_progress,
                            append_transition=self.append_transition)
        self.assertIn("PACKET_DIGEST_MISMATCH", str(ctx.exception))

    def test_a_duplicate_import_is_refused(self):
        self.apply(packet_for("RUN-A"), "first.json")
        self.refuses(packet_for("RUN-A"), "PACKET_ALREADY_CONSUMED",
                     "second.json")

    def test_a_replayed_packet_is_refused_even_from_a_new_file(self):
        """Replay is defeated by the packet's digest, not by its filename."""
        self.apply(packet_for("RUN-A"), "original.json")
        self.refuses(packet_for("RUN-A"), "PACKET_ALREADY_CONSUMED",
                     "renamed_copy.json")

    def test_a_destination_that_already_has_an_attempt_is_refused(self):
        self.apply(packet_for("RUN-A"), "first.json")
        packet = packet_for("RUN-A")
        packet["prepared_by"] = "a second preparation of the same phase"
        self.refuses(packet, "DESTINATION_NOT_EMPTY", "again.json")

    def test_a_source_with_fewer_records_than_required_steps_is_refused(self):
        """A sealed attempt that measured less than its plan required."""
        packet = self._synthetic_predecessor("FILE_TYPE")
        evidence = os.path.join(packet["source_root"], "evidence", "L1-A31",
                                "RUN-A", "attempt-1")
        with open(os.path.join(evidence, "commands.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write("")
        self.refuses(self._reseal(packet), "SOURCE_EVIDENCE_INCOMPLETE",
                     "short_evidence.json")


class ThePlanItself(unittest.TestCase):
    """The prepared plan, which the freeze binds and does not apply."""

    def setUp(self):
        self.plan = read(os.path.join(PACKETS, "MIGRATION_PLAN.json"))

    def test_it_is_not_applied_before_the_freeze(self):
        self.assertFalse(self.plan["applied_before_freeze"])
        for packet in self.plan["migratable_attempts"]:
            self.assertFalse(packet["applied"])

    def test_exactly_the_two_sealed_attempts_are_migratable(self):
        got = sorted("%s/%s" % (p["source_audit_id"], p["source_run_phase"])
                     for p in self.plan["migratable_attempts"])
        self.assertEqual(got, ["L1-A31/RUN-A", "L1-A31/RUN-B"])

    def test_the_defective_comparison_is_excluded_by_measured_reason(self):
        excluded = self.plan["excluded_attempts"]
        self.assertEqual(len(excluded), 1)
        row = excluded[0]
        self.assertEqual((row["audit_id"], row["run_phase"]),
                         ("L1-A31", "COMPARISON"))
        self.assertEqual(
            row["exclusion_reason"],
            "EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT")
        self.assertEqual(row["evidence_file_count"], 0)
        self.assertFalse(row["sealed"])

    def test_the_plan_binds_the_route_it_will_be_applied_by(self):
        module = os.path.join(ROOT, self.plan["route_module"])
        self.assertEqual(hashing.sha256_file(module),
                         self.plan["route_module_sha256"])

    def test_the_resume_sequence_freezes_before_it_imports(self):
        steps = self.plan["post_freeze_resume_sequence"]
        self.assertTrue(steps[0].startswith("freeze R8"))
        applied = next(i for i, s in enumerate(steps) if "apply" in s)
        self.assertGreater(applied, 0)


if __name__ == "__main__":
    unittest.main()
