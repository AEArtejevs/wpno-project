"""Declarative plan data for every audit that did not already have a plan.

One function per audit-phase. Each returns a complete execution plan; the
common envelope, the comparison shape, the schema validation and the argv
check all live in `plan_library`. Nothing here builds an argv by hand and
nothing here restates a rule the library already enforces.

Every plan is written from the audit's own prompt and binding. Where a prompt
names a control, the control is in the plan with its fixture and the reason it
is expected to succeed or fail; where a prompt says a control is not
applicable, the plan says so with the prompt's reason rather than quietly
leaving the section out.

Where a phase needs material that only exists once the phase has been
approved - a sandbox copy of the target, a synthetic document, a working
directory - the plan names the path under `work/<audit>/<phase>/` and the
preparation that creates it is described in `static_analysis`. The rehearsal
stages a synthetic analogue of those paths so that the plan is exercised
rather than merely parsed.
"""

import json
import os

from plan_library import (LEVEL1_ROOT, PROJECT_ROOT, ROOT,  # noqa: F401
                          PlanBuildError, binding_envelope, comparison_plan,
                          bind, pkg, proj, ref, sha_of, work)

# --------------------------------------------------------------- shorthand

REF11_ZIP = ref("REF-11-original-mail-attachment.zip")
REF11_P7S = ref("REF-11-vhn.xml.p7s")
REF11_CONTENT = ref("REF-11-vhn-covered-content.xml")
REF11_OSCI = ref("REF-11-563203462.xml")

# L1-A16's reference corpus, named exactly by the audit specification's
# STATIC ANALYSIS section: "ap18/korpus_docx contains W1 hidden, W2 white
# text, W3 tiny font, W4 document properties, W5 footnote, and two clean
# files". The plan previously pointed at `ap18`, the source tree that
# contains it, which is a different thing.
KORPUS_DOCX = proj("ap18", "korpus_docx")
KORPUS_SET_ID = "AP18_KORPUS_DOCX_W1_W5_PLUS_TWO_CLEAN"
REF11_PDF = ref("REF-11-berufungsbegruendung-O.pdf")
REF11_PDF_P7S = ref("REF-11-berufungsbegruendung-O.pdf.p7s")
REF11_XJUSTIZ = ref("REF-11-xjustiz_nachricht.xml")
REF12_DOCX = os.path.join(ROOT, "references", "REF-12", "376_DKB MH.docx")

MANIFEST_JSON = ref("manifest.json")

# The synthetic material L1-A31's preparation already built. It is reused
# rather than rebuilt: it is a control fixture, its digests are recorded in
# that preparation's staging record, and a second copy would be a second
# thing to keep in step.
A31_PREP = os.path.join(ROOT, "work", "L1-A31", "preparation_r8_2026-08-28")

# The content OpenSSL emitted from the CMS during staging. It is the same
# bytes as REF11_CONTENT reached by a different route, which is what makes
# it usable as the second operand of a comparison that must be able to
# disagree. It is never the arbiter: the oracle is the independent hash
# computation, as both L1-A28 and L1-A33 require.
CMS_EMITTED_CONTENT = os.path.join(
    A31_PREP, "outputs", "vhn_verified_content.bin")


def _synthetic_validation_time():
    """The validation epoch for the synthetic chain, read from its staging.

    R8 defect, found by the R8 rehearsal.

    Three steps in L1-A32 and two in L1-A35 carried the literal 1787787495 as
    their `-attime`. The literal was written when R7 staged its synthetic
    chain and it worked there only because that chain happened to have been
    issued the day before it. R8 stages a fresh chain, whose notBefore is
    2026-08-28T13:38:05Z, and the literal is now earlier than that, so every
    one of those five verifications failed with

        cms_signerinfo_verify_cert: certificate verify error:
        Verify error: certificate is not yet valid

    A positive control that cannot pass is not a strict control, and R6's
    RUN-A sealed an ERROR for exactly this reason -- its synthetic validation
    epoch was six days and eighteen hours before its own synthetic root's
    notBefore. R7 repaired that for L1-A31 by deriving the time from the
    moment of issue; L1-A32 and L1-A35 kept the literal and inherited the
    same latent defect, invisible for as long as the numbers happened to
    fall the right way round.

    The epoch is therefore derived from the staging record that describes the
    chain actually on disk, so it cannot drift from it again. The operator-
    supplied CMS objects keep their own literal epochs: those are real
    signatures over real material with real validity windows, and deriving
    their validation time from a staging run would be wrong.
    """
    record = os.path.join(A31_PREP, "STAGING_RECORD.json")
    if not os.path.isfile(record):
        raise PlanBuildError(
            "the synthetic chain has not been staged; run "
            "build/stage_l1a31_material.py before building plans that bind "
            "its validation time")
    with open(record, encoding="utf-8") as fh:
        staged = json.load(fh)
    value = staged["controls"]["notes"]["synthetic_validation_time"]
    if not isinstance(value, int) or value <= 0:
        raise PlanBuildError(
            "synthetic_validation_time is %r; a validation time is never "
            "left to the clock and never defaulted" % (value,))
    return value
SYN = os.path.join(A31_PREP, "synthetic")

REF11_LIMITATION = (
    "REF-11 is operator-supplied material. Its chain of custody is the "
    "operator's statement recorded in references/manifest.json. Hash identity "
    "against that record is what is verified here; it is not proof of how the "
    "bytes came to exist before intake, and is not reported as such.")


def _ref11_envelope_refs():
    return bind([REF11_ZIP, REF11_P7S, REF11_CONTENT, REF11_OSCI,
                 MANIFEST_JSON])


def _target(path, evidence):
    return {"path": path, "sha256": sha_of(path), "identity_evidence": evidence}


# ============================================================ L1-A27
# R8 repair: the self-comparisons.
#
# Six steps across five plans passed the same path as both operands of
# COMPARE_HASHES. A file compared with itself is equal by construction, so
# every one of them reported success without being able to report anything
# else -- a check that cannot fail is not a check. None of the six had ever
# been able to fail in any revision.
#
# Two shapes, repaired two ways.
#
# Where the step's purpose is a genuine two-artefact comparison -- L1-A28's
# "compare it with the extracted attribute", L1-A33's "declared versus
# actual" -- the second operand is now the content OpenSSL emitted from the
# CMS during staging, `outputs/vhn_verified_content.bin`. That artefact
# reaches the same bytes by a different route, so the comparison can now
# disagree, which is the whole point of making it. The independent hash
# computation is still the oracle; the CMS-emitted copy is the other side of
# the comparison and never the arbiter, as both prompts require.
#
# Where the step is really a single-file remeasurement written as a
# comparison -- L1-A27's and L1-A29's `hash_method_2_streaming`, whose
# agreement with method 1 is established at the reporting layer -- the
# operands stay as they are and `expected_sha256` is bound. The step then
# asserts the digest it exists to measure, and drift in the reference fails
# it.
#
# In both shapes the digest is bound from the accepted reference at build
# time by `sha_of`, so it is measured rather than written down.

def a27_run_a():
    audit, phase = "L1-A27", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Identify the operator-supplied archive, hash its raw bytes by two "
            "independent methods, record size, metadata and stored entry "
            "structure, and prove the measurement resolves a one-byte change. "
            "The archive is hashed as it lies: not opened, not extracted, not "
            "normalised first."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported; nothing here parses "
            "project code at all. The archive is located in references/ as "
            "REF-11 and its digest is checked against references/manifest.json "
            "before any other operation. STAT_FILE and FILE_TYPE establish "
            "what the file is before it is hashed, so that a hash is not "
            "computed over something other than the claimed object. ZIP_LIST "
            "reads the stored entry names, sizes, CRCs and timestamps without "
            "extracting.\n\n"
            "Preparation the approved phase performs first: copy the archive "
            "to work/L1-A27/RUN-A/controls/archive_one_byte_mutated.zip and "
            "flip exactly one byte, recording the offset and both byte values. "
            "The original in references/ is never written to."),
        "target": _target(REF11_ZIP,
                          "references/manifest.json binds this operator-supplied "
                          "archive as REF-11 with the same SHA-256"),
        "steps": [
            {"step_id": "stat_archive", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Size and metadata, recorded before the file is hashed.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 120},
            {"step_id": "file_type_archive", "operation": "FILE_TYPE",
             "control_role": "MEASUREMENT",
             "purpose": "Confirm the object is what it is claimed to be.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 120},
            {"step_id": "hash_method_1", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "First independent hash of the raw bytes.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "hash_method_2_streaming", "operation": "COMPARE_HASHES",
             "control_role": "ORACLE",
             "purpose": ("Second independent hash, computed by a streaming "
                         "standard-library read written for this audit, and "
                         "compared with the first. Two methods that disagree "
                         "mean one is not reading the raw bytes."),
             "params": {"left": REF11_ZIP, "right": REF11_ZIP,
                        "algorithms": ["sha256", "sha512"],
                        "expected_sha256": sha_of(REF11_ZIP)},
             "timeout_seconds": 300},
            {"step_id": "zip_list_no_extract", "operation": "ZIP_LIST",
             "control_role": "MEASUREMENT",
             "purpose": "Stored entry names, sizes, CRCs and timestamps.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "positive_control_known_hash", "operation": "SHA256_FILE",
             "control_role": "POSITIVE",
             "purpose": ("Hash a file whose digest is independently known from "
                         "the reference manifest, and confirm both methods "
                         "produce it."),
             "params": {"path": REF11_CONTENT}, "timeout_seconds": 120},
            {"step_id": "negative_control_two_files_differ",
             "operation": "COMPARE_HASHES", "control_role": "NEGATIVE",
             "purpose": ("Two files known to differ must hash differently. A "
                         "method that reports every pair equal reports nothing."),
             "params": {"left": REF11_CONTENT, "right": REF11_OSCI},
             "timeout_seconds": 120},
            {"step_id": "mutation_control_one_byte",
             "operation": "COMPARE_BINARY_FILES", "control_role": "MUTATION",
             "purpose": ("A sandbox copy with exactly one byte altered must be "
                         "detected by both methods. Zero detected differences "
                         "is a measurement error, not a pass."),
             "params": {"left": REF11_ZIP,
                        "right": w("controls", "archive_one_byte_mutated.zip")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="two independent hash computations over the raw bytes",
                executable="/usr/bin/file for FILE_TYPE; every other step is in-process",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[REF11_LIMITATION],
                independent_oracle=(
                    "Two independent hashing methods and the file's own byte "
                    "count. Neither method is derived from the other."),
                target_identification_rule=(
                    "Identity comes from the operator-supplied artefact alone. "
                    "The digest is checked against references/manifest.json "
                    "before any other operation. No similarly named file is "
                    "substituted and no project file that merely mentions the "
                    "subject is bound."),
                allowed_reads=["references/REF-11-*"],
                allowed_writes=["work/L1-A27/RUN-A/", "evidence/L1-A27/RUN-A/"],
                forbidden_reads=["any client document not in references/"],
                notes=["The archive is never copied into a report; only its "
                       "measurements are."]),
            {"check_id": "two_methods_agree",
             "question": "Do the two independent hash computations agree?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "hash_method_2_streaming",
             "required_result": "Both methods produce the same SHA-256.",
             "expected_exit_code": 0,
             "why": ("A disagreement means one method is not reading the raw "
                     "bytes, and it must be resolved before anything else is "
                     "interpreted."),
             "second_algorithm": ("SHA-512 is recorded as well, so a later "
                                  "comparison does not depend on one algorithm.")},
            {"check_id": "positive_control",
             "question": "Do the methods reproduce an independently known digest?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_hash",
             "expected_exit_code": 0,
             "required_result": ("The computed digest equals the value "
                                 "references/manifest.json records for the "
                                 "same file.")},
            {"check_id": "negative_control",
             "question": "Do the methods distinguish two different files?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_two_files_differ",
             "expected_result": "DIGESTS_DIFFER",
             "expected_failure_reason": "the two inputs are different files",
             "required_result": ("The digests differ. Equality here would mean "
                                 "the comparison is not reading both operands.")},
            {"check_id": "mutation_control",
             "question": "Does a one-byte change change the measurement?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_one_byte",
             "fixture": "work/L1-A27/RUN-A/controls/archive_one_byte_mutated.zip",
             "fixture_construction": ("a byte-for-byte copy of the archive with "
                                      "exactly one byte flipped; the offset and "
                                      "both values are recorded"),
             "proof_the_fixture_differs": ("the copy's SHA-256 differs from the "
                                           "original's, and the recorded offset "
                                           "names where"),
             "expected_result": "DIFFERENCE_DETECTED_AT_THE_RECORDED_OFFSET",
             "zero_changed_bytes_is": ("a measurement error and an invalid "
                                       "control, never a pass"),
             "required_result": "Both methods report the archive changed."},
            {"check_id": "raw_bytes_only",
             "question": "Was anything opened, extracted or normalised first?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("No. ZIP_LIST reads the central directory "
                                 "without extracting, and the hashes are taken "
                                 "over the file as it lies."),
             "verdict_effect": ("A hash computed after extraction would answer "
                                "a different question and voids this phase.")},
        ],
    }


# ============================================================ L1-A28
def a28_run_a():
    audit, phase = "L1-A28", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Identify the signed content and whether the CMS object carries it "
            "or references it, identify the digest algorithm from the "
            "structure rather than by assumption, extract the messageDigest "
            "signed attribute, recalculate the digest over an explicitly "
            "stated byte range by a method that is not the CMS library, and "
            "compare byte for byte. A match here does not establish that the "
            "signature verifies; that is L1-A34."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The CMS object and its "
            "content are located in references/ as REF-11 and their digests "
            "are checked against references/manifest.json first.\n\n"
            "Encapsulated versus detached is decided before anything is "
            "hashed, because it determines what is hashed and everything "
            "downstream rests on it. REF-11-vhn.xml.p7s is a detached CMS over "
            "REF-11-vhn-covered-content.xml: the covered content is a separate "
            "file, which is why every verification step names it explicitly.\n\n"
            "The structure is parsed and the result is marked "
            "PARSE_ONLY_NOT_VERIFICATION. A parse that is allowed to read as a "
            "verification is the confusion this audit exists to prevent.\n\n"
            "Preparation the approved phase performs: copy the covered content "
            "to work/L1-A28/RUN-A/controls/content_one_byte_mutated.xml and "
            "alter one byte, recording the offset."),
        "target": _target(REF11_P7S,
                          "references/manifest.json binds this CMS object as "
                          "REF-11 with the same SHA-256"),
        "steps": [
            {"step_id": "stat_cms", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Record the CMS object's size and metadata.",
             "params": {"path": REF11_P7S}, "timeout_seconds": 120},
            {"step_id": "hash_cms", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the CMS object being parsed.",
             "params": {"path": REF11_P7S}, "timeout_seconds": 120},
            {"step_id": "hash_covered_content", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": ("Bind the detached content whose digest the "
                         "messageDigest attribute is supposed to carry."),
             "params": {"path": REF11_CONTENT}, "timeout_seconds": 120},
            {"step_id": "parse_signer_certificate",
             "operation": "OPENSSL_PARSE_CERT", "control_role": "MEASUREMENT",
             "purpose": ("Read the signer certificate carried in the sealed "
                         "structure. PARSE_ONLY_NOT_VERIFICATION."),
             "params": {"cert": os.path.join(
                 A31_PREP, "certs",
                 "vhn_leaf_from_sealed_p7s_parse_evidence.pem")},
             "timeout_seconds": 120},
            {"step_id": "recalculate_digest_independently",
             "operation": "COMPARE_HASHES", "control_role": "ORACLE",
             "purpose": ("Recalculate the content digest over the stated byte "
                         "range with a standard-library streaming read, not "
                         "with the CMS library that parsed the structure, and "
                         "compare it with the extracted attribute."),
             "params": {"left": REF11_CONTENT,
                        "right": CMS_EMITTED_CONTENT,
                        "algorithms": ["sha256"],
                        "expected_sha256": sha_of(REF11_CONTENT)},
             "timeout_seconds": 300},
            {"step_id": "positive_control_known_digest",
             "operation": "SHA256_FILE", "control_role": "POSITIVE",
             "purpose": ("Digest an input whose value is independently known "
                         "from the reference manifest."),
             "params": {"path": os.path.join(SYN, "content.bin")},
             "timeout_seconds": 120},
            {"step_id": "negative_control_different_input",
             "operation": "COMPARE_HASHES", "control_role": "NEGATIVE",
             "purpose": "A different input must produce a different digest.",
             "params": {"left": os.path.join(SYN, "content.bin"),
                        "right": os.path.join(SYN, "wrong_content.bin"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 120},
            {"step_id": "mutation_control_content_byte",
             "operation": "COMPARE_BINARY_FILES", "control_role": "MUTATION",
             "purpose": ("One altered byte of the content must change the "
                         "recalculated digest so that it no longer matches the "
                         "attribute."),
             "params": {"left": REF11_CONTENT,
                        "right": w("controls", "content_one_byte_mutated.xml")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("ASN.1 structure read plus an independent digest "
                        "recalculation over an explicitly stated byte range"),
                executable="/usr/bin/openssl for the certificate parse; the digest steps are in-process",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[REF11_LIMITATION],
                independent_oracle=(
                    "An independent hash computation over a stated byte range, "
                    "plus the ASN.1 structure read directly. The signing "
                    "tool's own verification output is not the oracle here."),
                target_identification_rule=(
                    "The CMS object and its content come from the "
                    "operator-supplied REF-11 material and their digests are "
                    "checked against references/manifest.json first."),
                allowed_reads=["references/REF-11-*",
                               "work/L1-A31/preparation_r8_2026-08-28/"],
                allowed_writes=["work/L1-A28/RUN-A/", "evidence/L1-A28/RUN-A/"],
                notes=["A CMS verified without naming its detached content "
                       "proves nothing about any file, which is why the "
                       "content path is explicit in every step that uses it."]),
            {"check_id": "encapsulated_or_detached",
             "question": "Does the CMS carry the content or reference it?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "recorded_before": "any digest is computed",
             "required_result": ("Stated explicitly, with the structural "
                                 "evidence for it. Everything downstream "
                                 "depends on this answer."),
             "why": ("Hashing the wrong range produces a mismatch that looks "
                     "exactly like a tampered file.")},
            {"check_id": "digest_algorithm_from_structure",
             "question": "Which digest algorithm does the structure name?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Read from the parsed structure, never "
                                 "assumed from the file extension or from what "
                                 "is common.")},
            {"check_id": "three_results_reported_separately",
             "question": "Are the three results kept apart?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("(a) the recalculated content digest, (b) the "
                                 "extracted messageDigest attribute, (c) "
                                 "whether they match - reported as three "
                                 "values, never merged."),
             "never_reported_as": ("a verified signature. (c) matching does "
                                   "not establish that the signature verifies; "
                                   "that question belongs to L1-A34.")},
            {"check_id": "parse_only",
             "question": "Is the structural parse marked as a parse?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "parse_signer_certificate",
             "expected_exit_code": 0,
             "required_result": "PARSE_ONLY_NOT_VERIFICATION"},
            {"check_id": "positive_control",
             "question": "Is the digest method correct on a known input?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_digest",
             "expected_exit_code": 0},
            {"check_id": "negative_control",
             "question": "Does a different input give a different digest?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_different_input",
             "expected_result": "DIGESTS_DIFFER",
             "expected_failure_reason": "the two inputs are different content",
             "fixture": "the synthetic content and wrong-content pair staged for L1-A31"},
            {"check_id": "mutation_control",
             "question": "Does one altered content byte break the match?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_content_byte",
             "fixture": "work/L1-A28/RUN-A/controls/content_one_byte_mutated.xml",
             "fixture_construction": "a copy of the covered content with one byte altered",
             "proof_the_fixture_differs": "its SHA-256 differs from the original's",
             "expected_result": "DIGEST_CHANGES_AND_NO_LONGER_MATCHES_THE_ATTRIBUTE",
             "zero_changed_results_is": "a measurement error, not a pass"},
        ],
    }


# ============================================================ L1-A29
def a29_run_a():
    audit, phase = "L1-A29", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Establish what '376' refers to, then hash its exact raw bytes by "
            "two independent methods and compare against the operator's stated "
            "expected value with its provenance. A remeasurement without a "
            "stated expected value is a measurement, not a verification."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The referent question is "
            "answered first and from the operator's own statement: "
            "references/REF-12/REF-12_OPERATOR_PROVENANCE.txt defines 376 as "
            "376_DKB MH.docx and records the source-host path, the expected "
            "pre-transfer SHA-256, the size and the chain of custody. "
            "bindings/L1-A29.binding.json carries the same referent, the same "
            "expected value and the limitation that no older standalone "
            "historical manifest was located.\n\n"
            "Preparation the approved phase performs: copy the document to "
            "work/L1-A29/RUN-A/controls/document_one_byte_mutated.docx and "
            "alter one byte, recording the offset. The reference copy is never "
            "written to."),
        "target": _target(REF12_DOCX,
                          "references/REF-12/REF-12_MANIFEST.sha256 and "
                          "bindings/L1-A29.binding.json bind this file as the "
                          "referent of '376' with the same SHA-256"),
        "steps": [
            {"step_id": "read_operator_provenance",
             "operation": "READ_FILE_RANGE", "control_role": "MEASUREMENT",
             "purpose": ("Read the operator statement that defines the "
                         "referent and states the expected value."),
             "params": {"path": os.path.join(ROOT, "references", "REF-12",
                                             "REF-12_OPERATOR_PROVENANCE.txt"),
                        "start": 0, "length": 65536},
             "timeout_seconds": 120},
            {"step_id": "stat_document", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Canonical path and size, recorded before hashing.",
             "params": {"path": REF12_DOCX}, "timeout_seconds": 120},
            {"step_id": "file_type_document", "operation": "FILE_TYPE",
             "control_role": "MEASUREMENT",
             "purpose": "Confirm the object is the kind of file it is claimed to be.",
             "params": {"path": REF12_DOCX}, "timeout_seconds": 120},
            {"step_id": "hash_method_1", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "First independent hash of the raw bytes.",
             "params": {"path": REF12_DOCX}, "timeout_seconds": 300},
            {"step_id": "hash_method_2_streaming", "operation": "COMPARE_HASHES",
             "control_role": "ORACLE",
             "purpose": ("Second independent hash by a streaming "
                         "standard-library read, compared with the first."),
             "params": {"left": REF12_DOCX, "right": REF12_DOCX,
                        "algorithms": ["sha256", "sha512"],
                        "expected_sha256": sha_of(REF12_DOCX)},
             "timeout_seconds": 300},
            {"step_id": "positive_control_known_hash",
             "operation": "SHA256_FILE", "control_role": "POSITIVE",
             "purpose": "Both methods reproduce an independently known digest.",
             "params": {"path": REF11_CONTENT}, "timeout_seconds": 120},
            {"step_id": "negative_control_two_files_differ",
             "operation": "COMPARE_HASHES", "control_role": "NEGATIVE",
             "purpose": "Two different files must hash differently.",
             "params": {"left": REF11_CONTENT, "right": REF11_OSCI,
                        "algorithms": ["sha256"]},
             "timeout_seconds": 120},
            {"step_id": "mutation_control_one_byte",
             "operation": "COMPARE_BINARY_FILES", "control_role": "MUTATION",
             "purpose": "One altered byte must be detected by both methods.",
             "params": {"left": REF12_DOCX,
                        "right": w("controls", "document_one_byte_mutated.docx")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="two independent hash computations plus a stated expected value",
                executable="/usr/bin/file for FILE_TYPE; every other step is in-process",
                references=bind([REF12_DOCX,
                                 os.path.join(ROOT, "references", "REF-12",
                                              "REF-12_MANIFEST.sha256"),
                                 os.path.join(ROOT, "references", "REF-12",
                                              "REF-12_OPERATOR_PROVENANCE.txt"),
                                 MANIFEST_JSON]),
                reference_ids=["REF-12", "REF-11"],
                limitations=[
                    "No older standalone historical SHA-256 manifest was "
                    "located. The valid expected value is the operator-supplied "
                    "source-host measurement made before the server transfer, "
                    "and it is reported as that rather than as an independent "
                    "historical record.",
                    REF11_LIMITATION],
                human_decisions=[
                    "The operator identified the referent of '376' as "
                    "376_DKB MH.docx and supplied the source-host path and the "
                    "expected pre-transfer SHA-256. That identification is "
                    "recorded in bindings/L1-A29.binding.json and is not "
                    "re-decided here."],
                independent_oracle=(
                    "Two independent hashing methods plus the operator's "
                    "stated expected value with its provenance."),
                target_identification_rule=(
                    "The referent is established from the operator's statement "
                    "before anything is hashed. No file is bound because its "
                    "name contains 376."),
                allowed_reads=["references/REF-12/", "references/REF-11-*"],
                allowed_writes=["work/L1-A29/RUN-A/", "evidence/L1-A29/RUN-A/"]),
            {"check_id": "referent_established_first",
             "question": "What does 376 refer to, and on whose statement?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "read_operator_provenance",
             "expected_exit_code": 0,
             "required_result": ("376_DKB MH.docx, on the operator's recorded "
                                 "statement, with the source-host path and the "
                                 "chain of custody as the operator gave them."),
             "why": "A hash of the wrong file is a correct measurement of nothing."},
            {"check_id": "expected_value_and_its_source",
             "question": "What is the expected value and where did it come from?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "expected_sha256": "0b8403982880761b1e2bc31d8c15b756fad0fe12259d55d1611323a4e768b3ca",
             "expected_hash_source": "OPERATOR_SUPPLIED_SOURCE_HOST_MEASUREMENT_PRE_SERVER_TRANSFER",
             "required_result": ("Both stated. A remeasurement reported without "
                                 "its expected value is a measurement, not a "
                                 "verification.")},
            {"check_id": "two_methods_agree",
             "question": "Do the two independent hash computations agree?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "hash_method_2_streaming", "expected_exit_code": 0},
            {"check_id": "positive_control",
             "question": "Do both methods reproduce a known digest?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_hash", "expected_exit_code": 0},
            {"check_id": "negative_control",
             "question": "Do both methods distinguish two files?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_two_files_differ",
             "expected_result": "DIGESTS_DIFFER",
             "expected_failure_reason": "the two inputs are different files"},
            {"check_id": "mutation_control",
             "question": "Does a one-byte change change the measurement?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_one_byte",
             "fixture": "work/L1-A29/RUN-A/controls/document_one_byte_mutated.docx",
             "fixture_construction": "a copy of the document with one byte altered",
             "proof_the_fixture_differs": "its SHA-256 differs from the original's",
             "expected_result": "DIFFERENCE_DETECTED_AT_THE_RECORDED_OFFSET",
             "zero_changed_bytes_is": "a measurement error, not a pass",
             "client_material_note": ("The document is client material. The "
                                      "mutation is performed on a sandbox copy "
                                      "under work/ and the reference copy is "
                                      "never written to.")},
        ],
    }


# ============================================================ L1-A30
def a30_run_a():
    audit, phase = "L1-A30", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Detect AppleDouble and macOS metadata entries in the archive by "
            "reading the central directory rather than a listing summary, and "
            "determine for each whether it lies inside or outside the byte "
            "range the signature covers. Which entries exist, whether they are "
            "covered, and what follows for the signed content are three "
            "separate answers and are reported as three."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The only occurrence of "
            "the string AppleDouble anywhere in PROJECT_ROOT is in "
            "S7_bestand.sh, an unrelated inventory script; it is not this "
            "audit's target and is not bound as one.\n\n"
            "ZIP_LIST reads the archive without extracting. The central "
            "directory entries are inspected directly - names, order, sizes, "
            "external attributes, and any entry a normal listing omits - "
            "because a summary can drop exactly the entries this audit is "
            "looking for. Entry names are searched for __MACOSX prefixes, "
            "._ basename prefixes, .DS_Store and Icon entries.\n\n"
            "Unicode normal form is recorded with every name comparison: an "
            "entry name may differ in normal form between the archive and the "
            "filesystem, and a comparison that does not state its form is not "
            "a comparison.\n\n"
            "The coverage question requires the signature's coverage boundary "
            "from L1-A34. Until that boundary is available, entries are "
            "reported as found and their coverage is reported as not yet "
            "determined, never as outside coverage by default.\n\n"
            "Preparation the approved phase performs: build three synthetic "
            "archives under work/L1-A30/RUN-A/controls/ with zipfile - one "
            "carrying __MACOSX and ._ entries, one carrying none, and a copy of "
            "the second with exactly one ._ entry added."),
        "target": _target(REF11_ZIP,
                          "references/manifest.json binds this archive as REF-11"),
        "steps": [
            {"step_id": "zip_list_raw", "operation": "ZIP_LIST",
             "control_role": "MEASUREMENT",
             "purpose": ("The complete stored entry list, read without "
                         "extracting."),
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "central_directory_scan", "operation": "COUNT_TEXT_MATCHES",
             "control_role": "MEASUREMENT",
             "purpose": ("Search the entry names for __MACOSX, ._ basenames, "
                         ".DS_Store and Icon entries, with the Unicode normal "
                         "form of the comparison recorded."),
             "params": {"path": REF11_ZIP,
                        "patterns": ["__MACOSX", "\\._", "\\.DS_Store", "Icon\r"],
                        "word_boundary": False,
                        "normal_form": "NFC"},
             "timeout_seconds": 300},
            {"step_id": "positive_control_archive_with_metadata",
             "operation": "ZIP_LIST", "control_role": "POSITIVE",
             "purpose": ("A synthetic archive built to contain __MACOSX and ._ "
                         "entries. The method must find them."),
             "params": {"path": w("controls", "with_appledouble.zip")},
             "timeout_seconds": 120},
            {"step_id": "negative_control_archive_without_metadata",
             "operation": "ZIP_LIST", "control_role": "NEGATIVE",
             "purpose": ("A synthetic archive built with no such entries. The "
                         "method must report none. A method that reports "
                         "metadata everywhere reports nothing."),
             "params": {"path": w("controls", "without_appledouble.zip")},
             "timeout_seconds": 120},
            {"step_id": "mutation_control_added_entry",
             "operation": "ZIP_LIST", "control_role": "MUTATION",
             "purpose": ("The same synthetic archive with a single ._ entry "
                         "added. Detection must appear; with the entry removed "
                         "again it must disappear."),
             "params": {"path": w("controls", "one_added_appledouble.zip")},
             "timeout_seconds": 120},
            {"step_id": "extract_for_listing_comparison",
             "operation": "ARCHIVE_EXTRACT_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Extract into the audit work directory only, and "
                         "compare the extracted listing with the raw listing. "
                         "A difference between them is a property of the "
                         "extraction tool and is recorded as one."),
             "params": {"archive": REF11_ZIP, "dest": w("extracted")},
             "timeout_seconds": 600},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("central-directory read with the standard library's "
                        "zipfile, independent of any extraction tool"),
                executable="/usr/bin/unzip for the sandbox extraction; the listing steps are in-process",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[
                    REF11_LIMITATION,
                    "The coverage question depends on the signature coverage "
                    "boundary established by L1-A34. Until that boundary "
                    "exists, coverage is reported as not yet determined."],
                independent_oracle=(
                    "The raw central directory read with the standard "
                    "library's zipfile, independent of any extraction tool."),
                target_identification_rule=(
                    "The archive is the operator-supplied REF-11 artefact, "
                    "digest-checked against references/manifest.json. "
                    "S7_bestand.sh mentions AppleDouble and is explicitly not "
                    "bound as a target."),
                allowed_reads=["references/REF-11-*",
                               "work/L1-A30/RUN-A/controls/"],
                allowed_writes=["work/L1-A30/RUN-A/", "evidence/L1-A30/RUN-A/"]),
            {"check_id": "entries_found",
             "question": "Which macOS metadata entries exist in the archive?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "central_directory_scan",
             "required_result": ("The complete list, from the central "
                                 "directory rather than a listing summary."),
             "normal_form_recorded": "NFC, stated with the comparison"},
            {"check_id": "coverage",
             "question": "Do those entries lie inside the signature's coverage?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "depends_on": "the coverage boundary from L1-A34",
             "required_result": ("Reported per entry. Where the boundary is "
                                 "not yet available the answer is NOT_YET_"
                                 "DETERMINED, never OUTSIDE_COVERAGE by "
                                 "default."),
             "why": "This is the decisive question and it is not answerable alone."},
            {"check_id": "three_answers_kept_apart",
             "question": "Are the three answers reported separately?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("(a) which entries exist, (b) whether they "
                                 "are covered, (c) what follows for the signed "
                                 "content - never collapsed into one "
                                 "statement.")},
            {"check_id": "positive_control",
             "question": "Does the method find entries that are there?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_archive_with_metadata",
             "expected_exit_code": 0,
             "fixture": "work/L1-A30/RUN-A/controls/with_appledouble.zip",
             "fixture_construction": ("a synthetic archive containing a "
                                      "__MACOSX/ prefix entry and a ._ "
                                      "basename entry, built with zipfile"),
             "expected_result": "BOTH_METADATA_ENTRIES_DETECTED"},
            {"check_id": "negative_control",
             "question": "Does the method report none when there are none?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_archive_without_metadata",
             "expected_exit_code": 0,
             "fixture": "work/L1-A30/RUN-A/controls/without_appledouble.zip",
             "expected_result": "ZERO_METADATA_ENTRIES_DETECTED",
             "expected_failure_reason": ("no such entry exists in this "
                                         "archive; a detection here would mean "
                                         "the matcher matches everything")},
            {"check_id": "mutation_control",
             "question": "Does adding one entry change the answer?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_added_entry",
             "fixture": "work/L1-A30/RUN-A/controls/one_added_appledouble.zip",
             "fixture_construction": ("the negative-control archive with "
                                      "exactly one ._ entry added"),
             "proof_the_fixture_differs": ("its entry count is one higher and "
                                           "its SHA-256 differs from the "
                                           "negative control's"),
             "expected_result": "EXACTLY_ONE_METADATA_ENTRY_DETECTED",
             "zero_changed_results_is": "a measurement error, not a pass"},
            {"check_id": "extraction_differences_attributed",
             "question": "Are extraction-tool artefacts attributed to the tool?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "extract_for_listing_comparison",
             "expected_exit_code": 0,
             "required_result": ("Differences between the extracted listing and "
                                 "the raw listing are recorded as properties "
                                 "of the extraction tool, not of the archive.")},
        ],
    }


