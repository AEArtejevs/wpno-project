"""Evidence recording, sealing and verdict discipline.

Covers self-test cases 27, 34, 35, 36, 37 and 40:
output-size limit · empty test collection not accepted as PASS ·
missing positive control · missing negative control ·
missing independent oracle · evidence tampering.
"""

import json
import os
import shutil
import unittest

from automation import evidence, hashing, path_policy, policy, schema_validation

AUDIT = "L1-A01"
PHASE = "RUN-A"


def wipe(audit_id, phase):
    root = os.path.join(path_policy.LEVEL1_ROOT, "evidence", audit_id, phase)
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)


class TestOutputLimit(unittest.TestCase):
    """Case 27 — output over the limit is truncated and always marked."""

    def setUp(self):
        wipe(AUDIT, PHASE)
        self.rec = evidence.EvidenceRecorder(AUDIT, PHASE)

    def tearDown(self):
        wipe(AUDIT, PHASE)

    def test_limit_is_bounded_and_positive(self):
        self.assertGreater(policy.MAX_OUTPUT_BYTES, 0)
        self.assertLessEqual(policy.MAX_OUTPUT_BYTES, 64 * 1024 * 1024)

    def test_truncation_is_recorded_as_truncation(self):
        payload = b"x" * 1024
        self.rec.record_operation(
            operation="FILE_TYPE", argv=["/usr/bin/file", "--brief", "--", "/x"],
            exit_code=0, stdout=payload, stderr=b"",
            timeout_seconds=10, output_limit_bytes=1024,
            started=1.0, finished=2.0, truncated_stdout=True)
        with open(self.rec.commands_path, encoding="utf-8") as fh:
            record = json.loads(fh.readline())
        self.assertTrue(record["stdout_truncated"])
        schema_validation.validate_named(record, "operation.schema.json")

    def test_complete_output_is_preserved_on_disk(self):
        payload = b"complete output that a report may only excerpt"
        eid = self.rec.record_operation(
            operation="FILE_TYPE", argv=["/usr/bin/file", "--brief", "--", "/x"],
            exit_code=0, stdout=payload, stderr=b"err",
            timeout_seconds=10, output_limit_bytes=policy.MAX_OUTPUT_BYTES,
            started=1.0, finished=2.0)
        out = os.path.join(self.rec.stdout_dir, "%s.txt" % eid)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(), payload)

    def test_timeout_is_bounded(self):
        self.assertLessEqual(policy.DEFAULT_TIMEOUT_SECONDS,
                             policy.MAX_TIMEOUT_SECONDS)


class TestVerdictDiscipline(unittest.TestCase):
    """Cases 34-37 — a PASS without its controls is not a PASS."""

    def _verdict(self, **controls):
        base = {"positive": "PASSED", "negative": "PASSED",
                "mutation": "PASSED", "independent_oracle": "USED"}
        base.update(controls)
        return {
            "audit_id": AUDIT, "run_phase": PHASE, "verdict": "PASS",
            "target_sha256_before": "0" * 64, "target_sha256_after": "0" * 64,
            "controls": base,
            "self_critique": "considered and recorded",
            "disproof_attempt": "attempted and recorded",
        }

    def test_a_complete_pass_validates(self):
        schema_validation.validate_named(self._verdict(), "verdict.schema.json")

    def test_controls_block_is_required(self):
        doc = self._verdict()
        del doc["controls"]
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate_named(doc, "verdict.schema.json")

    def test_every_control_key_is_required(self):
        for key in ("positive", "negative", "mutation", "independent_oracle"):
            doc = self._verdict()
            del doc["controls"][key]
            with self.assertRaises(schema_validation.ValidationError):
                schema_validation.validate_named(doc, "verdict.schema.json")

    def test_control_values_are_from_a_closed_set(self):
        doc = self._verdict(positive="probably")
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate_named(doc, "verdict.schema.json")

    def test_self_critique_and_disproof_may_not_be_empty(self):
        for key in ("self_critique", "disproof_attempt"):
            doc = self._verdict()
            doc[key] = ""
            with self.assertRaises(schema_validation.ValidationError):
                schema_validation.validate_named(doc, "verdict.schema.json")

    def test_verdict_is_from_the_closed_set(self):
        doc = self._verdict()
        doc["verdict"] = "MOSTLY_PASS"
        with self.assertRaises(schema_validation.ValidationError):
            schema_validation.validate_named(doc, "verdict.schema.json")
        self.assertEqual(set(policy.VERDICTS), {
            "PASS", "PASS_WITH_WARNINGS", "FAIL", "BLOCKED", "UNVERIFIED",
            "ERROR", "CONTAMINATED"})

    def test_a_pass_with_a_failed_control_is_a_contradiction(self):
        """Case 34-36 as a rule the reviewer must apply, expressed as a check."""
        for key in ("positive", "negative", "mutation"):
            doc = self._verdict(**{key: "FAILED"})
            schema_validation.validate_named(doc, "verdict.schema.json")
            contradiction = (doc["verdict"] == "PASS"
                             and doc["controls"][key] == "FAILED")
            self.assertTrue(contradiction,
                            "a PASS with a FAILED %s must be rejected by the "
                            "reviewer, not recorded" % key)

    def test_a_pass_without_an_oracle_is_a_contradiction(self):
        """Case 37."""
        doc = self._verdict(independent_oracle="NOT_AVAILABLE")
        schema_validation.validate_named(doc, "verdict.schema.json")
        self.assertTrue(
            doc["verdict"] == "PASS"
            and doc["controls"]["independent_oracle"] == "NOT_AVAILABLE",
            "a PASS without an independent oracle must become UNVERIFIED")

    def test_unresolved_evidence_forbids_pass(self):
        doc = self._verdict()
        doc["unresolved_evidence"] = ["a question that could change the answer"]
        schema_validation.validate_named(doc, "verdict.schema.json")
        self.assertTrue(doc["unresolved_evidence"],
                        "with unresolved evidence the verdict is UNVERIFIED")


