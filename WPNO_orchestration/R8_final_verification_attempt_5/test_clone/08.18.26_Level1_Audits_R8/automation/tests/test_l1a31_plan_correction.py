"""The three L1-A31 plan defects that ended R6, each held shut by a test.

R6's RUN-A sealed verdict ERROR. Its evidence names the causes exactly, and
they are all parameters rather than findings:

    F1  `-purpose smimesign` against a leaf whose only extended key usage is
        id-kp-clientAuth. OpenSSL: "error 26 ... unsuitable certificate
        purpose". The same value was applied to the document chain, whose leaf
        carries no EKU at all and so passed — one purpose doing two jobs, and
        silently right for one of them.

    F2  `-attime 1787000000` on the synthetic positive control, whose own
        certificates were issued 585924 seconds later. OpenSSL: "error 9 ...
        certificate is not yet valid". The epoch was a literal.

    F3  a certificate mutation made by flipping one base64 character of the
        PEM text, which produced a file OpenSSL would not load. The step
        exited nonzero and was scored as a passing mutation control; what it
        proved was that OpenSSL refuses corrupt base64.

    F4  two CMS negative controls scored FAILS_AS_DESIGNED on exit code alone
        while both were failing on F1's certificate check, before either had
        compared a byte of content.

These tests do not restate the corrections. They exercise them, and several of
them reproduce the original defect first so that a repair which stops
repairing is visible.
"""

import io
import json
import os
import shutil
import subprocess
import unittest

from automation import (hashing, mutation_fixtures, operation_catalog,
                        path_policy, policy)

SANDBOX = os.path.join(path_policy.LEVEL1_ROOT, "work", "_selftest", "a31plan")
OPENSSL = policy.EXECUTABLES["openssl"]


def _require_replica():
    if os.path.basename(path_policy.LEVEL1_ROOT) != "selftest_runtime":
        raise AssertionError(
            "these tests write fixtures and must run only inside the isolated "
            "replica at verification/selftest_runtime; LEVEL1_ROOT is %s"
            % path_policy.LEVEL1_ROOT)


def _run(argv, cwd):
    return subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=120,
        env=policy.base_environment(), cwd=cwd, check=False)


class FixtureCase(unittest.TestCase):
    """A small real chain, so the defects can be reproduced on real bytes."""

    @classmethod
    def setUpClass(cls):
        _require_replica()
        if os.path.isdir(SANDBOX):
            shutil.rmtree(SANDBOX)
        os.makedirs(SANDBOX)
        from automation.tests.support import synthetic_chain
        cls.f = synthetic_chain.build(SANDBOX)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(SANDBOX, ignore_errors=True)


