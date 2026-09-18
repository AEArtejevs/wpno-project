#!/usr/bin/env python3
"""Stage the inputs the rehearsal needs so that every IN_PROCESS step can run.

Why this exists.

R7's rehearsal treated an in-process step whose input was absent as a lawful
deferral: `executed: false` with `ok: true`, reason
INPUT_PRODUCED_BY_AN_EARLIER_STEP_NOT_RUN_HERE. Twenty-two steps were excused
that way in the dirty repair run, and the excuse is the same shape as the
defect it accompanied -- a step that did not run counting as a step that
passed. R8 does not allow it: an IN_PROCESS operation is what this machine
does itself, so it is never a deferred class, and a rehearsal that cannot run
one has to say so as a failure rather than as a pass.

The way to make them runnable is to give them something real to read. That is
what this does, and it does it under the rehearsal root, never at the live
path the plan names. The rehearsal passes a substitution map to the executor
and the executor records both sides of every substitution, so a rehearsal
against a fixture can never be read as a live measurement of the real thing.

Three kinds of input are staged, and they are not equally strong. The
distinction is recorded per fixture in `origin`, because a reader has to be
able to tell which is which:

  REAL_BYTES_FROM_ACCEPTED_MATERIAL
      an exact copy, or an exact extraction, of material the package already
      holds and has already bound by digest. L1-A11's roster manifest is one:
      it is the operator supplement manifest, byte for byte, and the plan's
      `expected_sha256` assertion is therefore really tested rather than
      arranged to pass. L1-A14's app.xml is extracted from REF-06_S01.docx.
      L1-A20's identical copy is a copy of the real payload scanner.

  DERIVED_FROM_REAL_BYTES
      a deliberate one-change variation on accepted material, built so that a
      control which must detect a change has a change to detect. Each one is
      proved to differ from what it varies.

  SYNTHETIC_STAND_IN
      material the live phase produces on another host or from a run this
      rehearsal does not perform. It is well-formed and type-correct so the
      operation can really execute against it, and it is marked synthetic so
      nobody mistakes what it proves: that the operation runs, not that the
      audit's answer is what the fixture says.

A sealed synthetic attempt is staged for each COMPARISON phase, because a
comparison names sealed evidence of two phases that have not run. It is a
real seal over a real manifest of real files -- the sealing machinery is
exercised -- and the files under it are synthetic.
"""

import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy  # noqa: E402

FIXTURES = os.path.join(ROOT, "work", "_rehearsal_r8", "fixtures", "inputs")
RECORD = os.path.join(ROOT, "work", "_rehearsal_r8",
                      "REHEARSAL_INPUT_SUBSTITUTIONS.json")
PROJECT = os.path.dirname(ROOT)

REF05_SUPPLEMENT = ("/home/ubuntu/project/WPNO_operator_intake/"
                    "R7_all35_missing_material/REF-05/R7_REF05_SUPPLEMENT/"
                    "REF-05_SUPPLEMENT_MANIFEST.sha256")

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

substitutions = {}
fixtures = []


def _register(planned, actual, origin, note, differs_from=None):
    # A directory is registered as one. `prove_cases_are_novel` names two
    # directories as operands of COMPARE_HASHES, which is a finding about
    # that step rather than something to hash around here.
    is_dir = os.path.isdir(actual)
    entry = {
        "planned_path": planned,
        "actual_path": actual,
        "sha256": None if is_dir else hashing.sha256_file(actual),
        "size": None if is_dir else os.path.getsize(actual),
        "is_directory": is_dir,
        "origin": origin,
        "note": note,
    }
    if differs_from is not None:
        entry["differs_from"] = differs_from
        entry["differs_from_sha256"] = hashing.sha256_file(differs_from)
        entry["bytes_actually_differ"] = (
            entry["sha256"] != entry["differs_from_sha256"])
        if not entry["bytes_actually_differ"]:
            raise SystemExit(
                "fixture %s is byte-identical to what it must differ from; a "
                "control built on it would measure nothing" % actual)
    substitutions[planned] = actual
    fixtures.append(entry)
    return actual


def _out(*parts):
    path = os.path.join(FIXTURES, *parts)
    path_policy.ensure_dir(os.path.dirname(path))
    return path_policy.assert_writable(path)


