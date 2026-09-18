"""L1-A34 trust anchor staging, R5 remediation of known cause 2.

R4 handed `references/REF-08-safe-root-ca-2017.der` directly to
`openssl cms -verify -CAfile`. `-CAfile` reads PEM. The sealed R4 evidence for
L1-A34 RUN-A E0004 records exit 2 and the stderr line

    Error loading file .../references/REF-08-safe-root-ca-2017.der

The reference is valid DER, it is the correct anchor, and it is not missing.
Nothing about it may be replaced or rewritten. What was wrong was that a DER
file was passed where a PEM file was required, and neither platform said so:
LibreSSL called it a loading error, and OpenSSL 3.5.5 reports a certificate
verify error instead, which reads like a finding about the evidence.

The remediation is a staged copy: the DER stays exactly as it is, a PEM form
of it is written once under `work/`, proved to be the same certificate, and
that copy — and only that copy — is what `-CAfile` ever sees.
"""

import os
import shutil
import unittest

from automation import (hashing, operation_catalog, path_policy,
                        trust_material)

STAGING_DIR = os.path.join(path_policy.LEVEL1_ROOT, "work", "_r5_selftest",
                           "a34_staging")
REF08_DER = os.path.join(path_policy.LEVEL1_ROOT, "references",
                         "REF-08-safe-root-ca-2017.der")
REF08_DER_SHA256 = \
    "1abddfa573cf1dcd5a75f164bc828e6d4177c448849535912eed3c7825bfc9fc"
REF09_PEM = os.path.join(path_policy.LEVEL1_ROOT, "references",
                         "REF-09-bea-vhn-ca-2017.pem")


class TestTheDefectIsDetected(unittest.TestCase):
    """A DER anchor must be refused by name, not silently mis-parsed."""

    def test_der_passed_as_cafile_is_rejected_with_a_useful_message(self):
        with self.assertRaises(operation_catalog.OperationError) as caught:
            operation_catalog.build_argv("OPENSSL_VERIFY_CMS", {
                "cms": REF09_PEM, "anchor": REF08_DER, "content": REF09_PEM,
                "attime": 1772232925,
                "out": os.path.join(STAGING_DIR, "x.out")})
        message = str(caught.exception)
        self.assertIn("DER", message)
        self.assertIn("stage", message.lower())

    def test_the_rejection_is_by_content_not_by_file_extension(self):
        """A name is not evidence of a format."""
        os.makedirs(STAGING_DIR, exist_ok=True)
        misnamed = os.path.join(STAGING_DIR, "actually_der.pem")
        shutil.copyfile(REF08_DER, misnamed)
        try:
            with self.assertRaises(operation_catalog.OperationError):
                operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
                    "anchor": misnamed, "leaf": REF09_PEM,
                    "attime": 1772232925})
        finally:
            os.unlink(misnamed)

    def test_a_pem_anchor_is_accepted_unchanged(self):
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": REF09_PEM, "leaf": REF09_PEM, "attime": 1772232925})
        self.assertIn(path_policy.normalize(REF09_PEM), argv)