class TestF1Purpose(FixtureCase):
    """A purpose the certificate does not carry is refused, and separated."""

    def _clientauth_leaf(self):
        """Issue a leaf carrying clientAuth only — the VHN's shape."""
        d = os.path.join(SANDBOX, "clientauth")
        os.makedirs(d, exist_ok=True)
        cnf = os.path.join(d, "leaf.cnf")
        with io.open(cnf, "w", encoding="utf-8") as fh:
            fh.write("basicConstraints=critical,CA:FALSE\n"
                     "keyUsage=critical,digitalSignature,nonRepudiation\n"
                     "extendedKeyUsage=clientAuth\n"
                     "subjectKeyIdentifier=hash\n"
                     "authorityKeyIdentifier=keyid,issuer\n")
        req = os.path.join(d, "req.cnf")
        with io.open(req, "w", encoding="utf-8") as fh:
            fh.write("[req]\ndistinguished_name=dn\nprompt=no\n"
                     "[dn]\nC=ZZ\nO=WPNO R7 Control\nCN=R7 ClientAuth Signer\n")
        csr = os.path.join(d, "leaf.csr")
        key = os.path.join(d, "leaf.key")
        leaf = os.path.join(d, "leaf.pem")
        self.assertEqual(_run([OPENSSL, "req", "-new", "-newkey", "rsa:2048",
                               "-keyout", key, "-out", csr, "-nodes",
                               "-sha256", "-config", req], d).returncode, 0)
        self.assertEqual(_run([OPENSSL, "x509", "-req", "-in", csr,
                               "-CA", self.f["intermediate_pem"],
                               "-CAkey", os.path.join(SANDBOX,
                                                      "intermediate.key"),
                               "-CAcreateserial", "-out", leaf, "-days", "825",
                               "-sha256", "-extfile", cnf], d).returncode, 0)
        return leaf

    def test_the_r6_defect_still_reproduces_on_a_clientauth_leaf(self):
        """smimesign against clientAuth is error 26. It always was."""
        leaf = self._clientauth_leaf()
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": leaf,
            "attime": self.f["validation_time"],
            "purpose": "smimesign"})
        proc = _run(argv, SANDBOX)
        stderr = proc.stderr.decode("utf-8", "replace")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsuitable certificate purpose", stderr)
        self.assertIn("error 26", stderr)

    def test_the_same_chain_path_validates_under_the_corrected_purpose(self):
        """`any` validates the path. It is not a suppression flag."""
        leaf = self._clientauth_leaf()
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": leaf,
            "attime": self.f["validation_time"],
            "purpose": "any"})
        proc = _run(argv, SANDBOX)
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace"))

    def test_purpose_any_still_refuses_a_chain_that_should_not_verify(self):
        """The distinction that matters: `any` relaxes purpose, not trust."""
        leaf = self._clientauth_leaf()
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["other_root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": leaf,
            "attime": self.f["validation_time"],
            "purpose": "any"})
        proc = _run(argv, SANDBOX)
        self.assertNotEqual(proc.returncode, 0,
                           "`any` must not make an untrusted chain verify")

    def test_purpose_any_still_refuses_a_time_outside_validity(self):
        leaf = self._clientauth_leaf()
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": leaf,
            "attime": 946684800,                       # 2000-01-01
            "purpose": "any"})
        proc = _run(argv, SANDBOX)
        stderr = proc.stderr.decode("utf-8", "replace")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not yet valid", stderr)

    def test_purpose_any_is_not_on_the_suppression_list(self):
        self.assertNotIn("-purpose", operation_catalog.SUPPRESSION_FLAGS)
        self.assertIn("any", operation_catalog.ALLOWED_PURPOSES)
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"], "leaf": self.f["leaf_pem"],
            "attime": self.f["validation_time"], "purpose": "any"})
        for flag in operation_catalog.SUPPRESSION_FLAGS:
            self.assertNotIn(flag, argv)
        for flag in operation_catalog.NO_DEFAULT_TRUST_FLAGS:
            self.assertIn(flag, argv)

    def test_the_live_l1a31_plan_uses_the_corrected_purpose(self):
        """Read from the candidate plan, not from a description of it."""
        plan_path = os.path.join(
            path_policy.LEVEL1_ROOT, "build", "candidate_plans_r8",
            "L1-A31", "RUN-A", "plan.json")
        if not os.path.isfile(plan_path):
            self.skipTest("candidate plans are built at package level")
        with io.open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        steps = {s["step_id"]: s for s in plan["steps"]}
        self.assertEqual(steps["vhn_chain_path_validation"]["params"]["purpose"],
                         "any")
        self.assertEqual(steps["vhn_cms"]["params"]["purpose"], "any")
        model = [e for e in plan["test_matrix"] if "purpose_model" in e]
        self.assertEqual(len(model), 1)
        self.assertEqual(model[0]["purpose_model"]["entitlement_check"],
                         "vhn_key_usage_conformance")
        checks = [e for e in plan["test_matrix"]
                  if e.get("check_id") == "vhn_key_usage_conformance"]
        self.assertEqual(len(checks), 1,
                         "the entitlement question must be answered somewhere")


class TestF2ValidationEpoch(FixtureCase):
    """An epoch outside the fixture's own validity is a defect, not a result."""

    def test_the_r6_epoch_still_reproduces_the_defect(self):
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": self.f["leaf_pem"],
            "attime": 1,                               # 1970
            "purpose": "smimesign"})
        proc = _run(argv, SANDBOX)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not yet valid",
                      proc.stderr.decode("utf-8", "replace"))

    def test_the_control_time_is_derived_from_the_fixture_not_written_down(self):
        """The fixture computes its own validation time. That is the repair."""
        from automation.tests.support import synthetic_chain
        source = io.open(synthetic_chain.__file__, encoding="utf-8").read()
        self.assertIn("int(time.time())", source)
        self.assertNotIn("1787000000", source)

    def test_the_derived_time_is_inside_every_certificate_in_the_chain(self):
        when = self.f["validation_time"]
        for name in ("root_pem", "intermediate_pem", "leaf_pem"):
            proc = _run([OPENSSL, "x509", "-in", self.f[name], "-noout",
                         "-checkend", "0"], SANDBOX)
            self.assertEqual(proc.returncode, 0, name)
        argv = operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
            "anchor": self.f["root_pem"],
            "intermediates": self.f["intermediate_pem"],
            "leaf": self.f["leaf_pem"], "attime": when,
            "purpose": "smimesign"})
        self.assertEqual(_run(argv, SANDBOX).returncode, 0)

    def test_a_missing_attime_is_refused_outright(self):
        with self.assertRaises(operation_catalog.OperationError) as ctx:
            operation_catalog.build_argv("OPENSSL_VERIFY_CERT_CHAIN", {
                "anchor": self.f["root_pem"], "leaf": self.f["leaf_pem"],
                "purpose": "any"})
        self.assertIn("'now'", str(ctx.exception))

    def test_the_live_plan_epochs_are_inside_the_real_certificate_windows(self):
        plan_path = os.path.join(
            path_policy.LEVEL1_ROOT, "build", "candidate_plans_r8",
            "L1-A31", "RUN-A", "plan.json")
        if not os.path.isfile(plan_path):
            self.skipTest("candidate plans are built at package level")
        with io.open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        for entry in plan["test_matrix"]:
            if "validation_time_epoch" not in entry:
                continue
            self.assertTrue(entry["validation_time_inside_leaf_validity"])
            self.assertTrue(
                entry["validation_time_inside_intermediate_validity"])
            self.assertTrue(entry["validation_time_inside_root_validity"])