# ============================================================ L1-A32
def a32_run_a():
    audit, phase = "L1-A32", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Enumerate every SignerInfo in the CMS structure, record the count "
            "explicitly before anything else, map each signer to a carried "
            "certificate, verify each signer independently, and record "
            "countersignatures and timestamp tokens as what they are rather "
            "than as signers. No aggregate is reported: a structure with three "
            "signers gets three results."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The CMS object is "
            "located in references/ as REF-11 and digest-checked against "
            "references/manifest.json.\n\n"
            "The SignerInfo count is recorded first, because it is the fact "
            "this audit exists to establish and everything else is a per-signer "
            "elaboration of it. For each: the signer identifier as issuer and "
            "serial or subject key identifier, the digest algorithm, the "
            "signature algorithm, the complete signed attribute set and the "
            "messageDigest value. The certificates carried in the structure are "
            "enumerated and each SignerInfo is mapped to one; a SignerInfo with "
            "no matching certificate is a finding and is recorded as one rather "
            "than skipped.\n\n"
            "No suppression flag is used anywhere. Any parse-only result is "
            "marked PARSE_ONLY_NOT_VERIFICATION.\n\n"
            "Preparation the approved phase performs: build a synthetic "
            "two-signer CMS structure and a one-signer structure under "
            "work/L1-A32/RUN-A/synthetic/, and a copy of the two-signer "
            "structure with the second signature corrupted."),
        "target": _target(REF11_P7S,
                          "references/manifest.json binds this CMS object as REF-11"),
        "steps": [
            {"step_id": "hash_cms", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the structure being enumerated.",
             "params": {"path": REF11_P7S}, "timeout_seconds": 120},
            {"step_id": "parse_carried_certificate",
             "operation": "OPENSSL_PARSE_CERT", "control_role": "MEASUREMENT",
             "purpose": ("Read a certificate carried in the structure, to map "
                         "signers onto certificates. "
                         "PARSE_ONLY_NOT_VERIFICATION."),
             "params": {"cert": os.path.join(
                 A31_PREP, "certs",
                 "vhn_leaf_from_sealed_p7s_parse_evidence.pem")},
             "timeout_seconds": 120},
            {"step_id": "verify_signer_1", "operation": "OPENSSL_VERIFY_CMS",
             "control_role": "MEASUREMENT",
             "purpose": ("Verify the first signer in its own right, with its "
                         "own argv, exit code and result. No aggregate."),
             "params": {"cms": REF11_P7S, "content": REF11_CONTENT,
                        "anchor": os.path.join(A31_PREP, "staged_anchors",
                                               "vhn_root_from_der.pem"),
                        "certfile": os.path.join(
                            A31_PREP, "certs",
                            "vhn_intermediate_selected_manual_pem.pem"),
                        "attime": 1772232925, "purpose": "any",
                        "out": w("outputs", "signer_1_verified.bin")},
             "timeout_seconds": 300},
            {"step_id": "positive_control_two_signers",
             "operation": "OPENSSL_VERIFY_CMS", "control_role": "POSITIVE",
             "purpose": ("A synthetic structure known to carry two valid "
                         "signers. The enumeration must find two and verify "
                         "both; finding one would mean it stops at index zero."),
             "params": {"cms": w("synthetic", "two_signer.p7s"),
                        "content": os.path.join(SYN, "content.bin"),
                        "anchor": os.path.join(SYN, "root.pem"),
                        "attime": _synthetic_validation_time(), "purpose": "any",
                        "out": w("outputs", "two_signer_positive.bin")},
             "timeout_seconds": 300},
            {"step_id": "negative_control_one_signer",
             "operation": "OPENSSL_VERIFY_CMS", "control_role": "NEGATIVE",
             "purpose": ("A synthetic structure with exactly one signer. The "
                         "method must report exactly one, not two."),
             "params": {"cms": w("synthetic", "one_signer.p7s"),
                        "content": os.path.join(SYN, "content.bin"),
                        "anchor": os.path.join(SYN, "root.pem"),
                        "attime": _synthetic_validation_time(), "purpose": "any",
                        "out": w("outputs", "one_signer_negative.bin")},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_second_signature_corrupted",
             "operation": "OPENSSL_VERIFY_CMS", "control_role": "MUTATION",
             "purpose": ("The two-signer structure with the second signature "
                         "corrupted. The first must still verify and the "
                         "second must fail. An overall success here proves the "
                         "enumeration stops at the first signer."),
             "params": {"cms": w("synthetic", "two_signer_second_corrupt.p7s"),
                        "content": os.path.join(SYN, "content.bin"),
                        "anchor": os.path.join(SYN, "root.pem"),
                        "attime": _synthetic_validation_time(), "purpose": "any",
                        "out": w("outputs", "two_signer_mutation.bin")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="per-signer enumeration and independent verification",
                executable="/usr/bin/openssl",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[
                    REF11_LIMITATION,
                    "Revocation is not assessed offline. Where a signer "
                    "verifies, that is reported together with the explicit "
                    "statement that revocation was not checked, never as a "
                    "clean verification."],
                validation_time=("1772232925 (2026-02-27T22:55:25Z) for the "
                                 "operator-supplied CMS object; the synthetic chain's "
                                 "own staged validation time for "
                                 "the synthetic signer-count controls, whose "
                                 "control CA is valid from 2026-08-26."),
                trust_mode=("-purpose any, with -no-CAfile, -no-CApath and "
                            "-no-CAstore. No suppression flag is used "
                            "anywhere; a suppression flag would make a failure "
                            "look like a success."),
                independent_oracle=(
                    "The ASN.1 structure read directly, plus synthetic "
                    "structures with a known signer count."),
                allowed_reads=["references/REF-11-*",
                               "work/L1-A31/preparation_r8_2026-08-28/"],
                allowed_writes=["work/L1-A32/RUN-A/", "evidence/L1-A32/RUN-A/"]),
            {"check_id": "signer_count",
             "question": "How many SignerInfo entries does the structure carry?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "recorded_before": "any verification is attempted",
             "required_result": ("An explicit count. This is the fact the "
                                 "audit exists to establish.")},
            {"check_id": "per_signer_results",
             "question": "What is the result for each signer, separately?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "verify_signer_1",
             "required_result": ("One argv, one exit code and one result per "
                                 "signer. The summary states how many "
                                 "verified."),
             "never_reported_as": ("an aggregate. A single overall result "
                                   "hides which signer failed."),
             "revocation": "NOT_ASSESSED_OFFLINE, stated explicitly"},
            {"check_id": "signer_to_certificate_mapping",
             "question": "Does each signer map to a carried certificate?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_carried_certificate",
             "expected_exit_code": 0,
             "required_result": ("Each mapping is recorded. A SignerInfo with "
                                 "no matching certificate is a finding.")},
            {"check_id": "countersignatures_and_timestamps",
             "question": "Are countersignatures and timestamp tokens present?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Recorded as countersignatures and timestamp "
                                 "tokens, not as signers. For each token the "
                                 "authority, the time and whether it was "
                                 "verified are recorded, and verifying the "
                                 "token is treated as a separate question from "
                                 "verifying the signature it covers.")},
            {"check_id": "positive_control",
             "question": "Does the enumeration find both signers of a two-signer structure?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_two_signers",
             "expected_exit_code": 0,
             "fixture": "work/L1-A32/RUN-A/synthetic/two_signer.p7s",
             "fixture_construction": ("a synthetic detached CMS over "
                                      "content.bin signed twice under the "
                                      "synthetic root"),
             "expected_result": "TWO_SIGNERS_FOUND_BOTH_VERIFY"},
            {"check_id": "negative_control",
             "question": "Does it report exactly one for a one-signer structure?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_one_signer",
             "expected_exit_code": 0,
             "expected_result": "EXACTLY_ONE_SIGNER_FOUND",
             "expected_failure_reason": ("no second signer exists; reporting "
                                         "two would mean the enumeration "
                                         "invents entries")},
            {"check_id": "mutation_control",
             "question": "Does a corrupted second signature surface as such?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_second_signature_corrupted",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": ("the second signature does not verify "
                                         "over the content it covers"),
             "expected_failure_reason_canonical": "CONTENT_DIGEST_FAILURE",
             "why_the_canonical_reason_matters": (
                 "A run of bytes altered at an arbitrary offset would break "
                 "the DER framing instead, and OpenSSL would report a wrong "
                 "tag from the ASN.1 decoder before checking any signature. "
                 "That failure is indistinguishable from this one by exit code "
                 "alone, which is why the reason is asserted and not just the "
                 "exit status."),
             "fixture": "work/L1-A32/RUN-A/synthetic/two_signer_second_corrupt.p7s",
             "fixture_construction": ("the two-signer structure with bytes of "
                                      "the second signature altered"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "two-signer positive fixture's"),
             "expected_result": "FIRST_SIGNER_VERIFIES_SECOND_FAILS",
             "verdict_effect": ("An overall success here would prove the "
                                "enumeration stops at index zero, which is the "
                                "defect this audit exists to detect.")},
        ],
    }


# ============================================================ L1-A33
def a33_run_a():
    audit, phase = "L1-A33", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Compare the OSCI container's declared metadata against what the "
            "container actually holds - names, timestamps, declared and actual "
            "hashes, manifests, signed artefacts, sender and recipient "
            "references and chronology - and give byte-level evidence for "
            "every contradiction. The container's own metadata is one side of "
            "each comparison and is never the arbiter of it."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The container and "
            "563203462.xml are located in references/ as REF-11 and "
            "digest-checked against references/manifest.json.\n\n"
            "The XML reader is configured before anything is read: external "
            "entities disabled, DTD processing disabled, network access "
            "disabled, XInclude disabled. The configuration is recorded in the "
            "evidence, because a parse performed without it is not usable and "
            "would have to be redone.\n\n"
            "The container's entries are listed without extracting, and the "
            "manifest is parsed so that every declared entry, with its declared "
            "hash, size and name, is on the record before any actual value is "
            "computed.\n\n"
            "Timestamps come from three sources and are kept apart throughout: "
            "the XML metadata, the archive entry headers and the filesystem. A "
            "copy operation rewrites one and not the others, and the "
            "difference is informative - merging them would destroy exactly "
            "the evidence this audit needs.\n\n"
            "Preparation the approved phase performs: a sandbox copy of one "
            "entry with a single byte altered, and a sandbox copy of the "
            "manifest with one declared hash altered, so that both sides of "
            "the comparison can be shown to be live."),
        "target": _target(REF11_OSCI,
                          "references/manifest.json binds 563203462.xml as REF-11"),
        "steps": [
            {"step_id": "hash_container_xml", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the container metadata document being parsed.",
             "params": {"path": REF11_OSCI}, "timeout_seconds": 120},
            # R8 correction. REF11_OSCI is named .xml and is not XML. Its
            # first bytes are `MIME-Version: 1.0` and its Content-Type is
            # Multipart/Related; the XML is a part inside it. The frozen plan
            # pointed XML_PARSE_SANDBOX at it directly and the parser refused
            # at line 1 column 0 -- correctly. The step is a load-bearing
            # MEASUREMENT, not a control, so its refusal was not a finding
            # about the target but a defect in the plan.
            #
            # The operation had been chosen from the file extension.
            # CLAUDE.md section 4: a filename is not evidence of content.
            #
            # The accepted reference is not altered. The intended part is
            # decoded into work/ and the parser is pointed at the decoded
            # copy. Selection is by Content-ID as well as content type, so it
            # is deterministic rather than "the first one that looked right".
            {"step_id": "extract_container_xml_part",
             "operation": "MIME_EXTRACT_XML_PART_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Decode the intended text/xml part of the MIME "
                         "entity into the writable work area, leaving the "
                         "accepted reference byte-identical."),
             "params": {"path": REF11_OSCI,
                        "out": work(audit, phase, "extracted",
                                    "REF-11-563203462.part.xml"),
                        "select_content_type": "text/xml",
                        "select_content_id": "<osci@message>",
                        "resolve_entities": False, "no_network": True},
             "timeout_seconds": 300},
            {"step_id": "parse_container_xml_safely",
             "operation": "XML_PARSE_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Parse the extracted XML part with external "
                         "entities, DTD, network and XInclude disabled, and "
                         "record the reader configuration in the evidence."),
             "params": {"path": work(audit, phase, "extracted",
                                     "REF-11-563203462.part.xml"),
                        "resolve_entities": False, "load_dtd": False,
                        "no_network": True, "xinclude": False},
             "timeout_seconds": 300},
            {"step_id": "parse_xjustiz_message",
             "operation": "XML_PARSE_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Read the message metadata carrying sender and "
                         "recipient references, under the same reader "
                         "configuration."),
             "params": {"path": REF11_XJUSTIZ,
                        "resolve_entities": False, "load_dtd": False,
                        "no_network": True, "xinclude": False},
             "timeout_seconds": 300},
            {"step_id": "list_container_entries", "operation": "ZIP_LIST",
             "control_role": "MEASUREMENT",
             "purpose": ("List the transport archive's entries and their "
                         "stored header timestamps, without extracting."),
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "declared_versus_actual",
             "operation": "COMPARE_HASHES", "control_role": "ORACLE",
             "purpose": ("Compute the actual hash of a declared entry over the "
                         "byte range the manifest states, and compare it with "
                         "the declared value. Matches and mismatches are "
                         "reported as two lists, never as a score."),
             "params": {"left": REF11_CONTENT,
                        "right": CMS_EMITTED_CONTENT,
                        "algorithms": ["sha256"],
                        "expected_sha256": sha_of(REF11_CONTENT)},
             "timeout_seconds": 300},
            {"step_id": "positive_control_agreeing_entry",
             "operation": "COMPARE_HASHES", "control_role": "POSITIVE",
             "purpose": ("An entry whose declared and actual hash agree must "
                         "be reported as agreeing."),
             "params": {"left": REF11_CONTENT,
                        "right": CMS_EMITTED_CONTENT,
                        "algorithms": ["sha256"],
                        "expected_sha256": sha_of(REF11_CONTENT)},
             "timeout_seconds": 120},
            {"step_id": "negative_control_altered_entry",
             "operation": "COMPARE_BINARY_FILES", "control_role": "NEGATIVE",
             "purpose": ("One altered byte in a sandbox copy of an entry must "
                         "be reported as a mismatch."),
             "params": {"left": REF11_CONTENT,
                        "right": w("controls", "entry_one_byte_mutated.xml")},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_altered_declaration",
             "operation": "COMPARE_BINARY_FILES", "control_role": "MUTATION",
             "purpose": ("One altered declared hash in a sandbox copy of the "
                         "manifest must be reported as a mismatch too. This "
                         "proves the declaration side of the comparison is "
                         "live and not merely echoed."),
             "params": {"left": REF11_OSCI,
                        "right": w("controls", "manifest_declared_hash_altered.xml")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("safely configured XML read plus independent hash "
                        "computation over stated byte ranges"),
                executable="none; every step is in-process",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[REF11_LIMITATION],
                independent_oracle=(
                    "The container's own bytes read with a safely configured "
                    "parser, and independent hash computation. The container's "
                    "metadata is one side of the comparison and never the "
                    "arbiter."),
                allowed_reads=["references/REF-11-*",
                               "work/L1-A33/RUN-A/extracted/",
                               # The CMS-emitted copy of the covered content,
                               # which the repaired declared-versus-actual
                               # comparison reads as its second operand. The
                               # exact file, not the directory above it.
                               "work/L1-A31/preparation_r8_2026-08-28/"
                               "outputs/vhn_verified_content.bin"],
                allowed_writes=["work/L1-A33/RUN-A/", "evidence/L1-A33/RUN-A/"],
                forbidden_operations=["NETWORK_REQUEST"],
                notes=["A parse performed without the recorded reader "
                       "configuration is not usable and is redone rather than "
                       "interpreted."]),
            {"check_id": "mime_part_extracted",
             "question": ("Was the intended XML part decoded, deterministically, "
                          "leaving the reference unchanged?"),
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "extract_container_xml_part",
             "expected_exit_code": 0,
             "expected_boolean": True,
             "measured_field": "source_unchanged",
             "required_result": ("Exactly one text/xml part with Content-ID "
                                 "<osci@message>; the outer entity's digest "
                                 "unchanged; the decoded part written below "
                                 "work/ and its digest recorded."),
             "r8_repair": ("REF-11-563203462.xml is a MIME multipart entity, "
                           "not raw XML at byte zero; XML_PARSE_SANDBOX "
                           "refused it at line 1 column 0"),
             "why_compat32": ("the entity's boundary is unquoted and contains "
                              "'/', a tspecial; email.policy.default "
                              "truncates it there, finds no part and reports "
                              "success with zero parts")},
            {"check_id": "reader_configuration_recorded",
             "question": "Was the XML reader configured and was it recorded?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "parse_container_xml_safely",
             "expected_exit_code": 0,
             "required_result": ("External entities disabled, DTD disabled, "
                                 "network disabled, XInclude disabled, all four "
                                 "recorded in the evidence.")},
            {"check_id": "declared_versus_actual",
             "question": "Does every declared hash match the actual bytes?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "declared_versus_actual",
             "required_result": ("Two lists - matches and mismatches - with the "
                                 "byte range each was computed over stated.")},
            {"check_id": "names_and_normal_form",
             "question": "Do declared names match stored names?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Compared including Unicode normal form, with "
                                 "the form used stated.")},
            {"check_id": "three_timestamp_sources",
             "question": "What do the three timestamp sources say?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "sources": ["XML metadata", "archive entry headers", "filesystem"],
             "required_result": ("Reported separately and never merged. A copy "
                                 "operation rewrites one and not the others, "
                                 "and that difference is evidence."),
             "step_id": "list_container_entries"},
            {"check_id": "chronology",
             "question": "Is any ordering impossible?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("The chronology is built from the recorded "
                                 "timestamps and any impossible ordering is "
                                 "named with both sides and their sources.")},
            {"check_id": "contradiction_form",
             "question": "How is a contradiction reported?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("Both sides, their sources, their byte-level "
                                 "values, and why they cannot both be true.")},
            {"check_id": "positive_control",
             "question": "Does the method report agreement where it exists?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_agreeing_entry",
             "expected_exit_code": 0},
            {"check_id": "negative_control",
             "question": "Does one altered content byte surface as a mismatch?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_altered_entry",
             "fixture": "work/L1-A33/RUN-A/controls/entry_one_byte_mutated.xml",
             "fixture_construction": "a copy of an entry with one byte altered",
             "proof_the_fixture_differs": "its SHA-256 differs from the original's",
             "expected_result": "MISMATCH_REPORTED",
             "expected_failure_reason": "the entry's bytes no longer match its declaration"},
            {"check_id": "mutation_control",
             "question": "Is the declaration side of the comparison live?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_altered_declaration",
             "fixture": "work/L1-A33/RUN-A/controls/manifest_declared_hash_altered.xml",
             "fixture_construction": ("a copy of the metadata document with one "
                                      "declared hash character altered"),
             "proof_the_fixture_differs": "its SHA-256 differs from the original's",
             "expected_result": "MISMATCH_REPORTED_FROM_THE_DECLARATION_SIDE",
             "zero_changed_results_is": "a measurement error, not a pass",
             "why": ("A comparison that only reacts to content changes is "
                     "reading the declaration and echoing it back.")},
        ],
    }


# ============================================================ L1-A35
def a35_run_a():
    audit, phase = "L1-A35", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Test the hypothesis that the copy operation on 17.08 caused the "
            "damage, by measuring six byte layers separately and testing each "
            "against the signature's actual cryptographic coverage boundary. "
            "The two conclusions - what the signature proves and what it does "
            "not prove - are stated separately, and the second is the "
            "substance of this audit."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The layers are "
            "enumerated in advance and kept apart throughout: (1) raw file "
            "bytes; (2) container bytes; (3) signed content bytes; (4) archive "
            "metadata - central directory, entry order, compression parameters, "
            "stored timestamps; (5) filesystem metadata - mtime, ctime, "
            "extended attributes, resource forks, quarantine attributes; (6) "
            "post-signing container additions such as AppleDouble entries.\n\n"
            "For each layer, how it is measured and what a difference in it "
            "would and would not imply is stated before any measurement is "
            "taken.\n\n"
            "The hypothesis needs a source copy and a destination copy. REF-11 "
            "supplies one copy of the mail attachment. Where the second side is "
            "absent the layer comparison for that pair is reported BLOCKED for "
            "want of the other side, and is never answered from one side "
            "alone.\n\n"
            "The coverage boundary comes from L1-A34. Without it no layer can "
            "be classified as inside or outside coverage and the audit cannot "
            "conclude; that dependency is stated rather than worked around.\n\n"
            "Preparation the approved phase performs: a byte-preserving copy "
            "and a recompressing copy of a synthetic archive, a synthetic copy "
            "with one byte altered inside the signed content, and a synthetic "
            "copy with one byte of archive metadata altered outside coverage."),
        "target": _target(REF11_ZIP,
                          "references/manifest.json binds this archive as REF-11; "
                          "it is the copy that exists"),
        "steps": [
            {"step_id": "layer_1_raw_bytes", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Layer 1: the raw file bytes as they lie.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "layer_3_signed_content", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Layer 3: the bytes the signature actually covers.",
             "params": {"path": REF11_CONTENT}, "timeout_seconds": 120},
            {"step_id": "layer_4_archive_metadata", "operation": "ZIP_LIST",
             "control_role": "MEASUREMENT",
             "purpose": ("Layer 4: central directory, entry order, compression "
                         "method and compressed size per entry, stored "
                         "timestamps."),
             "params": {"path": REF11_ZIP}, "timeout_seconds": 300},
            {"step_id": "layer_5_filesystem_metadata", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Layer 5: filesystem metadata, recorded separately.",
             "params": {"path": REF11_ZIP}, "timeout_seconds": 120},
            {"step_id": "positive_control_byte_preserving_copy",
             "operation": "COMPARE_BINARY_FILES", "control_role": "POSITIVE",
             "purpose": ("A copy made by a method known to preserve bytes must "
                         "compare equal at every layer. This proves the "
                         "comparison does not manufacture differences."),
             "params": {"left": w("controls", "synthetic_source.zip"),
                        "right": w("controls", "synthetic_copy_preserving.zip")},
             "timeout_seconds": 300},
            {"step_id": "negative_control_recompressing_copy",
             "operation": "COMPARE_BINARY_FILES", "control_role": "NEGATIVE",
             "purpose": ("A copy made by a method known to recompress must "
                         "differ at the container layer while the content "
                         "layer stays equal. This proves the layers are "
                         "genuinely separated."),
             "params": {"left": w("controls", "synthetic_source.zip"),
                        "right": w("controls", "synthetic_copy_recompressed.zip")},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_inside_coverage",
             "operation": "OPENSSL_VERIFY_CMS", "control_role": "MUTATION",
             "purpose": ("One byte altered inside the signed content: the "
                         "content layer must differ and the signature must "
                         "fail."),
             "params": {"cms": w("controls", "synthetic_detached.p7s"),
                        "content": w("controls", "content_inside_coverage_mutated.bin"),
                        "anchor": os.path.join(SYN, "root.pem"),
                        "attime": _synthetic_validation_time(), "purpose": "any",
                        "out": w("outputs", "inside_coverage_mutation.bin")},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_outside_coverage",
             "operation": "OPENSSL_VERIFY_CMS", "control_role": "MUTATION",
             "purpose": ("One byte of archive metadata altered outside "
                         "coverage: the content layer must be unchanged and "
                         "the signature must still verify. Together with the "
                         "step above this locates the coverage boundary."),
             "params": {"cms": w("controls", "synthetic_detached.p7s"),
                        "content": os.path.join(SYN, "content.bin"),
                        "anchor": os.path.join(SYN, "root.pem"),
                        "attime": _synthetic_validation_time(), "purpose": "any",
                        "out": w("outputs", "outside_coverage_mutation.bin")},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="layer-by-layer independent hashing against the coverage boundary",
                executable="/usr/bin/openssl for the coverage controls; the layer measurements are in-process",
                references=_ref11_envelope_refs(), reference_ids=["REF-11"],
                limitations=[
                    REF11_LIMITATION,
                    "REF-11 supplies one copy of the mail attachment. Where a "
                    "source-and-destination pair is required and only one side "
                    "exists, that layer comparison is BLOCKED for want of the "
                    "other side and is not answered from one side alone.",
                    "The coverage boundary is established by L1-A34. Until it "
                    "exists, no layer is classified as inside or outside "
                    "coverage."],
                validation_time=("1772232925 (2026-02-27T22:55:25Z) for the "
                                 "operator-supplied material; the synthetic chain's "
                                 "own staged validation time for "
                                 "the synthetic coverage controls, whose "
                                 "control CA is valid from 2026-08-26. A "
                                 "control evaluated outside its own "
                                 "certificate's validity would fail on the "
                                 "dates and the failure would read as a "
                                 "verification defect."),
                trust_mode="-purpose any, with every default trust source refused",
                independent_oracle=(
                    "Layer-by-layer independent hashing plus the coverage "
                    "boundary from L1-A34. The signature's verification result "
                    "is one input to the analysis and never its conclusion."),
                allowed_reads=["references/REF-11-*",
                               "work/L1-A31/preparation_r8_2026-08-28/synthetic/"],
                allowed_writes=["work/L1-A35/RUN-A/", "evidence/L1-A35/RUN-A/"]),
            {"check_id": "layers_measured_separately",
             "question": "Are all six layers measured and kept apart?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "layers": ["raw file bytes", "container bytes",
                        "signed content bytes", "archive metadata",
                        "filesystem metadata", "post-signing additions"],
             "required_result": ("A table of layer, source value, destination "
                                 "value, equal, inside coverage. Twelve values "
                                 "for a pair, not two."),
             "why": ("A single overall comparison cannot distinguish a change "
                     "that breaks the signature from one that cannot.")},
            {"check_id": "second_side_availability",
             "question": "Is there a destination copy to compare against?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Stated per layer. Where the second side is "
                                 "absent the answer is BLOCKED for want of it, "
                                 "not an inference from one side."),
             "verdict_effect": ("The hypothesis cannot be confirmed or refuted "
                                "from one side, and the audit says so rather "
                                "than choosing.")},
            {"check_id": "recompression_detection",
             "question": "Was the container recompressed?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "layer_4_archive_metadata",
             "required_result": ("Compression method and compressed size "
                                 "compared per entry. Identical content with "
                                 "different compressed sizes is recompression: "
                                 "it changes the container and leaves the "
                                 "content intact.")},
            {"check_id": "positive_control",
             "question": "Does a byte-preserving copy compare equal everywhere?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_byte_preserving_copy",
             "fixture": "work/L1-A35/RUN-A/controls/synthetic_copy_preserving.zip",
             "fixture_construction": "a byte-for-byte copy of the synthetic source archive",
             "expected_result": "EQUAL_AT_EVERY_LAYER"},
            {"check_id": "negative_control",
             "question": "Does a recompressing copy differ only at the container layer?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_recompressing_copy",
             "fixture": "work/L1-A35/RUN-A/controls/synthetic_copy_recompressed.zip",
             "fixture_construction": ("the same entries rewritten with a "
                                      "different compression setting"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "source's while every entry's "
                                           "uncompressed content hashes the same"),
             "expected_result": "CONTAINER_LAYER_DIFFERS_CONTENT_LAYER_EQUAL",
             "expected_failure_reason": "recompression rewrites the container, not the content"},
            {"check_id": "mutation_control_inside",
             "question": "Does a change inside coverage break the signature?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_inside_coverage",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": ("the content no longer digests to the "
                                         "value the signature covers"),
             "expected_failure_reason_canonical": "CONTENT_DIGEST_FAILURE",
             "fixture": "work/L1-A35/RUN-A/controls/content_inside_coverage_mutated.bin",
             "proof_the_fixture_differs": "its SHA-256 differs from the signed content's",
             "expected_result": "CONTENT_LAYER_DIFFERS_AND_SIGNATURE_FAILS"},
            {"check_id": "mutation_control_outside",
             "question": "Does a change outside coverage leave the signature intact?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_outside_coverage",
             "expected_exit_code": 0,
             "expected_result": "CONTENT_LAYER_UNCHANGED_AND_SIGNATURE_VERIFIES",
             "why": ("Together with the step above, this is the demonstration "
                     "that the coverage boundary is real and correctly "
                     "located. Either alone proves nothing about where the "
                     "boundary lies.")},
            {"check_id": "two_conclusions_stated_separately",
             "question": "What does the signature prove, and what does it not?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Two statements, explicitly separate. The "
                                 "second is the substance of this audit and is "
                                 "not left implied.")},
        ],
    }


# ============================================================ L1-A19
A19_VECTORS = os.path.join(ROOT, "corpora", "R7_REF04_IDNR_VECTORS.jsonl")
A19_VECTORS_META = os.path.join(ROOT, "corpora",
                                "R7_REF04_IDNR_VECTORS.meta.json")
A19_TARGET = proj("anonymization", "payload_scan.py")

REF03_LIMITATION = (
    "The REF-03 ISO/IEC 7064 item is an eleven-page iTeh preview containing "
    "normative pages 1-5. It establishes that MOD 11,10 is the designated "
    "hybrid system with one check digit; it does not contain clauses 9 and 10 "
    "and must not be described as the complete ISO standard. The operational "
    "calculation is taken from the official ELSTER specification and "
    "corroborated by REF-04's independent implementation.")

A19_ORACLE = (
    "The official specification of the scheme (REF-03 ELSTER) plus independent "
    "vectors derived from REF-04 plus manual computation. Never the "
    "implementation under audit: a corpus derived from the target would agree "
    "with the target by construction.")


