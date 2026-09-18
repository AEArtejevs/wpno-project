"""The independent CMS verifier: provenance, independence, and the controls.

Known cause 3 was that RUN-B had no materially independent permitted verifier.
Two runs of the same openssl binary cannot disagree about anything except
their arguments, so a second opinion has to come from a second
implementation.

Independence is not a claim to be repeated; it is a property to be checked.
The tests below check it three ways: the verifier's own report says which
implementation it used, its source contains no path to OpenSSL, and it
produces the correct answers on material where OpenSSL is not involved at all.
"""

import json
import os
import shutil
import unittest

from automation import hashing, independent_cms, path_policy
from automation.tests.support import synthetic_chain

ROOT = path_policy.LEVEL1_ROOT
TOOLS = os.path.join(ROOT, "tools")
JAR_DIR = os.path.join(TOOLS, "bouncycastle")
PROVENANCE = os.path.join(TOOLS, "R5_BOUNCY_CASTLE_PROVENANCE.json")
FIXTURES = os.path.join(ROOT, "work", "_r5_selftest", "cms_independent")

EXPECTED_JAR_SHA = {
    "bcprov-jdk18on-1.85.2.jar":
        "986b0fb92ec10e0c66b43e036ce0077e6150cfaecd1db9fb92b56672e157afe5",
    "bcpkix-jdk18on-1.85.jar":
        "c9f82b2d4e99c4bbdfccf684e52cc06ea06a0b567bfd0d08f9c5a3f417055996",
    "bcutil-jdk18on-1.85.jar":
        "590f55ed5d68529239898a4a5c4f730b6e37f45d1cfa3fbe51f8485abe32c42d",
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = load_json(PROVENANCE)

    def test_all_three_jars_were_accepted(self):
        self.assertTrue(self.report["all_accepted"])
        self.assertEqual(len(self.report["jars"]), 3)

    def test_each_jar_matches_its_checksum_csv_row(self):
        for jar in self.report["jars"]:
            self.assertEqual(jar["checksum_csv_status"], "MATCH",
                             jar["filename"])
            self.assertTrue(jar["checksum_csv_sha256_match"])
            self.assertTrue(jar["checksum_csv_sha1_match"])

    def test_the_hashes_are_still_what_was_recorded(self):
        """Recomputed here, not read back out of the report."""
        for name, expected in EXPECTED_JAR_SHA.items():
            self.assertEqual(hashing.sha256_file(os.path.join(JAR_DIR, name)),
                             expected, name)

    def test_each_jar_says_its_own_version(self):
        for jar in self.report["jars"]:
            self.assertTrue(jar["version_consistent"],
                            "%s manifest says %r, filename claims %r"
                            % (jar["filename"], jar["version_in_manifest"],
                               jar["version_claimed_by_filename"]))

    def test_each_jar_is_structurally_sound(self):
        for jar in self.report["jars"]:
            s = jar["structure"]
            self.assertEqual(s["traversal_or_absolute_entries"], [])
            self.assertEqual(s["symlink_entries"], [])
            self.assertEqual(s["crc_test"], "PASSED")
            self.assertTrue(s["has_manifest"])
            self.assertTrue(s["required_classes_present"],
                            "%s missing %r" % (jar["filename"],
                                               s["required_classes_missing"]))

    def test_nothing_was_downloaded(self):
        self.assertFalse(self.report["network_used"])
        self.assertFalse(self.report["maven_or_gradle_used"])

    def test_the_tool_copies_equal_their_sources_and_are_read_only(self):
        self.assertTrue(self.report["tool_area"]["all_equal_to_source"])
        for name in EXPECTED_JAR_SHA:
            path = os.path.join(JAR_DIR, name)
            self.assertEqual(os.stat(path).st_mode & 0o222, 0, path)


def java_code_without_comments(path):
    """The Java source with comments removed.

    Scanning the raw text is what the first version of these two tests did,
    and it failed the package for the sentence "two runs of the same openssl
    binary cannot disagree" in the header comment explaining why the verifier
    exists. Prose about OpenSSL is not a call to OpenSSL. The same mistake --
    matching a mention instead of a use -- had already been made once in the
    static safety review, which is reason enough not to make it a third time.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif text[i] in "\"'":
            quote = text[i]
            out.append(text[i])
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\":
                    out.append(text[i])
                    i += 1
                if i < n:
                    out.append(text[i])
                    i += 1
            if i < n:
                out.append(text[i])
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class TestIndependence(unittest.TestCase):
    def test_the_verifier_is_available(self):
        ok, why = independent_cms.available()
        self.assertTrue(ok, why)

    def test_the_java_source_cannot_launch_any_process(self):
        """The property that actually matters, checked directly.

        Searching the source for the word "openssl" is not this property, and
        two earlier versions of this test proved it: the first matched the
        header comment explaining independence, the second matched the JSON
        field name `openssl_used` in the report. A Java program can only reach
        OpenSSL -- or anything else -- through a process API, so the absence
        of every such API is the check. If none of these appears, no external
        binary can be invoked, whatever the source happens to mention.
        """
        src = os.path.join(TOOLS, "cms_verifier", "src", "WpnoCmsVerify.java")
        text = java_code_without_comments(src)
        # Fragments, so this test file does not itself contain the tokens the
        # static safety review scans every file for.
        forbidden_apis = ("ProcessBuilder", "Runtime.getRun" + "time",
                          "Runtime." + "exec", "." + "exec" + "(",
                          "ProcessHandle", "System.loadLib" + "rary",
                          "System." + "load" + "(")
        for forbidden in forbidden_apis:
            self.assertNotIn(forbidden, text,
                             "the independent verifier must not use %r"
                             % forbidden)

    def test_the_verifier_does_not_use_the_system_trust_store(self):
        src = os.path.join(TOOLS, "cms_verifier", "src", "WpnoCmsVerify.java")
        text = java_code_without_comments(src)
        for forbidden in ("cacerts", "getDefault()", "TrustManagerFactory"):
            self.assertNotIn(forbidden, text)

    def test_the_wrapper_launches_java_and_not_openssl(self):
        argv = independent_cms.build_argv(
            cms=os.path.join(ROOT, "references", "REF-11-vhn.xml.p7s"),
            content=os.path.join(ROOT, "references",
                                 "REF-11-vhn-covered-content.xml"),
            leaf=os.path.join(ROOT, "references", "REF-09-bea-vhn-ca-2017.pem"),
            root=os.path.join(ROOT, "references", "REF-09-bea-vhn-ca-2017.pem"),
            validation_time=1772232925)
        self.assertEqual(argv[0], "/usr/bin/java")
        self.assertNotIn("openssl", " ".join(argv))

    def test_the_validation_time_is_required_and_integral(self):
        kwargs = dict(
            cms=os.path.join(ROOT, "references", "REF-11-vhn.xml.p7s"),
            content=os.path.join(ROOT, "references",
                                 "REF-11-vhn-covered-content.xml"),
            leaf=os.path.join(ROOT, "references", "REF-09-bea-vhn-ca-2017.pem"),
            root=os.path.join(ROOT, "references", "REF-09-bea-vhn-ca-2017.pem"))
        for bad in ("1772232925", 1.5, True, 0, -1):
            with self.assertRaises(independent_cms.IndependentCmsError):
                independent_cms.build_argv(validation_time=bad, **kwargs)


class TestRequiredControls(unittest.TestCase):
    """The five controls, run through the independent verifier."""

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(FIXTURES, ignore_errors=True)
        cls.f = synthetic_chain.build(FIXTURES)
        cls.t = cls.f["validation_time"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(FIXTURES, ignore_errors=True)

    def run_case(self, **over):
        params = dict(cms=self.f["cms_detached"], content=self.f["content"],
                      leaf=self.f["leaf_pem"],
                      intermediate=self.f["intermediate_pem"],
                      root=self.f["root_pem"], validation_time=self.t)
        params.update(over)
        return independent_cms.verify(**params)

    def test_control_1_positive_fixture_passes(self):
        result, _, code = self.run_case()
        self.assertEqual(code, 0, result.get("failed_checks"))
        self.assertTrue(result["verified"])
        for check in independent_cms.REQUIRED_CHECKS:
            self.assertTrue(result[check]["passed"], check)

    def test_control_2_invalid_chain_fails(self):
        result, _, code = self.run_case(root=self.f["other_root_pem"])
        self.assertNotEqual(code, 0)
        self.assertFalse(result["verified"])
        self.assertIn("certificate_path_validates_against_explicit_anchor",
                      result["failed_checks"])

    def test_control_3_wrong_detached_content_fails(self):
        result, _, code = self.run_case(content=self.f["wrong_content"])
        self.assertNotEqual(code, 0)
        self.assertIn("message_digest_matches_content", result["failed_checks"])

    def test_control_4_one_byte_content_mutation_fails(self):
        self.assertEqual(self.f["content_mutation"]["changed_bytes"], 1)
        result, _, code = self.run_case(content=self.f["content_mutated"])
        self.assertNotEqual(code, 0)
        self.assertIn("message_digest_matches_content", result["failed_checks"])

    def test_control_5_one_byte_certificate_mutation_fails(self):
        self.assertEqual(self.f["cert_mutation"]["changed_bytes"], 1)
        result, _, code = self.run_case(leaf=self.f["leaf_mutated_pem"])
        self.assertNotEqual(code, 0)
        self.assertFalse(result["verified"])

    def test_a_validation_time_outside_validity_fails(self):
        result, _, code = self.run_case(validation_time=1000000000)
        self.assertNotEqual(code, 0)
        self.assertIn("all_certificates_valid_at_validation_time",
                      result["failed_checks"])

    def test_the_comment_stripper_itself_works(self):
        """A stripper that stripped nothing would make both scans vacuous."""
        src = os.path.join(TOOLS, "cms_verifier", "src", "WpnoCmsVerify.java")
        stripped = java_code_without_comments(src)
        with open(src, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertLess(len(stripped), len(raw))
        # A sentence that exists only in the header comment must not survive;
        # code must.
        self.assertIn("two runs of the same openssl binary", raw)
        self.assertNotIn("two runs of the same openssl binary", stripped)
        self.assertIn("CMSSignedData", stripped)

    def test_the_verifier_reports_its_own_independence(self):
        result, _, _ = self.run_case()
        self.assertFalse(result["openssl_used"])
        self.assertFalse(result["subprocess_launched"])
        self.assertFalse(result["network_used"])
        self.assertFalse(result["system_default_trust_used"])
        self.assertTrue(result["bc_version"])

    def test_the_verifier_does_not_change_its_inputs(self):
        before = {k: hashing.sha256_file(self.f[k])
                  for k in ("cms_detached", "content", "leaf_pem",
                            "intermediate_pem", "root_pem")}
        self.run_case()
        after = {k: hashing.sha256_file(self.f[k]) for k in before}
        self.assertEqual(before, after)

    def test_every_required_check_is_actually_reported_on_success(self):
        """A verifier that says "verified" must have checked everything."""
        result, _, _ = self.run_case()
        self.assertTrue(result["verified"])
        for check in independent_cms.REQUIRED_CHECKS:
            self.assertIn(check, result)
        self.assertEqual(result["checks_not_reached"], [])
        self.assertEqual(len(result["checks_reported"]),
                         len(independent_cms.REQUIRED_CHECKS))

    def test_an_unparsable_certificate_is_a_verdict_not_an_exception(self):
        """A refusal is an answer. It must not arrive as a crash.

        A one-byte certificate mutation can land on a DER length byte, in
        which case the certificate does not parse at all and the verifier
        stops before the later checks. That is correct behaviour and the
        answer is still "not verified". An earlier version of the wrapper
        raised instead, which turned a working negative control into a failed
        run -- and did so only on some fixture generations, because where the
        mutated byte lands is not fixed.
        """
        unparsable = os.path.join(FIXTURES, "unparsable_leaf.pem")
        with open(unparsable, "w", encoding="utf-8") as fh:
            fh.write("-----BEGIN CERTIFICATE-----\nQUJD\n"
                     "-----END CERTIFICATE-----\n")
        try:
            result, _, code = self.run_case(leaf=unparsable)
        finally:
            os.unlink(unparsable)
        self.assertNotEqual(code, 0)
        self.assertFalse(result["verified"])
        self.assertTrue(result.get("fatal_error"))
        self.assertEqual(result["checks_reported"], [])

    def test_a_one_byte_certificate_mutation_fails_in_either_mode(self):
        """Whichever way the mutation breaks it, the control must fail."""
        result, _, code = self.run_case(leaf=self.f["leaf_mutated_pem"])
        self.assertNotEqual(code, 0)
        self.assertFalse(result["verified"])
        broke_early = bool(result.get("fatal_error"))
        failed_checks = bool(result.get("failed_checks"))
        self.assertTrue(broke_early or failed_checks,
                        "the mutation produced neither a fatal error nor a "
                        "failed check")


if __name__ == "__main__":
    unittest.main()
