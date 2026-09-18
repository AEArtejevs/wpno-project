"""External-host execution packets and the refusals that make them worth having.

L1-A24 asks what a tool loads when it is launched from a directory outside the
project root on the operator's Mac. This controller runs on Ubuntu. It cannot
answer that by running anything, and an answer produced here would be a
measurement of the wrong machine reported under the right audit's name.

The packet fixes what the operator is authorised to do and the intake is what
comes back. The value of the pair is entirely in what it refuses, so that is
what these tests are about: a different host, a different operating system, a
different directory, a different invocation, an unissued packet digest, a
malformed digest, evidence that predates the packet that authorises it, a run
that finished before it started, and an approval already spent.

The mechanism is generic. Nothing in it names L1-A24, and these tests use an
invented audit id to keep it that way.
"""

import json
import os
import tempfile
import unittest

from automation import external_host_evidence as ehe
from automation import path_policy

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def a_packet(**overrides):
    fields = dict(
        audit_id="L1-A24",
        run_phase="RUN-A",
        host_identity="operator-mac-001",
        operating_system="macOS 26.2.0 darwin-arm64",
        canonical_directory="/Users/operator/Downloads",
        invocation=["claude", "--print", "which instruction files loaded"],
        environment_redirection={"HOME": "work/L1-A24/RUN-A/home",
                                 "TMPDIR": "work/L1-A24/RUN-A/tmp"},
        pre_run_directory_manifest_sha256=SHA_A,
        expected_global_instruction_path="/Users/operator/.claude/CLAUDE.md",
        expected_project_instruction_condition="absent outside the project root",
        source_host_sha256={"project_instruction_file": SHA_B},
        issued_utc="2026-08-28T10:00:00Z",
    )
    fields.update(overrides)
    return ehe.build_packet(**fields)


def an_intake(packet, **overrides):
    fields = dict(
        schema=ehe.SCHEMA_INTAKE,
        packet_sha256=ehe.packet_digest(packet),
        host_identity=packet["host_identity"],
        operating_system=packet["operating_system"],
        canonical_directory=packet["canonical_directory"],
        invocation=list(packet["invocation"]),
        tool_version="claude-code 2.0.0",
        started_utc="2026-08-28T10:05:00Z",
        finished_utc="2026-08-28T10:06:00Z",
        stdout_sha256=SHA_B,
        stderr_sha256=SHA_C,
        post_run_directory_manifest_sha256=SHA_A,
        loaded_instruction_evidence={"files": [], "method": "session state"},
        operator_identity="operator",
    )
    fields.update(overrides)
    return fields


class PacketConstruction(unittest.TestCase):
    def test_a_packet_records_what_it_authorises(self):
        packet = a_packet()
        for field in ehe.BOUND_FIELDS:
            self.assertIn(field, packet)
        self.assertFalse(packet["controller_launches_this"])

    def test_the_external_directory_is_not_required_to_exist_here(self):
        """The directory is on another machine. A check would answer about this one."""
        packet = a_packet(canonical_directory="/Users/operator/Downloads")
        self.assertFalse(os.path.exists(packet["canonical_directory"]))
        self.assertEqual(packet["canonical_directory"],
                         "/Users/operator/Downloads")

    def test_a_relative_external_directory_is_refused(self):
        with self.assertRaises(ehe.ExternalHostError):
            a_packet(canonical_directory="Downloads")

    def test_an_empty_invocation_is_refused(self):
        with self.assertRaises(ehe.ExternalHostError):
            a_packet(invocation=[])

    def test_a_malformed_pre_run_manifest_digest_is_refused(self):
        with self.assertRaises(ehe.ExternalHostError):
            a_packet(pre_run_directory_manifest_sha256="not-a-digest")

    def test_the_digest_is_stable_across_serialisations(self):
        self.assertEqual(ehe.packet_digest(a_packet()),
                         ehe.packet_digest(a_packet()))

    def test_a_changed_field_changes_the_digest(self):
        self.assertNotEqual(
            ehe.packet_digest(a_packet()),
            ehe.packet_digest(a_packet(canonical_directory="/Users/operator/Other")))


class IntakeAdmission(unittest.TestCase):
    def test_a_matching_intake_is_admitted(self):
        packet = a_packet()
        result = ehe.validate_intake(packet, an_intake(packet))
        self.assertTrue(result["admitted"])
        self.assertTrue(result["external_directory_unchanged"])

    def test_a_changed_external_directory_is_reported_not_hidden(self):
        packet = a_packet()
        intake = an_intake(packet,
                           post_run_directory_manifest_sha256=SHA_C)
        result = ehe.validate_intake(packet, intake)
        self.assertTrue(result["admitted"])
        self.assertFalse(result["external_directory_unchanged"])


