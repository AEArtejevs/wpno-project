"""Generic external-host execution packets and hash-bound evidence intake.

Some audits ask a question about a machine this controller does not run on.
L1-A24 is the first: it asks which instruction files a tool loads when it is
launched from a directory outside the project root, on the operator's Mac.
The controller cannot answer that by running anything here, and it must not
try - a result produced on Ubuntu would be a measurement of the wrong machine
reported under the right audit's name.

This module is deliberately not L1-A24-specific. It defines two artefacts and
the rules that connect them:

  PACKET   what the operator is authorised to do, written by the controller
           before the run. It fixes the host, the operating system, the
           directory, the command, the environment redirection and the
           pre-run manifest of the directory. It is hashed, and its digest is
           part of the approval.

  INTAKE   what the operator brings back. It carries the packet digest, the
           post-run manifest, stdout, stderr, timestamps, the tool version
           and the loaded-instruction evidence. It is admitted only if it
           answers the packet it claims to answer.

The refusals are the substance. An intake is rejected when it comes from a
different host, a different operating system, a different directory, a
different command, a packet digest that is not the one issued, a manifest
that is missing on either side, a timestamp that precedes the packet, or an
approval that has already been spent. A packet that admitted anything would
be a decoration on an unbound claim.

What this module never does: launch anything, reach a network, write outside
LEVEL1_ROOT, or touch the external directory. The external directory is read
by the operator and described by manifests; the controller only compares the
two descriptions it was given.
"""

import json
import os
import time

from . import hashing, path_policy

SCHEMA_PACKET = "wpno.level1.external-host-packet/1"
SCHEMA_INTAKE = "wpno.level1.external-host-intake/1"

# Fields a packet fixes. An intake that disagrees on any of them is answering
# a different question from the one that was approved.
BOUND_FIELDS = (
    "audit_id",
    "run_phase",
    "host_identity",
    "operating_system",
    "canonical_directory",
    "invocation",
)

# Fields an intake must carry. Absence is a refusal, not a default: a missing
# post-run manifest is exactly the evidence that would show whether the run
# wrote into the external directory.
REQUIRED_INTAKE_FIELDS = (
    "schema",
    "packet_sha256",
    "host_identity",
    "operating_system",
    "canonical_directory",
    "invocation",
    "tool_version",
    "started_utc",
    "finished_utc",
    "stdout_sha256",
    "stderr_sha256",
    "post_run_directory_manifest_sha256",
    "loaded_instruction_evidence",
    "operator_identity",
)


class ExternalHostError(Exception):
    pass


def _is_sha256_hex(value):
    """A digest is 64 lowercase hex characters. Anything else is not one."""
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _require(condition, message):
    if not condition:
        raise ExternalHostError(message)


def build_packet(audit_id, run_phase, host_identity, operating_system,
                 canonical_directory, invocation, environment_redirection,
                 pre_run_directory_manifest_sha256,
                 expected_global_instruction_path,
                 expected_project_instruction_condition,
                 source_host_sha256, issued_utc=None):
    """The authorisation artefact. Written before the run, hashed, and bound.

    `canonical_directory` is a path on the external host. It is deliberately
    NOT checked for existence here: it does not exist on this machine, and a
    check that failed would be a fact about Ubuntu, not about the Mac. The
    packet records it as the operator's asserted, human-approved directory and
    the intake must name the same one.
    """
    _require(isinstance(audit_id, str) and audit_id,
             "an external-host packet must name its audit")
    _require(run_phase in ("RUN-A", "RUN-B", "COMPARISON"),
             "unknown run phase: %r" % (run_phase,))
    for label, value in (("host_identity", host_identity),
                         ("operating_system", operating_system),
                         ("canonical_directory", canonical_directory),
                         ("operator identity", expected_global_instruction_path)):
        _require(isinstance(value, str) and value.strip(),
                 "an external-host packet must state its %s" % label)
    _require(os.path.isabs(canonical_directory),
             "the external working directory must be an absolute path on the "
             "external host: %r" % (canonical_directory,))
    _require(isinstance(invocation, (list, tuple)) and invocation
             and all(isinstance(a, str) for a in invocation),
             "the invocation must be an explicit argv list of strings")
    _require(_is_sha256_hex(pre_run_directory_manifest_sha256),
             "the pre-run directory manifest digest must be a SHA-256")

    packet = {
        "schema": SCHEMA_PACKET,
        "audit_id": audit_id,
        "run_phase": run_phase,
        "host_identity": host_identity,
        "operating_system": operating_system,
        "canonical_directory": canonical_directory,
        "invocation": list(invocation),
        "environment_redirection": dict(environment_redirection or {}),
        "pre_run_directory_manifest_sha256": pre_run_directory_manifest_sha256,
        "expected_global_instruction_path": expected_global_instruction_path,
        "expected_project_instruction_condition":
            expected_project_instruction_condition,
        "source_host_sha256": dict(source_host_sha256 or {}),
        "issued_utc": issued_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime()),
        "controller_launches_this": False,
        "note": ("The controller does not launch this and never writes to the "
                 "external directory. The operator performs it under an "
                 "approval bound to this packet's digest, and returns an "
                 "intake record."),
    }
    return packet