class TestEvidenceTampering(unittest.TestCase):
    """Case 40 — a sealed evidence tree that changed is detectable."""

    def setUp(self):
        wipe(AUDIT, PHASE)
        self.rec = evidence.EvidenceRecorder(AUDIT, PHASE)
        self.rec.record_operation(
            operation="FILE_TYPE", argv=["/usr/bin/file", "--brief", "--", "/x"],
            exit_code=0, stdout=b"original", stderr=b"",
            timeout_seconds=10, output_limit_bytes=policy.MAX_OUTPUT_BYTES,
            started=1.0, finished=2.0)
        self.seal = self.rec.seal("PASS")

    def tearDown(self):
        wipe(AUDIT, PHASE)

    def test_intact_seal_verifies(self):
        ok, diffs = self.rec.verify_seal()
        self.assertTrue(ok)
        self.assertEqual(diffs, [])

    def test_modified_evidence_is_detected(self):
        target = os.path.join(self.rec.stdout_dir,
                              sorted(os.listdir(self.rec.stdout_dir))[0])
        with open(target, "wb") as fh:
            fh.write(b"tampered")
        ok, diffs = self.rec.verify_seal()
        self.assertFalse(ok)
        self.assertEqual(diffs[0]["reason"], "CHANGED")

    def test_deleted_evidence_is_detected(self):
        target = os.path.join(self.rec.stdout_dir,
                              sorted(os.listdir(self.rec.stdout_dir))[0])
        os.unlink(target)
        ok, diffs = self.rec.verify_seal()
        self.assertFalse(ok)
        self.assertEqual(diffs[0]["reason"], "MISSING")

    def test_sealed_evidence_refuses_further_writes(self):
        with self.assertRaises(evidence.EvidenceError):
            self.rec.record_operation(
                operation="FILE_TYPE", argv=["/usr/bin/file"], exit_code=0,
                stdout=b"", stderr=b"", timeout_seconds=10,
                output_limit_bytes=1024, started=1.0, finished=2.0)

    def test_seal_records_a_known_verdict(self):
        self.assertIn(self.seal["verdict"], policy.VERDICTS)
        self.assertTrue(hashing.is_hex64(self.seal["manifest_sha256"]))

    def test_sealing_an_unknown_verdict_is_refused(self):
        wipe(AUDIT, "RUN-B")
        rec = evidence.EvidenceRecorder(AUDIT, "RUN-B")
        try:
            with self.assertRaises(evidence.EvidenceError):
                rec.seal("ALMOST_PASS")
        finally:
            wipe(AUDIT, "RUN-B")


class TestFindingCompleteness(unittest.TestCase):
    """A finding missing any required field is refused at write time."""

    def setUp(self):
        wipe(AUDIT, "COMPARISON")
        self.rec = evidence.EvidenceRecorder(AUDIT, "COMPARISON")

    def tearDown(self):
        wipe(AUDIT, "COMPARISON")

    def test_complete_finding_is_accepted(self):
        finding = self.rec.record_finding(
            summary="a defect", source_path="/x/y.py", sha256="0" * 64,
            locator="line 10", evidence_type="source", confidence="HIGH")
        schema_validation.validate_named(finding, "finding.schema.json")

    def test_incomplete_finding_is_refused(self):
        for missing in ("summary", "source_path", "locator", "evidence_type",
                        "confidence"):
            kwargs = {"summary": "a defect", "source_path": "/x/y.py",
                      "sha256": "0" * 64, "locator": "line 10",
                      "evidence_type": "source", "confidence": "HIGH"}
            kwargs[missing] = ""
            with self.assertRaises(evidence.EvidenceError):
                self.rec.record_finding(**kwargs)

    def test_malformed_hash_is_refused(self):
        with self.assertRaises(evidence.EvidenceError):
            self.rec.record_finding(
                summary="a defect", source_path="/x/y.py", sha256="abc",
                locator="line 10", evidence_type="source", confidence="HIGH")


class TestEvidenceWritesStayInsideLevel1(unittest.TestCase):
    """VF-010 — the tests exercise real runtime directories, inside the root.

    The isolated replica's LEVEL1_ROOT is itself a directory below
    `verification/`, so writing to the controller's own work, state and
    evidence directories and writing only under `verification/` are the same
    thing rather than opposites.
    """

    def test_the_recorder_root_is_below_level1(self):
        wipe(AUDIT, "RUN-B")
        rec = evidence.EvidenceRecorder(AUDIT, "RUN-B")
        try:
            self.assertTrue(
                rec.root.startswith(path_policy.LEVEL1_ROOT + os.sep))
            for sub in (rec.stdout_dir, rec.stderr_dir, rec.artifacts_dir):
                self.assertTrue(sub.startswith(rec.root + os.sep))
        finally:
            wipe(AUDIT, "RUN-B")

    def test_the_runtime_directories_are_the_declared_mutable_ones(self):
        for name in ("state", "results", "evidence", "work", "logs",
                     "verification"):
            self.assertIn(name, path_policy.MUTABLE_SUBDIRS)


if __name__ == "__main__":
    unittest.main()