def _a19_refs():
    return bind([
        ref("REF-03_ELSTER_Pruefung_Steueridentifikationsnummer_2026-04-15.pdf"),
        ref("REF-03_ISO_IEC_7064_2003.pdf"),
        ref("REF-03_BZSt_German_IdNr_Issuer_Specification.pdf"),
        ref("REF-03_SOURCE_MAP.txt"),
        ref("REF-04_idnr.py"),
        ref("REF-04_test_de_idnr.doctest"),
        A19_VECTORS, A19_VECTORS_META, MANIFEST_JSON])


def _a19_target():
    return {
        "path": A19_TARGET,
        "sha256": sha_of(A19_TARGET),
        "identity_evidence": (
            "bindings/L1-A19.binding.json records productive_target_sha256 for "
            "the operator's own copy; the file on this machine hashes to the "
            "same value, so the two are the same bytes. Which copy is "
            "productive is L1-A20's question and is not decided here."),
    }


def a19_run_a():
    audit, phase = "L1-A19", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "ISO/IEC 7064 MOD 11,10 correctness of the payload scanner's "
            "German tax-identifier validator, checked in Python against the "
            "official ELSTER calculation and vectors derived from REF-04, over "
            "the full 34-vector set, with the empty string and a non-string "
            "both counted as inputs, and with two sabotage controls. Check-digit "
            "correctness and structural validity are two questions and are "
            "answered separately."),
        "static_analysis": (
            "payload_scan.py is parsed with PYTHON_AST_PARSE, never imported: a "
            "top-level import executes code. _validate_steuid11 is recorded "
            "verbatim, step by step, and the pattern that feeds it is recorded "
            "with its length and boundary constructs.\n\n"
            "The scheme is identified before any test: country Germany, "
            "identifier the steuerliche Identifikationsnummer, variant ISO/IEC "
            "7064 MOD 11,10, eleven digits, check digit in position eleven, "
            "separators ' -./,' stripped before validation. Each with its "
            "source recorded.\n\n"
            "The structural repetition rule - exactly one of the first ten "
            "digits repeating, twice or three times - is part of validity and "
            "is not part of the check digit. Whether the implementation "
            "enforces it is a distinct question from whether its check digit is "
            "right, and both are answered.\n\n"
            "RUN-A computes in the generation form: fold the first ten digits, "
            "produce the eleventh, compare. RUN-B uses the verification form in "
            "another language. The two are equivalent in arithmetic and "
            "different in expression, so a defect in one does not reproduce "
            "itself in the other."),
        "target": _a19_target(),
        "steps": [
            {"step_id": "parse_target", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Parse, do not import.",
             "params": {"path": A19_TARGET}, "timeout_seconds": 120},
            {"step_id": "bind_elster_specification", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": ("Bind the official specification the calculation is "
                         "taken from, so the formula's source is on the record."),
             "params": {"path": ref(
                 "REF-03_ELSTER_Pruefung_Steueridentifikationsnummer_2026-04-15.pdf")},
             "timeout_seconds": 120},
            {"step_id": "bind_iso_preview", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": ("Bind the ISO preview, which identifies the variant "
                         "and is not the source of the calculation."),
             "params": {"path": ref("REF-03_ISO_IEC_7064_2003.pdf")},
             "timeout_seconds": 120},
            {"step_id": "run_a_validation", "operation": "AUDIT_MODULE_RUN",
             "control_role": "MEASUREMENT",
             "purpose": "The full vector set through the Python generation form.",
             "params": {"module": "automation.a19_run_a_cli",
                        "args": ["--vectors", A19_VECTORS,
                                 "--out", w("run_a_results.json")]},
             "timeout_seconds": 300},
            {"step_id": "sabotage_modulus", "operation": "AUDIT_MODULE_RUN",
             "control_role": "MUTATION",
             "purpose": ("A deliberately wrong modulus must change the "
                         "answers. A sabotage that changes nothing is a "
                         "measurement error, not a passing control."),
             "params": {"module": "automation.a19_run_a_cli",
                        "args": ["--vectors", A19_VECTORS,
                                 "--out", w("sabotage_modulus.json"),
                                 "--sabotage", "mod_11_10"]},
             "timeout_seconds": 300},
            {"step_id": "sabotage_repetition_rule",
             "operation": "AUDIT_MODULE_RUN", "control_role": "MUTATION",
             "purpose": ("A structural rule that accepts everything must "
                         "change the answers of exactly the structural "
                         "vectors. This separates the two verdict dimensions "
                         "by showing they can be broken independently."),
             "params": {"module": "automation.a19_run_a_cli",
                        "args": ["--vectors", A19_VECTORS,
                                 "--out", w("sabotage_repetition.json"),
                                 "--sabotage", "repetition"]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("Python ISO/IEC 7064 MOD 11,10 generation form over "
                        "vectors derived from REF-04"),
                executable="/usr/bin/python3 -I -B via the frozen launcher run_audit_module.py",
                references=_a19_refs(), reference_ids=["REF-03", "REF-04"],
                limitations=[REF03_LIMITATION],
                independent_oracle=A19_ORACLE,
                target_identification_rule=(
                    "The target set is re-derived rather than adopted from the "
                    "binding, and every candidate is hashed and compared "
                    "against the binding. A mismatch is "
                    "BUILD_CONTAMINATED_SOURCE_CHANGED and the run stops. "
                    "Production identity requires execution-path evidence; "
                    "filename and version suffix are excluded by rule."),
                allowed_reads=["references/REF-03*", "references/REF-04*",
                               "corpora/R7_REF04_IDNR_VECTORS.jsonl",
                               A19_TARGET],
                allowed_writes=["work/L1-A19/RUN-A/", "evidence/L1-A19/RUN-A/"],
                notes=["The vector corpus records per vector whether its "
                       "expected answer is REF-04's own or derived by a named "
                       "rule from REF-04. No expected value came from the "
                       "implementation under audit."]),
            {"check_id": "scheme_identity",
             "question": "Which scheme is the implementation supposed to compute?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "recorded_before": "any test is run",
             "required_result": ("Country, identifier type, ISO 7064 variant, "
                                 "modulus, radix, character mapping, check-digit "
                                 "position and preprocessing rules, each with "
                                 "its source. If any cannot be established: "
                                 "BLOCKED_SCHEME_IDENTITY_UNCERTAIN and stop."),
             "specification_reference": "REF-03 ELSTER section 2.2, document pages 6-8"},
            {"check_id": "vector_coverage",
             "question": "What does the corpus cover?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "run_a_validation",
             "expected_exit_code": 0,
             "vectors_in_corpus": 34,
             "expected_total_inputs_answered": 34,
             "documented_vectors": 11,
             "derived_vectors": 23,
             "empty_input_counted_as_an_input": True,
             "non_string_input_counted_as_an_input": True,
             "scopes_covered": [
                 "REF04_DOCUMENTED", "CHECK_DIGIT_PLUS_ONE",
                 "REPETITION_VIOLATED_CHECK_DIGIT_CORRECT", "WRONG_LENGTH_10",
                 "WRONG_LENGTH_12", "SEPARATORS_HYPHEN", "SEPARATORS_DOT",
                 "SEPARATORS_SLASH", "SEPARATORS_COMMA",
                 "SURROUNDING_WHITESPACE", "LEADING_TEXT", "TRAILING_TEXT",
                 "EMPTY_INPUT", "NONE_INPUT", "VERY_LONG_INPUT",
                 "ALL_IDENTICAL_DIGITS", "MAX_ALLOWED_REPETITION",
                 "CHECK_DIGIT_COMPUTES_TO_ZERO", "LEADING_ZERO",
                 "FOREIGN_SCHEME_SAME_LENGTH", "OTHER_ISO7064_VARIANT"],
             "why": ("The edge cases the specification names are each present "
                     "as their own scope, so a missing one is visible rather "
                     "than absorbed into a total.")},
            {"check_id": "two_verdict_dimensions",
             "question": "Are check-digit correctness and structural validity separated?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Reported separately. Every record carries "
                                 "structurally_valid, computed_check_digit, "
                                 "carried_check_digit and check_digit_correct, "
                                 "and the deciding rule is named."),
             "why": ("A value can fail the repetition rule while carrying a "
                     "correct check digit. Collapsing the two would report "
                     "that as a check-digit defect.")},
            {"check_id": "positive_control",
             "question": "Do known-valid identifiers validate?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "references": "REF-04 documented vectors 36574261809, 11234567890, 11123456786",
             "required_result": "All three are answered VALID."},
            {"check_id": "negative_control",
             "question": "Do identifiers with a wrong check digit fail?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "expected_result": "INVALID_CHECKSUM",
             "expected_failure_reason": ("the eleventh digit is not the one "
                                         "MOD 11,10 produces for the first ten"),
             "fixture": ("the CHECK_DIGIT_PLUS_ONE vectors, each a "
                         "documented-valid identifier with its check digit "
                         "stepped by one and its repetition structure intact")},
            {"check_id": "mutation_control_modulus",
             "question": "Does a wrong modulus change the answers?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "sabotage_modulus",
             "expected_exit_code": 0,
             "fixture": "--sabotage mod_11_10, recorded in the argv",
             "fixture_construction": ("the same single implementation with the "
                                      "modulus changed from 11 to 10; there is "
                                      "no second copy of the validator"),
             "expected_result_differs_from": "run_a_validation",
             "expected_result": "AT_LEAST_ONE_ANSWER_CHANGES",
             "zero_changed_results_is": ("a measurement error and an invalid "
                                         "control, never a pass"),
             "why": "If nothing changes, the validator is not on the measured path."},
            {"check_id": "mutation_control_repetition",
             "question": "Does neutralising the structural rule change the answers?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "sabotage_repetition_rule",
             "expected_exit_code": 0,
             "fixture": "--sabotage repetition, recorded in the argv",
             "expected_result_differs_from": "run_a_validation",
             "expected_result": "THE_STRUCTURAL_VECTORS_CHANGE_ANSWER",
             "zero_changed_results_is": "a measurement error, not a pass",
             "why": ("The two sabotages break the two dimensions "
                     "independently, which is what shows they are two.")},
        ],
    }


def a19_run_b():
    audit, phase = "L1-A19", "RUN-B"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "The same 34 inputs through an independent implementation: a Java "
            "program that uses the ISO/IEC 7064 verification form - fold all "
            "eleven digits and require the final intermediate to be 1 - and "
            "never produces a check digit at all."),
        "static_analysis": (
            "RUN-B contains no Python validation logic. automation/a19_run_b.py "
            "writes the values out, launches the Java validator in one bounded "
            "process and reads back what it said; its import list is the "
            "evidence that it does not reach a19_run_a. The Java program "
            "implements the structural repetition rule independently as well, "
            "so both dimensions are answered twice by two different code "
            "paths.\n\n"
            "A non-string input has no representation on the Java boundary. It "
            "is answered NOT_A_STRING before the boundary and recorded as "
            "decided there, so RUN-A and RUN-B answer the same 34 inputs and "
            "the comparison has something to compare. An input that quietly "
            "disappeared would make the two runs incomparable while both "
            "looked complete."),
        "target": _a19_target(),
        "steps": [
            {"step_id": "run_b_validation", "operation": "AUDIT_MODULE_RUN",
             "control_role": "MEASUREMENT",
             "purpose": ("The full vector set through the Java verification "
                         "form."),
             "params": {"module": "automation.a19_run_b_cli",
                        "args": ["--vectors", A19_VECTORS,
                                 "--work-dir", w(),
                                 "--out", w("run_b_results.json")]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("Java ISO/IEC 7064 MOD 11,10 verification form: fold "
                        "all eleven digits, require the final intermediate to "
                        "be 1"),
                executable="/usr/bin/java, class WpnoIdnrValidateRunB under tools/a19_run_b/classes",
                references=_a19_refs(), reference_ids=["REF-03", "REF-04"],
                limitations=[REF03_LIMITATION],
                independent_oracle=A19_ORACLE,
                allowed_reads=["corpora/R7_REF04_IDNR_VECTORS.jsonl",
                               "tools/a19_run_b/classes/"],
                allowed_writes=["work/L1-A19/RUN-B/", "evidence/L1-A19/RUN-B/"],
                notes=["RUN-B reads nothing belonging to the other run: "
                       "not its work area, not its evidence, not its results. "
                       "The step list is the evidence - the only directory any "
                       "step names is this phase's own.",
                       "This plan deliberately spells out no path belonging to "
                       "the other run, not even to deny reading it. The "
                       "independent pre-freeze verification searched the plan "
                       "document for such a path and matched the sentence that "
                       "promised the path was not used, which is the same "
                       "mistake as a grep that finds its own invocation. A "
                       "claim that cannot be told apart from what it denies is "
                       "worth removing."]),
            {"check_id": "independence",
             "question": "Is RUN-B independent of RUN-A?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "run_b_validation",
             "expected_exit_code": 0,
             "independence": ("a different language, a different runtime and "
                              "the opposite formulation of the same scheme: "
                              "RUN-A produces a check digit and compares it, "
                              "RUN-B produces none and tests a fold invariant"),
             "isolation": ("automation/a19_run_b.py imports hashing, "
                           "path_policy and policy only. It does not import "
                           "a19_run_a and reads no RUN-A directory."),
             "why": ("Two runs that share an implementation agree for reasons "
                     "that have nothing to do with the answer being right.")},
            {"check_id": "same_inputs_answered",
             "question": "Does RUN-B answer the same inputs as RUN-A?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "expected_total_inputs_answered": 34,
             "inputs_passed_to_java": 33,
             "inputs_decided_before_the_boundary": 1,
             "required_result": ("34 answers. The non-string input is answered "
                                 "before the Java boundary and recorded as "
                                 "decided there rather than dropped."),
             "why": ("A comparison over different input sets compares "
                     "nothing, and a dropped input makes both runs look "
                     "complete while they are not.")},
            {"check_id": "no_suppression",
             "question": "Is any answer suppressed or defaulted?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("Every input receives an explicit category. "
                                 "The Java program writes one result line per "
                                 "input and the bridge refuses a result count "
                                 "that differs from the input count.")},
        ],
    }


def a19_comparison():
    return comparison_plan(
        "L1-A19", _a19_target(),
        run_a_method=("Python generation form - fold the first ten digits, "
                      "produce the eleventh, compare"),
        run_b_method=("Java verification form - fold all eleven digits, "
                      "require the final intermediate to be 1"),
        what_is_compared=("the per-input category assigned by each run over "
                          "the same 34 vectors, and each run's agreement with "
                          "the REF-04-derived reference answer"),
        references=_a19_refs(), reference_ids=["REF-03", "REF-04"],
        limitations=[REF03_LIMITATION])


# ================================================== static enumeration group
#
# These audits answer an identity or chain question and run nothing productive.
# Their operations are read-only and mostly in-process, which is why their
# plans are short: the substance is what is searched and what counts as
# evidence, not how much is executed.

WORD_BOUNDARY_NOTE = (
    "Every textual search is anchored with a word boundary. CLAUDE.md section "
    "10 records the cost of omitting one: a bare *bea* matched "
    "Projektbeauftragung, Beanstandung and Bearbeitung - twelve hits, none "
    "real. A search whose boundary handling is not stated is not a search.")

EXECUTION_PATH_RULE = (
    "Production identity requires execution-path evidence: an import, an "
    "invocation in a script, a container command, a workflow node or a "
    "scheduler entry. Filename, version suffix, modification time, file size, "
    "documentation, comments and proximity to another file are excluded by "
    "rule. If production identity cannot be proven the answer is that it "
    "cannot be proven from this machine; no most-likely candidate is "
    "nominated.")


def _search_step(step_id, purpose, patterns, control_role="MEASUREMENT",
                 root=None, word_boundary=True):
    return {
        "step_id": step_id, "operation": "COUNT_TEXT_MATCHES",
        "control_role": control_role, "purpose": purpose,
        "params": {"root": root or proj(), "patterns": list(patterns),
                   "word_boundary": word_boundary, "normal_form": "NFC",
                   "include_globs": ["*.py", "*.sh", "*.yml", "*.yaml",
                                     "*.json", "*.toml", "*.cfg", "*.ini",
                                     "*.plist", "Dockerfile*"]},
        "timeout_seconds": 600}


def a03_run_a():
    audit, phase = "L1-A03", "RUN-A"
    versions = [proj("authoring", "AP16_export_with_toc.py"),
                proj("authoring", "AP16_export_with_toc_v2.py"),
                proj("authoring", "AP16_export_with_toc_v4.py")]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Enumerate every version of the TOC exporter that exists on this "
            "machine, hash each, and prove from execution-path evidence which "
            "one is productive - or prove that it cannot be proven. Nothing is "
            "executed: no exporter needs to run to answer an identity "
            "question, and running one would not answer it."),
        "static_analysis": (
            "LIST_DIRECTORY over authoring/ identifies every file whose name "
            "contains export_with_toc. Each is hashed and compared against the "
            "binding; a mismatch means the tree changed since the package was "
            "built and the run stops with "
            "BUILD_CONTAMINATED_SOURCE_CHANGED.\n\n"
            "Three versions exist here: AP16_export_with_toc.py, "
            "AP16_export_with_toc_v2.py and AP16_export_with_toc_v4.py. "
            "Whether a v3 ever existed is answered from the Discovery hash "
            "inventory and from read-only git history over authoring/, and the "
            "places searched are recorded as evidence whether or not they "
            "yielded anything.\n\n"
            "Each version is AST-parsed and their function sets, arguments, "
            "constants and output paths are diffed. " + EXECUTION_PATH_RULE),
        "target": {
            "path": versions[2],
            "sha256": sha_of(versions[2]),
            "identity_evidence": (
                "The highest-numbered version present, bound as the "
                "enumeration's anchor and explicitly NOT as the productive "
                "version. Which version is productive is this audit's "
                "question and a version suffix is excluded by rule from "
                "answering it."),
        },
        "steps": [
            {"step_id": "enumerate_authoring", "operation": "LIST_DIRECTORY",
             "control_role": "MEASUREMENT",
             "purpose": "Re-derive the version set rather than adopt the binding's list.",
             "params": {"path": proj("authoring"),
                        "name_contains": "export_with_toc"},
             "timeout_seconds": 120},
            {"step_id": "hash_v1", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT", "purpose": "Bind version 1.",
             "params": {"path": versions[0]}, "timeout_seconds": 120},
            {"step_id": "hash_v2", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT", "purpose": "Bind version 2.",
             "params": {"path": versions[1]}, "timeout_seconds": 120},
            {"step_id": "hash_v4", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT", "purpose": "Bind version 4.",
             "params": {"path": versions[2]}, "timeout_seconds": 120},
            {"step_id": "ast_v1", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Function set, arguments, constants and output paths.",
             "params": {"path": versions[0]}, "timeout_seconds": 120},
            {"step_id": "ast_v2", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT", "purpose": "The same, for version 2.",
             "params": {"path": versions[1]}, "timeout_seconds": 120},
            {"step_id": "ast_v4", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT", "purpose": "The same, for version 4.",
             "params": {"path": versions[2]}, "timeout_seconds": 120},
            _search_step("search_callers",
                         ("Search the whole project for imports and textual "
                          "references to each version, across source, shell "
                          "scripts, compose files, Dockerfiles, workflow JSON, "
                          "MCP configuration and scheduler definitions."),
                         ["AP16_export_with_toc", "export_with_toc"]),
            _search_step("positive_control_unique_string",
                         ("A string known to exist in exactly one version must "
                          "be found there and nowhere else. This proves the "
                          "search method works before absence is interpreted."),
                         ["AP16_export_with_toc_v2"], control_role="POSITIVE"),
            _search_step("negative_control_absent_identifier",
                         ("A deliberately absent identifier must return zero "
                          "hits. This proves the search is not matching "
                          "everything."),
                         ["AP16_export_with_toc_v3_definitely_absent"],
                         control_role="NEGATIVE"),
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="enumeration, hashing, AST diff and execution-path search",
                executable="none; every step is in-process",
                independent_oracle=(
                    "Execution-path evidence only. Absence of every form of it "
                    "is itself the oracle's answer, and that answer is "
                    "'unprovable from this machine'."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[proj("authoring"), proj()],
                allowed_writes=["work/L1-A03/RUN-A/", "evidence/L1-A03/RUN-A/"],
                notes=[WORD_BOUNDARY_NOTE,
                       "No exporter is executed. Execution would produce a "
                       "document and still not say which version is "
                       "productive."]),
            {"check_id": "enumeration_versus_binding",
             "question": "Does the re-derived version set match the binding's?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "enumerate_authoring",
             "required_result": ("A file in one and not the other is a finding "
                                 "before anything else proceeds."),
             "versions_expected_here": 3},
            {"check_id": "did_v3_ever_exist",
             "question": "Did AP16_export_with_toc_v3.py ever exist?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "method": ("the Discovery hash inventory and read-only git "
                        "history over authoring/"),
             "required_result": ("Answered from the places searched, with "
                                 "every place recorded whether or not it "
                                 "yielded anything. 'Not found' is recorded as "
                                 "not found, never as 'does not exist'.")},
            {"check_id": "productive_version",
             "question": "Which version is productive?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "search_callers",
             "required_result": ("Proven from execution-path evidence, or "
                                 "reported as unprovable from this machine. "
                                 "No most-likely candidate is nominated."),
             "excluded_by_rule": ["filename", "version suffix", "mtime",
                                  "file size", "documentation", "comments",
                                  "proximity"]},
            {"check_id": "positive_control",
             "question": "Does the search find a string that is there?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_unique_string",
             "expected_result": "FOUND_IN_EXACTLY_THE_EXPECTED_PLACES",
             "why": "Absence is only a result once the search is shown to work."},
            {"check_id": "negative_control",
             "question": "Does the search return zero for an absent identifier?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_absent_identifier",
             "expected_result": "ZERO_HITS",
             "expected_failure_reason": ("the identifier does not occur "
                                         "anywhere in the tree")},
            {"check_id": "mutation_control",
             "question": "Is a mutation control applicable?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": "NOT_APPLICABLE",
             "reason": ("Nothing is being detected. The audit enumerates and "
                        "attributes; there is no detector whose sensitivity a "
                        "mutation would demonstrate. Recorded rather than "
                        "omitted, as the specification requires.")},
        ],
    }


def a10_run_a():
    audit, phase = "L1-A10", "RUN-A"
    checker = proj("authoring", "AP18_referenzpruefung.py")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Locate every copy of the reference checker, hash each, identify "
            "the repository state, distinguish backup, golden and test copies "
            "from productive ones, and prove the productive copy from "
            "execution evidence - or record that no caller exists in-tree and "
            "that production identity is therefore unprovable from this "
            "machine."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. LIST_DIRECTORY and a "
            "boundary-anchored textual search enumerate every file whose name "
            "contains AP18_referenzpruefung, and each is hashed. A test copy "
            "and a checker are distinguished by what they contain, not by "
            "their names.\n\n" + EXECUTION_PATH_RULE + "\n\n"
            "A container-side copy may only be hashed from an operator-produced "
            "export. The Docker socket is forbidden and no container command "
            "is run."),
        "target": {
            "path": checker, "sha256": sha_of(checker),
            "identity_evidence": (
                "bindings/L1-A10.binding.json records this path as a candidate "
                "with this digest. It is bound as the enumeration's anchor, "
                "not as the proven productive copy - which is the audit's "
                "question."),
        },
        "steps": [
            {"step_id": "enumerate_copies", "operation": "LIST_DIRECTORY",
             "control_role": "MEASUREMENT",
             "purpose": "Re-derive the copy set rather than adopt the binding's.",
             "params": {"path": proj("authoring"),
                        "name_contains": "AP18_referenzpruefung"},
             "timeout_seconds": 120},
            {"step_id": "hash_checker", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT", "purpose": "Bind the checker copy.",
             "params": {"path": checker}, "timeout_seconds": 120},
            {"step_id": "hash_test_copy", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the test copy, which is a different thing.",
             "params": {"path": proj("authoring",
                                     "AP18_referenzpruefung_test.py")},
             "timeout_seconds": 120},
            {"step_id": "ast_checker", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Parse, do not import; record what the checker defines.",
             "params": {"path": checker}, "timeout_seconds": 120},
            _search_step("search_callers",
                         ("Search for an import or invocation of the checker "
                          "anywhere in the project."),
                         ["AP18_referenzpruefung", "referenzpruefung"]),
            _search_step("positive_control_unique_string",
                         ("A string unique to the checker must be found in the "
                          "checker and nowhere unexpected."),
                         ["AP18_referenzpruefung"], control_role="POSITIVE"),
            _search_step("negative_control_absent_identifier",
                         "An absent identifier must return zero hits.",
                         ["AP18_referenzpruefung_no_such_symbol"],
                         control_role="NEGATIVE"),
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="enumeration, hashing and execution-path search",
                executable="none; every step is in-process",
                independent_oracle=(
                    "Execution-path evidence: import, invocation, container "
                    "command, workflow node, scheduler entry. Filename and "
                    "mtime are excluded by rule."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[proj("authoring"), proj()],
                allowed_writes=["work/L1-A10/RUN-A/", "evidence/L1-A10/RUN-A/"],
                forbidden_operations=["DOCKER_SOCKET_ACCESS", "DOCKER_EXEC",
                                      "DOCKER_RUN"],
                notes=[WORD_BOUNDARY_NOTE,
                       "A container copy's hash may come only from an "
                       "operator-produced export."]),
            {"check_id": "copies_enumerated",
             "question": "Which copies exist, and what is each?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "enumerate_copies",
             "required_result": ("Every copy hashed, and backup, golden and "
                                 "test copies distinguished from productive "
                                 "ones by content rather than by name.")},
            {"check_id": "productive_copy",
             "question": "Which copy is productive?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "search_callers",
             "known_difficulty": ("The binding records that no caller exists "
                                  "in-tree, so this may be unprovable from "
                                  "this machine."),
             "required_result": ("Proven from execution evidence or reported "
                                 "unprovable. Not nominated.")},
            {"check_id": "positive_control",
             "question": "Does the search find a string that is there?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_unique_string",
             "expected_result": "FOUND_IN_THE_EXPECTED_FILE"},
            {"check_id": "negative_control",
             "question": "Does an absent identifier return zero?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_absent_identifier",
             "expected_result": "ZERO_HITS",
             "expected_failure_reason": "the identifier does not occur in the tree"},
            {"check_id": "mutation_control",
             "question": "Is a mutation control applicable?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": "NOT_APPLICABLE",
             "reason": ("Nothing is being detected; the audit establishes "
                        "identity. Recorded rather than omitted.")},
        ],
    }


def a17_run_a():
    audit, phase = "L1-A17", "RUN-A"
    filt = proj("ap18", "AP18_eingangsfilter.py")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Establish the complete chain from production entrypoint through "
            "caller, gateway or orchestrator, into the input filter and on to "
            "the downstream processor - or establish that the filter is not on "
            "that chain, showing where the chain breaks. This is a static "
            "question and no part of the production system is executed."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The filter, the gateway "
            "and the orchestrator loop are AST-parsed and the call graph is "
            "derived from the parse, then cross-checked by an independent "
            "boundary-anchored textual search over source, shell scripts, "
            "compose files, Dockerfiles, workflow JSON, MCP configuration and "
            "scheduler definitions.\n\n"
            "Documentation claiming the filter is on the path is not evidence "
            "and is not counted as a link.\n\n"
            "REF-14 supplies the operator-produced production configuration "
            "and crosswalk, and is read as evidence of what the production "
            "host holds. It is redacted operator material: it establishes "
            "configuration, not runtime behaviour."),
        "target": {
            "path": filt, "sha256": sha_of(filt),
            "identity_evidence": (
                "bindings/L1-A17.binding.json records this path with this "
                "digest and REF-14 records the production-side file manifest; "
                "the two agree on the file's identity."),
        },
        "steps": [
            {"step_id": "ast_filter", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Parse the filter; record its entry points.",
             "params": {"path": filt}, "timeout_seconds": 120},
            {"step_id": "ast_gateway", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Parse the gateway; record whether it reaches the filter.",
             "params": {"path": proj("gateway", "WPNO_gateway.py")},
             "timeout_seconds": 120},
            {"step_id": "ast_orchestrator", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Parse the orchestrator loop; record the same.",
             "params": {"path": proj("orchestrator", "ap12_tool_loop.py")},
             "timeout_seconds": 120},
            {"step_id": "read_production_crosswalk",
             "operation": "PARSE_JSON_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Read the operator-produced production crosswalk as "
                         "configuration evidence, not as runtime evidence."),
             "params": {"path": ref("REF-14_production_crosswalk.json")},
             "timeout_seconds": 120},
            _search_step("search_invocations",
                         ("Independent textual cross-check of the AST-derived "
                          "call graph."),
                         ["AP18_eingangsfilter", "eingangsfilter"]),
            {"step_id": "import_prior_check_database",
             "operation": "DATABASE_EVIDENCE_IMPORT",
             "control_role": "MEASUREMENT",
             "purpose": ("Import an operator-produced export of the prior-check "
                         "database, if one is supplied. It is evidence that the "
                         "filter ran at some past time, which is not the same "
                         "as being on the current path."),
             "params": {"export": ref("REF-14_current_server_file_manifest.json"),
                        "no_connection": True},
             "timeout_seconds": 300},
            _search_step("positive_control_known_invocation",
                         ("A component with a known caller must be located by "
                          "this method. This proves that absence is a result "
                          "rather than a search failure."),
                         ["payload_scan"], control_role="POSITIVE"),
            _search_step("negative_control_absent_identifier",
                         "An identifier that certainly does not exist must return zero.",
                         ["AP18_eingangsfilter_no_such_entrypoint"],
                         control_role="NEGATIVE"),
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="AST call graph cross-checked by independent textual search",
                executable="none; every step is in-process",
                references=bind([ref("REF-14_production_crosswalk.json"),
                                 ref("REF-14_current_server_file_manifest.json"),
                                 ref("REF-14_MANIFEST.sha256"), MANIFEST_JSON]),
                reference_ids=["REF-14"],
                limitations=[
                    "REF-14 is redacted operator-produced material. It "
                    "establishes what the production host's configuration "
                    "holds; it does not establish runtime behaviour, and a "
                    "configuration that names the filter is not evidence that "
                    "the filter ran.",
                    "A prior-check database records that the filter ran at "
                    "some past time. That is not evidence that it is on the "
                    "current path, and the two are never merged."],
                independent_oracle=(
                    "The call graph derived by AST parse plus the "
                    "configuration files, cross-checked by an independent "
                    "textual search. Documentation claiming the filter is on "
                    "the path is not evidence."),
                target_identification_rule=EXECUTION_PATH_RULE,
                # R8 repair. The envelope declared three subdirectories
                # while three of this phase's steps scan PROJECT_ROOT. The
                # specification requires that scan: "Search for every
                # reference to AP18_eingangsfilter across source, shell,
                # compose, Dockerfile, workflow JSON, MCP configuration and
                # LaunchAgent plists", and "Record the search set
                # exhaustively, including every location searched and found
                # empty, so absence is documented rather than assumed."
                # Absence cannot be documented by searching three
                # subdirectories, so the envelope was under-declared rather
                # than the steps over-reaching. L1-A03, L1-A10 and L1-A26
                # already declare the project root for the same reason.
                allowed_reads=[PROJECT_ROOT, proj("ap18"), proj("gateway"),
                               proj("orchestrator"), "references/REF-14_*"],
                allowed_writes=["work/L1-A17/RUN-A/", "evidence/L1-A17/RUN-A/"],
                forbidden_operations=["DATABASE_CONNECTION", "SERVICE_MUTATION",
                                      "DOCKER_EXEC"],
                notes=[WORD_BOUNDARY_NOTE,
                       "No part of the production system is executed."]),
            {"check_id": "chain_in_required_form",
             "question": "What is the chain, link by link?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_form": ("production entrypoint -> caller -> gateway or "
                               "orchestrator -> input filter -> downstream "
                               "processor"),
             "required_result": ("Every link named with its evidence. If a "
                                 "link is missing, the chain is shown breaking "
                                 "at the exact point rather than summarised as "
                                 "incomplete.")},
            {"check_id": "database_evidence_scope",
             "question": "What does a prior-check record establish?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "import_prior_check_database",
             "required_result": ("That the filter ran at some past time. It is "
                                 "never reported as evidence of the current "
                                 "path."),
             "never_reported_as": "proof that the filter is on the current chain"},
            {"check_id": "positive_control",
             "question": "Can the method find an invocation that exists?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_invocation",
             "expected_result": "AT_LEAST_ONE_INVOCATION_LOCATED",
             "why": "Absence is only a result once the search is shown to work."},
            {"check_id": "negative_control",
             "question": "Does an absent identifier return zero?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_absent_identifier",
             "expected_result": "ZERO_HITS",
             "expected_failure_reason": "the identifier does not occur in the tree"},
            {"check_id": "mutation_control",
             "question": "Is a mutation control applicable?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": "NOT_APPLICABLE",
             "reason": ("A static chain analysis detects nothing at runtime, "
                        "so there is no detector to perturb. Recorded rather "
                        "than omitted.")},
        ],
    }