class TestF3MutationFixture(FixtureCase):
    """A mutation control must fail at the layer it claims."""

    def test_the_r6_construction_can_produce_an_unparseable_file(self):
        """The base64 flip's meaning depends on where it lands. That is the bug."""
        source = self.f["leaf_pem"]
        with io.open(source, "rb") as fh:
            data = bytearray(fh.read())
        start = data.index(b"-----BEGIN CERTIFICATE-----")
        offset = data.index(b"\n", start) + 2          # near the DER header
        data[offset] = ord("A") if data[offset] != ord("A") else ord("B")
        victim = os.path.join(SANDBOX, "r6_style_mutation.pem")
        with io.open(victim, "wb") as fh:
            fh.write(bytes(data))
        proc = _run([OPENSSL, "x509", "-in", victim, "-noout", "-subject"],
                    SANDBOX)
        stderr = proc.stderr.decode("utf-8", "replace")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(
            mutation_fixtures.reason_is_present(
                stderr, mutation_fixtures.REASON_PARSE_REFUSAL),
            "expected a parse refusal, which is exactly the wrong control: "
            + stderr)

    def test_the_corrected_mutation_parses_and_fails_on_signature(self):
        record = mutation_fixtures.signature_mutation(
            self.f["leaf_pem"],
            os.path.join(SANDBOX, "leaf_sig_mutated.pem"),
            self.f["root_pem"], SANDBOX,
            intermediates_pem=self.f["intermediate_pem"])
        self.assertTrue(record["proven_parseable"])
        self.assertTrue(record["proven_signature_fails"])
        self.assertEqual(record["differing_der_bytes"], 1)
        self.assertEqual(record["der_length_before"],
                         record["der_length_after"])
        self.assertEqual(record["expected_failure_reason"],
                         mutation_fixtures.REASON_CERT_SIGNATURE_FAILURE)
        self.assertNotEqual(record["source_sha256"], record["fixture_sha256"])

    def test_the_mutated_byte_lies_inside_the_signature_value(self):
        record = mutation_fixtures.signature_mutation(
            self.f["leaf_pem"],
            os.path.join(SANDBOX, "leaf_sig_mutated2.pem"),
            self.f["root_pem"], SANDBOX,
            intermediates_pem=self.f["intermediate_pem"])
        start, end = record["signature_value_span"]
        self.assertGreaterEqual(record["der_offset"], start)
        self.assertLess(record["der_offset"], end)

    def test_the_parse_refusal_control_is_a_separate_named_control(self):
        record = mutation_fixtures.parse_refusal(
            self.f["leaf_pem"],
            os.path.join(SANDBOX, "leaf_unparseable.pem"), SANDBOX)
        self.assertTrue(record["proven_unparseable"])
        self.assertEqual(record["expected_failure_reason"],
                         mutation_fixtures.REASON_PARSE_REFUSAL)
        self.assertNotEqual(record["expected_failure_reason"],
                            mutation_fixtures.REASON_CERT_SIGNATURE_FAILURE)
        self.assertIn("NOT a signature-failure control", record["note"])

    def test_a_content_mutation_that_changed_nothing_is_refused(self):
        source = self.f["content"]
        with self.assertRaises(mutation_fixtures.FixtureError):
            mutation_fixtures.content_mutation(
                source, os.path.join(SANDBOX, "beyond.bin"),
                offset=os.path.getsize(source) + 10)

    def test_a_content_mutation_preserves_length_and_changes_the_digest(self):
        record = mutation_fixtures.content_mutation(
            self.f["content"], os.path.join(SANDBOX, "content_mut.bin"),
            offset=3)
        self.assertEqual(record["length_before"], record["length_after"])
        self.assertEqual(record["differing_bytes"], 1)
        self.assertTrue(record["digest_differs"])
        self.assertNotEqual(record["source_sha256"], record["fixture_sha256"])


