"""Import a sealed attempt from the predecessor revision, or refuse to.

Why this exists.

R7 sealed two substantive L1-A31 attempts -- RUN-A with 33 evidence files and
RUN-B with 5 -- and then froze. Both are intact and neither has been verified.
Re-running them in R8 would repeat work the non-repeat ledger forbids and
would produce different evidence for the same question, so they are carried
across instead of redone.

What must not be carried across is R7's third L1-A31 attempt. COMPARISON
reported `executed=3` and entered state EXECUTED with zero evidence files,
because all three of its steps were IN_PROCESS and the frozen controller
performed none of them. It is the defect this revision exists to repair, and
importing it would import the defect's output as a result.

The distinction is not made by naming the two good attempts. It is made by
checking, for each attempt offered, that it was sealed, that its evidence
manifest and seal verify, that its plan binds no operation the frozen
controller could not perform, and that it produced an evidence record for
every step it was required to perform. An attempt that cannot pass those
checks is refused whatever it is called, which is what makes the route
generic rather than a list of two exceptions.

Three properties the route holds to.

  It runs only after R8 is FROZEN. Before the freeze, R8's active state must
  be 43/43 NOT_STARTED, and an import would break that invariant while the
  package still claims to be a clean generation.

  It imports evidence and state, never authority. No approval token crosses:
  a token authorises one execution of one plan in one revision, and a token
  that authorised R7 authorises nothing here. The imported phase is SEALED
  and UNVERIFIED, exactly as it was, and R8's own verdict is still to be
  reached.

  It is idempotent and replay-safe. A packet is consumed once and the
  consumption is journalled; offering it again is refused rather than
  silently repeated.
"""

import hashlib
import json
import os
import shutil
import time

from . import (attempts, hashing, operation_catalog, path_policy, policy,
               state_machine)


class MigrationError(Exception):
    """The import was refused. The message names the check that refused it."""


PACKET_SCHEMA = "wpno.level1.migration-packet/1"
LEDGER_REL = os.path.join("state", "migrations.jsonl")

# What an attempt must satisfy to be importable at all. Named as checks
# rather than as attempt ids, so the route refuses a bad attempt it has never
# heard of and admits a good one on its merits.
REQUIRED_SOURCE_STATE = "SEALED"

# Per-process memo of the predecessor's full control-manifest verification,
# keyed by (root, manifest digest). See `_check_source_package`.
_CONTROL_MANIFEST_CACHE = {}