def a20_run_a():
    audit, phase = "L1-A20", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    copies = [proj("anonymization", "payload_scan.py"),
              proj("docker", "litellm", "payload_scan.py"),
              proj("anonymization", "golden", "payload_scan.py"),
              proj("anonymization", "payload_scan.py.ALT.2026-08-05.bak"),
              proj("docker", "litellm", "payload_scan.py.ALT.2026-08-05.bak"),
              proj("docs", "Test_07.28.26", "AP-03", "logs",
                   "payload_scan.py.before_F-AP03")]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Enumerate every payload_scan copy that actually exists and "
            "compare them at each named level - raw hash, byte equality, "
            "normalised source, AST, functions, regexes, constants, validation "
            "rules, error handling, control flow and production status - "
            "reporting the level for every equality or inequality claim. "
            "Nothing is executed: this is a comparison and it is performed "
            "statically."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. Six copies exist here: "
            "the anonymization copy, the docker/litellm copy, the golden copy, "
            "two .ALT.2026-08-05.bak copies and one pre-fix copy under docs/. "
            "The set is re-derived rather than adopted, and each copy is "
            "hashed.\n\n"
            "'Equal' is meaningless without a level, so every claim carries "
            "one. Two files can be unequal at the raw level and equal at the "
            "AST level, which is exactly what a comment-only difference looks "
            "like - and the mutation control below demonstrates that "
            "distinction rather than asserting it.\n\n"
            "CLAUDE.md section 10 records the same file in four places as the "
            "cause rather than the inconvenience: one copy was corrected and "
            "the others stayed quietly old. This audit measures that "
            "condition.\n\n"
            "A container-side copy may only be hashed from an operator-produced "
            "export. The Docker socket is forbidden.\n\n"
            "Preparation the approved phase performs: copy one file into "
            "work/L1-A20/RUN-A/controls/ and change a single comment, "
            "recording both digests."),
        "target": {
            "path": copies[0], "sha256": sha_of(copies[0]),
            "identity_evidence": (
                "bindings/L1-A20.binding.json records this path with this "
                "digest. It anchors the comparison; which copy is productive "
                "is part of what this audit reports and is not assumed by "
                "binding one."),
        },
        "steps": (
            [{"step_id": "enumerate_copies", "operation": "LIST_DIRECTORY",
              "control_role": "MEASUREMENT",
              "purpose": "Re-derive the copy set rather than adopt the binding's.",
              "params": {"path": proj(), "name_contains": "payload_scan",
                         "recursive": True},
              "timeout_seconds": 300}]
            + [{"step_id": "hash_copy_%d" % (i + 1), "operation": "SHA256_FILE",
                "control_role": "MEASUREMENT",
                "purpose": "Raw-level identity of copy %d." % (i + 1),
                "params": {"path": p}, "timeout_seconds": 120}
               for i, p in enumerate(copies)]
            + [{"step_id": "ast_copy_%d" % (i + 1),
                "operation": "PYTHON_AST_PARSE", "control_role": "MEASUREMENT",
                "purpose": ("AST level of copy %d: functions, regexes, "
                            "constants, validation rules, error handling and "
                            "control flow." % (i + 1)),
                "params": {"path": p}, "timeout_seconds": 120}
               for i, p in enumerate(copies)]
            + [
                {"step_id": "import_container_copy_metadata",
                 "operation": "DOCKER_METADATA_IMPORT",
                 "control_role": "MEASUREMENT",
                 "purpose": ("Container-side copy identity from the "
                             "operator-produced export. The Docker socket is "
                             "never touched."),
                 "params": {"export": ref("REF-13_CONTAINER_INDEX.json"),
                            "no_socket": True},
                 "timeout_seconds": 300},
                {"step_id": "positive_control_identical_pair",
                 "operation": "COMPARE_BINARY_FILES", "control_role": "POSITIVE",
                 "purpose": ("Two files known to be byte-identical must compare "
                             "equal at every level. This proves the comparison "
                             "chain works."),
                 "params": {"left": copies[0],
                            "right": w("controls", "identical_copy.py")},
                 "timeout_seconds": 300},
                {"step_id": "negative_control_differing_pair",
                 "operation": "COMPARE_BINARY_FILES", "control_role": "NEGATIVE",
                 "purpose": ("Two files known to differ must compare unequal at "
                             "the raw level. This proves the comparison is not "
                             "reporting equality indiscriminately."),
                 "params": {"left": copies[0], "right": copies[2]},
                 "timeout_seconds": 300},
                {"step_id": "mutation_control_comment_only",
                 "operation": "PYTHON_AST_PARSE", "control_role": "MUTATION",
                 "purpose": ("A sandbox copy differing only in one comment: raw "
                             "must differ, normalised source must be equal and "
                             "AST must be equal. This proves each level "
                             "measures what it claims."),
                 "params": {"path": w("controls", "comment_changed.py")},
                 "timeout_seconds": 120},
            ]),
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="multi-level static comparison of every existing copy",
                executable="none; every step is in-process",
                references=bind([ref("REF-13_CONTAINER_INDEX.json"),
                                 MANIFEST_JSON]),
                reference_ids=["REF-13"],
                limitations=[
                    "The container-side copy's identity comes from an "
                    "operator-produced export. It describes the image as "
                    "exported; it is not a live read of a running container.",
                    "Production status is an execution-path question. Where no "
                    "execution-path evidence exists for a copy, its production "
                    "status is reported as unproven."],
                independent_oracle=(
                    "SHA-256 and the standard library's ast module, both "
                    "independent of the code under test."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[proj(), "references/REF-13_*"],
                allowed_writes=["work/L1-A20/RUN-A/", "evidence/L1-A20/RUN-A/"],
                forbidden_operations=["DOCKER_SOCKET_ACCESS", "DOCKER_EXEC",
                                      "DOCKER_RUN", "DOCKER_BUILD"],
                notes=["Every equality or inequality claim names the level it "
                       "holds at. A claim without a level is not a result."]),
            {"check_id": "copies_enumerated",
             "question": "How many copies exist, and where?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "enumerate_copies",
             "copies_expected_here": 6,
             "required_result": ("Every copy that exists, re-derived rather "
                                 "than adopted. A copy in one set and not the "
                                 "other is a finding.")},
            {"check_id": "levels_reported",
             "question": "At which level does each equality claim hold?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "levels": ["raw hash", "byte equality", "normalised source", "AST",
                        "functions", "regexes", "constants", "validation rules",
                        "error handling", "control flow", "production status"],
             "required_result": "A level accompanies every claim."},
            {"check_id": "positive_control",
             "question": "Do byte-identical files compare equal everywhere?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_identical_pair",
             "fixture": "work/L1-A20/RUN-A/controls/identical_copy.py",
             "fixture_construction": "a byte-for-byte copy of the anchor copy",
             "expected_result": "EQUAL_AT_EVERY_LEVEL"},
            {"check_id": "negative_control",
             "question": "Do differing files compare unequal at the raw level?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_differing_pair",
             "expected_result": "UNEQUAL_AT_THE_RAW_LEVEL",
             "expected_failure_reason": "the two copies are different files"},
            {"check_id": "mutation_control",
             "question": "Does a comment-only change separate the levels?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_comment_only",
             "fixture": "work/L1-A20/RUN-A/controls/comment_changed.py",
             "fixture_construction": ("a copy of the anchor with exactly one "
                                      "comment altered and no other change"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "anchor's while its AST dump is "
                                           "identical"),
             "expected_result": ("RAW_DIFFERS_NORMALISED_EQUAL_AST_EQUAL"),
             "zero_changed_results_is": "a measurement error, not a pass"},
        ],
    }


def a21_run_a():
    audit, phase = "L1-A21", "RUN-A"
    compose = proj("docker", "litellm", "docker-compose.yml")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Determine which payload scanner copy is inside the productive "
            "image or container, with image ID, digest, creation timestamps, "
            "mounts, entrypoint, command, build-context evidence and container "
            "mapping, and determine whether the image was rebuilt after the "
            "04.08 change. Every answer comes from the operator-produced "
            "export; the Docker socket is never touched and no container "
            "command is run."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported and no container "
            "command is executed. The compose file and the Dockerfile are read "
            "as declarations of intent. They state what was meant to be built "
            "and mounted; only the export describes what exists, and where the "
            "two differ the difference is the finding.\n\n"
            "REF-13 supplies the operator-produced Docker metadata export, "
            "redacted before intake. Its redaction manifest records that "
            "structural evidence - image IDs and digests, timestamps, mount "
            "destinations, source paths, entrypoint, command, working "
            "directory, labels - is retained and that only secret-bearing "
            "values were replaced by category placeholders. The structural "
            "questions this audit asks are therefore answerable from it.\n\n"
            "The image creation timestamp is compared against 2026-08-04, the "
            "date of the change in question. An image created before that date "
            "cannot contain the change, whatever the source tree now says."),
        "target": {
            "path": compose, "sha256": sha_of(compose),
            "identity_evidence": (
                "bindings/L1-A21.binding.json records this path as a "
                "candidate. It is bound as the declaration side of the "
                "comparison; the export is the other side and the export is "
                "what describes reality."),
        },
        "steps": [
            {"step_id": "read_compose_declaration",
             "operation": "READ_FILE_RANGE", "control_role": "MEASUREMENT",
             "purpose": "The declared services, mounts, entrypoint and command.",
             "params": {"path": compose, "start": 0, "length": 262144},
             "timeout_seconds": 120},
            {"step_id": "read_dockerfile_declaration",
             "operation": "READ_FILE_RANGE", "control_role": "MEASUREMENT",
             "purpose": "The declared build context and copy instructions.",
             "params": {"path": proj("docker", "litellm", "Dockerfile"),
                        "start": 0, "length": 262144},
             "timeout_seconds": 120},
            {"step_id": "import_image_metadata",
             "operation": "DOCKER_METADATA_IMPORT", "control_role": "MEASUREMENT",
             "purpose": ("Image ID, digest and creation timestamp from the "
                         "operator-produced export."),
             "params": {"export": ref("REF-13_image_wpno_litellm.json"),
                        "no_socket": True},
             "timeout_seconds": 300},
            {"step_id": "import_container_metadata",
             "operation": "DOCKER_METADATA_IMPORT", "control_role": "MEASUREMENT",
             "purpose": ("Container creation timestamp, state, effective "
                         "entrypoint and command."),
             "params": {"export": ref("REF-13_container_wpno_litellm.json"),
                        "no_socket": True},
             "timeout_seconds": 300},
            {"step_id": "import_attached_mounts",
             "operation": "DOCKER_METADATA_IMPORT", "control_role": "MEASUREMENT",
             "purpose": ("Mounts as actually attached, for comparison against "
                         "the compose declaration."),
             "params": {"export": ref("REF-13_mounts_wpno_litellm.json"),
                        "no_socket": True},
             "timeout_seconds": 300},
            {"step_id": "import_image_history",
             "operation": "DOCKER_METADATA_IMPORT", "control_role": "MEASUREMENT",
             "purpose": ("Build-context evidence and layer history, for the "
                         "rebuild question."),
             "params": {"export": ref("REF-13_image_history_wpno_litellm.txt"),
                        "no_socket": True},
             "timeout_seconds": 300},
            {"step_id": "positive_control_export_names_expected_service",
             "operation": "PARSE_JSON_READONLY", "control_role": "POSITIVE",
             "purpose": ("Confirm the export describes the expected image and "
                         "service by name, so the evidence is about the right "
                         "container."),
             "params": {"path": ref("REF-13_CONTAINER_INDEX.json"),
                        "expect_contains": "wpno_litellm"},
             "timeout_seconds": 120},
            # R8 correction. This step applied PARSE_JSON_READONLY to
            # REF-13_all_containers.txt, which is the tabular ASCII output of
            # `docker ps` -- 5449 bytes, first byte `C` of "CONTAINER ID" --
            # and not JSON. The parser refused at line 1 column 1 before the
            # `expect_absent` assertion was ever evaluated, so the negative
            # control tested nothing at all while returning a non-zero exit
            # that read, to a harness with no declared expectation, as a
            # control that had failed as designed.
            #
            # The operation had been chosen from the assertion it wanted
            # rather than from the bytes it was pointed at. The measurement
            # the control actually wants is a count: how many times does the
            # foreign-project marker appear in this listing? The answer must
            # be zero, and COUNT_TEXT_MATCHES measures it directly.
            #
            # `word_boundary` is on. CLAUDE.md section 10 records what its
            # absence cost here before: a pattern for `bea` matched
            # `Projektbeauftragung`, `Beanstandung` and `Bearbeitung` --
            # twelve hits, none of them real.
            {"step_id": "negative_control_export_is_not_another_project",
             "operation": "COUNT_TEXT_MATCHES", "control_role": "NEGATIVE",
             "purpose": ("Confirm the export does not describe a different "
                         "project's container. The listing is plain text, so "
                         "the marker is counted in it rather than sought "
                         "through a JSON parser that refuses the file."),
             "params": {"path": ref("REF-13_all_containers.txt"),
                        "patterns": ["not_a_wpno_project"],
                        "word_boundary": True,
                        "normal_form": "NFC"},
             "timeout_seconds": 120},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="operator-produced Docker metadata export, read offline",
                executable="none; every step is in-process",
                references=bind([ref("REF-13_CONTAINER_INDEX.json"),
                                 ref("REF-13_image_wpno_litellm.json"),
                                 ref("REF-13_container_wpno_litellm.json"),
                                 ref("REF-13_mounts_wpno_litellm.json"),
                                 ref("REF-13_REDACTION_MANIFEST.json"),
                                 ref("REF-13_REDACTED_MANIFEST.sha256"),
                                 MANIFEST_JSON]),
                reference_ids=["REF-13"],
                limitations=[
                    "REF-13 was redacted before intake. Secret-bearing values "
                    "are category placeholders; field names, image IDs and "
                    "digests, timestamps, mount destinations, source paths, "
                    "entrypoint, command, working directory and labels are "
                    "retained. Every question here is structural and is "
                    "answerable from what was retained.",
                    "The export describes the host at the moment it was taken. "
                    "It is not a live read and does not establish the present "
                    "state of a running container."],
                independent_oracle=(
                    "The operator-produced Docker metadata export. Compose and "
                    "Dockerfile are declarations of intent; only the export "
                    "describes what exists."),
                allowed_reads=[proj("docker", "litellm"), "references/REF-13_*"],
                allowed_writes=["work/L1-A21/RUN-A/", "evidence/L1-A21/RUN-A/"],
                forbidden_operations=["DOCKER_SOCKET_ACCESS", "DOCKER_EXEC",
                                      "DOCKER_RUN", "DOCKER_BUILD",
                                      "SERVICE_MUTATION"],
                notes=["No docker, docker compose or docker inspect command is "
                       "run at any point."]),
            {"check_id": "declared_versus_attached_mounts",
             "question": "Do the attached mounts match the compose declaration?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "import_attached_mounts",
             "required_result": ("Compared entry by entry. A difference "
                                 "between declared and attached is a finding.")},
            {"check_id": "rebuild_after_the_change",
             "question": "Was the image rebuilt after 2026-08-04?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "import_image_metadata",
             "comparison_date": "2026-08-04",
             "required_result": ("The image creation timestamp is compared "
                                 "against the date of the change. An image "
                                 "created before it cannot carry the change."),
             "why": ("A corrected source file and an unrebuilt image is "
                     "exactly the condition where the tree looks fixed and "
                     "production is not.")},
            {"check_id": "which_copy_is_inside",
             "question": "Which scanner copy is in the image?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Answered from the export's build-context and "
                                 "layer evidence, or reported unanswerable "
                                 "from the export supplied.")},
            {"check_id": "positive_control",
             "question": "Does the export describe the expected container?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_export_names_expected_service",
             "expected_result": "THE_EXPECTED_IMAGE_AND_SERVICE_ARE_NAMED"},
            {"check_id": "negative_control",
             "question": "Does the export describe some other project?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_export_is_not_another_project",
             "expected_result": "NO_FOREIGN_PROJECT_CONTAINER_DESCRIBED",
             # The control is negative in what it asserts about the export,
             # not in how the operation ends: the scan must complete, and
             # what it must find is nothing. So the expectation is a count of
             # zero on a successful scan, and both halves are checked. An
             # exit code alone could not tell "scanned, found nothing" apart
             # from "never scanned", which is exactly the confusion the
             # frozen version produced.
             "expected_exit_code": 0,
             "expected_count": 0,
             "measured_field": "total_matches",
             "sabotage_control": ("A copy of the listing carrying the marker "
                                  "must make this control fail. Proven in "
                                  "automation/package_tests/"
                                  "test_r8_plan_defect_repairs.py."),
             "expected_failure_reason": ("the export is scoped to this "
                                         "project's containers; a non-zero "
                                         "count names the foreign container "
                                         "found"),
             "r8_repair": ("PARSE_JSON_READONLY refused this plain-text "
                           "listing before evaluating expect_absent; the "
                           "control measured nothing")},
            {"check_id": "mutation_control",
             "question": "Is a mutation control applicable?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": "NOT_APPLICABLE",
             "reason": ("A mutation control here would require socket access "
                        "to change and re-read container state, which is "
                        "forbidden. Recorded rather than omitted, as the "
                        "specification requires.")},
        ],
    }


# ================================================== CLAUDE.md group
CLAUDE_MD = proj("CLAUDE.md")


def _claude_md_target(extra=""):
    return {
        "path": CLAUDE_MD, "sha256": sha_of(CLAUDE_MD),
        "identity_evidence": (
            "bindings/L1-A23.binding.json records productive_target_sha256 "
            "for the operator's own copy and the file on this machine hashes "
            "to the same value, so the two are the same bytes. File identity "
            "is not production identity." + (" " + extra if extra else "")),
    }


def a23_run_a():
    audit, phase = "L1-A23", "RUN-A"
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Compare every checkable rule and factual claim in CLAUDE.md "
            "against the actual state of the machine, and record each as "
            "confirmed, contradicted or uncheckable. Uncheckable is a real "
            "answer and is never rounded to confirmed."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The claims are "
            "enumerated from the file itself and each is classified in advance "
            "by what would settle it: a path claim, a file-kind claim, a "
            "repository claim, a configuration claim, a tool-version claim or "
            "a service claim.\n\n"
            "A version claim that can only be settled by running the tool is a "
            "gated operation. Where it is not approved the claim is recorded "
            "uncheckable, not confirmed - CLAUDE.md section 3 records the "
            "measurement that makes this rule: claude doctor reported no "
            "installation issues while no task could run at all.\n\n"
            "REF-14 supplies the operator-produced Mac reality evidence. The "
            "audit runs on Ubuntu and CLAUDE.md describes a Mac, so a claim "
            "about the Mac is settled from REF-14 or not at all; it is never "
            "settled from this host's own state under a Mac claim's name.\n\n"
            "The file under audit is never evidence for its own claims, and "
            "neither is any other document in the repository."),
        "target": _claude_md_target(),
        "steps": [
            {"step_id": "read_claims", "operation": "READ_FILE_RANGE",
             "control_role": "MEASUREMENT",
             "purpose": "Enumerate the claims from the file itself.",
             "params": {"path": CLAUDE_MD, "start": 0, "length": 262144},
             "timeout_seconds": 120},
            {"step_id": "hash_target", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the exact bytes whose claims are being checked.",
             "params": {"path": CLAUDE_MD}, "timeout_seconds": 120},
            {"step_id": "read_mac_reality", "operation": "PARSE_JSON_READONLY",
             "control_role": "ORACLE",
             "purpose": ("The operator-produced Mac evidence, which is the "
                         "only admissible oracle for a claim about the Mac."),
             "params": {"path": ref("REF-14_MAC_REALITY.json")},
             "timeout_seconds": 120},
            {"step_id": "read_mac_evidence_status",
             "operation": "PARSE_JSON_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Which Mac claims the evidence package can and cannot "
                         "settle, recorded before any claim is classified."),
             "params": {"path": ref("REF-14_MAC_EVIDENCE_STATUS.json")},
             "timeout_seconds": 120},
            {"step_id": "stat_project_root", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "A path claim, settled read-only.",
             "params": {"path": proj()}, "timeout_seconds": 120},
            {"step_id": "list_project_root", "operation": "LIST_DIRECTORY",
             "control_role": "MEASUREMENT",
             "purpose": "Directory-shape claims, settled read-only.",
             "params": {"path": proj()}, "timeout_seconds": 120},
            {"step_id": "positive_control_true_claim",
             "operation": "STAT_FILE", "control_role": "POSITIVE",
             "purpose": ("A claim known to be true - that PROJECT_ROOT holds a "
                         "git repository - must be confirmed by the method. "
                         "This proves the method can confirm."),
             "params": {"path": proj(".git")}, "timeout_seconds": 120},
            {"step_id": "negative_control_false_claim",
             "operation": "STAT_FILE", "control_role": "NEGATIVE",
             "purpose": ("A deliberately false claim constructed by this audit "
                         "- that a named path exists when it does not - must "
                         "be contradicted. This proves the method can "
                         "contradict."),
             "params": {"path": proj("this_path_does_not_exist_by_construction")},
             "timeout_seconds": 120},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="claim-by-claim read-only comparison against machine state",
                executable="none; every step is in-process",
                references=bind([ref("REF-14_MAC_REALITY.json"),
                                 ref("REF-14_MAC_REALITY.md"),
                                 ref("REF-14_MAC_EVIDENCE_STATUS.json"),
                                 ref("REF-14_MAC_MANIFEST.sha256"),
                                 MANIFEST_JSON]),
                reference_ids=["REF-14"],
                limitations=[
                    "Current Mac reality is measured evidence, not proof of "
                    "historical production identity.",
                    "Historical byte identity and continued production use "
                    "remain outside what this evidence can settle, and claims "
                    "resting on them are recorded uncheckable rather than "
                    "confirmed.",
                    "This host is Ubuntu and CLAUDE.md describes a Mac. A Mac "
                    "claim is settled from REF-14 or recorded uncheckable; it "
                    "is never settled from this host's state."],
                human_decisions=[
                    "The operator accepted the Mac evidence package "
                    "(mac_reality_status = ACCEPTED in "
                    "bindings/L1-A23.binding.json) with its manifest digest "
                    "recorded. That acceptance is not re-decided here."],
                independent_oracle=(
                    "The machine itself, read read-only, and for Mac claims "
                    "the operator-produced REF-14 evidence. The file under "
                    "audit is never evidence for its own claims."),
                allowed_reads=[proj(), "references/REF-14_*"],
                allowed_writes=["work/L1-A23/RUN-A/", "evidence/L1-A23/RUN-A/"],
                notes=["Every claim receives one of exactly three "
                       "classifications. There is no fourth that means "
                       "'probably true'."]),
            {"check_id": "three_classifications_only",
             "question": "How is each claim classified?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "classifications": ["CONFIRMED", "CONTRADICTED", "UNCHECKABLE"],
             "required_result": ("Exactly one per claim, with the evidence "
                                 "that settled it or the reason it cannot be "
                                 "settled."),
             "never_reported_as": ("confirmed on the strength of the document "
                                   "repeating itself")},
            {"check_id": "version_claims",
             "question": "How were tool and version claims obtained?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("The method of obtaining each is recorded. If "
                                 "obtaining it requires running the tool and "
                                 "that is not approved, the claim is "
                                 "UNCHECKABLE."),
             "specification_reference": ("CLAUDE.md section 3: claude doctor "
                                         "reported no installation issues "
                                         "while no task could run")},
            {"check_id": "positive_control",
             "question": "Can the method confirm a claim known to be true?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_true_claim",
             "expected_result": "CONFIRMED"},
            {"check_id": "negative_control",
             "question": "Can the method contradict a claim known to be false?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_false_claim",
             "expected_result": "CONTRADICTED",
             "expected_failure_reason": ("the path does not exist; the claim "
                                         "was constructed false by this audit"),
             "why": ("A method that can only confirm is not a comparison.")},
            {"check_id": "mutation_control",
             "question": "Is a mutation control applicable?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": "NOT_APPLICABLE",
             "reason": ("This is a documentation comparison; there is no "
                        "detector to perturb. Recorded rather than omitted.")},
        ],
    }


def a24_run_a():
    audit, phase = "L1-A24", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    external = "/Users/martinotten/Downloads"
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Establish which instruction files are actually in force when the "
            "tool is launched from a directory outside PROJECT_ROOT on the "
            "operator's Mac, and record the version that produced that "
            "behaviour. The launch happens on the Mac, under the operator's "
            "hand, against a directory the operator has approved. This "
            "controller does not launch it and never writes to that directory."),
        "static_analysis": (
            "This audit asks a question about a machine this controller does "
            "not run on. The approved external working directory is "
            + external + ", which is a path on the operator's Mac and does not "
            "exist on this Ubuntu host. It is deliberately not checked for "
            "existence here: a check that failed would be a fact about Ubuntu "
            "and not about the Mac, and substituting an Ubuntu directory would "
            "answer a different question under this audit's name.\n\n"
            "The operation is CLAUDE_LOAD_BEHAVIOUR_TEST, which the catalogue "
            "classifies GATED and OPERATOR_PERFORMED. It has no argv on this "
            "machine. The controller writes an execution packet fixing the "
            "host, the operating system, the directory, the invocation, the "
            "environment redirection and the directory's pre-run manifest; the "
            "packet is hashed and its digest forms part of the approval. What "
            "returns is an intake record, admitted by "
            "automation.external_host_evidence.validate_intake only if it "
            "answers that packet: same host, same operating system, same "
            "directory, same invocation, a packet digest that was issued, "
            "timestamps that do not precede the packet, well-formed digests "
            "for stdout, stderr and the post-run manifest, and an approval "
            "that has not already been spent.\n\n"
            "HOME, TMPDIR and every cache and configuration output are "
            "redirected below work/L1-A24/<RUN-ID>/, and the environment "
            "actually handed to the process is recorded verbatim rather than "
            "described.\n\n"
            "The mutation control available here is the write-topology "
            "control: a file created inside the redirected TMPDIR must appear "
            "below the audit's work directory and nowhere else, and the "
            "external directory's manifest must be unchanged between the "
            "pre-run and post-run captures. Mutating the loading behaviour "
            "itself is not available, because it would require modifying user "
            "configuration, which is forbidden."),
        "target": _claude_md_target(
            "The second candidate, /Users/martinotten/.claude/CLAUDE.md, is a "
            "Mac path and is absent here by construction; whether it "
            "participates in loading is precisely the runtime question this "
            "audit exists to answer."),
        "steps": [
            {"step_id": "hash_project_instruction_file",
             "operation": "SHA256_FILE", "control_role": "MEASUREMENT",
             "purpose": ("Bind the project instruction file whose "
                         "participation is in question."),
             "params": {"path": CLAUDE_MD}, "timeout_seconds": 120},
            {"step_id": "write_execution_packet",
             "operation": "PARSE_JSON_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Read back the execution packet the controller wrote "
                         "for this phase and bind its digest, so the approval "
                         "and the intake refer to the same authorisation."),
             "params": {"path": w("external_host", "EXECUTION_PACKET.json")},
             "timeout_seconds": 120},
            {"step_id": "external_launch_outside_project",
             "operation": "CLAUDE_LOAD_BEHAVIOUR_TEST",
             "control_role": "MEASUREMENT",
             "purpose": ("The operator launches from the approved external "
                         "directory on the Mac and returns an intake record. "
                         "The controller does not launch this."),
             "params": {"packet": w("external_host", "EXECUTION_PACKET.json"),
                        "intake": w("external_host", "INTAKE_OUTSIDE.json"),
                        "canonical_directory": external,
                        "host_class": "OPERATOR_MAC"},
             "timeout_seconds": 900},
            {"step_id": "external_launch_inside_project",
             "operation": "CLAUDE_LOAD_BEHAVIOUR_TEST",
             "control_role": "POSITIVE",
             "purpose": ("The same launch from inside PROJECT_ROOT on the same "
                         "machine. The project instruction file must be in "
                         "force; if it is not even there, the method is "
                         "measuring something else."),
             "params": {"packet": w("external_host",
                                    "EXECUTION_PACKET_INSIDE.json"),
                        "intake": w("external_host", "INTAKE_INSIDE.json"),
                        "canonical_directory": "/Users/martinotten/WPNO",
                        "host_class": "OPERATOR_MAC"},
             "timeout_seconds": 900},
            {"step_id": "external_launch_sibling_directory",
             "operation": "CLAUDE_LOAD_BEHAVIOUR_TEST",
             "control_role": "MEASUREMENT",
             "purpose": ("A sibling of PROJECT_ROOT, to separate 'outside the "
                         "project' from 'outside the home directory'."),
             "params": {"packet": w("external_host",
                                    "EXECUTION_PACKET_SIBLING.json"),
                        "intake": w("external_host", "INTAKE_SIBLING.json"),
                        "canonical_directory": "/Users/martinotten/WPNO_sibling",
                        "host_class": "OPERATOR_MAC"},
             "timeout_seconds": 900},
            {"step_id": "negative_control_impossible_file",
             "operation": "PARSE_JSON_READONLY", "control_role": "NEGATIVE",
             "purpose": ("From the external directory, a file that certainly "
                         "cannot apply must not be reported as loaded. The "
                         "intake's loaded-instruction evidence is checked for "
                         "its absence."),
             "params": {"path": w("external_host", "INTAKE_OUTSIDE.json"),
                        "expect_absent": "a_file_that_cannot_apply"},
             "timeout_seconds": 120},
            {"step_id": "mutation_control_write_topology",
             "operation": "COMPARE_HASHES", "control_role": "MUTATION",
             "purpose": ("Compare the external directory's pre-run and post-run "
                         "manifests. A file created inside the redirected "
                         "TMPDIR must appear below the audit's work directory "
                         "and the external directory must be unchanged. This "
                         "proves the redirection is in force rather than "
                         "assumed."),
             "params": {"left": w("external_host", "EXTERNAL_DIR_PRE.sha256"),
                        "right": w("external_host", "EXTERNAL_DIR_POST.sha256"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("operator-performed external-host launch on the "
                        "operator's Mac, with hash-bound evidence intake"),
                executable=("none on this machine. The invocation runs on the "
                            "external host and is fixed by the execution "
                            "packet."),
                references=bind([ref("REF-14_MAC_REALITY.json"),
                                 ref("REF-14_MAC_MANIFEST.sha256"),
                                 MANIFEST_JSON]),
                reference_ids=["REF-14"],
                limitations=[
                    "The approved external working directory "
                    + external + " is a path on the operator's Mac. It does "
                    "not exist on this Ubuntu host and is not claimed to. No "
                    "Ubuntu directory is substituted for it.",
                    "Nothing in this plan asserts that the Mac launch has "
                    "happened. Until an intake record is admitted, the "
                    "runtime question is unanswered and the phase's verdict is "
                    "BLOCKED, not PASS.",
                    "Mutation of the loading behaviour itself is not available: "
                    "it would require modifying user configuration, which is "
                    "forbidden. The write-topology control is the mutation "
                    "control that is available."],
                human_decisions=[
                    "The operator approved " + external + " as the external "
                    "working directory. The decision is recorded in "
                    "bindings/L1-A24.binding.json as a test candidate and is "
                    "not re-decided here. The operator is asserting that the "
                    "directory may be used, which is why the directory itself "
                    "is part of the approval and not merely a parameter."],
                independent_oracle=(
                    "The session's observable state, the documented precedence "
                    "rules for the recorded version, and the two filesystem "
                    "manifests of the external directory. The model's "
                    "recollection of what it loaded is not evidence."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[CLAUDE_MD, "references/REF-14_*",
                               "work/L1-A24/RUN-A/external_host/"],
                allowed_writes=["work/L1-A24/RUN-A/", "evidence/L1-A24/RUN-A/"],
                forbidden_operations=["NETWORK_REQUEST", "SERVICE_MUTATION",
                                      "LAUNCH_AGENT_MUTATION"],
                notes=[
                    "The controller never writes to the external directory. It "
                    "compares two manifests the operator produced of it.",
                    "CLAUDE_LOAD_BEHAVIOUR_TEST is GATED and OPERATOR_PERFORMED: "
                    "the catalogue refuses to build an argv for it, and the "
                    "controller records it as performed elsewhere rather than "
                    "launching it."]),
            {"check_id": "external_host_binding",
             "question": "What exactly is the operator authorised to do?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "write_execution_packet",
             "packet_binds": [
                 "audit_id", "run_phase", "host_identity", "operating_system",
                 "canonical_directory", "invocation",
                 "environment_redirection",
                 "pre_run_directory_manifest_sha256",
                 "expected_global_instruction_path",
                 "expected_project_instruction_condition",
                 "source_host_sha256", "issued_utc"],
             "intake_must_carry": [
                 "packet_sha256", "host_identity", "operating_system",
                 "canonical_directory", "invocation", "tool_version",
                 "started_utc", "finished_utc", "stdout_sha256",
                 "stderr_sha256", "post_run_directory_manifest_sha256",
                 "loaded_instruction_evidence", "operator_identity"],
             "refusals": [
                 "a different host", "a different operating system",
                 "a different directory", "a different invocation",
                 "an unissued packet digest", "a missing pre or post manifest",
                 "a malformed digest",
                 "evidence timestamped before the packet was issued",
                 "a chronology in which the run finished before it started",
                 "a packet digest that has already been answered"],
             "required_result": ("Every refusal is a refusal, not a warning. "
                                 "An intake that fails any of them is not "
                                 "admitted and the phase has no result.")},
            {"check_id": "loaded_instruction_files",
             "question": "Which instruction files are in force, and in what order?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "external_launch_outside_project",
             "required_result": ("Per launch directory: which files loaded, in "
                                 "what precedence, whether the project file "
                                 "participated, and which part of the run "
                                 "produced the observation."),
             "method_requirement": ("read from the session's own state, not "
                                    "from the model self-reporting from "
                                    "memory"),
             "not_yet_established": ("No launch has occurred. This is what the "
                                     "approved phase will establish.")},
            {"check_id": "positive_control",
             "question": "From inside PROJECT_ROOT, is the project file in force?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "external_launch_inside_project",
             "expected_result": "PROJECT_INSTRUCTION_FILE_IN_FORCE",
             "why": ("If it is not in force even from inside the project, the "
                     "test method is measuring something else and the external "
                     "result is uninterpretable.")},
            {"check_id": "negative_control",
             "question": "Is a file that cannot apply reported as loaded?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_impossible_file",
             "expected_result": "NOT_REPORTED_AS_LOADED",
             "expected_failure_reason": ("the file cannot apply from that "
                                         "directory under the recorded "
                                         "precedence rules")},
            {"check_id": "mutation_control_write_topology",
             "question": "Is the redirection in force, or merely assumed?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_write_topology",
             "fixture": ("a file created inside the redirected TMPDIR during "
                         "the run"),
             "proof_the_fixture_differs": ("the file exists below "
                                           "work/L1-A24/RUN-A/ after the run "
                                           "and did not before"),
             "expected_result": ("FILE_APPEARS_BELOW_THE_AUDIT_WORK_DIRECTORY_"
                                 "AND_THE_EXTERNAL_DIRECTORY_MANIFEST_IS_"
                                 "UNCHANGED"),
             "zero_changed_results_is": ("a measurement error: if nothing was "
                                         "written anywhere, the control did "
                                         "not exercise the redirection"),
             "verdict_effect": ("A changed external-directory manifest is a "
                                "finding that the run wrote outside its "
                                "sandbox, and forbids PASS.")},
            {"check_id": "no_claim_of_execution",
             "question": "Does this plan claim the Mac audit has run?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("No. Rehearsal exercises packet construction, "
                                 "intake binding, hash validation, mismatch "
                                 "refusal and replay refusal against a "
                                 "synthetic local fixture. It does not claim "
                                 "the real Mac launch occurred, and a "
                                 "rehearsal result is never a live result.")},
        ],
    }


