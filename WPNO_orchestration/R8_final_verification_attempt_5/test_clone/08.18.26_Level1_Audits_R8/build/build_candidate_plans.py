#!/usr/bin/env python3
"""Build the exact candidate live plans for all nine target phases.

These are the plans the live phases will run, byte for byte, produced before
the freeze so they can be rehearsed with the exact argv builder and the exact
parameters. They are candidates, not approvals: nothing here starts a phase,
records an approval or writes into `results/`.

Why this exists at all. R6's pre-freeze readiness fixture exercised the
operation catalogue generically and passed. The live L1-A31 plan then failed
on three parameters the fixture had never executed — a purpose, an epoch and a
mutation fixture. A readiness check that does not run the real parameters
checks the harness, not the plan.

The L1-A31 purpose correction, since it is the substantive one.

R6 asked OpenSSL to validate both certificate chains under `-purpose
smimesign`. The document leaf carries no extended key usage at all, so RFC
5280 imposes no purpose restriction on it and it passed. The VHN leaf carries
exactly one extended key usage, id-kp-clientAuth, so `smimesign` was refused
with error 26, and every later CMS control failed on the same certificate
check before it had compared one byte of content.

One purpose value was doing two different jobs. R7 separates them:

  * PATH VALIDATION asks whether the chain is well-formed and trusted — issuer
    chaining, signatures, validity at the stated time, basic constraints, no
    default trust store, no suppression flag. It runs under `-purpose any`,
    which does not suppress anything: it declines to impose an application
    purpose the certificate was never issued for. Removing that constraint
    from this check is only sound because the next one exists.

  * KEY-USAGE CONFORMANCE asks whether the certificate is entitled to do what
    it was used for. It is answered explicitly from the recorded certificate
    facts against stated criteria, and its result is reported in its own
    right — including when the answer is unwelcome.

For the VHN leaf the answer will be mixed, and the plan says so in advance
rather than discovering it: key usage is satisfied for a CMS signature
(digitalSignature and nonRepudiation are both asserted), while the extended
key usage does not include emailProtection or anyExtendedKeyUsage. That is the
L1-A31 specification's own listed edge case, "a certificate whose extended key
usage does not include the purpose in question". It is a finding for the run
to weigh, not a defect for this builder to route around, and this script does
not decide the verdict it leads to.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, schema_validation, operation_catalog  # noqa: E402

OUT = os.path.join(ROOT, "build", "candidate_plans_r8")
PREP = os.path.join(ROOT, "work", "L1-A31", "preparation_r8_2026-08-28")
STAGING_RECORD = os.path.join(PREP, "STAGING_RECORD.json")

REFERENCES = os.path.join(ROOT, "references")

# Claimed CMS signingTimes, carried forward from R6's parse evidence. They are
# not trusted timestamps and the plans say so wherever they appear.
VHN_SIGNING_TIME = 1772232925          # 2026-02-27T22:55:25Z
DOCUMENT_SIGNING_TIME = 1772232897     # 2026-02-27T22:54:57Z

# Per-phase working directories. Each phase writes only into its own, which is
# what keeps RUN-B's working set out of RUN-A's reach and the other way round.
RUNB_WORK = os.path.join(ROOT, "work", "L1-A31", "RUN-B")
A34_RUNB_WORK = os.path.join(ROOT, "work", "L1-A34", "RUN-B")
A18_RUNA_WORK = os.path.join(ROOT, "work", "L1-A18", "RUN-A")
A18_RUNB_WORK = os.path.join(ROOT, "work", "L1-A18", "RUN-B")

# The REF-02 vector corpus and the REF-01 country rules, by their real names.
# 219 vectors, of which 217 are applicable to an ISO 13616 validator; the
# other two are valid under ISO 13616 and rejected only by python-stdnum's
# country-specific national check, which is outside both ISO 13616 and REF-01.
VECTORS = os.path.join(ROOT, "corpora", "R5_REF02_IBAN_VECTORS.jsonl")
RULES = os.path.join(ROOT, "corpora", "R5_REF01_COUNTRY_RULES.jsonl")


def r(*parts):
    return os.path.join(ROOT, *parts)


def sha(path):
    return hashing.sha256_file(path)


def load_staging():
    with open(STAGING_RECORD, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------- L1-A31
def a31_run_a(staging):
    certs = os.path.join(PREP, "certs")
    controls = os.path.join(PREP, "controls")
    synth = staging["controls"]["synthetic"]
    synth_time = staging["controls"]["notes"]["synthetic_validation_time"]
    mut = staging["controls"]["mutations"]
    target = r("references", "REF-11-original-mail-attachment.zip")

    def c(name):
        return os.path.join(certs, name)

    def k(name):
        return os.path.join(controls, name)

    steps = []
    for stem, name in (
            ("vhn_leaf", "vhn_leaf_from_sealed_p7s_parse_evidence.pem"),
            ("vhn_intermediate", "vhn_intermediate_selected_manual_pem.pem"),
            ("vhn_root", "vhn_root.pem"),
            ("document_leaf", "document_leaf_from_sealed_p7s_parse_evidence.pem"),
            ("document_intermediate", "document_intermediate.pem"),
            ("document_root", "document_root.pem")):
        steps.append({
            "step_id": "parse_" + stem,
            "operation": "OPENSSL_PARSE_CERT",
            "params": {"cert": c(name)},
            "timeout_seconds": 120,
            "purpose": ("Record subject, issuer, serial, validity, key usage, "
                        "extended key usage, algorithms, basic constraints and "
                        "the SHA-256 fingerprint. PARSE_ONLY_NOT_VERIFICATION."),
            "control_role": "MEASUREMENT",
        })

    steps += [
        {"step_id": "synthetic_chain_positive",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": r(synth["root_pem"]),
                    "intermediates": r(synth["intermediate_pem"]),
                    "leaf": r(synth["leaf_pem"]),
                    "attime": synth_time,
                    "purpose": "smimesign"},
         "timeout_seconds": 120,
         "purpose": ("Independently constructed chain whose outcome is known "
                     "by construction. Its leaf carries emailProtection, so "
                     "smimesign is the purpose it is entitled to; its "
                     "validation time is derived from its own issue time, not "
                     "written as a literal. Both were wrong in R6."),
         "control_role": "POSITIVE"},

        {"step_id": "synthetic_chain_missing_anchor",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": r(synth["other_root_pem"]),
                    "intermediates": r(synth["intermediate_pem"]),
                    "leaf": r(synth["leaf_pem"]),
                    "attime": synth_time,
                    "purpose": "smimesign"},
         "timeout_seconds": 120,
         "purpose": ("An unrelated anchor must not verify this chain. Proves "
                     "the command can fail on trust, which is the point."),
         "control_role": "NEGATIVE"},

        {"step_id": "vhn_chain_path_validation",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": c("vhn_root.pem"),
                    "intermediates": c("vhn_intermediate_selected_manual_pem.pem"),
                    "leaf": c("vhn_leaf_from_sealed_p7s_parse_evidence.pem"),
                    "attime": VHN_SIGNING_TIME,
                    "purpose": "any"},
         "timeout_seconds": 120,
         "purpose": ("RFC 5280 path validation of the VHN chain at the claimed "
                     "CMS signingTime 2026-02-27T22:55:25Z, which is not a "
                     "trusted timestamp. `any` is the path-validation purpose; "
                     "entitlement is answered separately by "
                     "vhn_key_usage_conformance."),
         "control_role": "MEASUREMENT"},

        {"step_id": "document_chain_path_validation",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": c("document_root.pem"),
                    "intermediates": c("document_intermediate.pem"),
                    "leaf": c("document_leaf_from_sealed_p7s_parse_evidence.pem"),
                    "attime": DOCUMENT_SIGNING_TIME,
                    "purpose": "any"},
         "timeout_seconds": 120,
         "purpose": ("RFC 5280 path validation of the document chain at the "
                     "claimed CMS signingTime 2026-02-27T22:54:57Z, which is "
                     "not a trusted timestamp."),
         "control_role": "MEASUREMENT"},

        {"step_id": "vhn_cms",
         "operation": "OPENSSL_VERIFY_CMS",
         "params": {"cms": r("references", "REF-11-vhn.xml.p7s"),
                    "content": r("references", "REF-11-vhn-covered-content.xml"),
                    "anchor": c("vhn_root.pem"),
                    "certfile": c("vhn_intermediate_selected_manual_pem.pem"),
                    "inform": "DER", "binary": True,
                    "attime": VHN_SIGNING_TIME, "purpose": "any",
                    "out": os.path.join(PREP, "outputs",
                                        "vhn_verified_content.bin")},
         "timeout_seconds": 120,
         "purpose": "Verify the VHN CMS signature over the exact detached content.",
         "control_role": "MEASUREMENT"},

        {"step_id": "document_cms",
         "operation": "OPENSSL_VERIFY_CMS",
         "params": {"cms": r("references", "REF-11-berufungsbegruendung-O.pdf.p7s"),
                    "content": r("references", "REF-11-berufungsbegruendung-O.pdf"),
                    "anchor": c("document_root.pem"),
                    "certfile": c("document_intermediate.pem"),
                    "inform": "DER", "binary": True,
                    "attime": DOCUMENT_SIGNING_TIME, "purpose": "any",
                    "out": os.path.join(PREP, "outputs",
                                        "document_verified_content.bin")},
         "timeout_seconds": 120,
         "purpose": "Verify the document CMS signature over the exact detached content.",
         "control_role": "MEASUREMENT"},

        {"step_id": "mutated_vhn_leaf_signature",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": c("vhn_root.pem"),
                    "intermediates": c("vhn_intermediate_selected_manual_pem.pem"),
                    "leaf": k("vhn_leaf_der_signature_mutated.pem"),
                    "attime": VHN_SIGNING_TIME,
                    "purpose": "any"},
         "timeout_seconds": 120,
         "purpose": ("One byte inside the signatureValue BIT STRING. The "
                     "certificate still parses; its signature must fail. R6's "
                     "fixture could not be parsed at all and therefore proved "
                     "nothing about signatures."),
         "control_role": "MUTATION"},

        {"step_id": "unparseable_vhn_leaf",
         "operation": "OPENSSL_VERIFY_CERT_CHAIN",
         "params": {"anchor": c("vhn_root.pem"),
                    "intermediates": c("vhn_intermediate_selected_manual_pem.pem"),
                    "leaf": k("vhn_leaf_unparseable_der.pem"),
                    "attime": VHN_SIGNING_TIME,
                    "purpose": "any"},
         "timeout_seconds": 120,
         "purpose": ("A malformed certificate must be refused at load. A "
                     "separate control from the signature mutation above, "
                     "under its own name, so the two are never confused."),
         "control_role": "NEGATIVE"},

        {"step_id": "wrong_vhn_content",
         "operation": "OPENSSL_VERIFY_CMS",
         "params": {"cms": r("references", "REF-11-vhn.xml.p7s"),
                    "content": r("references", "REF-11-berufungsbegruendung-O.pdf"),
                    "anchor": c("vhn_root.pem"),
                    "certfile": c("vhn_intermediate_selected_manual_pem.pem"),
                    "inform": "DER", "binary": True,
                    "attime": VHN_SIGNING_TIME, "purpose": "any",
                    "out": os.path.join(PREP, "outputs",
                                        "wrong_content_control.bin")},
         "timeout_seconds": 120,
         "purpose": ("Unrelated detached content must not verify. Under R6's "
                     "purpose this control never reached the content at all."),
         "control_role": "NEGATIVE"},

        {"step_id": "mutated_vhn_content",
         "operation": "OPENSSL_VERIFY_CMS",
         "params": {"cms": r("references", "REF-11-vhn.xml.p7s"),
                    "content": k("vhn_covered_content_one_byte_mutated.xml"),
                    "anchor": c("vhn_root.pem"),
                    "certfile": c("vhn_intermediate_selected_manual_pem.pem"),
                    "inform": "DER", "binary": True,
                    "attime": VHN_SIGNING_TIME, "purpose": "any",
                    "out": os.path.join(PREP, "outputs",
                                        "mutated_content_control.bin")},
         "timeout_seconds": 120,
         "purpose": ("One byte of the covered content, length preserved. The "
                     "content digest must fail."),
         "control_role": "MUTATION"},
    ]

    matrix = [
        {"purpose_model": {
            "why_two_checks": (
                "R6 used one -purpose value for path validation and for "
                "signing entitlement at once. The VHN leaf's only extended "
                "key usage is id-kp-clientAuth, so smimesign was refused with "
                "error 26 and every downstream control failed on the "
                "certificate rather than on what it was testing."),
            "path_validation_purpose": "any",
            "path_validation_purpose_is_not_a_suppression_flag": True,
            "path_validation_reason": (
                "`any` selects X509_PURPOSE_ANY. Issuer chaining, signature "
                "checking, validity at -attime, basic constraints and the "
                "absence of any default trust store are all still enforced. "
                "It declines to impose an application purpose, and the "
                "application purpose is answered by the separate check below."),
            "entitlement_check": "vhn_key_usage_conformance",
            "no_suppression_flag_present": True}},

        {"step_id": "synthetic_chain_positive", "expected_exit_code": 0,
         "required_result": "PASS",
         "why": "if this fails, nothing below is evidence of anything"},
        {"step_id": "synthetic_chain_missing_anchor",
         "expected_exit_code": "NONZERO",
         "expected_failure_reason": "CHAIN_INCOMPLETE",
         "required_result": "FAILS_AS_DESIGNED"},

        {"step_id": "vhn_chain_path_validation", "expected_exit_code": 0,
         "validation_time": "2026-02-27T22:55:25Z",
         "validation_time_epoch": VHN_SIGNING_TIME,
         "validation_time_justification":
             "claimed CMS signingTime; not a trusted timestamp",
         "validation_time_inside_leaf_validity": True,
         "validation_time_inside_intermediate_validity": True,
         "validation_time_inside_root_validity": True},
        {"step_id": "document_chain_path_validation", "expected_exit_code": 0,
         "validation_time": "2026-02-27T22:54:57Z",
         "validation_time_epoch": DOCUMENT_SIGNING_TIME,
         "validation_time_justification":
             "claimed CMS signingTime; not a trusted timestamp",
         "validation_time_inside_leaf_validity": True,
         "validation_time_inside_intermediate_validity": True,
         "validation_time_inside_root_validity": True},

        {"step_id": "vhn_cms", "expected_exit_code": 0},
        {"step_id": "document_cms", "expected_exit_code": 0},

        {"step_id": "mutated_vhn_leaf_signature",
         "expected_exit_code": "NONZERO",
         "expected_failure_reason": "CERT_SIGNATURE_FAILURE",
         "required_result": "FAILS_AS_DESIGNED",
         "fixture": mut["cert_signature"]},
        {"step_id": "unparseable_vhn_leaf", "expected_exit_code": "NONZERO",
         "expected_failure_reason": "PARSE_REFUSAL",
         "required_result": "FAILS_AS_DESIGNED",
         "distinct_from": "mutated_vhn_leaf_signature",
         "fixture": mut["cert_parse_refusal"]},
        {"step_id": "wrong_vhn_content", "expected_exit_code": "NONZERO",
         "expected_failure_reason": "CONTENT_DIGEST_FAILURE",
         "required_result": "FAILS_AS_DESIGNED"},
        {"step_id": "mutated_vhn_content", "expected_exit_code": "NONZERO",
         "expected_failure_reason": "CONTENT_DIGEST_FAILURE",
         "required_result": "FAILS_AS_DESIGNED",
         "fixture": mut["content"]},

        {"check_id": "vhn_key_usage_conformance",
         "evaluated_from": ["parse_vhn_leaf"],
         "question": ("Is the VHN signer certificate entitled to produce the "
                      "CMS signature it produced?"),
         "measured_key_usage": ["digitalSignature", "nonRepudiation",
                                "keyEncipherment", "dataEncipherment"],
         "measured_extended_key_usage": ["id-kp-clientAuth (1.3.6.1.5.5.7.3.2)"],
         "criterion_key_usage": (
             "RFC 5652 requires digitalSignature or nonRepudiation for a CMS "
             "signing key"),
         "expected_key_usage_result": "SATISFIED",
         "criterion_extended_key_usage": (
             "an S/MIME signing purpose requires id-kp-emailProtection or "
             "anyExtendedKeyUsage"),
         "expected_extended_key_usage_result": "NOT_SATISFIED_FOR_SMIME",
         "specification_reference": (
             "prompts/L1-A31.md EDGE CASES: 'a certificate whose extended key "
             "usage does not include the purpose in question'"),
         "verdict_effect": (
             "REPORTED_AS_A_FINDING. This plan does not decide what verdict "
             "follows. Whether a beA VHN certificate carrying only clientAuth "
             "is conforming for its own profile is not answerable from the "
             "material bound here, and a run that answers it anyway would be "
             "asserting rather than measuring.")},

        {"check_id": "document_key_usage_conformance",
         "evaluated_from": ["parse_document_leaf"],
         "measured_key_usage": ["nonRepudiation"],
         "measured_extended_key_usage": [],
         "criterion_extended_key_usage": (
             "RFC 5280: an absent EKU extension imposes no purpose restriction"),
         "expected_key_usage_result": "SATISFIED",
         "expected_extended_key_usage_result": "NO_RESTRICTION_ASSERTED"},

        {"revocation": "NOT_ASSESSED_OFFLINE",
         "reason": "REF-10 is absent from the accepted reference manifest",
         "never_reported_as": "not revoked"},

        {"anchor_provenance": {
            "vhn_root": "SAFE Root CA 2017, O=BNotK — REF-08",
            "document_root": "BNotK Root CA 2017 — REF-08",
            "corroboration": (
                "each of the four CA certificates was compared in DER against "
                "the operator-supplied official chain material taken in at "
                "work/operator_intake/L1-A31/official_chain_material_r7_"
                "2026-08-26; all four are identical, and TL-DE.XML matches its "
                "own published SHA-256"),
            "not_thereby_trusted": (
                "presence in the supplied material is not trust; the "
                "provenance recorded here is where the bytes came from")}},
    ]

    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A31",
        "run_phase": "RUN-A",
        "scope": (
            "OpenSSL verification of both REF-11 detached CMS objects and "
            "their complete explicit certificate chains at the claimed signing "
            "times, with parse evidence, an explicit key-usage conformance "
            "determination, and positive, negative and mutation controls whose "
            "expected failure reason is asserted and not merely their exit "
            "code. Revocation is NOT_ASSESSED_OFFLINE because REF-10 is absent."),
        "static_analysis": (
            "The active target is the immutable REF-11 archive bound by "
            "references/manifest.json. Certificate PEM files are byte-for-byte "
            "carry-forwards of R6's staged set, each additionally compared in "
            "DER against the operator-supplied official material. Control "
            "fixtures are rebuilt for R7: the synthetic chain's leaf carries "
            "emailProtection and its validation time is derived from its own "
            "issue time; the certificate mutation is one byte inside the "
            "signatureValue BIT STRING, proved parseable and proved to fail "
            "on signature; a malformed certificate is a separate control under "
            "its own name. Path validation uses purpose `any` and the "
            "application purpose is determined separately; the frozen builder "
            "adds -no-CAfile, -no-CApath and -no-CAstore, and cannot emit any "
            "suppression flag."),
        "target": {
            "path": target,
            "sha256": sha(target),
            "identity_evidence": (
                "references/manifest.json identifies this operator-supplied "
                "archive and binds the same SHA-256; its extracted REF-11 "
                "members are separately hash-bound."),
        },
        "steps": steps,
        "test_matrix": matrix,
    }


def a31_run_b(staging):
    """RUN-B: a different implementation, given no RUN-A conclusion."""
    target = r("references", "REF-11-original-mail-attachment.zip")
    certs = os.path.join(PREP, "certs")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A31",
        "run_phase": "RUN-B",
        "scope": (
            "Independent verification of both REF-11 detached CMS objects and "
            "their certificate chains using the JDK PKIX CertPathValidator and "
            "Bouncy Castle 1.85, with no OpenSSL in the call path and no "
            "shared trust store. Same target, same references, same validation "
            "times, different implementation."),
        "static_analysis": (
            "RUN-B receives the audit id, the target and reference digests, "
            "the validation times, its own method and its own controls, plus "
            "the fact that RUN-A is sealed and whether its seal is intact. It "
            "receives no RUN-A finding, verdict, self-critique or disproof, "
            "and no path that points at one; policy.RUN_B_ALLOWED_KEYS is an "
            "allowlist and the isolation check covers results/, evidence/ and "
            "work/ for this audit."),
        "target": {
            "path": target,
            "sha256": sha(target),
            "identity_evidence": (
                "bound by references/manifest.json; identical digest to the "
                "one RUN-A was bound to, which is what makes the two "
                "comparable"),
        },
        "steps": [
            {"step_id": "independent_vhn_cms",
             "operation": "AUDIT_MODULE_RUN",
             "params": {
                 "module": "automation.independent_cms_cli",
                 "args": ["--cms", r("references", "REF-11-vhn.xml.p7s"),
                          "--content",
                          r("references", "REF-11-vhn-covered-content.xml"),
                          "--leaf", os.path.join(
                              certs,
                              "vhn_leaf_from_sealed_p7s_parse_evidence.pem"),
                          "--intermediate", os.path.join(
                              certs,
                              "vhn_intermediate_selected_manual_pem.pem"),
                          "--root", os.path.join(certs, "vhn_root.pem"),
                          "--validation-time", str(VHN_SIGNING_TIME),
                          "--out", os.path.join(
                              RUNB_WORK, "a31_independent_vhn.json")]},
             "timeout_seconds": 300,
             "purpose": ("JDK PKIX and Bouncy Castle verify the VHN CMS and "
                         "chain at the same stated time."),
             "control_role": "MEASUREMENT"},
            {"step_id": "independent_document_cms",
             "operation": "AUDIT_MODULE_RUN",
             "params": {
                 "module": "automation.independent_cms_cli",
                 "args": ["--cms", r("references",
                                     "REF-11-berufungsbegruendung-O.pdf.p7s"),
                          "--content", r("references",
                                         "REF-11-berufungsbegruendung-O.pdf"),
                          "--leaf", os.path.join(
                              certs,
                              "document_leaf_from_sealed_p7s_parse_evidence.pem"),
                          "--intermediate", os.path.join(
                              certs, "document_intermediate.pem"),
                          "--root", os.path.join(certs, "document_root.pem"),
                          "--validation-time", str(DOCUMENT_SIGNING_TIME),
                          "--out", os.path.join(
                              RUNB_WORK, "a31_independent_document.json")]},
             "timeout_seconds": 300,
             "purpose": "The same, for the document chain.",
             "control_role": "MEASUREMENT"},
        ],
        "test_matrix": [
            {"independence": {
                "language": "Java 21, not C",
                "library": "Bouncy Castle 1.85, not OpenSSL 3.5.5",
                "path_engine": "JDK PKIX CertPathValidator, not X509_verify_cert",
                "shared_code": "none", "shared_trust_store": "none"}},
            {"isolation": {
                "run_a_conclusions_supplied": False,
                "run_a_paths_supplied": False,
                "supplied": list(sorted((
                    "audit_id", "target_path", "target_sha256",
                    "validation_time", "independent_method",
                    "required_controls", "phase_sequencing",
                    "run_a_seal_integrity")))}},
            {"step_id": "independent_vhn_cms", "expected_exit_code": 0},
            {"step_id": "independent_document_cms", "expected_exit_code": 0},
            {"revocation": "NOT_ASSESSED_OFFLINE"},
        ],
    }


def comparison_plan(audit_id, scope, matrix):
    target = {
        "L1-A31": r("references", "REF-11-original-mail-attachment.zip"),
        "L1-A34": r("references", "REF-11-vhn.xml.p7s"),
        "L1-A18": r("anonymization", "payload_scan.py"),
    }[audit_id]
    if audit_id == "L1-A18":
        target = "/home/ubuntu/project/WPNO/anonymization/payload_scan.py"
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": audit_id,
        "run_phase": "COMPARISON",
        "scope": scope,
        "static_analysis": (
            "COMPARISON reads the accepted usable attempt of RUN-A and the "
            "accepted usable attempt of RUN-B, and the complete attempt "
            "history of both. Superseded attempts are reported, not filtered: "
            "a comparison that shows only the attempts that worked is not a "
            "record of what happened. It refuses to run at all unless both "
            "phases have an accepted usable sealed attempt."),
        "target": {"path": target, "sha256": sha(target),
                   "identity_evidence": (
                       "the same target both runs were bound to; a comparison "
                       "across two different targets compares nothing")},
        "steps": [
            {"step_id": "collect_accepted_attempts",
             "operation": "PARSE_JSON_READONLY",
             "params": {"path": os.path.join(ROOT, "state", "progress.json")},
             "timeout_seconds": 60,
             "purpose": ("Read the accepted attempt pointer and the full "
                         "attempt history for RUN-A and RUN-B."),
             "control_role": "MEASUREMENT"},
            {"step_id": "compare_run_a_seal",
             "operation": "SHA256_FILE",
             "params": {"path": os.path.join(
                 ROOT, "evidence", audit_id, "RUN-A", "ATTEMPT_INDEX.json")},
             "timeout_seconds": 60,
             "purpose": "Bind the comparison to the attempt history it read.",
             "control_role": "MEASUREMENT"},
            {"step_id": "compare_run_b_seal",
             "operation": "SHA256_FILE",
             "params": {"path": os.path.join(
                 ROOT, "evidence", audit_id, "RUN-B", "ATTEMPT_INDEX.json")},
             "timeout_seconds": 60,
             "purpose": "The same, for RUN-B.",
             "control_role": "MEASUREMENT"},
        ],
        "test_matrix": matrix + [
            {"refusal": ("COMPARISON refuses unless both RUN-A and RUN-B have "
                         "an accepted usable sealed attempt")},
            {"superseded_attempts": "REPORTED_NOT_HIDDEN"},
            {"disagreement": ("a disagreement between the two methods is a "
                              "finding in its own right and is never resolved "
                              "by preferring the run that matches expectation")},
        ],
    }


# --------------------------------------------------------------- L1-A34
def a34_run_a(staging):
    certs = os.path.join(PREP, "certs")
    synth = staging["controls"]["synthetic"]
    synth_time = staging["controls"]["notes"]["synthetic_validation_time"]
    target = r("references", "REF-11-vhn.xml.p7s")
    staged_anchor = os.path.join(PREP, "staged_anchors", "vhn_root_from_der.pem")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A34",
        "run_phase": "RUN-A",
        "scope": (
            "Full verification of vhn.xml.p7s: CMS structure, signer identity "
            "mapping, the signature over the exact detached content, and the "
            "chain to the REF-08 anchor at the claimed signing time, with the "
            "DER anchor staged to PEM through the sanctioned route and with "
            "positive, negative and mutation controls."),
        "static_analysis": (
            "REF-08's SAFE Root CA anchor is supplied in DER. `-CAfile` reads "
            "PEM, and the catalogue refuses a DER anchor by inspecting the "
            "file's first bytes rather than its name. The anchor is therefore "
            "staged to PEM under work/ by trust_material.stage_der_anchor_as_"
            "pem, which records both digests and refuses to write into "
            "references/. The reference itself is never replaced."),
        "target": {"path": target, "sha256": sha(target),
                   "identity_evidence":
                       "bound by references/manifest.json as REF-11"},
        "steps": [
            {"step_id": "stage_der_anchor",
             "operation": "SHA256_FILE",
             "params": {"path": r("references", "REF-08-safe-root-ca-2017.der")},
             "timeout_seconds": 60,
             "purpose": ("Record the DER anchor's identity before staging. The "
                         "staged PEM must re-encode to this exact DER."),
             "control_role": "MEASUREMENT"},
            {"step_id": "parse_staged_anchor",
             "operation": "OPENSSL_PARSE_CERT",
             "params": {"cert": staged_anchor},
             "timeout_seconds": 120,
             "purpose": "Facts and fingerprint of the staged PEM anchor.",
             "control_role": "MEASUREMENT"},
            {"step_id": "synthetic_cms_positive",
             "operation": "OPENSSL_VERIFY_CMS",
             "params": {"cms": r(synth["cms_detached"]),
                        "content": r(synth["content"]),
                        "anchor": r(synth["root_pem"]),
                        "certfile": r(synth["intermediate_pem"]),
                        "inform": "DER", "binary": True,
                        "attime": synth_time, "purpose": "smimesign",
                        "out": os.path.join(PREP, "outputs",
                                            "a34_synthetic_positive.bin")},
             "timeout_seconds": 120,
             "purpose": "A detached CMS known valid by construction.",
             "control_role": "POSITIVE"},
            {"step_id": "synthetic_cms_wrong_content",
             "operation": "OPENSSL_VERIFY_CMS",
             "params": {"cms": r(synth["cms_detached"]),
                        "content": r(synth["wrong_content"]),
                        "anchor": r(synth["root_pem"]),
                        "certfile": r(synth["intermediate_pem"]),
                        "inform": "DER", "binary": True,
                        "attime": synth_time, "purpose": "smimesign",
                        "out": os.path.join(PREP, "outputs",
                                            "a34_synthetic_wrong.bin")},
             "timeout_seconds": 120,
             "purpose": "Unrelated content must not verify.",
             "control_role": "NEGATIVE"},
            {"step_id": "synthetic_cms_mutated_content",
             "operation": "OPENSSL_VERIFY_CMS",
             "params": {"cms": r(synth["cms_detached"]),
                        "content": r(synth["content_mutated"]),
                        "anchor": r(synth["root_pem"]),
                        "certfile": r(synth["intermediate_pem"]),
                        "inform": "DER", "binary": True,
                        "attime": synth_time, "purpose": "smimesign",
                        "out": os.path.join(PREP, "outputs",
                                            "a34_synthetic_mutated.bin")},
             "timeout_seconds": 120,
             "purpose": "One byte of the content must break the digest.",
             "control_role": "MUTATION"},
            {"step_id": "vhn_cms_against_staged_anchor",
             "operation": "OPENSSL_VERIFY_CMS",
             "params": {"cms": target,
                        "content": r("references",
                                     "REF-11-vhn-covered-content.xml"),
                        "anchor": staged_anchor,
                        "certfile": os.path.join(
                            certs, "vhn_intermediate_selected_manual_pem.pem"),
                        "inform": "DER", "binary": True,
                        "attime": VHN_SIGNING_TIME, "purpose": "any",
                        "out": os.path.join(PREP, "outputs",
                                            "a34_vhn_verified.bin")},
             "timeout_seconds": 120,
             "purpose": ("The audit's own question, against the anchor staged "
                         "from REF-08's DER."),
             "control_role": "MEASUREMENT"},
        ],
        "test_matrix": [
            {"der_to_pem_staging": {
                "source": "references/REF-08-safe-root-ca-2017.der",
                "staged": os.path.relpath(staged_anchor, ROOT),
                "route": "trust_material.stage_der_anchor_as_pem",
                "reference_modified": False,
                "re_encoded_der_must_equal_source_der": True}},
            {"step_id": "synthetic_cms_positive", "expected_exit_code": 0,
             "required_result": "PASS"},
            {"step_id": "synthetic_cms_wrong_content",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "CONTENT_DIGEST_FAILURE",
             "required_result": "FAILS_AS_DESIGNED"},
            {"step_id": "synthetic_cms_mutated_content",
             "expected_exit_code": "NONZERO",
             "expected_failure_reason": "CONTENT_DIGEST_FAILURE",
             "required_result": "FAILS_AS_DESIGNED"},
            {"step_id": "vhn_cms_against_staged_anchor",
             "expected_exit_code": 0,
             "validation_time_epoch": VHN_SIGNING_TIME,
             "validation_time": "2026-02-27T22:55:25Z"},
            {"revocation": "NOT_ASSESSED_OFFLINE"},
        ],
    }


def a34_run_b(staging):
    certs = os.path.join(PREP, "certs")
    target = r("references", "REF-11-vhn.xml.p7s")
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A34",
        "run_phase": "RUN-B",
        "scope": (
            "Independent verification of vhn.xml.p7s with the JDK PKIX "
            "validator and Bouncy Castle, taking the REF-08 anchor in its "
            "original DER so that no staging step is shared with RUN-A."),
        "static_analysis": (
            "RUN-B needs no DER-to-PEM staging: the JDK reads DER directly, so "
            "the one preparation step RUN-A depends on is absent here. That is "
            "part of what makes the second opinion independent rather than a "
            "second pass over the same preparation."),
        "target": {"path": target, "sha256": sha(target),
                   "identity_evidence": "bound by references/manifest.json"},
        "steps": [
            {"step_id": "independent_vhn_verification",
             "operation": "AUDIT_MODULE_RUN",
             "params": {
                 "module": "automation.independent_cms_cli",
                 "args": ["--cms", target,
                          "--content", r("references",
                                         "REF-11-vhn-covered-content.xml"),
                          "--leaf", os.path.join(
                              certs,
                              "vhn_leaf_from_sealed_p7s_parse_evidence.pem"),
                          "--intermediate", os.path.join(
                              certs,
                              "vhn_intermediate_selected_manual_pem.pem"),
                          "--root", r("references",
                                      "REF-08-safe-root-ca-2017.der"),
                          "--validation-time", str(VHN_SIGNING_TIME),
                          "--out", os.path.join(
                              A34_RUNB_WORK, "a34_independent_vhn.json")]},
             "timeout_seconds": 300,
             "purpose": "JDK PKIX and Bouncy Castle, DER anchor read directly.",
             "control_role": "MEASUREMENT"},
        ],
        "test_matrix": [
            {"independence": {"library": "Bouncy Castle 1.85",
                              "path_engine": "JDK PKIX",
                              "der_staging_required": False}},
            {"isolation": {"run_a_conclusions_supplied": False}},
            {"step_id": "independent_vhn_verification", "expected_exit_code": 0},
        ],
    }


# --------------------------------------------------------------- L1-A18
def a18_run_a(staging):
    target = "/home/ubuntu/project/WPNO/anonymization/payload_scan.py"
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A18",
        "run_phase": "RUN-A",
        "scope": (
            "IBAN Mod-97 correctness of the payload scanner's validator, "
            "checked in Python against the REF-01 SWIFT registry and REF-02, "
            "over the full 217-vector set, with empty input counted as an "
            "input and with a sabotage control."),
        "static_analysis": (
            "payload_scan.py is parsed, never imported: a top-level import "
            "executes code. The country rules come from REF-01 by way of "
            "corpora/R5_REF01_COUNTRY_RULES.jsonl. The MOD97-10 fold is a "
            "streaming remainder that never materialises the ~30-digit "
            "integer, which is deliberately a different shape of computation "
            "from RUN-B's big-integer modulus."),
        "target": {"path": target, "sha256": sha(target),
                   "identity_evidence": (
                       "bindings/L1-A18.binding.json records "
                       "productive_target_sha256 = 99b9e18bde4ff88c271362c4"
                       "ccdc34e526d043cefea7a35d1b060d5fba25153b for the "
                       "operator's own copy; the file on this machine hashes "
                       "to the same value, so the two are the same bytes")},
        "steps": [
            {"step_id": "parse_target",
             "operation": "PYTHON_AST_PARSE",
             "params": {"path": target},
             "timeout_seconds": 120,
             "purpose": "Parse, do not import.",
             "control_role": "MEASUREMENT"},
            {"step_id": "run_a_validation",
             "operation": "AUDIT_MODULE_RUN",
             "params": {"module": "automation.a18_run_a_cli",
                        "args": ["--vectors", VECTORS, "--rules", RULES,
                                 "--out", os.path.join(
                                     A18_RUNA_WORK, "run_a_results.json")]},
             "timeout_seconds": 300,
             "purpose": "217 vectors through the Python method.",
             "control_role": "MEASUREMENT"},
            {"step_id": "sabotage_control",
             "operation": "AUDIT_MODULE_RUN",
             "params": {"module": "automation.a18_run_a_cli",
                        "args": ["--vectors", VECTORS, "--rules", RULES,
                                 "--out", os.path.join(
                                     A18_RUNA_WORK, "sabotage_results.json"),
                                 "--sabotage", "mod97"]},
             "timeout_seconds": 300,
             "purpose": ("A deliberately broken modulus must change the "
                         "results. A sabotage that changes nothing is a "
                         "measurement error, not a passing control."),
             "control_role": "MUTATION"},
        ],
        "test_matrix": [
            {"vectors_in_corpus": 219, "applicable_vectors": 217,
             "empty_input_counted_as_an_input": True,
             "why": ("an empty IBAN is one input with one answer; dropping it "
                     "from the count makes 217 look like 216 and hides which "
                     "one went missing")},
            {"step_id": "run_a_validation", "expected_exit_code": 0,
             "expected_applicable_vector_count": 217,
             "expected_total_inputs_answered": 218},
            {"step_id": "sabotage_control", "expected_exit_code": 0,
             "expected_result_differs_from": "run_a_validation",
             "required_result": "SABOTAGE_PROVEN_EFFECTIVE",
             "zero_changed_results_is": "A MEASUREMENT ERROR, NOT A PASS"},
            {"references": {"REF-01": "swift-iban-registry-release-102",
                            "REF-02": "python-stdnum-2.2"}},
        ],
    }


def a18_run_b(staging):
    target = "/home/ubuntu/project/WPNO/anonymization/payload_scan.py"
    return {
        "schema": "wpno.level1.execution_plan/1",
        "audit_id": "L1-A18",
        "run_phase": "RUN-B",
        "scope": (
            "The same 217 vectors through an independent Java validator, "
            "which computes the check digits by building the expanded digit "
            "string and taking one big-integer modulus."),
        "static_analysis": (
            "automation/a18_run_b.py contains no validation logic at all. It "
            "launches the Java program and reads back what it said; putting "
            "any part of the decision there would put RUN-A's runtime back "
            "inside RUN-B. Every input line is prefixed with a marker so that "
            "an empty IBAN is still one input and cannot be lost in a blank "
            "line."),
        "target": {"path": target, "sha256": sha(target),
                   "identity_evidence": "same digest RUN-A was bound to"},
        "steps": [
            {"step_id": "run_b_validation",
             "operation": "AUDIT_MODULE_RUN",
             "params": {"module": "automation.a18_run_b_cli",
                        "args": ["--vectors", VECTORS, "--rules", RULES,
                                 "--work-dir", A18_RUNB_WORK,
                                 "--out", os.path.join(
                                     A18_RUNB_WORK, "run_b_results.json")]},
             "timeout_seconds": 300,
             "purpose": "217 vectors through the Java method.",
             "control_role": "MEASUREMENT"},
        ],
        "test_matrix": [
            {"independence": {"language": "Java 21, not Python",
                              "algorithm_shape": ("expanded digit string and "
                                                  "one big-integer modulus, "
                                                  "not a streaming fold"),
                              "shared_code": "none"}},
            {"isolation": {"run_a_conclusions_supplied": False,
                           "imports_a18_run_a": False}},
            {"step_id": "run_b_validation", "expected_exit_code": 0,
             "expected_applicable_vector_count": 217,
             "expected_total_inputs_answered": 218},
        ],
    }


PLANS = {
    ("L1-A31", "RUN-A"): a31_run_a,
    ("L1-A31", "RUN-B"): a31_run_b,
    ("L1-A31", "COMPARISON"): lambda s: comparison_plan(
        "L1-A31",
        "Compare the accepted RUN-A and RUN-B attempts for L1-A31.",
        [{"compared": ["chain path validation outcome",
                       "CMS signature outcome",
                       "key-usage conformance determination",
                       "validation time used",
                       "anchor identity"]}]),
    ("L1-A34", "RUN-A"): a34_run_a,
    ("L1-A34", "RUN-B"): a34_run_b,
    ("L1-A34", "COMPARISON"): lambda s: comparison_plan(
        "L1-A34",
        "Compare the accepted RUN-A and RUN-B attempts for L1-A34.",
        [{"compared": ["CMS verification outcome", "anchor identity",
                       "validation time used",
                       "whether DER staging changed the answer"]}]),
    ("L1-A18", "RUN-A"): a18_run_a,
    ("L1-A18", "RUN-B"): a18_run_b,
    ("L1-A18", "COMPARISON"): lambda s: comparison_plan(
        "L1-A18",
        "Compare the accepted RUN-A and RUN-B attempts for L1-A18.",
        [{"compared": ["per-vector verdicts across all 217 vectors",
                       "the empty-input result",
                       "the reason recorded for every disagreement"]}]),
}


def main():
    staging = load_staging()
    written = []
    for (audit_id, phase), builder in sorted(PLANS.items()):
        plan = builder(staging)
        schema_validation.validate_named(plan, "execution_plan.schema.json")
        operation_catalog.validate_plan_operations(plan)
        directory = os.path.join(OUT, audit_id, phase)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "plan.json")
        raw = json.dumps(plan, indent=2, sort_keys=True) + "\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        with open(path + ".sha256", "w", encoding="utf-8") as fh:
            fh.write("%s  plan.json\n" % hashing.sha256_text(raw))
        written.append({"audit_id": audit_id, "run_phase": phase,
                        "path": os.path.relpath(path, ROOT),
                        "sha256": hashing.sha256_text(raw),
                        "steps": len(plan["steps"]),
                        "gated_operations": sorted(set(
                            operation_catalog.validate_plan_operations(plan)))})
    print(json.dumps({"candidate_plans": written, "count": len(written)},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