def _docx(path, paragraphs, *, toc_entries=()):
    """A real, minimal, valid .docx: a zip carrying word/document.xml.

    Real enough that ZIP_LIST lists it and DOCX_PARSE_SANDBOX parses it, which
    is what the steps that read it actually do.
    """
    body = []
    for text in paragraphs:
        body.append(
            '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % text)
    for instruction in toc_entries:
        body.append(
            '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve">%s</w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>' % instruction)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>'
        % (WORD_NS, "".join(body)))
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
        'content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxml'
        'formats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.wordprocessingml.document.main'
        '+xml"/></Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
        '2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
        'openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="word/document.xml"/></Relationships>')
    # A fixed timestamp: two runs of this stager must produce identical bytes
    # or a positive control asserting equality would depend on the clock.
    stamp = (2026, 8, 28, 0, 0, 0)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in (("[Content_Types].xml", content_types),
                           ("_rels/.rels", rels),
                           ("word/document.xml", document)):
            info = zipfile.ZipInfo(name, stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, text)
    return path


def stage_a01():
    a = _docx(_out("L1-A01", "RUN1", "output.docx"),
              ["Chapter one.", "Chapter two."])
    _register(os.path.join(ROOT, "work", "L1-A01", "RUN-A", "RUN1",
                           "output.docx"), a, "SYNTHETIC_STAND_IN",
              "stands in for the first of the two generator runs this "
              "rehearsal does not perform")
    b = _out("L1-A01", "RUN2", "output.docx")
    shutil.copyfile(a, b)
    _register(os.path.join(ROOT, "work", "L1-A01", "RUN-A", "RUN2",
                           "output.docx"), b, "SYNTHETIC_STAND_IN",
              "a byte-identical second run; whether the real generator is "
              "deterministic is the audit's question and is not decided here")
    changed = _docx(_out("L1-A01", "controls", "output_from_changed_input.docx"),
                    ["Chapter one, altered.", "Chapter two."])
    _register(os.path.join(ROOT, "work", "L1-A01", "RUN-A", "controls",
                           "output_from_changed_input.docx"),
              changed, "DERIVED_FROM_REAL_BYTES",
              "one paragraph altered, so the positive control has a "
              "difference to find", differs_from=a)
    ua = _docx(_out("L1-A01", "controls", "unchanged_a.docx"), ["Pinned."])
    ub = _out("L1-A01", "controls", "unchanged_b.docx")
    shutil.copyfile(ua, ub)
    for name, path in (("unchanged_a.docx", ua), ("unchanged_b.docx", ub)):
        _register(os.path.join(ROOT, "work", "L1-A01", "RUN-A", "controls",
                               name), path, "SYNTHETIC_STAND_IN",
                  "an identical pair; the control's outcome is substantive")


def stage_a02():
    f1 = _docx(_out("L1-A02", "fixtures", "F1.docx"),
               ["Heading", "Body text of the unmodified fixture."])
    _register(os.path.join(ROOT, "work", "L1-A02", "RUN-A", "fixtures",
                           "F1.docx"), f1, "SYNTHETIC_STAND_IN",
              "the unmodified document fixture the independent reader parses")


def stage_a04():
    t1 = _docx(_out("L1-A04", "generated", "T1.docx"),
               ["Introduction", "Method", "Result"],
               toc_entries=[' TOC \\o "1-3" \\h \\z \\u '])
    _register(os.path.join(ROOT, "work", "L1-A04", "RUN-A", "generated",
                           "T1.docx"), t1, "SYNTHETIC_STAND_IN",
              "a generated document carrying a real TOC field instruction, so "
              "the TOC extraction has a field to extract")


def stage_a11():
    """The roster manifest, byte-identical to the operator supplement.

    The plan binds `expected_sha256` to this file's digest. Staging anything
    else would make the assertion fail; staging bytes chosen to make it pass
    would be manufacturing the answer. So the real operator manifest is
    copied, and the assertion is genuinely exercised against the digest the
    reference record already published.
    """
    if not os.path.isfile(REF05_SUPPLEMENT):
        raise SystemExit("REF-05 supplement manifest is absent: %s"
                         % REF05_SUPPLEMENT)
    dest = _out("L1-A11", "roster", "SUPPLEMENT_MANIFEST.sha256")
    shutil.copyfile(REF05_SUPPLEMENT, dest)
    digest = hashing.sha256_file(dest)
    expected = ("374e18e51923327a25ad7ad285ae708db9ea1b3d9845c085194ae813"
                "db2f0e23")
    if digest != expected:
        raise SystemExit(
            "staged roster manifest hashes to %s, not the digest the plan "
            "binds (%s)" % (digest, expected))
    _register(os.path.join(ROOT, "work", "L1-A11", "RUN-A", "roster",
                           "SUPPLEMENT_MANIFEST.sha256"), dest,
              "REAL_BYTES_FROM_ACCEPTED_MATERIAL",
              "an exact copy of the REF-05 operator supplement manifest; the "
              "plan's expected_sha256 is really tested against it")


