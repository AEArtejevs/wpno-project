"""REF-01 and REF-02 acceptance.

Both references arrived as operator-supplied files. A filename is not
evidence, so what is asserted here is content: that the PDF and TXT are the
ISO 13616 registry material and say so themselves, and that the archive is
python-stdnum 2.2 and says so itself.

The vectors get particular attention. The rule is that no vector may be
invented and no valid vector may be mutated into an invalid one, and the way
to hold that rule is to check that every vector still appears verbatim in the
archive member it claims to come from.
"""

import hashlib
import json
import os
import unittest
import zipfile

from automation import hashing, path_policy

ROOT = path_policy.LEVEL1_ROOT
REFS = os.path.join(ROOT, "references")
CORPORA = os.path.join(ROOT, "corpora")

REF01_PDF = os.path.join(REFS, "REF-01-swift-iban-registry-release-102.pdf")
REF01_TXT = os.path.join(REFS, "REF-01-swift-iban-registry-release-102.txt")
REF02_ZIP = os.path.join(REFS, "REF-02-python-stdnum-2.2.zip")

REF01_PDF_SHA = "e5b0e447e91db94259c5222caa3f9b7f45db4dcbbe61fb99a09cb331a1cb4675"
REF01_TXT_SHA = "a98aae4d7b59544973415491accb1345cb449bfd75a67c8bc704fbe6e161c303"
REF02_SHA = "12b08a74c96478fa3c86c63721d531b3e07d233a2dd27ebea9c8df38f841622e"

RULES = os.path.join(CORPORA, "R5_REF01_COUNTRY_RULES.jsonl")
RULES_META = os.path.join(CORPORA, "R5_REF01_COUNTRY_RULES.meta.json")
VECTORS = os.path.join(CORPORA, "R5_REF02_IBAN_VECTORS.jsonl")
VECTORS_META = os.path.join(CORPORA, "R5_REF02_IBAN_VECTORS.meta.json")


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestRef01Bytes(unittest.TestCase):
    def test_both_files_are_bound_and_hash_as_the_operator_recorded(self):
        self.assertEqual(hashing.sha256_file(REF01_PDF), REF01_PDF_SHA)
        self.assertEqual(hashing.sha256_file(REF01_TXT), REF01_TXT_SHA)

    def test_the_references_are_read_only(self):
        for path in (REF01_PDF, REF01_TXT, REF02_ZIP):
            mode = os.stat(path).st_mode & 0o222
            self.assertEqual(mode, 0, "%s is writable" % path)

    def test_the_txt_is_decoded_read_only_and_not_re_encoded(self):
        """cp1252 in, cp1252 on disk. A re-encoded reference is a new file."""
        with open(REF01_TXT, "rb") as fh:
            raw = fh.read()
        self.assertTrue(any(b > 127 for b in raw),
                        "the file should carry cp1252 high bytes")
        with self.assertRaises(UnicodeDecodeError):
            raw.decode("utf-8")
        self.assertTrue(raw.decode("cp1252"))


class TestRef01Content(unittest.TestCase):
    """Identity from content, never from the filename."""

    @classmethod
    def setUpClass(cls):
        cls.rules = load_jsonl(RULES)
        cls.meta = load_json(RULES_META)

    def test_it_is_the_iso_13616_registry(self):
        self.assertEqual(self.meta["registry_release"], "Release 102, Jun 2026")

    def test_the_country_registry_is_present(self):
        self.assertEqual(len(self.rules), 89)
        for code in ("DE", "GB", "FR", "IT", "ES", "NL", "AT", "CH"):
            self.assertIn(code, {r["country_code"] for r in self.rules})

    def test_every_country_declares_an_iban_length(self):
        for r in self.rules:
            self.assertIsInstance(r["iban_length"], int)
            self.assertGreater(r["iban_length"], 4)

    def test_every_country_declares_an_iban_and_bban_structure(self):
        for r in self.rules:
            self.assertTrue(r["iban_structure"], r["country_code"])
            self.assertTrue(r["bban_structure"], r["country_code"])

    def test_every_country_carries_an_official_example(self):
        for r in self.rules:
            self.assertTrue(r["iban_electronic_example"], r["country_code"])
            self.assertTrue(r["iban_print_example"], r["country_code"])

    def test_the_mod97_10_rule_holds_over_every_official_example(self):
        """The registry has to agree with itself before we compute with it."""
        for r in self.rules:
            iban = r["iban_electronic_example"].replace(" ", "")
            total = 0
            for ch in iban[4:] + iban[:4]:
                total = ((total * 10 + int(ch)) % 97 if ch.isdigit()
                         else (total * 100 + (ord(ch) - 55)) % 97)
            self.assertEqual(total, 1, "%s example fails MOD97-10"
                             % r["country_code"])

    def test_every_example_matches_its_declared_length_and_prefix(self):
        for r in self.rules:
            iban = r["iban_electronic_example"].replace(" ", "")
            self.assertEqual(len(iban), r["iban_length"], r["country_code"])
            self.assertTrue(iban.startswith(r["country_code"]))

    def test_the_corpus_is_bound_to_the_exact_reference_bytes(self):
        self.assertEqual(self.meta["source_sha256"], REF01_TXT_SHA)
        self.assertEqual(self.meta["corpus_sha256"], hashing.sha256_file(RULES))

    def test_the_corpus_is_immutable(self):
        self.assertEqual(os.stat(RULES).st_mode & 0o222, 0)