def a25_run_a():
    audit, phase = "L1-A25", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Determine whether CLAUDE.md is tracked, ignored, untracked, "
            "outside the repository, symlinked or generated, and determine "
            "whether it would survive git clean -fd - without ever running "
            "that command in the real repository."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The state question is "
            "answered read-only: the file's presence and kind, the .gitignore "
            "rules that could match it, and the repository's own record of "
            "whether it is tracked.\n\n"
            "The survivability question is answered in a disposable "
            "repository built under work/L1-A25/RUN-A/synthetic_repo/, which "
            "reproduces the observed state and contains no project content - "
            "only files reproducing the state under test. git clean -fd is run "
            "there and nowhere else. The real repository is never the "
            "experiment: a destructive command run to find out what it does is "
            "not a measurement, it is the damage.\n\n"
            "git clean -nd in the real repository writes nothing, but it is "
            "still an operation on the real repository and is treated as "
            "gated. It is not part of this plan."),
        "target": _claude_md_target(),
        "steps": [
            {"step_id": "stat_target", "operation": "STAT_FILE",
             "control_role": "MEASUREMENT",
             "purpose": ("Presence, kind and whether the path is a symlink. A "
                         "symlinked instruction file survives differently from "
                         "a regular one."),
             "params": {"path": CLAUDE_MD}, "timeout_seconds": 120},
            {"step_id": "file_type_target", "operation": "FILE_TYPE",
             "control_role": "MEASUREMENT",
             "purpose": "Confirm the kind of object independently of its name.",
             "params": {"path": CLAUDE_MD}, "timeout_seconds": 120},
            {"step_id": "read_gitignore", "operation": "READ_FILE_RANGE",
             "control_role": "MEASUREMENT",
             "purpose": "The ignore rules that could match the file.",
             "params": {"path": proj(".gitignore"), "start": 0,
                        "length": 262144},
             "timeout_seconds": 120},
            {"step_id": "repository_status_readonly",
             "operation": "GIT_STATUS_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Whether the repository regards the file as tracked, "
                         "untracked or ignored. Read-only and writes nothing."),
             "params": {"repo": proj()}, "timeout_seconds": 300},
            {"step_id": "positive_control_untracked_is_removed",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("In the disposable repository, an untracked file must "
                         "be removed by git clean -fd. This proves the "
                         "reproduction is faithful."),
             "params": {"script": w("synthetic_repo", "run_clean_experiment.py"),
                        "args": ["--case", "untracked"]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_tracked_survives",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("In the disposable repository, a tracked file must "
                         "not be removed. This proves the command is "
                         "selective."),
             "params": {"script": w("synthetic_repo", "run_clean_experiment.py"),
                        "args": ["--case", "tracked"]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_state_change",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("Move the file between tracked, untracked and ignored "
                         "in the disposable repository and confirm the outcome "
                         "changes accordingly. This proves the state "
                         "classification determines the outcome."),
             "params": {"script": w("synthetic_repo", "run_clean_experiment.py"),
                        "args": ["--case", "state-transitions"]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method=("read-only state classification plus a disposable "
                        "repository experiment"),
                executable="/usr/bin/git read-only; /usr/bin/python3 for the sandbox experiment",
                independent_oracle=(
                    "Git's documented semantics plus the disposable-repository "
                    "experiment. The real repository is never the experiment."),
                allowed_reads=[CLAUDE_MD, proj(".gitignore"), proj()],
                allowed_writes=["work/L1-A25/RUN-A/", "evidence/L1-A25/RUN-A/"],
                forbidden_operations=["GIT_MUTATION"],
                notes=["git clean -fd is run only inside "
                       "work/L1-A25/RUN-A/synthetic_repo/, which contains no "
                       "project content.",
                       "git clean -nd against the real repository is gated and "
                       "is not part of this plan."]),
            {"check_id": "state_classification",
             "question": "What is the file's state in the repository?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "repository_status_readonly",
             "states": ["tracked", "ignored", "untracked",
                        "outside the repository", "symlinked", "generated"],
             "required_result": "Exactly one, with the evidence that settles it."},
            {"check_id": "survivability",
             "question": "Would the file survive git clean -fd?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Answered from the disposable repository "
                                 "reproducing the observed state, never from "
                                 "running the command in the real one."),
             "why": ("A destructive command run to find out what it does is "
                     "the damage, not the measurement.")},
            {"check_id": "positive_control",
             "question": "Does git clean -fd remove an untracked file?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_untracked_is_removed",
             "expected_exit_code": 0,
             "expected_result": "UNTRACKED_FILE_REMOVED"},
            {"check_id": "negative_control",
             "question": "Does it leave a tracked file alone?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_tracked_survives",
             "expected_exit_code": 0,
             "expected_result": "TRACKED_FILE_SURVIVES",
             "expected_failure_reason": ("git clean does not remove tracked "
                                         "files; a removal here would mean the "
                                         "reproduction is not faithful")},
            {"check_id": "mutation_control",
             "question": "Does changing the state change the outcome?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_state_change",
             "expected_exit_code": 0,
             "fixture": "work/L1-A25/RUN-A/synthetic_repo/",
             "fixture_construction": ("a repository containing only files that "
                                      "reproduce the state under test, moved "
                                      "between tracked, untracked and ignored"),
             "proof_the_fixture_differs": ("the file's git status differs "
                                           "between the three cases"),
             "expected_result": "OUTCOME_FOLLOWS_THE_STATE_IN_ALL_THREE_CASES",
             "zero_changed_results_is": "a measurement error, not a pass"},
        ],
    }


def a26_run_a():
    audit, phase = "L1-A26", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "For each of the nine error classes in section ten, identify its "
            "exact definition, the actual detection implementation, the actual "
            "caller, the actual test, a positive and a negative example, the "
            "false-positive and false-negative risk, and any mismatch with "
            "machine reality. Where no implementation exists the class is "
            "recorded undetected and the examples are constructed anyway, so a "
            "future implementation has a test set."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The nine classes are "
            "enumerated from section ten itself and each is stated in its own "
            "terms before anything is searched for: the missing word boundary; "
            "the regex without a quantifier; one court's rule applied to all; "
            "the test that exits zero without asserting; the counter that "
            "counts only what it knows; find without parentheses; the check "
            "that counts its own invocation; green tests that never touch the "
            "new code; and the same file in several places.\n\n"
            "For each class the detection implementation is looked for by a "
            "boundary-anchored search; absence is recorded as absence rather "
            "than as a class that does not apply.\n\n"
            "Preparation the approved phase performs: for every class, a "
            "positive example that must be detected and a negative example "
            "that must not be, written under work/L1-A26/RUN-A/examples/, plus "
            "a sandbox copy of any detection implementation found so its rule "
            "can be neutralised without touching the original."),
        "target": _claude_md_target(),
        "steps": [
            {"step_id": "read_section_ten", "operation": "READ_FILE_RANGE",
             "control_role": "MEASUREMENT",
             "purpose": "Enumerate the nine classes from the file itself.",
             "params": {"path": CLAUDE_MD, "start": 0, "length": 262144},
             "timeout_seconds": 120},
            _search_step("search_detection_implementations",
                         ("Look for a detection implementation for each class. "
                          "Absence is recorded as absence."),
                         ["word_boundary", "\\\\b", "re.compile",
                          "__pycache__", "payload_scan"]),
            {"step_id": "run_positive_examples",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("Per class, the positive example must be detected by "
                         "its implementation where one exists."),
             "params": {"script": w("examples", "run_class_examples.py"),
                        "args": ["--mode", "positive"]},
             "timeout_seconds": 300},
            {"step_id": "run_negative_examples",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("Per class, the negative example must not be "
                         "detected."),
             "params": {"script": w("examples", "run_class_examples.py"),
                        "args": ["--mode", "negative"]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_neutralise_rule",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("Where a detection exists, neutralise its rule in a "
                         "sandbox copy and confirm the positive example stops "
                         "being detected. This proves the detection was doing "
                         "the work."),
             "params": {"script": w("examples", "run_class_examples.py"),
                        "args": ["--mode", "neutralised"]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="per-class definition, implementation search and example matrix",
                executable="/usr/bin/python3 for the sandbox example runner",
                independent_oracle=(
                    "The class definitions as written in section ten, plus "
                    "examples constructed by this audit. No prior report under "
                    "docs/ is an oracle."),
                allowed_reads=[CLAUDE_MD, proj()],
                allowed_writes=["work/L1-A26/RUN-A/", "evidence/L1-A26/RUN-A/"],
                notes=[WORD_BOUNDARY_NOTE,
                       "A class with no implementation is recorded undetected "
                       "and still receives its two examples."]),
            {"check_id": "nine_classes_enumerated",
             "question": "Are all nine classes covered, each in its own terms?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "read_section_ten",
             "classes_expected": 9,
             "required_result": ("Definition, implementation, caller, test, "
                                 "positive example, negative example, "
                                 "false-positive risk and false-negative risk "
                                 "per class.")},
            {"check_id": "positive_control",
             "question": "Is each positive example detected where an implementation exists?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "run_positive_examples",
             "expected_exit_code": 0,
             "expected_result": "EACH_POSITIVE_EXAMPLE_DETECTED_BY_ITS_IMPLEMENTATION"},
            {"check_id": "negative_control",
             "question": "Is each negative example left undetected?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "run_negative_examples",
             "expected_exit_code": 0,
             "expected_result": "NO_NEGATIVE_EXAMPLE_DETECTED",
             "expected_failure_reason": ("the negative example does not "
                                         "instantiate the class; a detection "
                                         "here is a false positive and is "
                                         "reported as one")},
            {"check_id": "mutation_control",
             "question": "Does neutralising a rule stop its detection?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_neutralise_rule",
             "expected_exit_code": 0,
             "fixture": "a sandbox copy of the detection implementation with its rule neutralised",
             "proof_the_fixture_differs": ("the sandbox copy's SHA-256 differs "
                                           "from the original's and the "
                                           "neutralised line is recorded"),
             "expected_result": "THE_POSITIVE_EXAMPLE_STOPS_BEING_DETECTED",
             "zero_changed_results_is": ("a measurement error: the detection "
                                         "was not what produced the result"),
             "not_applicable_where": ("no implementation exists for a class; "
                                      "recorded as not applicable with that "
                                      "reason")},
        ],
    }


# ================================================== output-guard group
GUARD_V3 = proj("authoring", "AP17_output_guardrail_v3.py")
GUARD_V1 = proj("authoring", "AP17_output_guardrail_VERALTET.py.txt")
GUARD_V2 = proj("authoring", "AP17_output_guardrail_v2_VERALTET.py.txt")

GUARD_SANDBOX_NOTE = (
    "PYTHON_SCRIPT_RUN_SANDBOX runs a script under work/ and nowhere else, so "
    "the approved phase first copies the guard to "
    "work/<audit>/RUN-A/sandbox/ and records the copy's digest beside the "
    "original's. The original in authoring/ is read and never written to. "
    "Where a rule has to be neutralised to attribute a rejection, it is "
    "neutralised in that copy and the neutralised line is recorded.")


def _guard_target(path, note=""):
    return {
        "path": path, "sha256": sha_of(path),
        "identity_evidence": (
            "bindings records this path with this digest. Which guardrail "
            "version is productive is an open question in this audit's "
            "binding and a version suffix is excluded by rule from answering "
            "it." + (" " + note if note else "")),
    }


def a05_run_a():
    audit, phase = "L1-A05", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Prove that the productive output guard rejects the known-bad "
            "report, and that the rejection is caused by the rule intended to "
            "catch it rather than by an unrelated failure. Exit code and "
            "semantic verdict are recorded separately: a guard that prints "
            "REJECT and exits 0 is a finding."),
        "static_analysis": (
            "The guard is parsed with PYTHON_AST_PARSE, never imported. Its "
            "rule set is enumerated from the parse - each rule with its "
            "pattern, its boundary constructs and the verdict it produces - "
            "because attribution needs the rule list before it needs any "
            "output.\n\n"
            "The binding records two open questions and neither is resolved by "
            "assumption: what 'report_bad' is on this machine, and which "
            "guardrail version is productive. The known-bad input is "
            "identified from the enumerated rules by constructing an input "
            "that violates one named rule, so that the audit does not depend "
            "on an identifier that does not exist here.\n\n"
            + GUARD_SANDBOX_NOTE),
        "target": _guard_target(GUARD_V3),
        "steps": [
            {"step_id": "parse_guard", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Enumerate the rule set. Parse, do not import.",
             "params": {"path": GUARD_V3}, "timeout_seconds": 120},
            {"step_id": "hash_guard", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Bind the exact guard bytes under test.",
             "params": {"path": GUARD_V3}, "timeout_seconds": 120},
            {"step_id": "run_against_known_bad",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Run the sandbox copy against the known-bad input. "
                         "Record argv, exit code and complete stdout and "
                         "stderr."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "known_bad.md")]},
             "timeout_seconds": 300},
            {"step_id": "run_against_known_bad_reformatted",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("The same input trivially reformatted - whitespace "
                         "and line endings - to confirm the rejection is of "
                         "the content and not of the formatting."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs",
                                              "known_bad_reformatted.md")]},
             "timeout_seconds": 300},
            {"step_id": "positive_control_single_rule_violation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A minimal input constructed to violate exactly one "
                         "enumerated rule must be rejected, and the rejection "
                         "must be attributable to that rule."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs",
                                              "isolating_one_rule.md")]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_clean_input",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("A minimal clean input must be accepted. If "
                         "everything is rejected, rejecting the bad input "
                         "carries no information."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "clean_minimal.md")]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_neutralise_the_rule",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("With the triggering rule neutralised in the sandbox "
                         "copy, the known-bad input must be accepted. If it is "
                         "still rejected, the rejection came from somewhere "
                         "else and the attribution was wrong."),
             "params": {"script": w("sandbox",
                                    "AP17_output_guardrail_v3_rule_neutralised.py"),
                        "args": ["--input", w("inputs", "known_bad.md")]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="rule enumeration by AST, then attribution by selective neutralisation",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "The enumerated rule set from the AST parse, plus inputs "
                    "constructed by this audit to isolate one rule each. The "
                    "guard's own report files in authoring/ are prior "
                    "artefacts, not oracles."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[GUARD_V3],
                allowed_writes=["work/L1-A05/RUN-A/", "evidence/L1-A05/RUN-A/"],
                notes=[GUARD_SANDBOX_NOTE,
                       "The binding's two open questions - what report_bad is "
                       "here, and which version is productive - are carried "
                       "into the result rather than resolved by assumption."]),
            {"check_id": "exit_code_and_verdict_separately",
             "question": "What did the guard return, and what did it say?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_against_known_bad",
             "required_result": ("Exit code and semantic verdict recorded as "
                                 "two values."),
             "verdict_effect": ("A guard that prints REJECT and exits 0 is a "
                                "finding: a caller reading the exit code would "
                                "proceed.")},
            {"check_id": "attribution",
             "question": "Which rule caused the rejection?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "method": ("from the guard's own output if it identifies the "
                        "rule; otherwise by selectively neutralising rules in "
                        "the sandbox copy and observing which change makes the "
                        "rejection disappear"),
             "required_result": "One named rule, with the evidence for it."},
            {"check_id": "reformatting_invariance",
             "question": "Does trivial reformatting change the verdict?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_against_known_bad_reformatted",
             "required_result": ("Recorded. A rejection that disappears under "
                                 "whitespace changes is matching formatting "
                                 "rather than content.")},
            {"check_id": "positive_control",
             "question": "Is a single-rule violation rejected and attributed?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_single_rule_violation",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the one rule the input was built to violate",
             "fixture": "work/L1-A05/RUN-A/inputs/isolating_one_rule.md",
             "fixture_construction": ("minimal text violating exactly one "
                                      "enumerated rule and nothing else"),
             "expected_result": "REJECTED_AND_ATTRIBUTED_TO_THAT_RULE"},
            {"check_id": "negative_control",
             "question": "Is a clean input accepted?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_clean_input",
             "expected_exit_code": 0,
             "expected_result": "ACCEPTED",
             "expected_failure_reason": ("none expected; a rejection here "
                                         "would mean the guard rejects "
                                         "everything and its rejection of the "
                                         "bad input carries no information")},
            {"check_id": "mutation_control",
             "question": "Does neutralising the rule change the verdict?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_neutralise_the_rule",
             "expected_exit_code": 0,
             "fixture": "work/L1-A05/RUN-A/sandbox/AP17_output_guardrail_v3_rule_neutralised.py",
             "fixture_construction": ("the sandbox copy with the attributed "
                                      "rule disabled and nothing else changed"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "sandbox copy's and the neutralised "
                                           "line is recorded verbatim"),
             "expected_result": "THE_KNOWN_BAD_INPUT_IS_NOW_ACCEPTED",
             "zero_changed_results_is": ("proof that the attribution was "
                                         "wrong, not a passing control")},
        ],
    }


def a06_run_a():
    audit, phase = "L1-A06", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Prove that the productive guard accepts the known-good report, "
            "that the acceptance is a real evaluation rather than a skipped or "
            "no-op execution, and that no suppression mechanism is hiding a "
            "rejection. Zero rules evaluated with exit 0 is not a pass."),
        "static_analysis": (
            "The guard is parsed, never imported, and its rule set is "
            "enumerated so that the number of rules that ought to run is known "
            "before any run happens. Acceptance is only meaningful relative to "
            "the number of rules that actually ran.\n\n"
            "CLAUDE.md section 10 records the vacuous-success pattern this "
            "audit exists to detect: two test functions and no __main__ block, "
            "exit 0, nothing executed. An acceptance produced the same way is "
            "the same defect wearing a different name, and here it is a FAIL "
            "rather than a pass.\n\n"
            "Where the guard does not report how many rules it evaluated, a "
            "sandbox copy is instrumented to count, and the count is reported "
            "as coming from an instrumented copy whose digest is recorded.\n\n"
            + GUARD_SANDBOX_NOTE),
        "target": _guard_target(GUARD_V3),
        "steps": [
            {"step_id": "parse_guard", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Enumerate the rules that ought to run.",
             "params": {"path": GUARD_V3}, "timeout_seconds": 120},
            {"step_id": "run_against_known_good",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "Run the sandbox copy against the known-good input.",
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "known_good.md")]},
             "timeout_seconds": 300},
            {"step_id": "count_rules_evaluated",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "ORACLE",
             "purpose": ("An instrumented sandbox copy that counts the rules "
                         "actually evaluated. Zero with exit 0 is a FAIL."),
             "params": {"script": w("sandbox",
                                    "AP17_output_guardrail_v3_instrumented.py"),
                        "args": ["--input", w("inputs", "known_good.md"),
                                 "--count-rules"]},
             "timeout_seconds": 300},
            {"step_id": "run_without_configuration",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("With the guard's configuration or pattern file "
                         "removed from the sandbox environment: does it block, "
                         "or pass silently?"),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "known_good.md"),
                                 "--config", w("inputs", "absent_config.json")]},
             "timeout_seconds": 300},
            {"step_id": "positive_control_known_bad_still_rejected",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("The known-bad input from L1-A05 must be rejected by "
                         "this same invocation path. This proves the guard was "
                         "actually evaluating during this audit's runs, and it "
                         "is the single most important control here."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "known_bad.md")]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_known_good_accepted",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("The known-good input must be accepted. On its own "
                         "this is worth nothing without the positive control "
                         "above."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs", "known_good.md")]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_bad_token_inserted",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("One known-bad token inserted into a copy of the "
                         "known-good input. It must now be rejected. If a "
                         "known-good document stays accepted after a known-bad "
                         "token is added, acceptance is not an evaluation."),
             "params": {"script": w("sandbox", "AP17_output_guardrail_v3.py"),
                        "args": ["--input", w("inputs",
                                              "known_good_with_bad_token.md")]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="acceptance measured against the count of rules actually evaluated",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "The rule enumeration from the AST parse, plus the "
                    "rule-evaluation count. Acceptance is only meaningful "
                    "relative to the number of rules that ran."),
                allowed_reads=[GUARD_V3],
                allowed_writes=["work/L1-A06/RUN-A/", "evidence/L1-A06/RUN-A/"],
                notes=[GUARD_SANDBOX_NOTE,
                       "A count obtained from an instrumented copy is reported "
                       "as such, with that copy's digest."]),
            {"check_id": "rules_evaluated",
             "question": "How many rules actually ran?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "count_rules_evaluated",
             "required_result": ("A count, compared against the number the AST "
                                 "enumeration says exist."),
             "zero_rules_with_exit_zero_is": ("a FAIL for this audit, not a "
                                              "pass. It is the vacuous-success "
                                              "pattern CLAUDE.md section 10 "
                                              "records."),
             "specification_reference": "CLAUDE.md section 10, bullet 4"},
            {"check_id": "configuration_absent_behaviour",
             "question": "What happens when the configuration is missing?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_without_configuration",
             "required_result": ("Recorded as blocking or as passing silently. "
                                 "A guard that passes silently when its "
                                 "patterns are absent protects nothing.")},
            {"check_id": "positive_control",
             "question": "Was the guard evaluating at all during these runs?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_bad_still_rejected",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the known-bad content the guard is built to reject",
             "expected_result": "REJECTED",
             "why": ("This is the single most important control here. Without "
                     "it, acceptance of the good input is indistinguishable "
                     "from the guard doing nothing.")},
            {"check_id": "negative_control",
             "question": "Is the known-good input accepted?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_known_good_accepted",
             "expected_exit_code": 0,
             "expected_result": "ACCEPTED",
             "worth_on_its_own": ("nothing, without the positive control")},
            {"check_id": "mutation_control",
             "question": "Does adding a bad token change acceptance?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_bad_token_inserted",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the inserted known-bad token",
             "fixture": "work/L1-A06/RUN-A/inputs/known_good_with_bad_token.md",
             "fixture_construction": ("the known-good input with exactly one "
                                      "known-bad token inserted"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "known-good input's and the "
                                           "inserted token is recorded"),
             "expected_result": "NOW_REJECTED",
             "zero_changed_results_is": ("proof that acceptance is not an "
                                         "evaluation, not a passing control")},
        ],
    }


def a07_run_a():
    audit, phase = "L1-A07", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Run every known-bad case that v1 detects against v3, and identify "
            "every protection lost, every false positive introduced and every "
            "false negative introduced between the versions. The corpus is "
            "derived from the two rule sets, never from either guard's output."),
        "static_analysis": (
            "Both versions are parsed, never imported, and their rule sets are "
            "extracted separately. The v1 known-bad corpus is then built from "
            "the v1 patterns - one isolating input per v1 rule - so that every "
            "input maps to a named rule. A corpus derived from a guard's "
            "output would agree with that guard by construction and could not "
            "show what it misses.\n\n"
            "v1 is AP17_output_guardrail_VERALTET.py.txt and v3 is "
            "AP17_output_guardrail_v3.py. v2 exists as well and is hashed and "
            "parsed so that the version set is enumerated rather than "
            "assumed.\n\n" + GUARD_SANDBOX_NOTE),
        "target": _guard_target(
            GUARD_V1,
            "This phase compares two versions; v1 is bound as the target "
            "because it is the side whose detections define the corpus."),
        "steps": [
            {"step_id": "parse_v1", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Extract the v1 rule set.",
             "params": {"path": GUARD_V1}, "timeout_seconds": 120},
            {"step_id": "parse_v2", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Enumerate the version set rather than assume it.",
             "params": {"path": GUARD_V2}, "timeout_seconds": 120},
            {"step_id": "parse_v3", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "Extract the v3 rule set.",
             "params": {"path": GUARD_V3}, "timeout_seconds": 120},
            {"step_id": "run_corpus_against_v1",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "The full isolating corpus against the v1 sandbox copy.",
             "params": {"script": w("sandbox", "guard_v1.py"),
                        "args": ["--corpus", w("corpus", "v1_known_bad")]},
             "timeout_seconds": 600},
            {"step_id": "run_corpus_against_v3",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "The identical corpus against the v3 sandbox copy.",
             "params": {"script": w("sandbox", "guard_v3.py"),
                        "args": ["--corpus", w("corpus", "v1_known_bad")]},
             "timeout_seconds": 600},
            {"step_id": "run_known_good_corpus_against_both",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("A corpus of legitimate content against both "
                         "versions. Detections here are false positives and "
                         "the two rates are compared."),
             "params": {"script": w("sandbox", "run_both_versions.py"),
                        "args": ["--corpus", w("corpus", "known_good")]},
             "timeout_seconds": 600},
            {"step_id": "positive_control_each_rule_detects_its_input",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("Each isolating input must be detected by the version "
                         "whose rule it targets. If v1 does not detect its own "
                         "rule's input, the corpus is wrong and not the guard."),
             "params": {"script": w("sandbox", "guard_v1.py"),
                        "args": ["--corpus", w("corpus", "v1_known_bad"),
                                 "--assert-each-rule-detected"]},
             "timeout_seconds": 600},
            {"step_id": "negative_control_known_good_clean_in_v1",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("The known-good corpus must produce no detections in "
                         "v1, so that the false-positive comparison has a "
                         "baseline before v3 is judged."),
             "params": {"script": w("sandbox", "guard_v1.py"),
                        "args": ["--corpus", w("corpus", "known_good")]},
             "timeout_seconds": 600},
            {"step_id": "mutation_control_shared_rule_neutralised",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("A rule present in both versions, neutralised in the "
                         "v3 sandbox copy: its corresponding input must stop "
                         "being detected. This proves the corpus-to-rule "
                         "mapping is real."),
             "params": {"script": w("sandbox", "guard_v3_rule_neutralised.py"),
                        "args": ["--corpus", w("corpus", "v1_known_bad")]},
             "timeout_seconds": 600},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="rule-derived isolating corpus run against both versions",
                executable="/usr/bin/python3 -I -B against sandbox copies",
                independent_oracle=(
                    "The AST-extracted rule sets themselves, and inputs "
                    "constructed from them. Neither guard version validates "
                    "the other; the corpus comes from the patterns, not from "
                    "either guard's output."),
                allowed_reads=[GUARD_V1, GUARD_V2, GUARD_V3],
                allowed_writes=["work/L1-A07/RUN-A/", "evidence/L1-A07/RUN-A/"],
                notes=[GUARD_SANDBOX_NOTE]),
            {"check_id": "difference_table",
             "question": "What changed between the versions?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Two lists: detected by v1 and not by v3 - "
                                 "lost protection; detected by v3 and not by "
                                 "v1 - added protection.")},
            {"check_id": "false_positive_rates",
             "question": "How do the false-positive rates compare?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_known_good_corpus_against_both",
             "required_result": ("Both rates reported, against the same "
                                 "known-good corpus.")},
            {"check_id": "lost_protection_explained",
             "question": "Is each lost protection explained?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Per lost protection: whether the omission is "
                                 "explained by an intentional narrowing "
                                 "visible in the code, or is unexplained. An "
                                 "unexplained loss is a finding.")},
            {"check_id": "positive_control",
             "question": "Does each isolating input hit the rule it targets?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_each_rule_detects_its_input",
             "expected_exit_code": 0,
             "expected_result": "EVERY_V1_RULE_DETECTS_ITS_OWN_INPUT",
             "why": ("If v1 misses its own rule's input, the corpus is wrong "
                     "and every downstream comparison is uninterpretable.")},
            {"check_id": "negative_control",
             "question": "Is the known-good corpus clean in v1?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_known_good_clean_in_v1",
             "expected_exit_code": 0,
             "expected_result": "ZERO_DETECTIONS",
             "expected_failure_reason": ("legitimate content matches no v1 "
                                         "rule; detections here are the "
                                         "baseline false-positive rate and "
                                         "must be recorded before v3 is "
                                         "judged")},
            {"check_id": "mutation_control",
             "question": "Is the corpus-to-rule mapping real?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_shared_rule_neutralised",
             "expected_exit_code": 0,
             "fixture": "work/L1-A07/RUN-A/sandbox/guard_v3_rule_neutralised.py",
             "fixture_construction": ("the v3 sandbox copy with one rule "
                                      "present in both versions disabled"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the v3 "
                                           "sandbox copy's and the neutralised "
                                           "line is recorded"),
             "expected_result": "THAT_RULES_INPUT_STOPS_BEING_DETECTED",
             "zero_changed_results_is": ("proof the mapping is wrong, not a "
                                         "passing control")},
        ],
    }