def stage_a14():
    """docProps/app.xml, extracted from the real REF-06 document."""
    source = os.path.join(ROOT, "references", "REF-06_S01.docx")
    dest = _out("L1-A14", "extracted", "docProps", "app.xml")
    with zipfile.ZipFile(path_policy.assert_readable(source)) as archive:
        names = archive.namelist()
        if "docProps/app.xml" not in names:
            raise SystemExit("REF-06_S01.docx has no docProps/app.xml")
        data = archive.read("docProps/app.xml")
    with open(dest, "wb") as fh:
        fh.write(data)
    _register(os.path.join(ROOT, "work", "L1-A14", "RUN-A", "extracted",
                           "docProps", "app.xml"), dest,
              "REAL_BYTES_FROM_ACCEPTED_MATERIAL",
              "extracted from references/REF-06_S01.docx; the reference is "
              "read and not modified")


KORPUS_DOCX = "/home/ubuntu/project/WPNO/ap18/korpus_docx"
KORPUS_W1 = os.path.join(KORPUS_DOCX, "angriff_W1_ausgeblendet.docx")


def stage_a16():
    """The five authored cases, and the three novelty controls.

    The novelty controls are the point. `prove_cases_are_novel` used to bind
    COMPARE_HASHES to two directories and could not run at all; the repaired
    step measures each case against `ap18/korpus_docx` by content digest, and
    these three fixtures are what prove the measurement can tell the two
    answers apart:

      novel      a case absent from the corpus, which must be reported novel;
      duplicate  a byte-identical copy of W1, which must be reported duplicate;
      renamed    the same bytes under a different filename, which must still
                 be reported duplicate -- renaming is the evasion a name-based
                 check would miss, and this is the fixture that proves the
                 comparison is on content.

    The duplicate fixtures are copies of a real corpus member, so the control
    is measured against the corpus the audit actually names rather than
    against something built to agree with it.
    """
    n1 = None
    for cid in ("N1", "N2", "N3", "N4", "N5"):
        path = _docx(_out("L1-A16", "cases", "%s.docx" % cid),
                     ["Case %s." % cid, "Rendered body text for %s." % cid])
        if cid == "N1":
            n1 = path
        _register(os.path.join(ROOT, "work", "L1-A16", "RUN-A", "cases",
                               "%s.docx" % cid), path, "SYNTHETIC_STAND_IN",
                  "one of the five cases the phase builds; novelty against "
                  "the real corpus is measured, the content is synthetic")
    _register(os.path.join(ROOT, "work", "L1-A16", "RUN-A", "cases"),
              os.path.dirname(n1), "SYNTHETIC_STAND_IN",
              "the candidate directory the novelty measurement enumerates")

    novel = _docx(_out("L1-A16", "cases", "novelty_controls", "novel",
                       "NOVEL_CONTROL.docx"),
                  ["A case absent from the corpus by construction."])
    _register(os.path.join(ROOT, "work", "L1-A16", "RUN-A", "cases",
                           "novelty_controls", "novel"),
              os.path.dirname(novel), "SYNTHETIC_STAND_IN",
              "a case known to be absent from the corpus; it must be "
              "reported novel or the measurement cannot recognise novelty")

    if not os.path.isfile(KORPUS_W1):
        raise SystemExit("the corpus member the controls copy is absent: %s"
                         % KORPUS_W1)
    dup = _out("L1-A16", "cases", "novelty_controls", "duplicate",
               "angriff_W1_ausgeblendet.docx")
    shutil.copyfile(KORPUS_W1, dup)
    if hashing.sha256_file(dup) != hashing.sha256_file(KORPUS_W1):
        raise SystemExit("the duplicate control is not byte-identical to W1")
    _register(os.path.join(ROOT, "work", "L1-A16", "RUN-A", "cases",
                           "novelty_controls", "duplicate"),
              os.path.dirname(dup), "REAL_BYTES_FROM_ACCEPTED_MATERIAL",
              "a byte-identical copy of corpus member W1; it must be "
              "reported duplicate")

    renamed = _out("L1-A16", "cases", "novelty_controls", "renamed",
                   "an_entirely_different_filename.docx")
    shutil.copyfile(KORPUS_W1, renamed)
    if hashing.sha256_file(renamed) != hashing.sha256_file(KORPUS_W1):
        raise SystemExit("the renamed control is not byte-identical to W1")
    _register(os.path.join(ROOT, "work", "L1-A16", "RUN-A", "cases",
                           "novelty_controls", "renamed"),
              os.path.dirname(renamed), "REAL_BYTES_FROM_ACCEPTED_MATERIAL",
              "corpus member W1 under a different filename; it must still be "
              "reported duplicate")