class TestRef02Archive(unittest.TestCase):
    def test_the_archive_hashes_as_the_operator_recorded(self):
        self.assertEqual(hashing.sha256_file(REF02_ZIP), REF02_SHA)

    def test_the_archive_is_structurally_safe(self):
        with zipfile.ZipFile(REF02_ZIP) as z:
            names = z.namelist()
            self.assertEqual([n for n in names if n.startswith("/")], [])
            self.assertEqual([n for n in names if ".." in n.split("/")], [])
            self.assertEqual(
                [i.filename for i in z.infolist()
                 if (i.external_attr >> 16) & 0o170000 == 0o120000], [])
            self.assertIsNone(z.testzip())

    def test_the_archive_identifies_itself_as_python_stdnum_2_2(self):
        with zipfile.ZipFile(REF02_ZIP) as z:
            setup = z.read("python-stdnum-2.2/setup.py").decode("utf-8")
            init = z.read("python-stdnum-2.2/stdnum/__init__.py").decode("utf-8")
        self.assertIn("name='python-stdnum'", setup)
        self.assertIn("__version__ = '2.2'", init)

    def test_the_archive_carries_a_licence(self):
        with zipfile.ZipFile(REF02_ZIP) as z:
            self.assertIn("python-stdnum-2.2/COPYING", z.namelist())

    def test_the_required_members_are_present(self):
        with zipfile.ZipFile(REF02_ZIP) as z:
            names = z.namelist()
        self.assertIn("python-stdnum-2.2/stdnum/iban.py", names)
        self.assertIn("python-stdnum-2.2/tests/test_iban.doctest", names)


class TestRef02Vectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_jsonl(VECTORS)
        cls.meta = load_json(VECTORS_META)
        with zipfile.ZipFile(REF02_ZIP) as z:
            cls.doctest = z.read(
                "python-stdnum-2.2/tests/test_iban.doctest").decode("utf-8")

    def test_no_archive_code_was_executed(self):
        self.assertFalse(self.meta["archive_code_executed"])

    def test_nothing_was_invented_or_mutated(self):
        self.assertFalse(self.meta["vectors_invented"])
        self.assertFalse(self.meta["valid_vectors_mutated_into_invalid"])
        for v in self.vectors:
            self.assertFalse(v["invented"])
            self.assertFalse(v["mutated_from_a_valid_vector"])

    def test_every_vector_appears_verbatim_in_the_source_member(self):
        """The rule that nothing was invented, checked rather than asserted."""
        for v in self.vectors:
            self.assertIn(v["iban_raw"], self.doctest,
                          "vector not found verbatim in the source: %r"
                          % v["iban_raw"])

    def test_every_vector_records_its_provenance(self):
        for v in self.vectors:
            self.assertEqual(v["source_archive_sha256"], REF02_SHA)
            self.assertEqual(v["internal_archive_member"],
                             "python-stdnum-2.2/tests/test_iban.doctest")
            self.assertTrue(v["source_locator"])
            self.assertTrue(v["source_assertion"])
            self.assertEqual(v["normalization"],
                             "clean(number, ' -.').strip().upper()")
            self.assertEqual(v["transformation_status"],
                             "VERBATIM_FROM_SOURCE_NORMALIZED_ONLY")
            self.assertIn(v["expected_result"], ("VALID", "INVALID"))
            self.assertTrue(v["country"])

    def test_the_normalization_recorded_is_the_normalization_applied(self):
        for v in self.vectors:
            expected = v["iban_raw"]
            for ch in " -.":
                expected = expected.replace(ch, "")
            self.assertEqual(v["iban"], expected.strip().upper())

    def test_both_outcomes_are_covered_for_at_least_six_countries(self):
        both = self.meta["applicable_countries_with_both"]
        self.assertGreaterEqual(
            len(both), 6,
            "only %d countries have both a valid and an invalid vector: %r"
            % (len(both), both))

    def test_there_are_valid_and_invalid_vectors(self):
        self.assertGreater(self.meta["applicable_valid"], 0)
        self.assertGreater(self.meta["applicable_invalid"], 0)

    def test_the_corpus_is_bound_to_the_archive_and_immutable(self):
        self.assertEqual(self.meta["source_archive_sha256"], REF02_SHA)
        self.assertEqual(self.meta["corpus_sha256"], hashing.sha256_file(VECTORS))
        self.assertEqual(os.stat(VECTORS).st_mode & 0o222, 0)

    def test_the_member_hash_recorded_is_the_member_hash(self):
        digest = hashlib.sha256(self.doctest.encode("utf-8")).hexdigest()
        self.assertEqual(self.meta["internal_archive_member_sha256"], digest)

    def test_the_country_specific_vectors_are_scoped_not_discarded(self):
        """The two Spanish numbers keep both of the source's statements."""
        scoped = [v for v in self.vectors
                  if not v["applicable_to_iso13616_validator"]]
        self.assertTrue(scoped)
        for v in scoped:
            self.assertTrue(v["not_applicable_reason"])
            self.assertEqual(v["country"], "ES")
            twin = [w for w in self.vectors
                    if w["iban"] == v["iban"] and w["scope"] == "ISO13616_GENERIC"]
            self.assertEqual(len(twin), 1)
            self.assertEqual(twin[0]["expected_result"], "VALID")


if __name__ == "__main__":
    unittest.main()
