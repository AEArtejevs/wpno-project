"""Evidence recording and sealing.

Two properties matter. First, an operation's complete output survives on disk
even when a report shows an excerpt. Second, once an audit reaches a terminal
status its evidence is sealed and any later change is detectable.

Sealing is a manifest plus a seal file. It is tamper-evident, not
tamper-proof: a determined editor can rewrite both. What it prevents is the
quiet edit, which is the realistic failure.
"""

import json
import os
import time

from . import hashing, path_policy, policy, redaction


class EvidenceError(Exception):
    pass


class EvidenceRecorder(object):
    """Records and seals the evidence of ONE attempt at ONE phase.

    R7 change. The recorder used to be addressed by (audit, phase) and wrote
    into `evidence/<audit>/<phase>/`. A phase now has attempts, and each
    attempt owns its own directory, `evidence/<audit>/<phase>/attempt-<n>/`.
    The sealing logic is unchanged and deliberately so: what an attempt seals,
    and how, is exactly what R6 sealed. Only the address changed.

    `attempt` defaults to 1 so that a caller which knows nothing about
    attempts still addresses a real, well-formed attempt directory rather than
    the phase directory itself. The phase directory now holds the attempt
    index and nothing else, so no seal can ever cover a sibling attempt's
    bytes.
    """

    def __init__(self, audit_id, run_phase, attempt=1):
        self.audit_id = audit_id
        self.run_phase = run_phase
        self.attempt = attempt
        self.root = path_policy.ensure_dir(
            path_policy.audit_attempt_evidence_dir(audit_id, run_phase,
                                                   attempt))
        self.stdout_dir = path_policy.ensure_dir(os.path.join(self.root, "stdout"))
        self.stderr_dir = path_policy.ensure_dir(os.path.join(self.root, "stderr"))
        self.artifacts_dir = path_policy.ensure_dir(os.path.join(self.root, "artifacts"))
        self.commands_path = os.path.join(self.root, "commands.jsonl")
        self.seal_path = os.path.join(self.root, "SEAL.json")
        self.manifest_path = os.path.join(self.root, "EVIDENCE_MANIFEST.sha256")
        self._counter = 0

    # -- ids ---------------------------------------------------------------
    def next_evidence_id(self):
        """A globally distinct id, attempt included.

        R6 produced `L1-A31-RUN-A-E0001`. With attempts, that id would be
        produced again by attempt 2 and two different commands would share one
        name across two sealed manifests. The attempt number is therefore part
        of the id, not merely part of the path.
        """
        self._counter += 1
        return "%s-%s-A%d-E%04d" % (self.audit_id, self.run_phase,
                                    self.attempt, self._counter)

    def _assert_unsealed(self):
        if os.path.exists(self.seal_path):
            raise EvidenceError(
                "evidence for %s %s is sealed; a correction is an amendment "
                "with its own id, not an edit"
                % (self.audit_id, self.run_phase))

    # -- operations --------------------------------------------------------
    def record_operation(self, operation, argv, exit_code, stdout, stderr,
                         timeout_seconds, output_limit_bytes,
                         started, finished, truncated_stdout=False,
                         truncated_stderr=False, note=None):
        """Persist one operation completely. Returns the evidence id."""
        self._assert_unsealed()
        eid = self.next_evidence_id()

        out_path = os.path.join(self.stdout_dir, "%s.txt" % eid)
        err_path = os.path.join(self.stderr_dir, "%s.txt" % eid)
        _write_bytes(out_path, stdout)
        _write_bytes(err_path, stderr)

        record = {
            "evidence_id": eid,
            "audit_id": self.audit_id,
            "run_phase": self.run_phase,
            "operation": operation,
            "argv": list(argv),
            "exit_code": exit_code,
            "stdout_path": os.path.relpath(out_path, self.root),
            "stderr_path": os.path.relpath(err_path, self.root),
            "stdout_sha256": hashing.sha256_bytes(_as_bytes(stdout)),
            "stderr_sha256": hashing.sha256_bytes(_as_bytes(stderr)),
            "stdout_bytes": len(_as_bytes(stdout)),
            "stderr_bytes": len(_as_bytes(stderr)),
            "stdout_truncated": bool(truncated_stdout),
            "stderr_truncated": bool(truncated_stderr),
            "timeout_seconds": timeout_seconds,
            "output_limit_bytes": output_limit_bytes,
            "started": started,
            "finished": finished,
            "note": note,
        }
        with open(self.commands_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return eid

    def record_finding(self, summary, source_path, sha256, locator,
                       evidence_type, confidence, critical=False):
        """A finding without all six fields is not a finding."""
        self._assert_unsealed()
        for name, value in (("summary", summary), ("source_path", source_path),
                            ("locator", locator), ("evidence_type", evidence_type),
                            ("confidence", confidence)):
            if value in (None, ""):
                raise EvidenceError("finding is missing %s" % name)
        if sha256 is not None and not hashing.is_hex64(sha256):
            raise EvidenceError("finding sha256 is not 64 hex characters")
        eid = self.next_evidence_id()
        finding = {
            "finding_id": eid,
            "summary": redaction.safe_quote(summary, 400),
            "source_path": source_path,
            "sha256": sha256,
            "locator": locator,
            "evidence_type": evidence_type,
            "confidence": confidence,
            "critical": bool(critical),
        }
        path = os.path.join(self.root, "findings.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(finding, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return finding

    # -- sealing -----------------------------------------------------------
    def _collect_files(self):
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not os.path.islink(
                os.path.join(dirpath, d)))
            for name in sorted(filenames):
                if name in ("SEAL.json", "EVIDENCE_MANIFEST.sha256"):
                    continue
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    raise EvidenceError("symlink in evidence tree: %s" % full)
                files.append(full)
        return files

    def seal(self, verdict):
        """Freeze the evidence for this phase."""
        if verdict not in policy.VERDICTS:
            raise EvidenceError("unknown verdict: %r" % verdict)
        self._assert_unsealed()
        manifest = hashing.manifest_for(self._collect_files(), self.root)
        hashing.write_manifest(manifest, self.manifest_path)
        seal = {
            "audit_id": self.audit_id,
            "run_phase": self.run_phase,
            "attempt_number": self.attempt,
            "attempt_id": "%s/%s/attempt-%d" % (self.audit_id, self.run_phase,
                                                self.attempt),
            "verdict": verdict,
            "sealed_at": time.time(),
            "file_count": len(manifest),
            "manifest_sha256": hashing.sha256_file(self.manifest_path),
        }
        with open(self.seal_path, "w", encoding="utf-8") as fh:
            json.dump(seal, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return seal

    def verify_seal(self):
        """Return (ok, differences). A sealed tree that changed is CONTAMINATED."""
        if not os.path.exists(self.seal_path):
            raise EvidenceError("not sealed: %s" % self.root)
        with open(self.seal_path, encoding="utf-8") as fh:
            seal = json.load(fh)
        actual_manifest_sha = hashing.sha256_file(self.manifest_path)
        if actual_manifest_sha != seal["manifest_sha256"]:
            return False, [{"path": "EVIDENCE_MANIFEST.sha256",
                            "expected": seal["manifest_sha256"],
                            "actual": actual_manifest_sha,
                            "reason": "MANIFEST_CHANGED"}]
        return hashing.verify_manifest(self.manifest_path, self.root)


def _as_bytes(value):
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", "surrogateescape")


def _write_bytes(path, value):
    canonical = path_policy.assert_writable(path)
    with open(canonical, "wb") as fh:
        fh.write(_as_bytes(value))
    return canonical