class TestF4ControlsFailForTheStatedReason(FixtureCase):
    """Exit code alone is not a control. R6 scored two on exit code alone."""

    def test_the_four_failure_modes_are_distinct_labels(self):
        labels = {mutation_fixtures.REASON_PARSE_REFUSAL,
                  mutation_fixtures.REASON_CERT_SIGNATURE_FAILURE,
                  mutation_fixtures.REASON_CHAIN_INCOMPLETE,
                  mutation_fixtures.REASON_CONTENT_DIGEST_FAILURE}
        self.assertEqual(len(labels), 4)

    def test_a_purpose_error_is_not_accepted_as_a_content_digest_failure(self):
        """The precise confusion R6's matrix could not see."""
        purpose_stderr = ("CMS Verification failure\nerror:17000064:CMS "
                          "routines:cms_signerinfo_verify_cert:certificate "
                          "verify error:Verify error: unsuitable certificate "
                          "purpose")
        self.assertTrue(mutation_fixtures.reason_is_present(
            purpose_stderr, mutation_fixtures.REASON_UNSUITABLE_PURPOSE))
        self.assertFalse(mutation_fixtures.reason_is_present(
            purpose_stderr, mutation_fixtures.REASON_CERT_SIGNATURE_FAILURE))
        self.assertFalse(mutation_fixtures.reason_is_present(
            purpose_stderr, mutation_fixtures.REASON_PARSE_REFUSAL))

    def test_an_unknown_reason_is_refused_rather_than_assumed_absent(self):
        with self.assertRaises(mutation_fixtures.FixtureError):
            mutation_fixtures.reason_is_present("anything", "NOT_A_REASON")

    def test_every_control_in_the_live_plan_states_its_failure_reason(self):
        plan_path = os.path.join(
            path_policy.LEVEL1_ROOT, "build", "candidate_plans_r8",
            "L1-A31", "RUN-A", "plan.json")
        if not os.path.isfile(plan_path):
            self.skipTest("candidate plans are built at package level")
        with io.open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        roles = {s["step_id"]: s.get("control_role") for s in plan["steps"]}
        by_step = {e["step_id"]: e for e in plan["test_matrix"]
                   if "step_id" in e}
        for step_id, role in roles.items():
            if role not in ("NEGATIVE", "MUTATION"):
                continue
            entry = by_step.get(step_id)
            self.assertIsNotNone(entry, step_id)
            self.assertEqual(entry.get("expected_exit_code"), "NONZERO",
                             step_id)
            self.assertIn("expected_failure_reason", entry,
                          "%s asserts an exit code and nothing else, which is "
                          "the R6 defect" % step_id)


class TestAuditModuleOperation(unittest.TestCase):
    """The operation that runs a frozen second implementation."""

    def test_a_module_outside_the_allowlist_is_refused(self):
        for name in ("os", "subprocess", "automation.controller",
                     "automation", ""):
            with self.assertRaises(operation_catalog.OperationError):
                operation_catalog.build_argv(
                    "AUDIT_MODULE_RUN", {"module": name, "args": []})

    def test_an_option_the_catalogue_does_not_know_is_refused(self):
        for option in ("--force", "--yes", "-c", "--auto-approve"):
            with self.assertRaises(Exception):
                operation_catalog.build_argv("AUDIT_MODULE_RUN", {
                    "module": "automation.a18_run_a_cli",
                    "args": [option, "x"]})

    def test_the_argv_is_isolated_and_writes_no_bytecode(self):
        argv = operation_catalog.build_argv("AUDIT_MODULE_RUN", {
            "module": "automation.a18_run_a_cli",
            "args": ["--vectors", "/tmp/x", "--rules", "/tmp/y",
                     "--out", "/tmp/z"]})
        self.assertEqual(argv[0], policy.EXECUTABLES["python3"])
        self.assertIn("-I", argv)
        self.assertIn("-B", argv)
        self.assertTrue(argv[3].endswith("run_audit_module.py"))
        self.assertEqual(argv[4], "automation.a18_run_a_cli")

    def test_the_launcher_checks_the_allowlist_on_its_own_side_too(self):
        launcher = os.path.join(path_policy.LEVEL1_ROOT,
                                "run_audit_module.py")
        with io.open(launcher, encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("RUNNABLE_AUDIT_MODULES", source)
        for token in policy.DANGEROUS_TOKENS:
            self.assertNotIn(token, source)

    def test_it_is_gated_and_therefore_needs_a_human_token(self):
        self.assertEqual(operation_catalog.classify("AUDIT_MODULE_RUN"),
                         "GATED")


if __name__ == "__main__":
    unittest.main()
