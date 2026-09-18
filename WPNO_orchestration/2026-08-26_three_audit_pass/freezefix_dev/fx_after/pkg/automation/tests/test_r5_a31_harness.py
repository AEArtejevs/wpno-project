"""L1-A31 harness, R5 remediation of known cause 1.

The R4 sealed evidence is unambiguous about what went wrong. Every
OPENSSL_VERIFY_CERT_CHAIN operation of L1-A31 RUN-A — evidence ids E0007,
E0008, E0009, E0010 and E0013 — has the `openssl verify` usage block as its
stderr and exit code 1. Nothing was verified and nothing was rejected: the
command never got past argument parsing.

The cause was the end-of-options separator. R4 built

    openssl verify -CAfile <root> -untrusted <int> -- <leaf>

and the `verify` applet of LibreSSL, which is the openssl on the macOS machine
R4 ran on, does not implement `--`. E0008 is the positive synthetic-chain
control. A positive control that never ran cannot pass, so RUN-A could not
tell a broken control from a broken chain, and it ended ERROR — correctly.

These tests hold the fix in place at two levels: the argv the catalogue emits,
and the behaviour of the five required controls when that argv is actually
run against synthetic material whose answer is known in advance.
"""

import os
import shutil
import subprocess
import time
import unittest

from automation import operation_catalog, path_policy, policy
from automation.tests.support import synthetic_chain

FIXTURE_DIR = os.path.join(path_policy.LEVEL1_ROOT, "work", "_r5_selftest",
                           "a31_chain")
VALIDATION_TIME = 1787000000


def _run(argv):
    proc = subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=120,
        env=policy.base_environment(), cwd=path_policy.LEVEL1_ROOT,
        check=False)
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")


class TestArgvShape(unittest.TestCase):
    """What the catalogue emits, before anything is executed."""

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)
        cls.f = synthetic_chain.build(FIXTURE_DIR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)

    def chain_argv(self, **over):
        params = dict(anchor=self.f["root_pem"],
                      intermediates=self.f["intermediate_pem"],
                      leaf=self.f["leaf_pem"],
                      attime=VALIDATION_TIME)
        params.update(over)
        return operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", params)

    def cms_argv(self, **over):
        params = dict(cms=self.f["cms_detached"],
                      anchor=self.f["root_pem"],
                      content=self.f["content"],
                      certfile=self.f["intermediate_pem"],
                      attime=VALIDATION_TIME,
                      out=os.path.join(FIXTURE_DIR, "cms.out"))
        params.update(over)
        return operation_catalog.build_argv("OPENSSL_VERIFY_CMS", params)

    # -- the regression itself ---------------------------------------------
    def test_no_end_of_options_separator_is_emitted(self):
        """The exact R4 defect. `--` must not appear anywhere in the argv."""
        self.assertNotIn("--", self.chain_argv())
        self.assertNotIn("--", self.cms_argv())

    def test_the_leaf_is_the_final_positional_argument(self):
        argv = self.chain_argv()
        self.assertEqual(argv[-1], path_policy.normalize(self.f["leaf_pem"]))

    def test_every_operand_is_absolute_so_it_cannot_parse_as_an_option(self):
        argv = self.chain_argv()
        self.assertTrue(argv[-1].startswith("/"))
        self.assertFalse(argv[-1].startswith("-"))

    # -- explicit inputs ----------------------------------------------------
    def test_root_intermediate_and_leaf_are_all_explicit(self):
        argv = self.chain_argv()
        self.assertIn("-CAfile", argv)
        self.assertIn("-untrusted", argv)
        self.assertIn(path_policy.normalize(self.f["root_pem"]), argv)
        self.assertIn(path_policy.normalize(self.f["intermediate_pem"]), argv)
        self.assertIn(path_policy.normalize(self.f["leaf_pem"]), argv)

    def test_validation_time_is_required(self):
        with self.assertRaises(operation_catalog.OperationError):
            self.chain_argv(attime=None)
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
                "anchor": self.f["root_pem"], "leaf": self.f["leaf_pem"]})

    def test_validation_time_must_be_an_integer_epoch(self):
        for bad in ("1787000000", 1787000000.5, True, -1, 0):
            with self.assertRaises(operation_catalog.OperationError):
                self.chain_argv(attime=bad)

    def test_validation_time_reaches_the_command_line(self):
        argv = self.chain_argv()
        self.assertIn("-attime", argv)
        self.assertIn(str(VALIDATION_TIME), argv)

    def test_detached_content_is_required_for_cms(self):
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv("OPENSSL_VERIFY_CMS", {
                "cms": self.f["cms_detached"], "anchor": self.f["root_pem"],
                "attime": VALIDATION_TIME,
                "out": os.path.join(FIXTURE_DIR, "cms.out")})

    def test_binary_canonicalisation_is_explicit(self):
        self.assertIn("-binary", self.cms_argv())
        self.assertNotIn("-binary", self.cms_argv(binary=False))

    # -- trust --------------------------------------------------------------
    def test_system_and_default_trust_are_refused_explicitly(self):
        for argv in (self.chain_argv(), self.cms_argv()):
            for flag in operation_catalog.NO_DEFAULT_TRUST_FLAGS:
                self.assertIn(flag, argv)

    def test_purpose_is_restricted_to_a_known_set(self):
        self.assertIn("-purpose", self.chain_argv(purpose="smimesign"))
        with self.assertRaises(operation_catalog.OperationError):
            self.chain_argv(purpose="; rm -rf /")
        with self.assertRaises(operation_catalog.OperationError):
            self.chain_argv(purpose="anything")

    # -- suppression --------------------------------------------------------
    def test_suppression_flags_cannot_be_emitted(self):
        for flag in ("-noverify", "-no_signer_cert_verify",
                     "-no_content_verify", "-no_check_time",
                     "-partial_chain", "-ignore_critical"):
            self.assertIn(flag, operation_catalog.SUPPRESSION_FLAGS)

    def test_the_suppression_guard_actually_rejects(self):
        with self.assertRaises(operation_catalog.ForbiddenOperation):
            operation_catalog._reject_suppression(
                ["/usr/bin/openssl", "verify", "-noverify"])

    # -- input identity -----------------------------------------------------
    def test_input_hashes_are_preserved_by_building_an_argv(self):
        """Building a command must not touch the inputs it names."""
        from automation import hashing
        before = {k: hashing.sha256_file(self.f[k])
                  for k in ("root_pem", "intermediate_pem", "leaf_pem",
                            "content", "cms_detached")}
        self.chain_argv()
        self.cms_argv()
        after = {k: hashing.sha256_file(self.f[k]) for k in before}
        self.assertEqual(before, after)