def serialize(document):
    """One canonical byte form, so a digest means one thing."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def packet_digest(packet):
    return hashing.sha256_text(serialize(packet))


def write_packet(packet, path):
    target = path_policy.assert_writable(path)
    path_policy.ensure_dir(os.path.dirname(target))
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(serialize(packet))
    return hashing.sha256_file(target)


def _parse_utc(value, label):
    try:
        return time.mktime(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        raise ExternalHostError("%s is not an ISO UTC timestamp: %r"
                                % (label, value))


def validate_intake(packet, intake, spent_packet_digests=()):
    """Admit or refuse one external-host evidence record.

    Returns the list of checks made, each with its own verdict, so that an
    admission is readable rather than a single boolean. Raises on refusal.
    """
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    _require(isinstance(intake, dict), "the intake must be a record")
    missing = [f for f in REQUIRED_INTAKE_FIELDS if f not in intake]
    if not check("required_fields_present", not missing,
                 "missing: %s" % missing):
        raise ExternalHostError(
            "EXTERNAL_EVIDENCE_INCOMPLETE: missing %s" % missing)

    if not check("schema", intake["schema"] == SCHEMA_INTAKE,
                 intake["schema"]):
        raise ExternalHostError("EXTERNAL_EVIDENCE_WRONG_SCHEMA: %r"
                                % (intake["schema"],))

    digest = packet_digest(packet)
    if not check("packet_binding", intake["packet_sha256"] == digest,
                 "intake names %s, packet is %s"
                 % (intake["packet_sha256"], digest)):
        raise ExternalHostError(
            "EXTERNAL_EVIDENCE_UNBOUND: the intake answers packet %s, not %s"
            % (intake["packet_sha256"], digest))

    if not check("approval_not_replayed",
                 digest not in set(spent_packet_digests), digest):
        raise ExternalHostError(
            "EXTERNAL_EVIDENCE_REPLAY: packet %s has already been answered"
            % digest)

    for field in BOUND_FIELDS:
        if field in ("audit_id", "run_phase"):
            continue
        expected = packet[field]
        got = intake[field]
        if isinstance(expected, list):
            got = list(got) if isinstance(got, (list, tuple)) else got
        if not check("bound_%s" % field, got == expected,
                     "packet %r, intake %r" % (expected, got)):
            raise ExternalHostError(
                "EXTERNAL_EVIDENCE_MISMATCH on %s: the packet authorised %r "
                "and the intake reports %r" % (field, expected, got))

    for label in ("stdout_sha256", "stderr_sha256",
                  "post_run_directory_manifest_sha256"):
        if not check("digest_shape_%s" % label,
                     _is_sha256_hex(intake[label]), intake[label]):
            raise ExternalHostError(
                "EXTERNAL_EVIDENCE_MALFORMED_DIGEST: %s=%r"
                % (label, intake[label]))

    issued = _parse_utc(packet["issued_utc"], "the packet's issued_utc")
    started = _parse_utc(intake["started_utc"], "the intake's started_utc")
    finished = _parse_utc(intake["finished_utc"], "the intake's finished_utc")
    if not check("evidence_after_packet", started >= issued,
                 "packet issued %s, run started %s"
                 % (packet["issued_utc"], intake["started_utc"])):
        raise ExternalHostError(
            "EXTERNAL_EVIDENCE_PREDATES_PLAN: the run started before the "
            "packet that authorises it was issued")
    if not check("chronology", finished >= started,
                 "%s -> %s" % (intake["started_utc"], intake["finished_utc"])):
        raise ExternalHostError(
            "EXTERNAL_EVIDENCE_INCONSISTENT_CHRONOLOGY: finished before started")

    # The write-topology question. Equality means the external directory is
    # unchanged; inequality is a finding for the audit, not an error here. It
    # is reported either way and never silently accepted as equal.
    unchanged = (intake["post_run_directory_manifest_sha256"]
                 == packet["pre_run_directory_manifest_sha256"])
    check("external_directory_unchanged", True,
          "pre %s, post %s, unchanged=%s"
          % (packet["pre_run_directory_manifest_sha256"],
             intake["post_run_directory_manifest_sha256"], unchanged))

    return {
        "admitted": True,
        "packet_sha256": digest,
        "external_directory_unchanged": unchanged,
        "checks": checks,
    }


def load_and_validate(packet_path, intake_path, spent_packet_digests=()):
    with open(path_policy.assert_readable(packet_path), encoding="utf-8") as fh:
        packet = json.load(fh)
    with open(path_policy.assert_readable(intake_path), encoding="utf-8") as fh:
        intake = json.load(fh)
    return packet, intake, validate_intake(packet, intake,
                                           spent_packet_digests)