def a08_run_a():
    audit, phase = "L1-A08", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    cases = [
        ("C1", "UNICODE",
         "the forbidden content expressed with a canonically equivalent but "
         "differently encoded sequence - a precomposed character against base "
         "plus combining mark"),
        ("C2", "PUNCTUATION",
         "the forbidden content interrupted by punctuation a human reads "
         "through - a soft hyphen, a zero-width joiner, a period between "
         "characters"),
        ("C3", "WHITESPACE",
         "non-breaking space, narrow no-break space and other whitespace a "
         "reader does not distinguish from a plain space"),
        ("C4", "LINE_BREAKS",
         "the forbidden content split across a line break, including CRLF"),
        ("C5", "HOMOGLYPH_OR_MIXED_ENCODING",
         "Latin characters replaced by visually identical characters from "
         "another script, or a mixed encoding"),
    ]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Design five edge cases that exist in no current test file, "
            "covering Unicode, punctuation, whitespace, line breaks and "
            "homoglyphs or mixed encoding; run them against the productive "
            "guard; record what it does. Each case is paired with its own "
            "negative counterpart."),
        "static_analysis": (
            "The guard is parsed, never imported, and its patterns are "
            "extracted so that each case can be aimed at a named pattern.\n\n"
            "The binding records that the five edge cases do not exist and "
            "must be authored. They are authored here, and for each the plan "
            "records the case identifier, the exact bytes in hex where they "
            "are not printable, the vector it exercises, why it is not a "
            "renaming of an existing fixture, and the expected verdict with "
            "its reason. 'Not a renaming' is established by searching the "
            "existing test corpus for each case's bytes before it is "
            "accepted.\n\n" + GUARD_SANDBOX_NOTE),
        "target": _guard_target(GUARD_V3),
        "steps": (
            [{"step_id": "parse_guard", "operation": "PYTHON_AST_PARSE",
              "control_role": "MEASUREMENT",
              "purpose": "Extract the patterns each case is aimed at.",
              "params": {"path": GUARD_V3}, "timeout_seconds": 120},
             _search_step("prove_cases_are_novel",
                          ("Search the existing test corpus for each case's "
                           "bytes. A case already present is a renaming and is "
                           "replaced before the run."),
                          ["AP17_make_poisoned_test_v3"],
                          root=proj("authoring"))]
            + [{"step_id": "run_case_%s" % cid.lower(),
                "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                "control_role": "MEASUREMENT",
                "purpose": "%s (%s): %s" % (cid, vector, description),
                "params": {"script": w("sandbox",
                                       "AP17_output_guardrail_v3.py"),
                           "args": ["--input", w("cases", "%s.md" % cid)]},
                "timeout_seconds": 300}
               for cid, vector, description in cases]
            + [
                {"step_id": "positive_control_unmodified_forbidden_content",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "POSITIVE",
                 "purpose": ("The unmodified forbidden content must be "
                             "detected. Every case is a variation on it, so if "
                             "the base case is missed the five results are "
                             "uninterpretable."),
                 "params": {"script": w("sandbox",
                                        "AP17_output_guardrail_v3.py"),
                            "args": ["--input", w("cases", "BASE.md")]},
                 "timeout_seconds": 300},
                {"step_id": "negative_control_innocent_arrangements",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "NEGATIVE",
                 "purpose": ("Legitimate text containing the same characters "
                             "in an innocent arrangement must not be detected. "
                             "Each of the five vectors has its own negative "
                             "counterpart."),
                 "params": {"script": w("sandbox",
                                        "AP17_output_guardrail_v3.py"),
                            "args": ["--corpus", w("cases", "negatives")]},
                 "timeout_seconds": 300},
                {"step_id": "mutation_control_specificity",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "MUTATION",
                 "purpose": ("For each case the guard detects, one character "
                             "is altered so it should no longer match. It must "
                             "not. This proves detection is specific rather "
                             "than incidental."),
                 "params": {"script": w("sandbox",
                                        "AP17_output_guardrail_v3.py"),
                            "args": ["--corpus", w("cases", "specificity")]},
                 "timeout_seconds": 300},
            ]),
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="five authored edge cases, each with a negative counterpart",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "A human-readable rendering of each case plus an explicit "
                    "statement of what a reader sees. The claim 'a reader "
                    "would read this as the forbidden content' is the oracle, "
                    "and it is stated per case rather than assumed."),
                allowed_reads=[GUARD_V3, proj("authoring")],
                allowed_writes=["work/L1-A08/RUN-A/", "evidence/L1-A08/RUN-A/"],
                notes=[GUARD_SANDBOX_NOTE,
                       "The binding records that the five cases do not exist "
                       "and must be authored. They are authored here and their "
                       "novelty is proved by search, not asserted."]),
            {"check_id": "five_cases_recorded",
             "question": "Are the five cases fully specified?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "cases": [{"case_id": cid, "vector": vector,
                        "description": description} for cid, vector, description
                       in cases],
             "required_result": ("Per case: identifier, exact bytes in hex "
                                 "where not printable, the vector exercised, "
                                 "why it is not a renaming, and the expected "
                                 "verdict with its reason.")},
            {"check_id": "novelty_proved",
             "question": "Is each case genuinely absent from the existing corpus?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "prove_cases_are_novel",
             "required_result": ("Established by searching the existing test "
                                 "corpus for each case's bytes. A case already "
                                 "present is replaced before the run.")},
            {"check_id": "positive_control",
             "question": "Is the base forbidden content detected?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_unmodified_forbidden_content",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the unmodified forbidden content",
             "expected_result": "DETECTED",
             "why": ("Every case is a variation on the base. If the base is "
                     "missed the five results mean nothing.")},
            {"check_id": "negative_control",
             "question": "Is innocent text using the same characters left alone?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_innocent_arrangements",
             "expected_exit_code": 0,
             "expected_result": "NO_DETECTIONS",
             "expected_failure_reason": ("the characters appear in an innocent "
                                         "arrangement; a detection here is a "
                                         "false positive and is reported as "
                                         "one"),
             "one_per_vector": True},
            {"check_id": "mutation_control",
             "question": "Is detection specific or incidental?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_specificity",
             "fixture": "work/L1-A08/RUN-A/cases/specificity/",
             "fixture_construction": ("for each detected case, one character "
                                      "altered so the content should no longer "
                                      "match"),
             "proof_the_fixture_differs": ("each altered case's SHA-256 differs "
                                           "from its original and the altered "
                                           "character is recorded"),
             "expected_result": "THE_ALTERED_CASES_ARE_NOT_DETECTED",
             "zero_changed_results_is": ("proof the detection is incidental, "
                                         "not a passing control")},
        ],
    }


def a09_run_a():
    audit, phase = "L1-A09", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    delimiters = [
        "start of string", "end of string", "ASCII space",
        "non-breaking space U+00A0", "narrow no-break space U+202F",
        "newline LF", "newline CRLF", "comma", "period", "colon", "semicolon",
        "opening parenthesis", "closing parenthesis", "double quote",
        "German opening quotation mark", "German closing quotation mark",
        "apostrophe", "typographic apostrophe", "hyphen-minus", "en dash",
        "em dash", "soft hyphen", "digit", "uppercase letter",
        "lowercase letter", "non-ASCII Unicode letter (umlaut)",
        "non-ASCII Unicode letter (sharp s)", "direct concatenation",
    ]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "For every pattern in the productive rule set, test boundary "
            "behaviour on both sides against the full delimiter inventory, and "
            "record false positives and false negatives separately. The "
            "expected verdict per case is stated by this audit in advance from "
            "the pattern semantics, never read off the guard's output."),
        "static_analysis": (
            "Both the guard and the payload scanner are parsed, never "
            "imported, and every pattern is extracted with its boundary "
            "constructs recorded verbatim. 'Every relevant article' is not a "
            "defined set; the pattern enumeration defines it, and the "
            "enumeration is the first thing recorded.\n\n"
            "CLAUDE.md section 10 records both failures this audit measures: a "
            "bare *bea* matching Projektbeauftragung, Beanstandung and "
            "Bearbeitung; and a regex without a quantifier failing to see "
            "/F1+0. The German compound set is therefore explicit in the "
            "matrix rather than left to the cross product.\n\n"
            + GUARD_SANDBOX_NOTE),
        "target": _guard_target(
            GUARD_V3,
            "The payload scanner is parsed as well, because the binding names "
            "both and the pattern set spans them."),
        "steps": [
            {"step_id": "parse_guard_patterns", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": ("Enumerate every pattern with its boundary "
                         "constructs. This enumeration defines the set."),
             "params": {"path": GUARD_V3}, "timeout_seconds": 120},
            {"step_id": "parse_scanner_patterns",
             "operation": "PYTHON_AST_PARSE", "control_role": "MEASUREMENT",
             "purpose": "The same, for the payload scanner's pattern set.",
             "params": {"path": proj("anonymization", "payload_scan.py")},
             "timeout_seconds": 120},
            {"step_id": "run_delimiter_cross_product",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Every pattern preceded by each delimiter, followed "
                         "by each delimiter, and both. The expected verdict "
                         "per case was stated in advance."),
             "params": {"script": w("sandbox", "boundary_matrix.py"),
                        "args": ["--cases", w("cases", "cross_product.jsonl")]},
             "timeout_seconds": 900},
            {"step_id": "run_german_compound_set",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("The pattern embedded in a longer German compound "
                         "word. This is the case that produced twelve false "
                         "hits and no real ones."),
             "params": {"script": w("sandbox", "boundary_matrix.py"),
                        "args": ["--cases", w("cases", "german_compounds.jsonl")]},
             "timeout_seconds": 600},
            {"step_id": "positive_control_pattern_matches_own_literal",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("Each pattern must match its own literal surrounded "
                         "by plain spaces. A pattern that does not is broken "
                         "independently of boundaries."),
             "params": {"script": w("sandbox", "boundary_matrix.py"),
                        "args": ["--cases", w("cases", "own_literal.jsonl")]},
             "timeout_seconds": 600},
            {"step_id": "negative_control_disjoint_string",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("Each pattern must not match a string sharing no "
                         "substring with it. This proves the harness is not "
                         "reporting matches indiscriminately."),
             "params": {"script": w("sandbox", "boundary_matrix.py"),
                        "args": ["--cases", w("cases", "disjoint.jsonl")]},
             "timeout_seconds": 600},
            {"step_id": "mutation_control_boundary_removed",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("For a pattern using a word boundary, the boundary "
                         "construct is removed in a sandbox copy and the "
                         "compound cases are re-run. The false-positive count "
                         "must rise. This proves the boundary construct is "
                         "what is being measured."),
             "params": {"script": w("sandbox", "boundary_matrix_no_boundary.py"),
                        "args": ["--cases", w("cases", "german_compounds.jsonl")]},
             "timeout_seconds": 600},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="pattern-by-delimiter cross product with verdicts stated in advance",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "The expected verdict per case, stated by this audit "
                    "before the run from the pattern semantics. Labels "
                    "produced by the tool under test are not labels."),
                allowed_reads=[GUARD_V3, proj("anonymization", "payload_scan.py")],
                allowed_writes=["work/L1-A09/RUN-A/", "evidence/L1-A09/RUN-A/"],
                notes=[WORD_BOUNDARY_NOTE, GUARD_SANDBOX_NOTE]),
            {"check_id": "delimiter_inventory",
             "question": "What is the delimiter inventory?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "delimiters": delimiters,
             "delimiter_count": len(delimiters),
             "required_result": ("The full inventory, applied on both sides and "
                                 "on both sides at once.")},
            {"check_id": "false_positives_and_negatives_separately",
             "question": "How are the two error kinds reported?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_delimiter_cross_product",
             "required_result": ("Two counts, never one score. A pattern that "
                                 "is both overbroad and incomplete would show "
                                 "as neither under a single number.")},
            {"check_id": "german_compounds",
             "question": "Does the pattern match inside a longer German word?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_german_compound_set",
             "specification_reference": ("CLAUDE.md section 10: a bare *bea* "
                                         "matched Projektbeauftragung, "
                                         "Beanstandung and Bearbeitung - twelve "
                                         "hits, none real"),
             "required_result": "Reported per pattern with the compound used."},
            {"check_id": "positive_control",
             "question": "Does each pattern match its own literal?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_pattern_matches_own_literal",
             "expected_exit_code": 0,
             "expected_result": "EVERY_PATTERN_MATCHES_ITS_OWN_LITERAL"},
            {"check_id": "negative_control",
             "question": "Does a disjoint string stay unmatched?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_disjoint_string",
             "expected_exit_code": 0,
             "expected_result": "NO_MATCHES",
             "expected_failure_reason": ("the string shares no substring with "
                                         "the pattern; a match here would mean "
                                         "the harness reports matches "
                                         "indiscriminately")},
            {"check_id": "mutation_control",
             "question": "Is the boundary construct what is being measured?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_boundary_removed",
             "expected_exit_code": 0,
             "fixture": "work/L1-A09/RUN-A/sandbox/boundary_matrix_no_boundary.py",
             "fixture_construction": ("the same matrix runner against a pattern "
                                      "set with the word-boundary construct "
                                      "removed"),
             "proof_the_fixture_differs": ("its SHA-256 differs and the removed "
                                           "construct is recorded verbatim"),
             "expected_result": "THE_FALSE_POSITIVE_COUNT_RISES",
             "zero_changed_results_is": ("proof the boundary construct was not "
                                         "what produced the earlier counts, "
                                         "not a passing control")},
        ],
    }


# ================================================== reference-checker group
CHECKER = proj("authoring", "AP18_referenzpruefung.py")
BGH_REGISTER = proj("authoring", "bgh_referenz.json")

CHECKER_SANDBOX_NOTE = (
    "PYTHON_SCRIPT_RUN_SANDBOX runs a script under work/ and nowhere else, so "
    "the approved phase first copies the checker to "
    "work/<audit>/RUN-A/sandbox/ and records the copy's digest beside the "
    "original's. The original in authoring/ is read and never written to.")


def _checker_target(note=""):
    return {
        "path": CHECKER, "sha256": sha_of(CHECKER),
        "identity_evidence": (
            "The binding records this path as a candidate with this digest. It "
            "is bound as the anchor; which copy is productive is L1-A10's "
            "question and a filename does not answer it."
            + (" " + note if note else "")),
    }


def a11_run_a():
    audit, phase = "L1-A11", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    coverage = ref("REF-05_COVERAGE.json")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Compare the register the checker relies on against the "
            "operator-supplied official roster, and identify missing entries, "
            "obsolete entries, spelling and normalisation differences, and "
            "role or date validity mismatches. The roster is the only "
            "admissible oracle."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The register the "
            "checker relies on is read as data, and the checker itself is "
            "parsed to establish which register it reads and how it "
            "normalises names before comparing them - a comparison that does "
            "not state its normalisation is not a comparison.\n\n"
            "What REF-05 is, exactly. The artefact accepted into this package "
            "is references/REF-05_COVERAGE.json, a coverage record. It binds "
            "the saved official BGH annual page and the current annual PDF, "
            "records the six listed 2026 Presidium decision dates, and "
            "establishes publication coverage through 2026-08-27 with no "
            "decision falling in the delta interval. It carries the SHA-256 of "
            "the operator-supplied supplement manifest.\n\n"
            "The roster document bytes themselves are not in the package. They "
            "are in the operator intake area at the supplement root the "
            "coverage record names, which is outside this package's read "
            "roots: automation.path_policy admits PROJECT_ROOT, DISCOVERY_ROOT "
            "and LEVEL1_ROOT and refuses everything else, so no step here can "
            "reach them directly. The approved phase's preparation stages the "
            "roster into work/L1-A11/RUN-A/roster/ and verifies the staged "
            "bytes against the bound supplement manifest digest before any "
            "comparison runs. If that staging has not happened, or the staged "
            "bytes do not verify, the phase is "
            "BLOCKED_MISSING_OFFICIAL_REFERENCE and no comparison is "
            "attempted - a four-set comparison against a roster that was never "
            "read would produce four empty sets and look like agreement.\n\n"
            "REF-05 was accepted as a focused official-coverage delta record "
            "rather than as a complete roster of every senate and every "
            "period. A comparison outside what the coverage record states is "
            "reported as outside coverage rather than as a missing entry: a "
            "name absent from material that never claimed to list it is not an "
            "absence.\n\n"
            "bgh_referenz.json is not an oracle here: it is one side of the "
            "comparison. Neither is model knowledge, and the network is never "
            "reached.\n\n" + CHECKER_SANDBOX_NOTE),
        "target": _checker_target(),
        "steps": [
            {"step_id": "parse_checker", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": ("Establish which register the checker reads and how "
                         "it normalises names. Parse, do not import."),
             "params": {"path": CHECKER}, "timeout_seconds": 120},
            {"step_id": "read_register", "operation": "PARSE_JSON_READONLY",
             "control_role": "MEASUREMENT",
             "purpose": ("Read the register as data. It is one side of the "
                         "comparison, never the arbiter."),
             "params": {"path": BGH_REGISTER}, "timeout_seconds": 120},
            {"step_id": "verify_coverage_record_digest",
             "operation": "SHA256_FILE", "control_role": "MEASUREMENT",
             "purpose": ("Verify the accepted REF-05 coverage record against "
                         "references/manifest.json before it is used."),
             "params": {"path": coverage}, "timeout_seconds": 120},
            {"step_id": "read_coverage_record",
             "operation": "PARSE_JSON_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Read what the accepted official material covers, and "
                         "the supplement manifest digest the staged roster must "
                         "verify against, before any absence is called an "
                         "absence."),
             "params": {"path": coverage}, "timeout_seconds": 120},
            {"step_id": "verify_staged_roster",
             "operation": "COMPARE_HASHES", "control_role": "MEASUREMENT",
             "purpose": ("Verify the staged roster against the supplement "
                         "manifest digest the coverage record binds. A roster "
                         "that does not verify is not read."),
             "params": {"left": w("roster", "SUPPLEMENT_MANIFEST.sha256"),
                        "right": w("roster", "SUPPLEMENT_MANIFEST.sha256"),
                        "expected_sha256": (
                            "374e18e51923327a25ad7ad285ae708db9ea1b3d9845c085"
                            "194ae813db2f0e23"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 300},
            {"step_id": "compute_four_sets",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Present in both; in the register only, which is "
                         "obsolete; in the roster only, which is missing; and "
                         "present in both but differing in spelling, "
                         "normalisation, role or date validity."),
             "params": {"script": w("sandbox", "compare_register.py"),
                        "args": ["--register", BGH_REGISTER,
                                 "--roster", w("roster"),
                                 "--coverage", coverage,
                                 "--out", w("four_sets.json")]},
             "timeout_seconds": 600},
            {"step_id": "positive_control_matched_entry",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("An entry known to be in both must be reported as "
                         "matched. This proves the comparison can see "
                         "agreement."),
             "params": {"script": w("sandbox", "compare_register.py"),
                        "args": ["--case", "known-matched"]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_fabricated_name",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("A fabricated name inserted into the comparison input "
                         "must be reported as present-in-register-only. This "
                         "proves the comparison can see disagreement."),
             "params": {"script": w("sandbox", "compare_register.py"),
                        "args": ["--case", "fabricated-name"]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_one_character",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("One character of a matched entry altered: it must "
                         "move from the matched set to the differing set "
                         "rather than silently staying matched."),
             "params": {"script": w("sandbox", "compare_register.py"),
                        "args": ["--case", "one-character-altered"]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="four-set comparison against the official roster",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                references=bind([coverage, MANIFEST_JSON]),
                reference_ids=["REF-05"],
                limitations=[
                    "The artefact accepted into this package is the coverage "
                    "record references/REF-05_COVERAGE.json, not the roster "
                    "document. The record establishes publication coverage "
                    "through 2026-08-27 and binds the supplement manifest "
                    "digest; it does not itself enumerate senate membership.",
                    "The roster bytes are in the operator intake area, outside "
                    "the read roots automation.path_policy admits. They are "
                    "staged into work/L1-A11/RUN-A/roster/ by the approved "
                    "phase's preparation and verified against the bound "
                    "supplement manifest digest. Unstaged or unverified, the "
                    "phase is BLOCKED_MISSING_OFFICIAL_REFERENCE.",
                    "REF-05 was accepted as a focused official-coverage delta "
                    "record, not as a complete roster of every senate and "
                    "every period. A comparison outside that coverage is "
                    "reported as outside coverage, never as a missing entry.",
                    "Browser-extension-injected markup in the saved HTML is "
                    "excluded from evidence. Only BGH page content, the "
                    "canonical URL, the annual list, the official PDF link and "
                    "the BGH generation marker are relied upon."],
                human_decisions=[
                    "The operator settled the REF-05 period question and "
                    "accepted the official-coverage closure recorded in "
                    "references/REF-05_COVERAGE.json, with the six listed 2026 "
                    "Presidium decision dates and coverage through 2026-08-27. "
                    "That decision is not re-opened here."],
                independent_oracle=(
                    "The operator-supplied official roster bound by REF-05 and "
                    "nothing else. Neither the register, nor "
                    "bgh_referenz.json, nor any docs/ report, nor model "
                    "knowledge."),
                allowed_reads=[CHECKER, BGH_REGISTER, "references/REF-05_COVERAGE.json",
                               "work/L1-A11/RUN-A/roster/"],
                allowed_writes=["work/L1-A11/RUN-A/", "evidence/L1-A11/RUN-A/"],
                forbidden_operations=["NETWORK_REQUEST"],
                notes=[CHECKER_SANDBOX_NOTE,
                       "No step reaches the operator intake area directly; "
                       "path_policy refuses it and the plan does not try."]),
            {"check_id": "roster_available_and_verified",
             "question": "Is the roster staged and does it verify?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "verify_staged_roster",
             "expected_sha256": ("374e18e51923327a25ad7ad285ae708db9ea1b3d9845"
                                 "c085194ae813db2f0e23"),
             "required_result": ("The staged bytes verify against the "
                                 "supplement manifest digest the coverage "
                                 "record binds."),
             "verdict_effect": ("If they do not, the phase is "
                                "BLOCKED_MISSING_OFFICIAL_REFERENCE and no "
                                "comparison runs. Four empty sets would look "
                                "like agreement.")},
            {"check_id": "four_sets",
             "question": "How do the register and the roster differ?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "compute_four_sets",
             "sets": ["present in both", "register only (obsolete)",
                      "roster only (missing)",
                      "both but differing in spelling, normalisation, role or "
                      "date validity"],
             "required_result": "Four sets, each enumerated, never a single score."},
            {"check_id": "normalisation_stated",
             "question": "How were names normalised before comparison?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "parse_checker",
             "required_result": ("Stated explicitly, including Unicode normal "
                                 "form. A comparison whose normalisation is "
                                 "unstated cannot be reproduced.")},
            {"check_id": "coverage_boundary_respected",
             "question": "Is every absence inside the roster's coverage?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "read_coverage_record",
             "coverage_through": "2026-08-27",
             "listed_decision_dates": ["2026-01-27", "2026-02-24", "2026-04-28",
                                       "2026-06-17", "2026-07-07", "2026-08-11"],
             "required_result": ("Each reported absence is inside what the "
                                 "coverage record says the material covers. "
                                 "Anything outside is labelled "
                                 "OUTSIDE_ACCEPTED_COVERAGE.")},
            {"check_id": "positive_control",
             "question": "Can the comparison see agreement?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_matched_entry",
             "expected_exit_code": 0,
             "expected_result": "THE_KNOWN_ENTRY_IS_REPORTED_MATCHED"},
            {"check_id": "negative_control",
             "question": "Can the comparison see disagreement?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_fabricated_name",
             "expected_exit_code": 0,
             "fixture": "a fabricated name inserted into the comparison input",
             "expected_result": "REPORTED_AS_PRESENT_IN_REGISTER_ONLY",
             "expected_failure_reason": ("the name exists in no official "
                                         "roster because it was invented for "
                                         "this control")},
            {"check_id": "mutation_control",
             "question": "Does a one-character change move an entry between sets?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_one_character",
             "fixture": "a matched entry with one character altered",
             "proof_the_fixture_differs": ("the altered string differs from the "
                                           "original and both are recorded"),
             "expected_result": "MOVES_FROM_MATCHED_TO_DIFFERING",
             "zero_changed_results_is": ("proof that the comparison normalises "
                                         "the difference away silently, not a "
                                         "passing control")},
        ],
    }


def a12_run_a():
    audit, phase = "L1-A12", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    labels = ref("REF-07_labels.jsonl")
    corpus = ref("REF-07_reuters21578.tar.gz")
    inventory = ref("REF-07_collection_inventory.json")
    derivation = ref("REF-07_label_derivation.json")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Measure the checker's true positives, false positives, true "
            "negatives and false negatives against the operator-supplied "
            "corpus with independent labels, and identify the specific "
            "patterns that are overbroad. All four counts are reported; never "
            "a single score."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The checker's pattern "
            "set is extracted by AST so that every false positive can be "
            "attributed to a named pattern rather than to the checker as a "
            "whole.\n\n"
            "REF-07 supplies the corpus and the independent labels. The labels "
            "were produced without running the checker, and "
            "REF-07_label_derivation.json records how - the checker may never "
            "label its own evaluation corpus, because a corpus labelled by the "
            "tool under test agrees with it by construction.\n\n"
            "The corpus origin, document count, total length and per-document "
            "hashes are recorded before any measurement, so that a later "
            "disagreement can be located in a document rather than in a "
            "total.\n\n"
            "The corpus is a gzipped tar archive of 22 SGML members, not a "
            "ZIP. Its members are enumerated with TAR_LIST, which reads the "
            "archive in-process. ARCHIVE_EXTRACT_SANDBOX is not used here: it "
            "invokes unzip, and unzip on a tarball reports that the "
            "end-of-central-directory signature was not found - a failure "
            "about the tool's format assumption that says nothing about the "
            "corpus. The pre-freeze rehearsal executed the step and found "
            "exactly that, which is why the operation is TAR_LIST.\n\n"
            "Extraction into work/L1-A12/RUN-A/corpus/ is preparation the "
            "approved phase performs, as with every other sandbox copy in this "
            "package.\n\n" + CHECKER_SANDBOX_NOTE),
        "target": _checker_target(),
        "steps": [
            {"step_id": "parse_checker_patterns",
             "operation": "PYTHON_AST_PARSE", "control_role": "MEASUREMENT",
             "purpose": ("Extract the pattern set, so false positives can be "
                         "attributed per pattern."),
             "params": {"path": CHECKER}, "timeout_seconds": 120},
            {"step_id": "verify_corpus_digest", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": "Verify the corpus against references/manifest.json.",
             "params": {"path": corpus}, "timeout_seconds": 300},
            {"step_id": "read_collection_inventory",
             "operation": "PARSE_JSON_READONLY", "control_role": "MEASUREMENT",
             "purpose": ("Corpus origin, document count, total length and "
                         "per-document hashes, recorded before measurement."),
             "params": {"path": inventory}, "timeout_seconds": 120},
            {"step_id": "read_label_derivation",
             "operation": "PARSE_JSON_READONLY", "control_role": "ORACLE",
             "purpose": ("How the independent labels were produced, and by "
                         "what, recorded as the oracle's provenance."),
             "params": {"path": derivation}, "timeout_seconds": 120},
            {"step_id": "list_corpus_members", "operation": "TAR_LIST",
             "control_role": "MEASUREMENT",
             "purpose": ("Enumerate the archive's members without extracting, "
                         "and reconcile them against the collection "
                         "inventory's recorded member list."),
             "params": {"path": corpus},
             "timeout_seconds": 600},
            {"step_id": "run_checker_over_corpus",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "Run the checker over the corpus and record raw output.",
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--corpus", w("corpus"),
                                 "--out", w("checker_output.json")]},
             "timeout_seconds": 900},
            {"step_id": "positive_control_known_form_citation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A document containing a citation of a form the "
                         "checker is known to handle must yield a true "
                         "positive."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--corpus", w("controls", "known_form")]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_no_citation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("A document containing no citation at all must yield "
                         "no hits. Hits here mean the pattern set matches "
                         "ordinary prose."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--corpus", w("controls", "no_citation")]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_narrow_one_pattern",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("One overbroad pattern narrowed in a sandbox copy: "
                         "the false-positive count attributed to it must fall. "
                         "This proves the attribution is correct."),
             "params": {"script": w("sandbox",
                                    "AP18_referenzpruefung_narrowed.py"),
                        "args": ["--corpus", w("corpus"),
                                 "--out", w("narrowed_output.json")]},
             "timeout_seconds": 900},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="confusion matrix against independently labelled corpus",
                executable="/usr/bin/python3 -I -B against a sandbox copy; /usr/bin/unzip for extraction",
                references=bind([corpus, labels, inventory, derivation,
                                 ref("REF-07_MANIFEST.sha256"), MANIFEST_JSON]),
                reference_ids=["REF-07"],
                limitations=[
                    "REF-07 is a general news corpus, not a corpus of German "
                    "legal writing. It measures whether the pattern set fires "
                    "on ordinary prose; it does not measure recall over the "
                    "citation forms a legal document would contain, and the "
                    "result is reported with that scope stated.",
                    "The labels are independent of the checker by "
                    "construction, and REF-07_label_derivation.json records "
                    "how they were produced."],
                independent_oracle=(
                    "The independent labels in REF-07, produced without the "
                    "checker. The checker may never label its own evaluation "
                    "corpus."),
                allowed_reads=[CHECKER, "references/REF-07_*"],
                allowed_writes=["work/L1-A12/RUN-A/", "evidence/L1-A12/RUN-A/"],
                notes=[CHECKER_SANDBOX_NOTE]),
            {"check_id": "confusion_matrix",
             "question": "What are the four counts?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_checker_over_corpus",
             "archive_members_expected": 32,
             "sgm_members_expected": 22,
             "document_count_expected": 21578,
             "required_result": ("TP, FP, TN and FN, all four reported. Never "
                                 "a single score: a single number cannot "
                                 "distinguish an overbroad pattern set from an "
                                 "incomplete one."),
             "corpus_recorded": ("origin, document count, total length and "
                                 "per-document hashes")},
            {"check_id": "false_positive_attribution",
             "question": "Which pattern produced each false positive?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_checker_patterns",
             "required_result": ("Every false positive attributed to a named "
                                 "pattern. An unattributed false positive is "
                                 "not yet a finding about any pattern.")},
            {"check_id": "positive_control",
             "question": "Does a handled citation form yield a true positive?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_form_citation",
             "expected_exit_code": 0,
             "expected_result": "TRUE_POSITIVE"},
            {"check_id": "negative_control",
             "question": "Does prose with no citation yield no hits?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_no_citation",
             "expected_exit_code": 0,
             "expected_result": "ZERO_HITS",
             "expected_failure_reason": ("the document contains no citation; "
                                         "hits here mean the pattern set "
                                         "matches ordinary prose")},
            {"check_id": "mutation_control",
             "question": "Is the false-positive attribution correct?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_narrow_one_pattern",
             "fixture": "work/L1-A12/RUN-A/sandbox/AP18_referenzpruefung_narrowed.py",
             "fixture_construction": ("the sandbox copy with one overbroad "
                                      "pattern narrowed and nothing else "
                                      "changed"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "sandbox copy's and the narrowed "
                                           "pattern is recorded before and "
                                           "after"),
             "expected_result": "THE_ATTRIBUTED_FALSE_POSITIVE_COUNT_FALLS",
             "zero_changed_results_is": ("proof the attribution was wrong, not "
                                         "a passing control")},
        ],
    }