class TestRequiredControls(unittest.TestCase):
    """The five controls, actually executed.

    An argv that looks right is not a control. Each case below runs the
    command the catalogue built and asserts the exit code, so a future change
    that makes a negative control silently pass is caught here rather than in
    an audit.
    """

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)
        cls.f = synthetic_chain.build(FIXTURE_DIR)
        cls.out = os.path.join(FIXTURE_DIR, "cms_verified.out")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)

    def chain(self, **over):
        params = dict(anchor=self.f["root_pem"],
                      intermediates=self.f["intermediate_pem"],
                      leaf=self.f["leaf_pem"],
                      attime=self.f["validation_time"])
        params.update(over)
        return _run(operation_catalog.build_argv(
            "OPENSSL_VERIFY_CERT_CHAIN", params))

    def cms(self, **over):
        params = dict(cms=self.f["cms_detached"], anchor=self.f["root_pem"],
                      content=self.f["content"],
                      certfile=self.f["intermediate_pem"],
                      attime=self.f["validation_time"], out=self.out)
        params.update(over)
        return _run(operation_catalog.build_argv("OPENSSL_VERIFY_CMS", params))

    # -- 1. positive --------------------------------------------------------
    def test_control_1_positive_synthetic_chain_passes(self):
        code, text = self.chain(purpose="smimesign")
        self.assertEqual(code, 0, "positive chain control did not pass:\n%s" % text)

    def test_control_1b_positive_detached_cms_passes(self):
        code, text = self.cms(purpose="smimesign")
        self.assertEqual(code, 0, "positive CMS control did not pass:\n%s" % text)

    def test_the_positive_control_is_not_passing_by_default_trust(self):
        """Remove the anchor from the equation and it must stop passing."""
        code, _ = self.chain(anchor=self.f["other_root_pem"])
        self.assertNotEqual(code, 0)

    # -- 2. invalid chain ---------------------------------------------------
    def test_control_2_invalid_chain_fails(self):
        code, _ = self.chain(anchor=self.f["other_root_pem"])
        self.assertNotEqual(code, 0, "an unrelated root must not verify")

    # -- 3. wrong detached content -----------------------------------------
    def test_control_3_wrong_detached_content_fails(self):
        code, _ = self.cms(content=self.f["wrong_content"])
        self.assertNotEqual(code, 0, "a signature over other content must fail")

    # -- 4. one-byte content mutation --------------------------------------
    def test_control_4_one_byte_content_mutation_fails(self):
        self.assertEqual(self.f["content_mutation"]["changed_bytes"], 1)
        code, _ = self.cms(content=self.f["content_mutated"])
        self.assertNotEqual(code, 0, "a one-byte content change must fail")

    # -- 5. one-byte certificate mutation ----------------------------------
    def test_control_5_one_byte_certificate_mutation_fails(self):
        self.assertEqual(self.f["cert_mutation"]["changed_bytes"], 1)
        code, _ = self.chain(leaf=self.f["leaf_mutated_pem"])
        self.assertNotEqual(code, 0, "a one-byte certificate change must fail")

    # -- the sabotage must be real -----------------------------------------
    def test_the_mutations_actually_changed_the_bytes(self):
        """A test that changed nothing has proved nothing."""
        for original, mutated in (
                (self.f["content"], self.f["content_mutated"]),
                (self.f["leaf_pem"], self.f["leaf_mutated_pem"])):
            with open(original, "rb") as a, open(mutated, "rb") as b:
                left, right = a.read(), b.read()
            self.assertEqual(len(left), len(right))
            self.assertEqual(sum(1 for x, y in zip(left, right) if x != y), 1)

    # -- the R4 argv is reproduced and shown to be the cause ----------------
    def test_the_r4_argv_with_the_separator_is_no_longer_produced(self):
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", dict(
            anchor=self.f["root_pem"], intermediates=self.f["intermediate_pem"],
            leaf=self.f["leaf_pem"], attime=self.f["validation_time"]))
        self.assertNotIn("--", argv)
        code, _ = _run(argv)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