def stage_a20():
    """A byte-identical copy, and a copy differing only in one comment."""
    source = os.path.join(PROJECT, "anonymization", "payload_scan.py")
    canonical = path_policy.assert_readable(source)
    identical = _out("L1-A20", "controls", "identical_copy.py")
    shutil.copyfile(canonical, identical)
    if hashing.sha256_file(identical) != hashing.sha256_file(canonical):
        raise SystemExit("the identical copy is not identical")
    _register(os.path.join(ROOT, "work", "L1-A20", "RUN-A", "controls",
                           "identical_copy.py"), identical,
              "REAL_BYTES_FROM_ACCEPTED_MATERIAL",
              "a byte-for-byte copy of the real payload scanner; the positive "
              "control's equality is therefore a real equality")

    with open(canonical, "rb") as fh:
        original = fh.read()
    changed = _out("L1-A20", "controls", "comment_changed.py")
    marker = b"\n# R8 rehearsal control: this comment is the only difference.\n"
    with open(changed, "wb") as fh:
        fh.write(original + marker)
    _register(os.path.join(ROOT, "work", "L1-A20", "RUN-A", "controls",
                           "comment_changed.py"), changed,
              "DERIVED_FROM_REAL_BYTES",
              "the same source with one comment appended: the raw bytes "
              "differ and the AST must not", differs_from=canonical)