def a13_run_a():
    audit, phase = "L1-A13", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    mandatory = ["XY ZR 999/99", "ABC ZR 1/20", "IIII ZR 1/20", "0 ZR 1/20",
                 "14 StR 1/20"]
    real_forms = ["20 F 15/22", "I-25 U 75/25", "16 U 139/23"]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Determine whether invented case references are blocked, using the "
            "five mandatory exact cases plus systematic variants, and separate "
            "'blocked' from 'never examined'. Those two outcomes look "
            "identical from the outside and mean opposite things."),
        "static_analysis": (
            "The checker is parsed, never imported. Its recognised senate set "
            "and its citation grammar are extracted, because the decisive "
            "question is whether an input it does not recognise is reported as "
            "passed or as not examined.\n\n"
            "CLAUDE.md section 10 records the failure this audit measures "
            "directly: a BGH senate rule applied to every court declared "
            "20 F 15/22, I-25 U 75/25 and 16 U 139/23 impossible. Those three "
            "real forms are in the matrix by name.\n\n"
            "The five mandatory cases are fabrications by construction: "
            + "; ".join(mandatory) + ". Their status as fabrications does not "
            "depend on any lookup, which is what makes them usable as an "
            "oracle.\n\n"
            "The binding records an open question - whether the checker has a "
            "distinct output state for 'not examined'. It is answered from the "
            "parse and from the run, and if no such state exists that absence "
            "is itself the finding.\n\n" + CHECKER_SANDBOX_NOTE),
        "target": _checker_target(),
        "steps": [
            {"step_id": "parse_checker_grammar",
             "operation": "PYTHON_AST_PARSE", "control_role": "MEASUREMENT",
             "purpose": ("Extract the recognised senate set, the citation "
                         "grammar and the output states the checker can "
                         "produce."),
             "params": {"path": CHECKER}, "timeout_seconds": 120},
            {"step_id": "run_five_mandatory_cases",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "The five mandatory fabricated citations, exactly as specified.",
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "mandatory.jsonl")]},
             "timeout_seconds": 300},
            {"step_id": "run_systematic_variants",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Each mandatory case with leading and trailing "
                         "punctuation, single, double and no spaces, split "
                         "across a line break, with non-breaking and narrow "
                         "no-break space, in upper and lower case, with a "
                         "malformed separator, and with a vgl. prefix and a "
                         "Rn. suffix."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "variants.jsonl")]},
             "timeout_seconds": 600},
            {"step_id": "run_court_coverage_set",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("OLG, LG, BAG, BSG, BFH and EuGH forms, plus the three "
                         "real forms a BGH senate rule wrongly declared "
                         "impossible."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "court_coverage.jsonl")]},
             "timeout_seconds": 600},
            {"step_id": "positive_control_real_wellformed_citation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A real, well-formed BGH citation of a form the "
                         "checker handles must be examined and pass. This "
                         "proves the checker is evaluating."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "real_citation.jsonl")]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_prose_without_citations",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("Ordinary prose containing no citation must produce no "
                         "verdicts at all."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "plain_prose.jsonl")]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_outside_senate_set",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("A citation the checker flags, altered to a form "
                         "outside its recognised senate set. If it changes "
                         "from flagged to passed rather than to never "
                         "examined, the silent-skip defect is demonstrated "
                         "directly."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--cases", w("cases", "outside_senate.jsonl")]},
             "timeout_seconds": 300},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="fabricated-citation matrix with blocked and never-examined kept apart",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "The structural rules of German case-reference formation, "
                    "stated by this audit in advance per input, together with "
                    "the fact that the five mandatory cases are fabrications "
                    "by construction. Not the checker's own verdict."),
                allowed_reads=[CHECKER, BGH_REGISTER],
                allowed_writes=["work/L1-A13/RUN-A/", "evidence/L1-A13/RUN-A/"],
                notes=[CHECKER_SANDBOX_NOTE,
                       "The five mandatory cases are fabrications by "
                       "construction, so their expected classification does "
                       "not depend on any lookup succeeding."]),
            {"check_id": "blocked_versus_never_examined",
             "question": "Does the checker distinguish blocked from never examined?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_checker_grammar",
             "required_result": ("Answered from the parse and from the run. If "
                                 "no distinct state exists, that absence is "
                                 "the finding."),
             "why": ("A fabricated citation that was never examined and one "
                     "that was examined and passed produce the same silence, "
                     "and mean opposite things.")},
            {"check_id": "five_mandatory_cases",
             "question": "What does the checker do with each fabrication?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_five_mandatory_cases",
             "cases": mandatory,
             "required_result": ("One classification per case: blocked, "
                                 "passed, or never examined.")},
            {"check_id": "court_coverage",
             "question": "Which courts does the checker actually cover?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_court_coverage_set",
             "real_forms_that_must_not_be_declared_impossible": real_forms,
             "specification_reference": ("CLAUDE.md section 10: the BGH senate "
                                         "rule applied to all courts declared "
                                         "these three real forms impossible"),
             "required_result": ("Per court family: covered, not covered, or "
                                 "wrongly rejected.")},
            {"check_id": "positive_control",
             "question": "Is a real well-formed citation examined and passed?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_real_wellformed_citation",
             "expected_exit_code": 0,
             "expected_result": "EXAMINED_AND_PASSED",
             "why": "This is what proves the checker is evaluating at all."},
            {"check_id": "negative_control",
             "question": "Does prose without citations produce verdicts?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_prose_without_citations",
             "expected_exit_code": 0,
             "expected_result": "NO_VERDICTS_AT_ALL",
             "expected_failure_reason": ("there is no citation to examine; "
                                         "verdicts here would mean the checker "
                                         "is matching ordinary prose")},
            {"check_id": "mutation_control",
             "question": "What happens to a citation outside the senate set?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_outside_senate_set",
             "fixture": "work/L1-A13/RUN-A/cases/outside_senate.jsonl",
             "fixture_construction": ("a citation the checker flags, altered "
                                      "only in its senate designation"),
             "proof_the_fixture_differs": ("the altered citation differs from "
                                           "the flagged one in exactly the "
                                           "recorded characters"),
             "expected_result": "CHANGES_TO_NEVER_EXAMINED_NOT_TO_PASSED",
             "verdict_effect": ("A change to 'passed' demonstrates the "
                                "silent-skip defect directly and forbids "
                                "PASS."),
             "zero_changed_results_is": "a measurement error, not a pass"},
        ],
    }


def a14_run_a():
    audit, phase = "L1-A14", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    doc = ref("REF-06_S01.docx")
    SOURCE_BOUND = ("9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc"
                    "48722675")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Independently enumerate and classify all citations in the "
            "recovered checker input, compute the BGH count without the "
            "production counter, compare, and record every disagreement. The "
            "source-bound structural oracle is the DOCX with SHA-256 "
            + SOURCE_BOUND + ", 165 total citation occurrences and 64 unique "
            "citations."),
        "static_analysis": (
            "No module under PROJECT_ROOT is imported. The document is located "
            "in references/ as REF-06 and its digest is verified against "
            "references/manifest.json and against the source-bound value "
            + SOURCE_BOUND + " before anything else. A hash mismatch is "
            "BLOCKED; the document is client material and is never copied into "
            "a report.\n\n"
            "Page identity is two separate measurements of the same hash-bound "
            "file and they are kept apart: Word extended-properties metadata "
            "stores 111 pages, while prior independent visible-pagination "
            "parsing resolves 'Seite 1 von 138' through 'Seite 138 von 138'. "
            "Both are recorded. A page-measurement discrepancy alone does not "
            "override exact hash identity and original checker-input "
            "provenance, and it is not reported as evidence that the document "
            "is the wrong one.\n\n"
            "The document's text is extracted independently in the sandbox - "
            "unzip and parse word/document.xml with external entities and DTD "
            "disabled - and the citation grammar this audit states is applied "
            "to it. The production counter is never the oracle, and neither is "
            "any prior report under docs/.\n\n" + CHECKER_SANDBOX_NOTE),
        "target": _checker_target(
            "REF-06 is the input document, not the target; the target is the "
            "checker whose count is under audit."),
        "steps": [
            {"step_id": "verify_document_digest", "operation": "SHA256_FILE",
             "control_role": "MEASUREMENT",
             "purpose": ("Verify the document against the manifest and against "
                         "the source-bound value before any extraction."),
             "params": {"path": doc, "expected_sha256": SOURCE_BOUND},
             "timeout_seconds": 300},
            {"step_id": "extract_document_parts",
             "operation": "ARCHIVE_EXTRACT_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": "Extract the OOXML parts into the audit work directory only.",
             "params": {"archive": doc, "dest": w("extracted")},
             "timeout_seconds": 600},
            {"step_id": "parse_document_xml", "operation": "DOCX_PARSE_SANDBOX",
             "control_role": "ORACLE",
             "purpose": ("Read word/document.xml with external entities and "
                         "DTD disabled, and reconstruct the text run by run."),
             "params": {"path": doc, "resolve_entities": False,
                        "load_dtd": False, "no_network": True},
             "timeout_seconds": 600},
            {"step_id": "read_extended_properties",
             "operation": "XML_PARSE_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Word extended-properties page count, recorded as its "
                         "own measurement and not merged with the visible "
                         "pagination."),
             "params": {"path": w("extracted", "docProps", "app.xml"),
                        "resolve_entities": False, "load_dtd": False,
                        "no_network": True},
             "timeout_seconds": 300},
            {"step_id": "independent_citation_enumeration",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "ORACLE",
             "purpose": ("Enumerate and classify every citation by the grammar "
                         "this audit states, without the production counter."),
             "params": {"script": w("sandbox", "independent_citations.py"),
                        "args": ["--text", w("extracted_text.txt"),
                                 "--out", w("independent_counts.json")]},
             "timeout_seconds": 600},
            {"step_id": "production_counter",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Run the checker's own counter over the same text, "
                         "for comparison only."),
             "params": {"script": w("sandbox", "AP18_referenzpruefung.py"),
                        "args": ["--text", w("extracted_text.txt"),
                                 "--out", w("production_counts.json")]},
             "timeout_seconds": 600},
            {"step_id": "positive_control_seeded_citation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A synthetic copy seeded with one additional "
                         "unmistakable BGH citation: both methods must "
                         "increase by one. This proves both respond."),
             "params": {"script": w("sandbox", "independent_citations.py"),
                        "args": ["--text", w("controls", "seeded_plus_one.txt"),
                                 "--out", w("controls", "seeded_counts.json")]},
             "timeout_seconds": 600},
            {"step_id": "negative_control_no_citations",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": "Over a text with no citations, both methods must report zero.",
             "params": {"script": w("sandbox", "independent_citations.py"),
                        "args": ["--text", w("controls", "no_citations.txt"),
                                 "--out", w("controls", "zero_counts.json")]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_removed_citation",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("A synthetic copy with one BGH citation removed: the "
                         "independent count must fall by one. If it does not, "
                         "the independent method is not independent enough to "
                         "be an oracle."),
             "params": {"script": w("sandbox", "independent_citations.py"),
                        "args": ["--text", w("controls", "removed_one.txt"),
                                 "--out", w("controls", "removed_counts.json")]},
             "timeout_seconds": 600},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="independent citation grammar against the production counter",
                executable="/usr/bin/python3 -I -B against a sandbox copy; /usr/bin/unzip for extraction",
                references=bind([doc, MANIFEST_JSON]),
                reference_ids=["REF-06"],
                limitations=[
                    "The document is client material. It is read in the "
                    "sandbox and never copied into a report; only counts and "
                    "classifications leave the work directory.",
                    "Page identity is two separate measurements of the same "
                    "hash-bound file: Word extended-properties metadata stores "
                    "111 pages, and prior independent visible-pagination "
                    "parsing resolves 138. Both are recorded and neither is "
                    "corrected into the other.",
                    "A page-measurement discrepancy alone does not override "
                    "exact hash identity and original checker-input "
                    "provenance."],
                human_decisions=[
                    "The operator supplied REF-06 as the recovered checker "
                    "input and its identity is bound by the source-bound "
                    "SHA-256 " + SOURCE_BOUND + "."],
                independent_oracle=(
                    "The independent citation grammar and manual "
                    "classification produced by this audit. The production "
                    "counter may never serve as the oracle, and neither may "
                    "any prior report under docs/."),
                allowed_reads=[CHECKER, "references/REF-06_S01.docx"],
                allowed_writes=["work/L1-A14/RUN-A/", "evidence/L1-A14/RUN-A/"],
                notes=[CHECKER_SANDBOX_NOTE]),
            {"check_id": "document_identity",
             "question": "Is this the source-bound document?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "verify_document_digest",
             "expected_sha256": SOURCE_BOUND,
             "expected_exit_code": 0,
             "required_result": ("The digest matches both the manifest and the "
                                 "source-bound value. A mismatch is BLOCKED."),
             "structural_oracle": {"total_citation_occurrences": 165,
                                   "unique_citations": 64}},
            {"check_id": "page_identity_two_measurements",
             "question": "How many pages does the document have?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "read_extended_properties",
             "word_extended_properties_pages": 111,
             "visible_pagination_pages": 138,
             "required_result": ("Both recorded, as two measurements of the "
                                 "same hash-bound file. Neither is corrected "
                                 "into the other and the discrepancy is not "
                                 "reported as a document-identity failure.")},
            {"check_id": "independent_versus_production_count",
             "question": "Do the two counts agree, and where do they differ?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "independent_citation_enumeration",
             "required_result": ("Both counts reported with every "
                                 "disagreement located at the citation that "
                                 "produced it, never as a difference of "
                                 "totals.")},
            {"check_id": "positive_control",
             "question": "Do both methods respond to an added citation?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_seeded_citation",
             "expected_exit_code": 0,
             "fixture": "work/L1-A14/RUN-A/controls/seeded_plus_one.txt",
             "fixture_construction": ("the extracted text with one unmistakable "
                                      "BGH citation added"),
             "expected_result": "BOTH_COUNTS_INCREASE_BY_EXACTLY_ONE"},
            {"check_id": "negative_control",
             "question": "Do both methods report zero on citation-free text?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_no_citations",
             "expected_exit_code": 0,
             "expected_result": "BOTH_REPORT_ZERO",
             "expected_failure_reason": ("the text contains no citation; a "
                                         "nonzero count would mean the method "
                                         "matches ordinary prose")},
            {"check_id": "mutation_control",
             "question": "Is the independent method genuinely independent?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_removed_citation",
             "fixture": "work/L1-A14/RUN-A/controls/removed_one.txt",
             "fixture_construction": ("the extracted text with one BGH "
                                      "citation removed"),
             "proof_the_fixture_differs": ("its SHA-256 differs from the "
                                           "extracted text's and the removed "
                                           "citation is recorded"),
             "expected_result": "THE_INDEPENDENT_COUNT_FALLS_BY_EXACTLY_ONE",
             "zero_changed_results_is": ("proof that the independent method is "
                                         "not independent enough to be an "
                                         "oracle, not a passing control")},
        ],
    }


# ================================================== pytest and DOCX group
FILTER = proj("ap18", "AP18_eingangsfilter.py")
TEST_INJECTION = proj("ap18", "AP18_test_injection.py")
PYTEST_INI = proj("pytest.ini")
GOLDEN_TEST = proj("anonymization", "golden", "payload_scan_golden_test.py")

SANDBOX_TREE_NOTE = (
    "All pytest work happens in a sandbox copy of the tree under the audit "
    "work directory. A collection run creates __pycache__ and .pytest_cache, "
    "and creating those in PROJECT_ROOT would be a write into a root this "
    "package treats as read-only.")


def a15_run_a():
    audit, phase = "L1-A15", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Establish how many tests are collected, how many execute, how "
            "many meaningful assertions run, and whether the test can fail at "
            "all - then prove it detects a controlled mutation. An exit code "
            "of zero from a file that only defines functions is the defect, "
            "not the result."),
        "static_analysis": (
            "The test file is parsed, never imported, and its assertions are "
            "counted statically. CLAUDE.md section 10 records the exact shape "
            "this audit looks for: two test functions, no __main__ block, and "
            "a direct invocation that defines them and runs nothing while "
            "exiting zero.\n\n"
            "The static assertion count is the number that the runtime "
            "behaviour is checked against. A suite reporting passes with fewer "
            "assertions executed than the file contains is reporting on code "
            "it did not reach.\n\n" + SANDBOX_TREE_NOTE),
        "target": {
            "path": TEST_INJECTION, "sha256": sha_of(TEST_INJECTION),
            "identity_evidence": (
                "bindings/L1-A15.binding.json records this path with this "
                "digest and the file on disk hashes to the same value."),
        },
        "steps": [
            {"step_id": "parse_test_file", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": ("Count assertions statically and record whether a "
                         "__main__ block exists. Parse, do not import."),
             "params": {"path": TEST_INJECTION}, "timeout_seconds": 120},
            {"step_id": "collect_in_sandbox", "operation": "PYTEST_COLLECT_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Collected count and the complete collection report, "
                         "including collection errors."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "ap18", "AP18_test_injection.py")},
             "timeout_seconds": 600},
            {"step_id": "run_in_sandbox", "operation": "PYTEST_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Collected, executed, passed, failed, skipped, "
                         "xfailed and errored, each recorded separately."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "ap18", "AP18_test_injection.py")},
             "timeout_seconds": 900},
            {"step_id": "invoke_directly",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Invoke the file the way a person would. An exit 0 "
                         "that only defines functions is the finding."),
             "params": {"script": w("tree", "ap18", "AP18_test_injection.py"),
                        "args": []},
             "timeout_seconds": 300},
            {"step_id": "positive_control_failing_assertion",
             "operation": "PYTEST_RUN_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A deliberately failing assertion added to a sandbox "
                         "copy must cause a failure and a non-zero exit. This "
                         "proves the harness reports failure at all."),
             "params": {"rootdir": w("tree_failing"),
                        "target": w("tree_failing", "ap18",
                                    "AP18_test_injection.py")},
             "timeout_seconds": 600},
            {"step_id": "negative_control_unmutated_tree",
             "operation": "PYTEST_RUN_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("The unmutated tree must pass, so that the mutation "
                         "result is attributable to the mutation."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "ap18", "AP18_test_injection.py")},
             "timeout_seconds": 600},
            {"step_id": "mutation_control_inverted_detection",
             "operation": "PYTEST_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("The detection condition inverted in a sandbox copy "
                         "of the filter. The test must fail. This is the "
                         "decisive control of this audit: a test that passes "
                         "against an inverted detector is not testing the "
                         "detector."),
             "params": {"rootdir": w("tree_inverted"),
                        "target": w("tree_inverted", "ap18",
                                    "AP18_test_injection.py")},
             "timeout_seconds": 900},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="static assertion count cross-checked against runtime behaviour",
                executable="/usr/bin/python3 -m pytest inside a sandbox tree",
                independent_oracle=(
                    "The static assertion count, the collection report, and "
                    "the mutation outcome. The test suite's own exit code is "
                    "the thing under test and is never the oracle."),
                allowed_reads=[TEST_INJECTION, FILTER, PYTEST_INI],
                allowed_writes=["work/L1-A15/RUN-A/", "evidence/L1-A15/RUN-A/"],
                notes=[SANDBOX_TREE_NOTE,
                       "CLAUDE.md section 10: two test functions, no __main__ "
                       "block, exit 0 and nothing executed."]),
            {"check_id": "four_counts",
             "question": "Collected, executed, assertions run, can it fail?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_in_sandbox",
             "required_result": ("Collected, executed, passed, failed, "
                                 "skipped, xfailed and errored, each its own "
                                 "number. Zero collected is itself the primary "
                                 "finding and the run continues to establish "
                                 "why.")},
            {"check_id": "direct_invocation",
             "question": "What happens when the file is run directly?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "invoke_directly",
             "required_result": ("Exit code recorded together with whether "
                                 "anything actually ran."),
             "verdict_effect": ("An exit 0 that only defines functions is the "
                                "vacuous-success pattern and is a finding.")},
            {"check_id": "positive_control",
             "question": "Can the harness report a failure at all?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_failing_assertion",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the deliberately failing assertion",
             "fixture": "work/L1-A15/RUN-A/tree_failing/",
             "fixture_construction": ("a sandbox tree with one assertion "
                                      "altered so it must fail"),
             "expected_result": "FAILURE_REPORTED_AND_NONZERO_EXIT"},
            {"check_id": "negative_control",
             "question": "Does the unmutated tree pass?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_unmutated_tree",
             "expected_exit_code": 0,
             "expected_result": "PASSES",
             "expected_failure_reason": ("none expected; a failure here would "
                                         "make the mutation result "
                                         "unattributable")},
            {"check_id": "mutation_control",
             "question": "Does the test detect an inverted detector?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_inverted_detection",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the inverted detection condition",
             "fixture": "work/L1-A15/RUN-A/tree_inverted/",
             "fixture_construction": ("a sandbox tree with the filter's "
                                      "detection condition inverted"),
             "proof_the_fixture_differs": ("the inverted file's SHA-256 differs "
                                           "from the original's and the "
                                           "inverted line is recorded verbatim"),
             "expected_result": "THE_TEST_FAILS",
             "zero_changed_results_is": ("proof the test does not test the "
                                         "detector, not a passing control"),
             "decisive": True},
        ],
    }


def a16_run_a():
    audit, phase = "L1-A16", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    cases = [
        ("N1", "RUN_SPLIT",
         "instruction text split across several w:r runs so no single run "
         "contains a matching substring, while the rendered paragraph reads as "
         "one sentence"),
        ("N2", "HIDDEN_OR_ALTERNATE_TEXT",
         "instruction text placed where an alternate-content or fallback "
         "branch renders it, distinct from W1's vanish property"),
        ("N3", "UNICODE_HOMOGLYPH",
         "instruction text using visually identical characters from another "
         "script"),
        ("N4", "EXTERNAL_RELATIONSHIP",
         "an external relationship reference present in the file; it is never "
         "fetched"),
        ("N5", "NESTED_OR_OBFUSCATED",
         "instruction text nested or obfuscated inside another structure"),
    ]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Build five synthetic DOCX cases absent from the existing corpus, "
            "covering run-split XML text, hidden or alternate text, Unicode "
            "homoglyphs, an external relationship reference and nested or "
            "obfuscated instruction text; run them against the filter and "
            "record the result. No external relationship is ever resolved."),
        "static_analysis": (
            "The filter is parsed, never imported, and the text it actually "
            "reads is established: whether it reconstructs a paragraph from "
            "its runs or matches run by run decides whether N1 can be seen at "
            "all.\n\n"
            "All five files are built inside the audit work directory with "
            "zipfile and hand-written OOXML. Synthetic content only, no client "
            "document, no macro, no GUI application. The external relationship "
            "in N4 is present in the file and must never be fetched - the "
            "audit records that the reference exists, not what it points at.\n\n"
            "The five cases must not repeat W1 to W5 from the existing corpus. "
            "That is established by comparison against the existing corpus "
            "before the run, not asserted.\n\n" + SANDBOX_TREE_NOTE),
        "target": {
            "path": FILTER, "sha256": sha_of(FILTER),
            "identity_evidence": (
                "bindings/L1-A16.binding.json records this path as a candidate "
                "with this digest."),
        },
        "steps": (
            [{"step_id": "parse_filter", "operation": "PYTHON_AST_PARSE",
              "control_role": "MEASUREMENT",
              "purpose": ("Establish what text the filter reads: reconstructed "
                          "paragraphs or individual runs."),
              "params": {"path": FILTER}, "timeout_seconds": 120},
             # R8 repair. This step bound COMPARE_HASHES to two directories:
             # `work/L1-A16/RUN-A/cases` and `ap18`. COMPARE_HASHES opens
             # files, so a directory raised IsADirectoryError and the step
             # could never run -- and it never had run, because R7 deferred
             # it for a missing input and the deferral hid the defect.
             #
             # The type error was the smaller half. The digest of one
             # directory against the digest of another cannot answer whether
             # N3 repeats W2: novelty is a per-case question and an aggregate
             # comparison collapses five answers into one bit. And `ap18` is
             # the AP18 source tree; the specification's STATIC ANALYSIS
             # section names the corpus exactly -- "ap18/korpus_docx contains
             # W1 hidden, W2 white text, W3 tiny font, W4 document
             # properties, W5 footnote, and two clean files".
             #
             # The corpus size is bound so that a corpus which is absent,
             # empty or no longer seven entries fails closed. "No duplicates
             # found" and "nothing to compare against" are the same answer to
             # a caller that reads only the verdict, and they are not the
             # same fact -- which is what the BLOCKED criterion, "the existing
             # corpus cannot be enumerated so novelty cannot be proven",
             # exists to keep apart.
             {"step_id": "prove_cases_are_novel",
              "operation": "PROVE_SET_NOVELTY", "control_role": "MEASUREMENT",
              "purpose": ("Prove per case that none of the five repeats W1 to "
                          "W5, by content digest against the existing "
                          "corpus."),
              "params": {"candidate_root": w("cases"),
                         "reference_root": KORPUS_DOCX,
                         "reference_set_id": KORPUS_SET_ID,
                         "include_globs": ["*.docx"],
                         "expected_reference_entry_count": 7,
                         "require_non_empty_reference": True},
              "timeout_seconds": 300},
             {"step_id": "positive_control_novel_case_accepted",
              "operation": "PROVE_SET_NOVELTY", "control_role": "POSITIVE",
              "purpose": ("A case known to be absent from the corpus must be "
                          "reported novel. If it is not, the measurement "
                          "cannot recognise novelty and no result from it "
                          "means anything."),
              "params": {"candidate_root": w("cases", "novelty_controls",
                                             "novel"),
                         "reference_root": KORPUS_DOCX,
                         "reference_set_id": KORPUS_SET_ID,
                         "include_globs": ["*.docx"],
                         "expected_reference_entry_count": 7,
                         "require_non_empty_reference": True},
              "timeout_seconds": 300},
             {"step_id": "negative_control_duplicate_rejected",
              "operation": "PROVE_SET_NOVELTY", "control_role": "NEGATIVE",
              "purpose": ("A byte-identical copy of a corpus member must be "
                          "reported as a duplicate. A measurement that called "
                          "it novel would call anything novel."),
              "params": {"candidate_root": w("cases", "novelty_controls",
                                             "duplicate"),
                         "reference_root": KORPUS_DOCX,
                         "reference_set_id": KORPUS_SET_ID,
                         "include_globs": ["*.docx"],
                         "expected_reference_entry_count": 7,
                         "require_non_empty_reference": True},
              "timeout_seconds": 300},
             {"step_id": "negative_control_renamed_duplicate_rejected",
              "operation": "PROVE_SET_NOVELTY", "control_role": "NEGATIVE",
              "purpose": ("The same duplicate under a different filename must "
                          "still be reported as a duplicate. Renaming is the "
                          "evasion a name-based novelty check would miss, and "
                          "this control is what proves the comparison is on "
                          "content."),
              "params": {"candidate_root": w("cases", "novelty_controls",
                                             "renamed"),
                         "reference_root": KORPUS_DOCX,
                         "reference_set_id": KORPUS_SET_ID,
                         "include_globs": ["*.docx"],
                         "expected_reference_entry_count": 7,
                         "require_non_empty_reference": True},
              "timeout_seconds": 300}]
            + [{"step_id": "run_case_%s" % cid.lower(),
                "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                "control_role": "MEASUREMENT",
                "purpose": "%s (%s): %s" % (cid, vector, description),
                "params": {"script": w("sandbox", "AP18_eingangsfilter.py"),
                           "args": ["--input", w("cases", "%s.docx" % cid)]},
                "timeout_seconds": 300}
               for cid, vector, description in cases]
            + [
                {"step_id": "independent_rendered_text",
                 "operation": "DOCX_PARSE_SANDBOX", "control_role": "ORACLE",
                 "purpose": ("Reconstruct the rendered text run by run with an "
                             "independent reader, so that what a human would "
                             "read is established without the filter."),
                 "params": {"path": w("cases", "N1.docx"),
                            "resolve_entities": False, "load_dtd": False,
                            "no_network": True},
                 "timeout_seconds": 300},
                {"step_id": "positive_control_plain_instruction",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "POSITIVE",
                 "purpose": ("Plain, unconcealed instruction text in a normal "
                             "paragraph must be detected. If the base case is "
                             "missed the five results mean nothing."),
                 "params": {"script": w("sandbox", "AP18_eingangsfilter.py"),
                            "args": ["--input", w("cases", "BASE.docx")]},
                 "timeout_seconds": 300},
                {"step_id": "negative_control_clean_structural_forms",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "NEGATIVE",
                 "purpose": ("A clean document in each of the five structural "
                             "forms must not be flagged. A document that is "
                             "merely run-split, or merely contains a "
                             "relationship, must not be flagged on structure "
                             "alone."),
                 "params": {"script": w("sandbox", "AP18_eingangsfilter.py"),
                            "args": ["--corpus", w("cases", "clean_forms")]},
                 "timeout_seconds": 600},
                {"step_id": "mutation_control_payload_altered",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "MUTATION",
                 "purpose": ("For each detected case, the payload is altered so "
                             "it should no longer match. It must not. This "
                             "proves detection is of the content and not of "
                             "the structure."),
                 "params": {"script": w("sandbox", "AP18_eingangsfilter.py"),
                            "args": ["--corpus", w("cases", "payload_altered")]},
                 "timeout_seconds": 600},
            ]),
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="five authored DOCX cases with structural negatives",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "An independent OOXML reader written for this audit which "
                    "reconstructs the rendered text run by run, plus an "
                    "explicit statement per case of what a human reader would "
                    "see."),
                allowed_reads=[FILTER, proj("ap18"), KORPUS_DOCX],
                allowed_writes=["work/L1-A16/RUN-A/", "evidence/L1-A16/RUN-A/"],
                forbidden_operations=["NETWORK_REQUEST", "NETWORK_UPLOAD"],
                notes=[SANDBOX_TREE_NOTE,
                       "N4's external relationship is present in the file and "
                       "is never resolved. The finding is that the reference "
                       "exists, not what it points at."]),
            {"check_id": "five_cases_recorded",
             "question": "Are the five cases fully specified and novel?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "prove_cases_are_novel",
             "cases": [{"case_id": cid, "vector": vector,
                        "description": description}
                       for cid, vector, description in cases],
             # The measurement must complete and must have had a real corpus
             # to measure against. Whether all five turn out novel is the
             # audit's finding and is not written down here: the cases are
             # authored by this audit, and if one of them repeated W1 that
             # would be a finding about the authoring rather than a defect in
             # the harness.
             "expected_exit_code": 0,
             "reference_corpus": "ap18/korpus_docx",
             "reference_entry_count": 7,
             "required_result": ("Per case: identifier, structural vector, "
                                 "what a human reader would see, why it is not "
                                 "a repetition of W1 to W5, and the expected "
                                 "verdict with its reason. The novelty is "
                                 "measured per case by content digest, never "
                                 "as one aggregate comparison."),
             "r8_repair": ("COMPARE_HASHES was bound to two directories, "
                           "could not run, and could not have answered a "
                           "per-case question if it had")},
            {"check_id": "novelty_positive_control",
             "question": "Is a case known to be absent reported novel?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_novel_case_accepted",
             "expected_exit_code": 0,
             "expected_boolean": True,
             "expected_count": 0,
             "measured_fields": ["all_novel", "duplicate_count"],
             "expected_result": "REPORTED_NOVEL"},
            {"check_id": "novelty_negative_control_duplicate",
             "question": "Is a byte-identical corpus member reported duplicate?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_duplicate_rejected",
             "expected_exit_code": 0,
             "expected_boolean": False,
             "expected_count": 1,
             "measured_fields": ["all_novel", "duplicate_count"],
             "expected_result": "REPORTED_DUPLICATE",
             "expected_failure_reason": ("byte-identical to a reference entry; "
                                         "the candidate is the corpus member "
                                         "it was copied from")},
            {"check_id": "novelty_negative_control_renamed_duplicate",
             "question": "Does renaming a duplicate hide it?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_renamed_duplicate_rejected",
             "expected_exit_code": 0,
             "expected_boolean": False,
             "expected_count": 1,
             "measured_fields": ["all_novel", "duplicate_count"],
             "expected_result": "REPORTED_DUPLICATE_DESPITE_RENAME",
             "expected_failure_reason": ("a different filename does not make "
                                         "it a different document; the "
                                         "comparison is on content digest and "
                                         "never on the name")},
            {"check_id": "run_split_visibility",
             "question": "Can the filter see text split across runs?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_filter",
             "required_result": ("Answered from the parse: whether the filter "
                                 "reconstructs paragraphs from runs or matches "
                                 "run by run. A run-by-run matcher cannot see "
                                 "N1 by construction, and that is a finding "
                                 "about the filter rather than about the "
                                 "case.")},
            {"check_id": "positive_control",
             "question": "Is plain instruction text detected?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_plain_instruction",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the plain instruction text",
             "expected_result": "DETECTED"},
            {"check_id": "negative_control",
             "question": "Is a clean document in each form left alone?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_clean_structural_forms",
             "expected_exit_code": 0,
             "expected_result": "NO_DETECTIONS",
             "expected_failure_reason": ("the documents carry the structure "
                                         "without the payload; a detection "
                                         "here would mean the filter flags "
                                         "structure rather than content"),
             "one_per_vector": True},
            {"check_id": "mutation_control",
             "question": "Is detection of the content or of the structure?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_payload_altered",
             "fixture": "work/L1-A16/RUN-A/cases/payload_altered/",
             "fixture_construction": ("each detected case with its payload "
                                      "altered so it should no longer match, "
                                      "structure unchanged"),
             "proof_the_fixture_differs": ("each altered case's SHA-256 differs "
                                           "from its original and the altered "
                                           "payload is recorded"),
             "expected_result": "THE_ALTERED_CASES_ARE_NOT_DETECTED",
             "zero_changed_results_is": ("proof the filter is matching "
                                         "structure, not content")},
        ],
    }