class IntakeRefusals(unittest.TestCase):
    def refuse(self, **overrides):
        packet = a_packet()
        with self.assertRaises(ehe.ExternalHostError) as caught:
            ehe.validate_intake(packet, an_intake(packet, **overrides))
        return str(caught.exception)

    def test_a_different_host_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_MISMATCH",
                      self.refuse(host_identity="some-other-machine"))

    def test_a_different_operating_system_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_MISMATCH",
                      self.refuse(operating_system="Ubuntu 24.04"))

    def test_a_different_directory_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_MISMATCH",
                      self.refuse(canonical_directory="/Users/operator/Desktop"))

    def test_a_different_invocation_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_MISMATCH",
                      self.refuse(invocation=["claude", "--print", "something else"]))

    def test_an_unbound_packet_digest_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_UNBOUND",
                      self.refuse(packet_sha256=SHA_C))

    def test_a_missing_field_is_refused(self):
        packet = a_packet()
        intake = an_intake(packet)
        del intake["post_run_directory_manifest_sha256"]
        with self.assertRaises(ehe.ExternalHostError) as caught:
            ehe.validate_intake(packet, intake)
        self.assertIn("EXTERNAL_EVIDENCE_INCOMPLETE", str(caught.exception))

    def test_a_malformed_digest_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_MALFORMED_DIGEST",
                      self.refuse(stdout_sha256="short"))

    def test_evidence_predating_the_packet_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_PREDATES_PLAN",
                      self.refuse(started_utc="2026-08-28T09:00:00Z",
                                  finished_utc="2026-08-28T09:30:00Z"))

    def test_an_impossible_chronology_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_INCONSISTENT_CHRONOLOGY",
                      self.refuse(started_utc="2026-08-28T10:06:00Z",
                                  finished_utc="2026-08-28T10:05:00Z"))

    def test_the_wrong_schema_is_refused(self):
        self.assertIn("EXTERNAL_EVIDENCE_WRONG_SCHEMA",
                      self.refuse(schema="wpno.level1.something-else/1"))


class ReplayRefusal(unittest.TestCase):
    def test_a_packet_already_answered_is_refused(self):
        packet = a_packet()
        digest = ehe.packet_digest(packet)
        intake = an_intake(packet)
        ehe.validate_intake(packet, intake)          # first answer: admitted
        with self.assertRaises(ehe.ExternalHostError) as caught:
            ehe.validate_intake(packet, intake, spent_packet_digests=(digest,))
        self.assertIn("EXTERNAL_EVIDENCE_REPLAY", str(caught.exception))

    def test_a_fresh_packet_is_not_caught_by_another_packets_spend(self):
        first = a_packet()
        second = a_packet(issued_utc="2026-08-28T11:00:00Z")
        # The second packet's run has to happen after the second packet was
        # issued. Reusing the first packet's timeline would be refused for
        # predating its own authorisation, which is a different refusal and
        # would make this test pass for the wrong reason.
        result = ehe.validate_intake(
            second,
            an_intake(second, started_utc="2026-08-28T11:05:00Z",
                      finished_utc="2026-08-28T11:06:00Z"),
            spent_packet_digests=(ehe.packet_digest(first),))
        self.assertTrue(result["admitted"])


class GenericByConstruction(unittest.TestCase):
    def test_the_module_names_no_specific_audit(self):
        path = os.path.join(path_policy.LEVEL1_ROOT, "automation",
                            "external_host_evidence.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        body = code.split('"""', 2)[-1]
        self.assertNotIn("L1-A24", body,
                         "the mechanism must not be specific to one audit")

    def test_it_works_for_an_audit_that_is_not_l1_a24(self):
        packet = a_packet(audit_id="L1-A99")
        result = ehe.validate_intake(packet, an_intake(packet))
        self.assertTrue(result["admitted"])


class WriteConfinement(unittest.TestCase):
    def test_a_packet_cannot_be_written_outside_the_package(self):
        packet = a_packet()
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(Exception):
                ehe.write_packet(packet, os.path.join(outside, "packet.json"))

    def test_a_packet_written_inside_the_work_area_hashes_to_its_digest(self):
        packet = a_packet()
        target = os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest",
                              "external_host_packet.json")
        written = ehe.write_packet(packet, target)
        self.assertEqual(written, ehe.packet_digest(packet))
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["audit_id"], "L1-A24")
        os.remove(target)