def stage_a24():
    """The external-host material. Synthetic: it is produced on another host."""
    packet = _out("L1-A24", "external_host", "EXECUTION_PACKET.json")
    with open(packet, "w", encoding="utf-8") as fh:
        json.dump({
            "schema": "wpno.level1.execution_packet/1",
            "audit_id": "L1-A24", "run_phase": "RUN-A",
            "synthetic_rehearsal_fixture": True,
            "host": "SYNTHETIC_REHEARSAL_HOST_NOT_A_REAL_INTAKE",
            "launch_directories": ["outside_project", "inside_project",
                                   "sibling_directory"],
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")
    _register(os.path.join(ROOT, "work", "L1-A24", "RUN-A", "external_host",
                           "EXECUTION_PACKET.json"), packet,
              "SYNTHETIC_STAND_IN",
              "the execution packet is written for the live phase on the "
              "external host; this stands in so the step can parse something")

    intake = _out("L1-A24", "external_host", "INTAKE_OUTSIDE.json")
    with open(intake, "w", encoding="utf-8") as fh:
        json.dump({
            "schema": "wpno.level1.external_intake/1",
            "synthetic_rehearsal_fixture": True,
            "launch_directory": "outside_project",
            "instruction_files_reported_loaded": [],
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")
    _register(os.path.join(ROOT, "work", "L1-A24", "RUN-A", "external_host",
                           "INTAKE_OUTSIDE.json"), intake,
              "SYNTHETIC_STAND_IN",
              "an intake record shaped like the real one; the control's "
              "substantive assertion is not expressible in the step, which "
              "is recorded in the control coverage record")

    manifest = ("d41d8cd98f00b204e9800998ecf8427e  placeholder_only\n")
    pre = _out("L1-A24", "external_host", "EXTERNAL_DIR_PRE.sha256")
    post = _out("L1-A24", "external_host", "EXTERNAL_DIR_POST.sha256")
    for path in (pre, post):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(manifest)
    for name, path in (("EXTERNAL_DIR_PRE.sha256", pre),
                       ("EXTERNAL_DIR_POST.sha256", post)):
        _register(os.path.join(ROOT, "work", "L1-A24", "RUN-A",
                               "external_host", name), path,
                  "SYNTHETIC_STAND_IN",
                  "pre and post manifests of the external directory, staged "
                  "equal because the control asserts the external directory "
                  "did not change; a test proves the control fails when they "
                  "differ")


# ------------------------------------------------- sealed comparison fixtures
def _seal_attempt(audit_id, run_phase, index_name):
    """A real seal over a real manifest of real files, all of them synthetic.

    The point is not the content. It is that a COMPARISON step which reads a
    sealed attempt has a sealed attempt to read, so the step really executes
    instead of being excused. `EXECUTING_WOULD_BE_THE_LIVE_PHASE` was the
    excuse in R7 and it covered four phases that had never run a single
    operation between them.
    """
    root = _out("_sealed_attempts", audit_id, run_phase, "attempt-1")
    path_policy.ensure_dir(root)
    payload = os.path.join(root, "commands.jsonl")
    with open(payload, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "synthetic_rehearsal_fixture": True,
            "audit_id": audit_id, "run_phase": run_phase,
            "note": "not a real attempt; staged so the comparison can read a "
                    "sealed attempt"}, sort_keys=True) + "\n")

    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rows.append("%s  %s" % (hashing.sha256_file(full),
                                    os.path.relpath(full, root)))
    manifest_path = os.path.join(root, "EVIDENCE_MANIFEST.sha256")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(rows)) + "\n")

    seal = {
        "audit_id": audit_id, "run_phase": run_phase,
        "attempt_number": 1,
        "attempt_id": "%s/%s/attempt-1" % (audit_id, run_phase),
        "manifest_sha256": hashing.sha256_file(manifest_path),
        "sealed_at": 1787900000,
        "synthetic_rehearsal_fixture": True,
        "verdict": "UNVERIFIED",
    }
    seal_path = os.path.join(root, "SEAL.json")
    with open(seal_path, "w", encoding="utf-8") as fh:
        json.dump(seal, fh, indent=2, sort_keys=True)
        fh.write("\n")

    phase_root = os.path.dirname(root)
    index_path = os.path.join(phase_root, index_name)
    if index_name == "SEAL.json":
        shutil.copyfile(seal_path, index_path)
    else:
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump({"audit_id": audit_id, "run_phase": run_phase,
                       "accepted_attempt": 1, "attempts": [1],
                       "synthetic_rehearsal_fixture": True,
                       "seal_sha256": hashing.sha256_file(seal_path)},
                      fh, indent=2, sort_keys=True)
            fh.write("\n")

    _register(os.path.join(ROOT, "evidence", audit_id, run_phase, index_name),
              index_path, "SYNTHETIC_STAND_IN",
              "a sealed synthetic attempt under the rehearsal root; the "
              "comparison step really hashes it, and it is not live evidence")


def stage_comparisons():
    for audit_id, index_name in (("L1-A18", "ATTEMPT_INDEX.json"),
                                 ("L1-A19", "SEAL.json"),
                                 ("L1-A31", "ATTEMPT_INDEX.json"),
                                 ("L1-A34", "ATTEMPT_INDEX.json")):
        for run_phase in ("RUN-A", "RUN-B"):
            _seal_attempt(audit_id, run_phase, index_name)


def main():
    path_policy.ensure_dir(FIXTURES)
    stage_a01()
    stage_a02()
    stage_a04()
    stage_a11()
    stage_a14()
    stage_a16()
    stage_a20()
    stage_a24()
    stage_comparisons()

    payload = {
        "schema": "wpno.level1.rehearsal-input-substitutions/1",
        "revision": "R8",
        "staged_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule": ("every entry maps a path a plan names to the path the "
                 "rehearsal actually reads; the executor records both sides "
                 "on every step that uses one"),
        "count": len(fixtures),
        "by_origin": {origin: sum(1 for f in fixtures
                                  if f["origin"] == origin)
                      for origin in sorted({f["origin"] for f in fixtures})},
        "fixtures": fixtures,
        "substitutions": substitutions,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with open(path_policy.assert_writable(RECORD), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    print(json.dumps({
        "record": os.path.relpath(RECORD, ROOT),
        "record_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "count": payload["count"],
        "by_origin": payload["by_origin"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