def a22_run_a():
    audit, phase = "L1-A22", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Determine whether the golden test is collected, and if not, "
            "determine the cause from the full list of possible causes; then "
            "determine, in a sandbox copy, what the test would report if it "
            "were collected."),
        "static_analysis": (
            "The pytest configuration is read directly rather than inferred "
            "from behaviour: testpaths, python_files, python_classes, "
            "python_functions, norecursedirs, rootdir determination and any "
            "addopts that change collection.\n\n"
            "The golden test file and the golden copy of the scanner are "
            "hashed and parsed. A file collectable by path but not by the "
            "default invocation is a configuration finding and not a file "
            "finding, which is why both invocations are run and "
            "compared.\n\n" + SANDBOX_TREE_NOTE),
        "target": {
            "path": PYTEST_INI, "sha256": sha_of(PYTEST_INI),
            "identity_evidence": (
                "bindings/L1-A22.binding.json records this path with this "
                "digest. The configuration is bound as the target because the "
                "audit's first question is whether the configuration collects "
                "the file."),
        },
        "steps": [
            {"step_id": "read_pytest_configuration",
             "operation": "READ_FILE_RANGE", "control_role": "MEASUREMENT",
             "purpose": ("Read the configuration directly. Collection "
                         "behaviour is not inferred from its own output."),
             "params": {"path": PYTEST_INI, "start": 0, "length": 65536},
             "timeout_seconds": 120},
            {"step_id": "parse_golden_test", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": "What the golden test asserts. Parse, do not import.",
             "params": {"path": GOLDEN_TEST}, "timeout_seconds": 120},
            {"step_id": "collect_default_invocation",
             "operation": "PYTEST_COLLECT_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Collect from the sandbox project root exactly as the "
                         "project would be invoked, recording the complete "
                         "output including errors."),
             "params": {"rootdir": w("tree"), "target": w("tree")},
             "timeout_seconds": 900},
            {"step_id": "collect_by_explicit_path",
             "operation": "PYTEST_COLLECT_SANDBOX", "control_role": "MEASUREMENT",
             "purpose": ("Collect the golden test by path. A file collectable "
                         "by path but not by default is a configuration "
                         "finding."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "anonymization", "golden",
                                    "payload_scan_golden_test.py")},
             "timeout_seconds": 900},
            {"step_id": "run_if_collected", "operation": "PYTEST_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("What the test reports in the sandbox once it is "
                         "collected."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "anonymization", "golden",
                                    "payload_scan_golden_test.py")},
             "timeout_seconds": 900},
            {"step_id": "positive_control_trivial_test_collected",
             "operation": "PYTEST_COLLECT_SANDBOX", "control_role": "POSITIVE",
             "purpose": ("A trivially collectable test placed in the same "
                         "sandbox directory must be collected. This proves the "
                         "collection run works and isolates the cause to the "
                         "file or its configuration."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "anonymization", "golden",
                                    "test_trivially_collectable.py")},
             "timeout_seconds": 600},
            {"step_id": "negative_control_unmatched_name",
             "operation": "PYTEST_COLLECT_SANDBOX", "control_role": "NEGATIVE",
             "purpose": ("A file deliberately named so as not to match any "
                         "pattern must not be collected. This proves "
                         "collection is selective."),
             "params": {"rootdir": w("tree"),
                        "target": w("tree", "anonymization", "golden",
                                    "not_a_matching_name.py")},
             "timeout_seconds": 600},
            {"step_id": "mutation_control_golden_diverges",
             "operation": "PYTEST_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("Once the test collects and passes in the sandbox, "
                         "the golden copy is altered so it diverges from the "
                         "live copy. The test must fail. A golden test that "
                         "passes when the copies differ is not a golden test."),
             "params": {"rootdir": w("tree_diverged"),
                        "target": w("tree_diverged", "anonymization", "golden",
                                    "payload_scan_golden_test.py")},
             "timeout_seconds": 900},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="configuration read directly, then collection compared two ways",
                executable="/usr/bin/python3 -m pytest inside a sandbox tree",
                independent_oracle=(
                    "The pytest configuration read directly, plus the "
                    "collection report itself. The suite's exit code is the "
                    "thing under test."),
                allowed_reads=[PYTEST_INI, GOLDEN_TEST,
                               proj("anonymization", "golden")],
                allowed_writes=["work/L1-A22/RUN-A/", "evidence/L1-A22/RUN-A/"],
                notes=[SANDBOX_TREE_NOTE]),
            {"check_id": "collected_or_not",
             "question": "Is the golden test collected by the default invocation?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "collect_default_invocation",
             "required_result": ("The collected count and the complete report "
                                 "including collection errors.")},
            {"check_id": "cause_if_not_collected",
             "question": "If it is not collected, why not?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "method": ("compare the default invocation against collection by "
                        "explicit path, then apply one candidate cause at a "
                        "time"),
             "step_id": "collect_by_explicit_path",
             "required_result": ("One named cause with the evidence for it. "
                                 "Collectable by path but not by default is a "
                                 "configuration finding, not a file finding.")},
            {"check_id": "what_it_would_report",
             "question": "What does the test report once collected?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "run_if_collected",
             "required_result": ("Recorded from the sandbox run, stated as "
                                 "what it would report rather than as what the "
                                 "project currently reports.")},
            {"check_id": "positive_control",
             "question": "Does the collection run work at all?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_trivial_test_collected",
             "expected_exit_code": 0,
             "fixture": "work/L1-A22/RUN-A/tree/anonymization/golden/test_trivially_collectable.py",
             "expected_result": "COLLECTED",
             "why": ("If a trivial test is not collected either, the cause is "
                     "the run and not the golden file.")},
            {"check_id": "negative_control",
             "question": "Is collection selective?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_unmatched_name",
             "expected_result": "NOT_COLLECTED",
             "expected_failure_reason": ("the filename matches no configured "
                                         "collection pattern")},
            {"check_id": "mutation_control",
             "question": "Does the golden test fail when the copies diverge?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_golden_diverges",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the golden copy no longer matches the live copy",
             "fixture": "work/L1-A22/RUN-A/tree_diverged/",
             "fixture_construction": ("the sandbox tree with the golden copy "
                                      "altered so it differs from the live "
                                      "copy"),
             "proof_the_fixture_differs": ("the golden copy's SHA-256 differs "
                                           "from the live copy's and both are "
                                           "recorded"),
             "expected_result": "THE_TEST_FAILS",
             "zero_changed_results_is": ("proof it is not a golden test, not a "
                                         "passing control")},
        ],
    }


# ================================================== authoring / DOCX group
ASSEMBLER = proj("authoring", "AP16_assemble_long_document.py")
VERIFIER = proj("authoring", "AP16_verify_document.py")
EXPORTER_V4 = proj("authoring", "AP16_export_with_toc_v4.py")

DOCX_ORACLE_NOTE = (
    "The independent reader is written for this audit with zipfile and "
    "xml.etree, external entities and DTD disabled. It states what the "
    "document contains; the target states what it claims. The generator is "
    "never its own oracle, and a prior report under docs/ is not one either.")


def a01_run_a():
    audit, phase = "L1-A01", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Establish whether two runs of the assembly path, given identical "
            "input and identical configuration, produce byte-identical output; "
            "and where they do not, establish exactly which bytes differ and "
            "whether those bytes are document content or container metadata. "
            "Those two are different findings and are never merged."),
        "static_analysis": (
            "The assembler is parsed with PYTHON_AST_PARSE, never imported. "
            "Every source of nondeterminism reachable from module scope and "
            "from the entry point is enumerated: datetime and time calls, "
            "uuid, random, os.urandom, hash-order-dependent iteration over "
            "dict or set, os.listdir and glob ordering, locale-dependent "
            "formatting, tempfile names and environment reads. Every write "
            "target and every constructed path is enumerated with them.\n\n"
            "The output container format is determined from the parse. If it "
            "is ZIP-based, as DOCX is, then ZIP local headers carry an mtime "
            "and that alone breaks byte equality unless the writer pins it - "
            "so a raw-hash difference is not yet evidence of nondeterministic "
            "content, and the layer must be identified before the difference "
            "is interpreted.\n\n"
            "Preparation the approved phase performs: two clean work "
            "directories RUN1 and RUN2, neither pre-existing, each receiving a "
            "copy of a synthetic input fixture built inside the audit work "
            "directory. Never a client document. The environment is pinned "
            "identically for both - TZ, LC_ALL, LANG, PYTHONHASHSEED, and "
            "SOURCE_DATE_EPOCH where the code honours it - and the exact "
            "allowlist is recorded."),
        "target": {
            "path": ASSEMBLER, "sha256": sha_of(ASSEMBLER),
            "identity_evidence": (
                "bindings/L1-A01.binding.json records this path with this "
                "digest and the file on disk hashes to the same value."),
        },
        "steps": [
            {"step_id": "parse_assembler", "operation": "PYTHON_AST_PARSE",
             "control_role": "MEASUREMENT",
             "purpose": ("Enumerate nondeterminism sources, write targets and "
                         "the entry point's argument surface."),
             "params": {"path": ASSEMBLER}, "timeout_seconds": 120},
            {"step_id": "run1", "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": "First run, in its own clean directory.",
             "params": {"script": w("sandbox",
                                    "AP16_assemble_long_document.py"),
                        "args": ["--input", w("RUN1", "input"),
                                 "--out", w("RUN1", "output.docx")]},
             "timeout_seconds": 600},
            {"step_id": "run2", "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
             "control_role": "MEASUREMENT",
             "purpose": ("Second run, identical input and identical pinned "
                         "environment, in its own clean directory."),
             "params": {"script": w("sandbox",
                                    "AP16_assemble_long_document.py"),
                        "args": ["--input", w("RUN2", "input"),
                                 "--out", w("RUN2", "output.docx")]},
             "timeout_seconds": 600},
            {"step_id": "hash_both_outputs_raw", "operation": "COMPARE_HASHES",
             "control_role": "MEASUREMENT",
             "purpose": ("Hash the raw output of each run before touching it "
                         "in any way."),
             "params": {"left": w("RUN1", "output.docx"),
                        "right": w("RUN2", "output.docx"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 300},
            {"step_id": "locate_differences", "operation": "COMPARE_BINARY_FILES",
             "control_role": "MEASUREMENT",
             "purpose": ("If the raw hashes differ, locate the differing bytes "
                         "and attribute them to a layer."),
             "params": {"left": w("RUN1", "output.docx"),
                        "right": w("RUN2", "output.docx")},
             "timeout_seconds": 600},
            {"step_id": "independent_container_read",
             "operation": "ZIP_LIST", "control_role": "ORACLE",
             "purpose": ("Read the container structure with the standard "
                         "library so that a metadata difference can be told "
                         "from a content difference."),
             "params": {"path": w("RUN1", "output.docx")},
             "timeout_seconds": 300},
            {"step_id": "positive_control_known_input_difference",
             "operation": "COMPARE_HASHES", "control_role": "POSITIVE",
             "purpose": ("One known character changed in the RUN2 input "
                         "fixture: the raw hashes must differ and the located "
                         "difference must be the one introduced. This proves "
                         "the comparison can see a change."),
             "params": {"left": w("RUN1", "output.docx"),
                        "right": w("controls", "output_from_changed_input.docx"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 300},
            {"step_id": "negative_control_same_input_twice",
             "operation": "COMPARE_HASHES", "control_role": "NEGATIVE",
             "purpose": ("The assembler run twice on the same input in the "
                         "same directory shape with no change at all. Any "
                         "difference observed here is nondeterminism rather "
                         "than input variation, which is what separates the "
                         "two causes."),
             "params": {"left": w("controls", "unchanged_a.docx"),
                        "right": w("controls", "unchanged_b.docx"),
                        "algorithms": ["sha256"]},
             "timeout_seconds": 300},
            {"step_id": "mutation_control_pin_nondeterminism",
             "operation": "PYTHON_SCRIPT_RUN_SANDBOX", "control_role": "MUTATION",
             "purpose": ("Pin every identified nondeterminism source - fixed "
                         "TZ, fixed PYTHONHASHSEED, fixed SOURCE_DATE_EPOCH - "
                         "and repeat. If the output becomes deterministic the "
                         "nondeterminism is environmental; if it does not it "
                         "is in the code, and the AST enumeration is "
                         "re-examined for what it missed."),
             "params": {"script": w("sandbox",
                                    "AP16_assemble_long_document.py"),
                        "args": ["--input", w("controls", "pinned_input"),
                                 "--out", w("controls", "pinned_output.docx")]},
             "timeout_seconds": 600},
        ],
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="two pinned runs compared at the raw and container layers",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=DOCX_ORACLE_NOTE,
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[ASSEMBLER],
                allowed_writes=["work/L1-A01/RUN-A/", "evidence/L1-A01/RUN-A/"],
                notes=["The input fixture is synthetic and is built inside the "
                       "audit work directory. Never a client document.",
                       "ZIP local headers carry an mtime; a raw-hash "
                       "difference is not by itself evidence of "
                       "nondeterministic content."]),
            {"check_id": "byte_identity",
             "question": "Are the two outputs byte-identical?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "hash_both_outputs_raw",
             "required_result": ("The two raw digests, and whether they are "
                                 "equal. Hashed before either file is touched.")},
            {"check_id": "layer_of_any_difference",
             "question": "If they differ, is it content or container metadata?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "locate_differences",
             "required_result": ("The differing byte ranges, each attributed "
                                 "to document content or to container "
                                 "metadata. The two are different findings and "
                                 "are never merged.")},
            {"check_id": "environment_recorded",
             "question": "Was the environment identical for both runs?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "pinned": ["TZ", "LC_ALL", "LANG", "PYTHONHASHSEED",
                        "SOURCE_DATE_EPOCH"],
             "required_result": ("The exact allowlist recorded, not described. "
                                 "Two runs under different environments "
                                 "compare nothing.")},
            {"check_id": "positive_control",
             "question": "Can the comparison see a known change?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "positive_control_known_input_difference",
             "fixture": "work/L1-A01/RUN-A/controls/output_from_changed_input.docx",
             "fixture_construction": ("output produced from the RUN2 input "
                                      "fixture with one character changed"),
             "proof_the_fixture_differs": ("the input fixtures' digests differ "
                                           "and the changed character is "
                                           "recorded"),
             "expected_result": "HASHES_DIFFER_AT_THE_INTRODUCED_DIFFERENCE"},
            {"check_id": "negative_control",
             "question": "Does the same input twice produce the same output?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_same_input_twice",
             "expected_result": "ANY_DIFFERENCE_HERE_IS_NONDETERMINISM",
             "expected_failure_reason": ("nothing was changed between the two "
                                         "runs, so a difference cannot be "
                                         "input variation"),
             "why": "This is what separates nondeterminism from input variation."},
            {"check_id": "mutation_control",
             "question": "Is the nondeterminism environmental or in the code?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_id": "mutation_control_pin_nondeterminism",
             "fixture": "every identified nondeterminism source pinned",
             "expected_result": ("DETERMINISTIC_MEANS_ENVIRONMENTAL; "
                                 "STILL_VARYING_MEANS_IN_THE_CODE"),
             "zero_changed_results_is": ("informative here rather than an "
                                         "error: if pinning changes nothing "
                                         "and the output was already "
                                         "identical, the control has not been "
                                         "exercised and is recorded as not "
                                         "exercised"),
             "follow_up": ("If the output still varies, the AST enumeration is "
                           "re-examined for the source it missed.")},
        ],
    }


def a02_run_a():
    audit, phase = "L1-A02", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    fixtures = [
        ("F1", "valid document", "success"),
        ("F2", "missing file", "a clear, distinguishable failure, not a crash"),
        ("F3", "empty file, 0 bytes", "failure"),
        ("F4", "parseable but semantically wrong: valid OOXML, correct "
               "structure, body text replaced with unrelated content", "open"),
        ("F5", "modified body: one sentence changed", "open"),
        ("F6", "modified heading: one heading renamed", "open"),
        ("F7", "damaged TOC: field retained, entries no longer matching "
               "headings", "open"),
        ("F8", "broken relationship: an r:id referenced from document.xml "
               "with no matching entry in the .rels part", "open"),
        ("F9", "truncated document: the ZIP cut at 60 percent", "open"),
    ]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Determine what verify_document actually asserts about a document, "
            "and whether a document that parses but is semantically wrong "
            "passes it. Nine fixtures, each a separate question, with the "
            "independent reader stating what the document contains."),
        "static_analysis": (
            "The verifier is parsed, never imported. Every assertion it makes "
            "is enumerated - what is compared, against what, and what causes a "
            "non-success return. Every try/except is recorded with what it "
            "swallows: an except that returns success is the defect this audit "
            "exists to find.\n\n"
            "The return contract is recorded - exit code, boolean, exception, "
            "printed text - together with whether a caller could mistake one "
            "for another.\n\n"
            "Whether the check reads the document's XML parts or only opens "
            "the container is decided from the parse, and then which of these "
            "are checked at all: body text, heading text, heading order, "
            "heading hierarchy, table of contents, relationships, content "
            "types, document properties and part integrity.\n\n"
            "All nine fixtures are synthetic and built inside the audit work "
            "directory. Never a client document."),
        "target": {
            "path": VERIFIER, "sha256": sha_of(VERIFIER),
            "identity_evidence": (
                "bindings/L1-A02.binding.json records this path with this "
                "digest and the file on disk hashes to the same value."),
        },
        "steps": (
            [{"step_id": "parse_verifier", "operation": "PYTHON_AST_PARSE",
              "control_role": "MEASUREMENT",
              "purpose": ("Enumerate assertions, exception handling and the "
                          "return contract."),
              "params": {"path": VERIFIER}, "timeout_seconds": 120}]
            + [{"step_id": "run_%s" % fid.lower(),
                "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                "control_role": ("POSITIVE" if fid == "F1"
                                 else "NEGATIVE" if fid == "F3"
                                 else "MUTATION" if fid in ("F5", "F6", "F9")
                                 else "MEASUREMENT"),
                "purpose": "%s: %s. Expected: %s." % (fid, description, expected),
                "params": {"script": w("sandbox", "AP16_verify_document.py"),
                           "args": ["--document", w("fixtures", "%s.docx" % fid)]},
                "timeout_seconds": 300}
               for fid, description, expected in fixtures]
            + [{"step_id": "independent_reader",
                "operation": "DOCX_PARSE_SANDBOX", "control_role": "ORACLE",
                "purpose": ("Extract the heading list and body text directly "
                            "from word/document.xml, with external entities "
                            "and DTD disabled. The oracle states what the "
                            "document contains; the target states what it "
                            "claims."),
                "params": {"path": w("fixtures", "F1.docx"),
                           "resolve_entities": False, "load_dtd": False,
                           "no_network": True},
                "timeout_seconds": 300}]),
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="nine-fixture matrix against an independent OOXML reader",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=DOCX_ORACLE_NOTE,
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[VERIFIER],
                allowed_writes=["work/L1-A02/RUN-A/", "evidence/L1-A02/RUN-A/"],
                notes=["All nine fixtures are synthetic. Never a client "
                       "document."]),
            {"check_id": "what_is_asserted",
             "question": "What does the verifier actually assert?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_verifier",
             "checked_or_not": ["body text", "heading text", "heading order",
                                "heading hierarchy", "table of contents",
                                "relationships", "content types",
                                "document properties", "part integrity"],
             "required_result": "Each listed as checked or not checked."},
            {"check_id": "exception_handling",
             "question": "Does any except return success?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "required_result": ("Every try/except recorded with what it "
                                 "swallows."),
             "verdict_effect": ("An except that returns success turns a "
                                "failure into a pass and is the defect this "
                                "audit exists to find.")},
            {"check_id": "fixture_matrix",
             "question": "What does the verifier do with each fixture?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "fixtures": [{"fixture_id": fid, "description": description,
                           "expected": expected}
                          for fid, description, expected in fixtures],
             "required_result": ("One result per fixture, with the exit code "
                                 "and the semantic verdict recorded "
                                 "separately.")},
            {"check_id": "positive_control",
             "question": "Does a valid document pass?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "run_f1",
             "expected_exit_code": 0,
             "expected_result": "SUCCESS",
             "why": ("If a known-good document does not pass, the verifier is "
                     "unusable and the rest of the matrix is uninterpretable.")},
            {"check_id": "negative_control",
             "question": "Does a zero-byte file fail?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "run_f3",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "the file has no content at all",
             "expected_result": "FAILURE",
             "verdict_effect": ("A verifier that passes a zero-byte file has "
                                "no content check at all.")},
            {"check_id": "mutation_control",
             "question": "Does any real change to the document cause a failure?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_ids": ["run_f5", "run_f6", "run_f9"],
             "fixture_construction": ("F5 one sentence changed; F6 one heading "
                                      "renamed; F9 the ZIP cut at 60 percent"),
             "proof_the_fixture_differs": ("each fixture's SHA-256 differs from "
                                           "F1's and the change is recorded"),
             "expected_result": "AT_LEAST_ONE_MUST_FAIL",
             "verdict_effect": ("If a modified body, a renamed heading and a "
                                "truncated container all pass, the verifier "
                                "does not verify the document - it verifies "
                                "that a file is there, and the audit says "
                                "exactly that."),
             "zero_changed_results_is": ("the finding itself here, and it is "
                                         "reported as a finding about the "
                                         "verifier rather than as a failed "
                                         "control")},
        ],
    }


def a04_run_a():
    audit, phase = "L1-A04", "RUN-A"
    w = lambda *p: work(audit, phase, *p)
    fixtures = [
        ("T1", "baseline"),
        ("T2", "a heading removed from the source after the TOC list is built"),
        ("T3", "a duplicate heading with identical text"),
        ("T4", "a renamed heading"),
        ("T5", "a hidden heading with the vanish property set"),
        ("T6", "a heading-styled paragraph in the body that the TOC omits"),
    ]
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit,
        "run_phase": phase,
        "scope": (
            "Compare the generated table of contents against the headings "
            "actually present in the generated document, extracted "
            "independently of the generator. Under no circumstances does the "
            "exporter's internal heading list serve as the reference side."),
        "static_analysis": (
            "The exporter is parsed, never imported. How the TOC is built and "
            "from what data structure is recorded, and then the decisive "
            "structural question: whether the TOC is a static list of "
            "paragraphs or an OOXML TOC field. A field is resolved by Word "
            "rather than by the generator, and that changes the comparison "
            "entirely.\n\n"
            "The heading style names the generator uses are recorded, together "
            "with whether it recognises any other heading style. A generator "
            "that emits one style and reads another would produce exactly the "
            "disagreement this audit measures.\n\n"
            "Any existing self-check that compares the TOC against the "
            "generator's own list is named as the circular check it is.\n\n"
            "The target depends on L1-A03. If A03 returned "
            "BLOCKED_TARGET_IDENTITY_UNCERTAIN, this audit runs against a "
            "named candidate and says so in every conclusion rather than "
            "presenting the result as being about the productive exporter."),
        "target": {
            "path": EXPORTER_V4, "sha256": sha_of(EXPORTER_V4),
            "identity_evidence": (
                "bindings/L1-A04.binding.json names this candidate with this "
                "digest. It is a named candidate, not a proven productive "
                "version: L1-A03 owns that question and a version suffix is "
                "excluded by rule from answering it."),
        },
        "steps": (
            [{"step_id": "parse_exporter", "operation": "PYTHON_AST_PARSE",
              "control_role": "MEASUREMENT",
              "purpose": ("How the TOC is built, from what structure, and "
                          "which heading styles are used and recognised."),
              "params": {"path": EXPORTER_V4}, "timeout_seconds": 120}]
            + [{"step_id": "generate_%s" % tid.lower(),
                "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                "control_role": ("POSITIVE" if tid == "T1"
                                 else "MUTATION" if tid in ("T2", "T4", "T6")
                                 else "MEASUREMENT"),
                "purpose": "%s: %s. A separate generation." % (tid, description),
                "params": {"script": w("sandbox", "AP16_export_with_toc_v4.py"),
                           "args": ["--source", w("fixtures", "%s.json" % tid),
                                    "--out", w("generated", "%s.docx" % tid)]},
                "timeout_seconds": 600}
               for tid, description in fixtures]
            + [
                {"step_id": "extract_real_headings",
                 "operation": "DOCX_PARSE_SANDBOX", "control_role": "ORACLE",
                 "purpose": ("Extract the real heading set from the generated "
                             "document independently: parse word/document.xml "
                             "with entities and DTD disabled, select "
                             "paragraphs by style, and record text, order and "
                             "nesting level."),
                 "params": {"path": w("generated", "T1.docx"),
                            "resolve_entities": False, "load_dtd": False,
                            "no_network": True},
                 "timeout_seconds": 300},
                {"step_id": "extract_toc_entries",
                 "operation": "DOCX_PARSE_SANDBOX", "control_role": "ORACLE",
                 "purpose": ("Extract the TOC entries from the generated "
                             "document, not from the generator's memory."),
                 "params": {"path": w("generated", "T1.docx"),
                            "resolve_entities": False, "load_dtd": False,
                            "no_network": True, "select": "toc"},
                 "timeout_seconds": 300},
                {"step_id": "negative_control_no_headings",
                 "operation": "PYTHON_SCRIPT_RUN_SANDBOX",
                 "control_role": "NEGATIVE",
                 "purpose": ("A document with zero headings must yield an "
                             "empty TOC and an empty heading set, agreeing "
                             "trivially. This proves the comparison does not "
                             "manufacture entries."),
                 "params": {"script": w("sandbox",
                                        "AP16_export_with_toc_v4.py"),
                            "args": ["--source", w("fixtures", "no_headings.json"),
                                     "--out", w("generated", "no_headings.docx")]},
                 "timeout_seconds": 600},
            ]),
        "test_matrix": [
            binding_envelope(
                audit, phase,
                method="independent heading extraction compared against the generated TOC",
                executable="/usr/bin/python3 -I -B against a sandbox copy",
                independent_oracle=(
                    "An independent OOXML reader written for this audit. Under "
                    "no circumstances may the exporter's internal heading list "
                    "serve as the reference side of the comparison."),
                target_identification_rule=EXECUTION_PATH_RULE,
                allowed_reads=[EXPORTER_V4],
                allowed_writes=["work/L1-A04/RUN-A/", "evidence/L1-A04/RUN-A/"],
                limitations=[
                    "The target depends on L1-A03's identity result. If A03 "
                    "could not prove which exporter is productive, every "
                    "conclusion here names the candidate it was run against "
                    "and is not presented as a finding about the productive "
                    "exporter."],
                notes=["All fixtures are synthetic and built inside the audit "
                       "work directory."]),
            {"check_id": "toc_kind",
             "question": "Is the TOC a static list or an OOXML field?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "step_id": "parse_exporter",
             "required_result": ("Decided from the parse. A field is resolved "
                                 "by Word rather than by the generator, which "
                                 "changes what the comparison can conclude."),
             "why": ("Comparing a field's placeholder against real headings "
                     "would report a disagreement that says nothing about the "
                     "generator.")},
            {"check_id": "circular_self_check_named",
             "question": "Does an existing self-check compare the TOC against the generator's own list?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "required_result": ("If one exists it is named as the circular "
                                 "check it is, and it is not used as evidence.")},
            {"check_id": "comparison_dimensions",
             "question": "On what is the TOC compared against the headings?",
             "expectation_class": "SUBSTANTIVE_EXPECTATION",
             "dimensions": ["text equality", "order", "hierarchy level",
                            "anchor or bookmark mapping where the format "
                            "carries one"],
             "step_id": "extract_toc_entries",
             "required_result": "All four, reported separately."},
            {"check_id": "positive_control",
             "question": "Does the baseline agree completely?",
             "expectation_class": "INFRASTRUCTURE_EXPECTATION",
             "step_id": "generate_t1",
             "expected_exit_code": 0,
             "expected_result": "COMPLETE_AGREEMENT",
             "why": ("If the baseline disagrees, the extractor is wrong and "
                     "must be fixed before anything else is interpreted.")},
            {"check_id": "negative_control",
             "question": "Does a document with no headings agree trivially?",
             "expectation_class": "NEGATIVE_CONTROL_EXPECTATION",
             "step_id": "negative_control_no_headings",
             "expected_exit_code": 0,
             "expected_result": "EMPTY_TOC_AND_EMPTY_HEADING_SET",
             "expected_failure_reason": ("there are no headings to list; "
                                         "entries here would mean the "
                                         "comparison manufactures them")},
            {"check_id": "mutation_control",
             "question": "Does the comparison detect a real divergence?",
             "expectation_class": "MUTATION_CONTROL_EXPECTATION",
             "step_ids": ["generate_t2", "generate_t4", "generate_t6"],
             "fixture_construction": ("T2 a heading removed after the TOC list "
                                      "is built; T4 a heading renamed; T6 a "
                                      "heading-styled body paragraph the TOC "
                                      "omits"),
             "proof_the_fixture_differs": ("each source fixture differs from "
                                           "T1's and the change is recorded"),
             "expected_result": "EACH_MUST_BE_DETECTED",
             "verdict_effect": ("If a removed heading, a renamed heading and a "
                                "body-only heading all compare equal, the "
                                "comparison is not comparing."),
             "zero_changed_results_is": "a measurement error, not a pass"},
        ],
    }