def _read_mode(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def packet_digest(packet):
    """The digest of a packet's own bytes, excluding any recorded digest.

    A packet that carried its digest inside the bytes the digest covers could
    never be checked against itself.
    """
    body = {k: v for k, v in packet.items() if k != "migration_packet_sha256"}
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_packet(path):
    packet = _read_json(path_policy.assert_readable(path))
    if packet.get("schema") != PACKET_SCHEMA:
        raise MigrationError(
            "PACKET_SCHEMA_MISMATCH: %r" % packet.get("schema"))
    recorded = packet.get("migration_packet_sha256")
    measured = packet_digest(packet)
    if recorded != measured:
        raise MigrationError(
            "PACKET_DIGEST_MISMATCH: the packet records %s and its bytes "
            "hash to %s" % (recorded, measured))
    return packet, measured


def consumed_packets(level1_root):
    ledger = os.path.join(level1_root, LEDGER_REL)
    if not os.path.isfile(ledger):
        return {}
    out = {}
    with open(ledger, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                out[row["migration_packet_sha256"]] = row
    return out


# ------------------------------------------------------------------ checks

def _check_active_revision(level1_root, packet, findings):
    mode_path = os.path.join(level1_root, "MODE")
    mode = _read_mode(mode_path)
    if mode != policy.MODE_FROZEN:
        raise MigrationError(
            "ACTIVE_REVISION_NOT_FROZEN: MODE is %r. A predecessor attempt is "
            "imported after the freeze, never before it: before the freeze "
            "this package must be 43/43 NOT_STARTED, and an import would make "
            "that claim false while it was still being made." % mode)
    findings.append({"check": "active_revision_is_frozen", "ok": True,
                     "mode": mode})

    record = _read_json(os.path.join(level1_root, "state", "REVISION.json"))
    if record.get("revision") != packet["destination_revision"]:
        raise MigrationError(
            "WRONG_DESTINATION_REVISION: this package is %s and the packet is "
            "addressed to %s"
            % (record.get("revision"), packet["destination_revision"]))
    if record.get("predecessor") != packet["source_revision"]:
        raise MigrationError(
            "WRONG_PREDECESSOR: this package's predecessor is %s and the "
            "packet imports from %s"
            % (record.get("predecessor"), packet["source_revision"]))
    findings.append({"check": "revision_identity", "ok": True,
                     "destination": record.get("revision"),
                     "predecessor": record.get("predecessor")})


def _check_source_package(packet, findings):
    source_root = packet["source_root"]
    if not os.path.isdir(source_root):
        raise MigrationError("SOURCE_ROOT_ABSENT: %s" % source_root)

    mode = _read_mode(os.path.join(source_root, "MODE"))
    if mode != policy.MODE_FROZEN:
        raise MigrationError(
            "SOURCE_NOT_FROZEN: %s reads MODE %r" % (source_root, mode))

    manifest = os.path.join(source_root, "CONTROL_MANIFEST.sha256")
    measured = hashing.sha256_file(manifest)
    if measured != packet["source_control_manifest_sha256"]:
        raise MigrationError(
            "SOURCE_CONTROL_MANIFEST_DRIFT: expected %s, measured %s"
            % (packet["source_control_manifest_sha256"], measured))

    # Every entry, not a sample. The predecessor's integrity is the thing the
    # imported evidence rests on, and R7's manifest is 15804 entries.
    #
    # The result is memoised for the life of the process, keyed by the root
    # and the manifest's own digest. A real import is its own process --
    # `controller import-sealed-predecessor-attempt` runs once and exits --
    # so it always does the full verification. What the memo buys is a test
    # suite that exercises this route two dozen times without re-hashing the
    # predecessor two dozen times, which is the difference between a route
    # that is tested and one that is too slow to be.
    key = (os.path.realpath(source_root), measured)
    cached = _CONTROL_MANIFEST_CACHE.get(key)
    if cached is None:
        entries = ok = 0
        bad = []
        with open(manifest, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entries += 1
                digest, rel = line.split("  ", 1)
                full = os.path.join(source_root, rel)
                if os.path.isfile(full) and hashing.sha256_file(full) == digest:
                    ok += 1
                else:
                    bad.append(rel)
        cached = (entries, ok, bad)
        _CONTROL_MANIFEST_CACHE[key] = cached
    entries, ok, bad = cached
    if bad or ok != packet["source_control_manifest_entries"]:
        raise MigrationError(
            "SOURCE_CONTROL_MANIFEST_FAILED: %d/%d verified, %d mismatching "
            "(first: %s)" % (ok, entries, len(bad), bad[:3]))
    findings.append({"check": "source_control_manifest", "ok": True,
                     "verified": "%d/%d" % (ok, entries)})

    # The predecessor's post-freeze modification incident must be disclosed,
    # and its record must verify. R7's control manifest matching says only
    # that the bytes match now; it cannot record that they once did not.
    incident = packet["source_incident_manifest_path"]
    if not os.path.isfile(incident):
        raise MigrationError("SOURCE_INCIDENT_RECORD_ABSENT: %s" % incident)
    if hashing.sha256_file(incident) != packet[
            "source_incident_manifest_sha256"]:
        raise MigrationError("SOURCE_INCIDENT_RECORD_DRIFT: %s" % incident)
    if packet.get("predecessor_incident_disclosed") is not True:
        raise MigrationError(
            "SOURCE_INCIDENT_NOT_DISCLOSED: the packet must state that the "
            "predecessor was modified after its freeze and restored")
    findings.append({"check": "source_incident_disclosed", "ok": True,
                     "record": incident})


def _check_source_attempt(packet, findings):
    source_root = packet["source_root"]
    audit_id = packet["source_audit_id"]
    phase = packet["source_run_phase"]
    attempt = packet["source_attempt_number"]

    progress = _read_json(os.path.join(source_root, "state", "progress.json"))
    node = progress["audits"].get(audit_id, {}).get(phase)
    if node is None:
        raise MigrationError(
            "SOURCE_PHASE_ABSENT: %s/%s is not in the predecessor's state"
            % (audit_id, phase))
    if node.get("state") != REQUIRED_SOURCE_STATE:
        raise MigrationError(
            "SOURCE_PHASE_NOT_SEALED: %s/%s is %s. An unsealed attempt has "
            "no manifest and no seal, so nothing about it can be verified -- "
            "which is exactly the condition of the predecessor's COMPARISON "
            "attempt, executed with zero evidence."
            % (audit_id, phase, node.get("state")))

    row = (node.get("attempts") or {}).get(str(attempt))
    if row is None:
        raise MigrationError(
            "SOURCE_ATTEMPT_ABSENT: %s/%s has no attempt %s"
            % (audit_id, phase, attempt))
    for field, key in (("plan_sha256", "source_plan_sha256"),
                       ("target_sha256", "source_target_sha256"),
                       ("evidence_manifest_sha256",
                        "source_evidence_manifest_sha256"),
                       ("seal_sha256", "source_seal_sha256")):
        if row.get(field) != packet[key]:
            raise MigrationError(
                "SOURCE_%s_DRIFT: state records %s, packet binds %s"
                % (field.upper(), row.get(field), packet[key]))
    if row.get("verdict") != packet["source_verdict"]:
        raise MigrationError(
            "SOURCE_VERDICT_DRIFT: %r vs %r"
            % (row.get("verdict"), packet["source_verdict"]))

    evidence_dir = os.path.join(source_root, "evidence", audit_id, phase,
                                "attempt-%d" % attempt)
    if not os.path.isdir(evidence_dir):
        raise MigrationError("SOURCE_EVIDENCE_ABSENT: %s" % evidence_dir)

    manifest_path = os.path.join(evidence_dir, "EVIDENCE_MANIFEST.sha256")
    seal_path = os.path.join(evidence_dir, "SEAL.json")
    for path in (manifest_path, seal_path):
        if not os.path.isfile(path):
            raise MigrationError("SOURCE_ATTEMPT_INCOMPLETE: %s" % path)
    if hashing.sha256_file(manifest_path) != packet[
            "source_evidence_manifest_sha256"]:
        raise MigrationError("SOURCE_EVIDENCE_MANIFEST_MISMATCH")
    if hashing.sha256_file(seal_path) != packet["source_seal_sha256"]:
        raise MigrationError("SOURCE_SEAL_MISMATCH")

    # The seal must cover the manifest that is actually there.
    seal = _read_json(seal_path)
    if seal.get("manifest_sha256") != packet[
            "source_evidence_manifest_sha256"]:
        raise MigrationError(
            "SOURCE_SEAL_DOES_NOT_COVER_ITS_MANIFEST: seal names %s, manifest "
            "hashes to %s" % (seal.get("manifest_sha256"),
                              packet["source_evidence_manifest_sha256"]))

    # Every file the manifest names, re-hashed here.
    checked = 0
    bad = []
    with open(manifest_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            full = os.path.join(evidence_dir, rel)
            checked += 1
            if not os.path.isfile(full) or hashing.sha256_file(full) != digest:
                bad.append(rel)
    if bad:
        raise MigrationError(
            "SOURCE_EVIDENCE_FAILED: %d of %d entries do not verify: %s"
            % (len(bad), checked, bad[:3]))
    findings.append({"check": "source_attempt_evidence", "ok": True,
                     "entries_verified": checked})

    # The target the attempt was bound to must still hash to what it did.
    target = packet["source_target_path"]
    if not os.path.isfile(target):
        raise MigrationError("SOURCE_TARGET_ABSENT: %s" % target)
    if hashing.sha256_file(target) != packet["source_target_sha256"]:
        raise MigrationError(
            "SOURCE_TARGET_DRIFT: %s no longer hashes to %s"
            % (target, packet["source_target_sha256"]))

    # Every reference the attempt bound must still hash to what it did.
    for entry in packet.get("source_reference_hashes", []):
        if not os.path.isfile(entry["path"]):
            raise MigrationError("SOURCE_REFERENCE_ABSENT: %s" % entry["path"])
        if hashing.sha256_file(entry["path"]) != entry["sha256"]:
            raise MigrationError(
                "SOURCE_REFERENCE_DRIFT: %s" % entry["path"])
    findings.append({"check": "source_bindings_stable", "ok": True,
                     "references": len(packet.get("source_reference_hashes",
                                                  []))})

    # The plan must bind no operation the frozen predecessor could not
    # perform. This is the check that keeps the route generic: an attempt
    # whose plan contains an IN_PROCESS step was executed by a controller
    # that did not perform IN_PROCESS steps, so its evidence is incomplete
    # whatever its seal says.
    plan_path = os.path.join(source_root, "results", audit_id, phase,
                             "attempt-%d" % attempt, "plan.json")
    if not os.path.isfile(plan_path):
        raise MigrationError("SOURCE_PLAN_ABSENT: %s" % plan_path)
    if hashing.sha256_file(plan_path) != packet["source_plan_sha256"]:
        raise MigrationError("SOURCE_PLAN_DRIFT: %s" % plan_path)
    plan = _read_json(plan_path)
    in_process = sorted({step["operation"] for step in plan["steps"]
                         if step["operation"] in operation_catalog.IN_PROCESS})
    if in_process:
        raise MigrationError(
            "SOURCE_PLAN_CONTAINS_IN_PROCESS: %s. The predecessor's "
            "controller performed no in-process operation, so an attempt "
            "binding one did not measure what its plan says it measured."
            % in_process)

    # And the recorded execution must show a real operation per required
    # step, not the note the defective branch wrote instead of running one.
    commands_path = os.path.join(evidence_dir, "commands.jsonl")
    if not os.path.isfile(commands_path):
        raise MigrationError("SOURCE_COMMANDS_ABSENT: %s" % commands_path)
    records = []
    with open(commands_path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    required = [step for step in plan["steps"]
                if step["operation"] not in operation_catalog.OPERATOR_PERFORMED]
    if len(records) < len(required):
        raise MigrationError(
            "SOURCE_EVIDENCE_INCOMPLETE: %d required steps produced %d "
            "operation records" % (len(required), len(records)))
    for record in records:
        note = str(record.get("note") or "")
        if "performed by the worker" in note:
            raise MigrationError(
                "SOURCE_USED_THE_DEFECTIVE_BRANCH: an operation is recorded "
                "with the note the frozen controller wrote instead of "
                "performing it")
        if not record.get("argv"):
            raise MigrationError(
                "SOURCE_OPERATION_HAS_NO_ARGV: %s ran no process and left no "
                "in-process result" % record.get("evidence_id"))
    findings.append({"check": "source_execution_was_real", "ok": True,
                     "operation_records": len(records),
                     "required_steps": len(required)})
    return plan, evidence_dir, row


def _check_destination(level1_root, packet, findings):
    audit_id = packet["destination_audit_id"]
    phase = packet["destination_run_phase"]
    progress = _read_json(os.path.join(level1_root, "state", "progress.json"))
    node = progress["audits"].get(audit_id, {}).get(phase)
    if node is None:
        raise MigrationError(
            "DESTINATION_PHASE_ABSENT: %s/%s" % (audit_id, phase))
    if node.get("state") != "NOT_STARTED":
        raise MigrationError(
            "DESTINATION_NOT_EMPTY: %s/%s is %s; an import never overwrites a "
            "phase that has a history" % (audit_id, phase, node.get("state")))
    if node.get("attempts"):
        raise MigrationError(
            "DESTINATION_ATTEMPT_EXISTS: %s/%s already records %d attempt(s)"
            % (audit_id, phase, len(node["attempts"])))
    destination = os.path.join(level1_root, "evidence", audit_id, phase)
    if os.path.isdir(destination) and os.listdir(destination):
        raise MigrationError(
            "DESTINATION_EVIDENCE_EXISTS: %s is not empty" % destination)
    findings.append({"check": "destination_is_empty", "ok": True,
                     "phase": "%s/%s" % (audit_id, phase)})
    return progress, node


# Text that only ever appears inside an approval token. A key *named* for a
# token is a declaration about one -- `approval_token_imported: false` says
# the opposite of carrying one -- so the scan is over values, not over keys.
# Scanning keys as well was the first version of this check, and it refused
# the packet for stating that it carried no token.
TOKEN_MARKERS = ("APPROVE-EXECUTION", "RUN-ONCE", "PLAN-SHA256=",
                 "TARGET-SHA256=")


def _walk_values(node):
    if isinstance(node, dict):
        for value in node.values():
            for found in _walk_values(value):
                yield found
    elif isinstance(node, list):
        for value in node:
            for found in _walk_values(value):
                yield found
    elif isinstance(node, str):
        yield node


def _check_no_token(packet, findings):
    """No approval token crosses, in any form."""
    for value in _walk_values(packet):
        for marker in TOKEN_MARKERS:
            if marker in value:
                raise MigrationError(
                    "PACKET_CARRIES_APPROVAL_MATERIAL: a value contains %r. A "
                    "token authorises one execution of one plan in one "
                    "revision; a predecessor's token authorises nothing here."
                    % marker)
    if packet.get("approval_token_imported") is not False:
        raise MigrationError(
            "PACKET_DOES_NOT_DECLARE_TOKEN_EXCLUSION: the packet must state "
            "approval_token_imported false explicitly")
    findings.append({"check": "no_approval_token_imported", "ok": True,
                     "scanned": "values only; a key naming a token is a "
                                "declaration about one, not one"})


def verify(level1_root, packet_path):
    """Run every check and return the findings. Writes nothing."""
    packet, digest = load_packet(packet_path)
    findings = []

    consumed = consumed_packets(level1_root)
    if digest in consumed:
        raise MigrationError(
            "PACKET_ALREADY_CONSUMED: %s was applied at %s. A migration is "
            "applied once; replaying one would duplicate imported evidence "
            "under a second attempt number."
            % (digest, consumed[digest].get("imported_utc")))
    findings.append({"check": "packet_unconsumed", "ok": True,
                     "migration_packet_sha256": digest})

    _check_no_token(packet, findings)
    _check_active_revision(level1_root, packet, findings)
    _check_source_package(packet, findings)
    plan, evidence_dir, row = _check_source_attempt(packet, findings)
    progress, node = _check_destination(level1_root, packet, findings)
    return {"packet": packet, "migration_packet_sha256": digest,
            "findings": findings, "source_evidence_dir": evidence_dir,
            "source_state_row": row, "progress": progress}


def apply(level1_root, packet_path, *, save_progress, append_transition):
    """Verify, then import. Idempotent by refusal, never by silent success."""
    checked = verify(level1_root, packet_path)
    packet = checked["packet"]
    digest = checked["migration_packet_sha256"]
    audit_id = packet["destination_audit_id"]
    phase = packet["destination_run_phase"]

    # Derived from the root the caller named, not from the module-level
    # LEVEL1_ROOT, so this route is testable end to end against a sandbox
    # that stands in for a frozen package. A route whose only exercise is a
    # refusal has had its refusals tested and its imports assumed.
    destination = os.path.join(level1_root, "evidence", audit_id, phase,
                               "attempt-1")
    if os.path.realpath(level1_root) == os.path.realpath(
            path_policy.LEVEL1_ROOT):
        destination = path_policy.audit_attempt_evidence_dir(audit_id, phase, 1)
    os.makedirs(destination, exist_ok=True)
    copied = []
    for dirpath, dirnames, filenames in os.walk(checked["source_evidence_dir"]):
        dirnames.sort()
        for name in sorted(filenames):
            source = os.path.join(dirpath, name)
            rel = os.path.relpath(source, checked["source_evidence_dir"])
            target = os.path.join(destination, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
            if hashing.sha256_file(target) != hashing.sha256_file(source):
                raise MigrationError("IMPORT_COPY_MISMATCH: %s" % rel)
            copied.append(rel)

    # Re-verify the imported copy against the seal, here, rather than
    # trusting that a copy of verified bytes is still verified.
    imported_manifest = os.path.join(destination, "EVIDENCE_MANIFEST.sha256")
    if hashing.sha256_file(imported_manifest) != packet[
            "source_evidence_manifest_sha256"]:
        raise MigrationError("IMPORTED_MANIFEST_MISMATCH")

    row = checked["source_state_row"]
    progress = checked["progress"]
    node = progress["audits"][audit_id][phase]
    imported_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    node.update({
        "state": "SEALED",
        "audit_id": audit_id,
        "run_phase": phase,
        "attempt_number": 1,
        "accepted_attempt": 1,
        "verdict": packet["source_verdict"],
        "classification": row.get("classification"),
        "plan_sha256": packet["source_plan_sha256"],
        "target_sha256": packet["source_target_sha256"],
        "target_path": packet["source_target_path"],
        "imported_from_predecessor": True,
        "updated": time.time(),
        "attempts": {"1": {
            "attempt_id": "%s/%s/attempt-1" % (audit_id, phase),
            "attempt_number": 1,
            "audit_id": audit_id,
            "run_phase": phase,
            "state": "SEALED",
            "verdict": packet["source_verdict"],
            "classification": row.get("classification"),
            "evidence_file_count": row.get("evidence_file_count"),
            "evidence_manifest_sha256":
                packet["source_evidence_manifest_sha256"],
            "seal_sha256": packet["source_seal_sha256"],
            "plan_sha256": packet["source_plan_sha256"],
            "target_sha256": packet["source_target_sha256"],
            "usable": True,
            "superseded": False,
            "source_revision": packet["source_revision"],
            "source_attempt_id": packet["source_attempt_id"],
            "source_root": packet["source_root"],
            "imported_utc": imported_utc,
            "imported_by_route": "import-sealed-predecessor-attempt",
            "predecessor_incident_disclosed": True,
            "approval_token_imported": False,
        }},
    })
    save_progress(progress)

    ledger_row = {
        "migration_packet_sha256": digest,
        "source_revision": packet["source_revision"],
        "source_attempt_id": packet["source_attempt_id"],
        "source_plan_sha256": packet["source_plan_sha256"],
        "source_target_sha256": packet["source_target_sha256"],
        "source_evidence_manifest_sha256":
            packet["source_evidence_manifest_sha256"],
        "source_seal_sha256": packet["source_seal_sha256"],
        "source_verdict": packet["source_verdict"],
        "destination": "%s/%s" % (audit_id, phase),
        "imported_utc": imported_utc,
        "imported_by_route": "import-sealed-predecessor-attempt",
        "predecessor_incident_disclosed": True,
        "files_imported": len(copied),
    }
    ledger = os.path.join(level1_root, LEDGER_REL)
    with open(ledger, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ledger_row, sort_keys=True) + "\n")

    append_transition(audit_id=audit_id, run_phase=phase,
                      from_state="NOT_STARTED", to_state="SEALED",
                      route="import-sealed-predecessor-attempt",
                      binding=ledger_row)
    return {"imported": True, "files": len(copied), "ledger": ledger_row,
            "findings": checked["findings"]}