class TestStaging(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
        os.makedirs(STAGING_DIR, exist_ok=True)
        self.dest = os.path.join(STAGING_DIR, "ref08.staged.pem")

    def tearDown(self):
        shutil.rmtree(STAGING_DIR, ignore_errors=True)

    def stage(self, **over):
        kwargs = dict(der_path=REF08_DER, dest_path=self.dest,
                      expected_sha256=REF08_DER_SHA256,
                      audit_id="L1-A34", run_phase="RUN-A")
        kwargs.update(over)
        return trust_material.stage_der_anchor_as_pem(**kwargs)

    # -- identity -----------------------------------------------------------
    def test_the_staged_copy_is_the_same_certificate(self):
        record = self.stage()
        self.assertTrue(record["identity_equal"])
        for field in ("fingerprint_equal", "subject_equal", "issuer_equal",
                      "public_key_equal"):
            self.assertTrue(record["identity_equality"][field], field)

    def test_the_record_states_both_hashes(self):
        record = self.stage()
        self.assertEqual(record["source_der_sha256"], REF08_DER_SHA256)
        self.assertEqual(record["staged_pem_sha256"],
                         hashing.sha256_file(self.dest))
        self.assertNotEqual(record["source_der_sha256"],
                            record["staged_pem_sha256"])

    def test_the_subject_is_the_expected_anchor(self):
        record = self.stage()
        self.assertIn("SAFE Root CA 2017", record["staged_identity"]["subject"])

    # -- the source is untouched -------------------------------------------
    def test_the_der_reference_is_not_modified(self):
        before = hashing.sha256_file(REF08_DER)
        record = self.stage()
        after = hashing.sha256_file(REF08_DER)
        self.assertEqual(before, after)
        self.assertTrue(record["source_reference_unchanged"])

    def test_a_wrong_expected_hash_stops_the_staging(self):
        with self.assertRaises(trust_material.TrustMaterialError):
            self.stage(expected_sha256="0" * 64)
        self.assertFalse(os.path.exists(self.dest))

    # -- placement ----------------------------------------------------------
    def test_conversion_inside_references_is_forbidden(self):
        inside = os.path.join(path_policy.LEVEL1_ROOT, "references",
                              "REF-08-safe-root-ca-2017.staged.pem")
        with self.assertRaises(trust_material.TrustMaterialError) as caught:
            self.stage(dest_path=inside)
        self.assertIn("references", str(caught.exception))
        self.assertFalse(os.path.exists(inside))

    def test_staging_outside_work_is_forbidden(self):
        outside = os.path.join(path_policy.LEVEL1_ROOT, "state", "anchor.pem")
        with self.assertRaises(trust_material.TrustMaterialError):
            self.stage(dest_path=outside)
        self.assertFalse(os.path.exists(outside))

    def test_an_existing_staged_file_is_never_overwritten(self):
        self.stage()
        with self.assertRaises(trust_material.TrustMaterialError) as caught:
            self.stage()
        self.assertIn("never overwritten", str(caught.exception))

    def test_the_staged_file_is_read_only(self):
        self.stage()
        self.assertEqual(oct(os.stat(self.dest).st_mode & 0o777), oct(0o444))

    # -- evidence -----------------------------------------------------------
    def test_staging_evidence_is_retained(self):
        record = self.stage()
        out = os.path.join(STAGING_DIR, "ref08.staging_evidence.json")
        trust_material.write_staging_evidence(record, out)
        self.assertTrue(os.path.exists(out))
        import json
        with open(out, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["source_der_sha256"], REF08_DER_SHA256)
        self.assertFalse(saved["system_trust_used"])
        self.assertFalse(saved["default_trust_used"])
        self.assertFalse(saved["conversion_inside_references"])

    # -- conversion ---------------------------------------------------------
    def test_conversion_is_in_process(self):
        record = self.stage()
        self.assertEqual(record["conversion_method"],
                         "IN_PROCESS_BASE64_NO_SUBPROCESS")

    def test_pem_input_is_refused_by_the_encoder(self):
        with open(REF09_PEM, "rb") as fh:
            pem = fh.read()
        with self.assertRaises(trust_material.TrustMaterialError):
            trust_material.der_to_pem_bytes(pem)

    def test_non_der_input_is_refused_by_the_encoder(self):
        with self.assertRaises(trust_material.TrustMaterialError):
            trust_material.der_to_pem_bytes(b"not a certificate at all")
        with self.assertRaises(trust_material.TrustMaterialError):
            trust_material.der_to_pem_bytes(b"")

    def test_the_encoder_round_trips_through_openssl(self):
        """Our encoder's output must be readable by a tool we did not write."""
        record = self.stage()
        self.assertEqual(record["staged_identity"]["fingerprint_sha256"],
                         record["source_identity"]["fingerprint_sha256"])


class TestResolveForCafile(unittest.TestCase):
    """The call site never has to remember which case it is in."""

    def setUp(self):
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
        os.makedirs(STAGING_DIR, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(STAGING_DIR, ignore_errors=True)

    def test_a_der_anchor_is_staged_and_the_staged_path_returned(self):
        result = trust_material.resolve_anchor_for_cafile(
            REF08_DER, STAGING_DIR, audit_id="L1-A34", run_phase="RUN-A",
            expected_sha256=REF08_DER_SHA256)
        self.assertTrue(result["staged"])
        self.assertTrue(result["cafile_path"].endswith(".staged.pem"))
        self.assertTrue(os.path.exists(result["cafile_path"]))
        self.assertTrue(os.path.exists(result["staging_evidence_path"]))

    def test_a_pem_anchor_is_returned_unchanged_and_nothing_is_staged(self):
        result = trust_material.resolve_anchor_for_cafile(
            REF09_PEM, STAGING_DIR)
        self.assertFalse(result["staged"])
        self.assertEqual(result["cafile_path"], path_policy.normalize(REF09_PEM))
        self.assertEqual(os.listdir(STAGING_DIR), [])

    def test_the_staged_path_is_accepted_by_the_operation_catalogue(self):
        """The end-to-end point: what staging returns is what -CAfile takes."""
        result = trust_material.resolve_anchor_for_cafile(
            REF08_DER, STAGING_DIR, expected_sha256=REF08_DER_SHA256)
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": result["cafile_path"], "leaf": REF09_PEM,
            "attime": 1772232925})
        self.assertIn("-CAfile", argv)
        self.assertIn(result["cafile_path"], argv)


if __name__ == "__main__":
    unittest.main()
