"""L1-A18: two independent validators over the REF-02 corpus.

The point of a second implementation is that it can disagree. Agreement is
only evidence when disagreement was possible, so these tests do three things,
in order of increasing awkwardness:

  1. check that each validator matches the source-declared outcome for every
     applicable vector;
  2. check that the two validators agree with each other;
  3. break things on purpose and check that both notice.

The third is the one that matters. A validator that returns VALID for
everything would pass (1) for the 196 valid vectors and would pass (2) if the
other did the same. What it cannot survive is being handed a corrupted rule
set and still answering the same way.
"""

import ast
import json
import os
import shutil
import unittest

from automation import a18_run_a, a18_run_b, hashing, path_policy

ROOT = path_policy.LEVEL1_ROOT
CORPORA = os.path.join(ROOT, "corpora")
RULES = os.path.join(CORPORA, "R5_REF01_COUNTRY_RULES.jsonl")
VECTORS = os.path.join(CORPORA, "R5_REF02_IBAN_VECTORS.jsonl")
WORK = os.path.join(ROOT, "work", "_r5_selftest", "a18")


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class TestCorpusAndRules(unittest.TestCase):
    def test_both_corpora_are_present_and_immutable(self):
        for path in (RULES, VECTORS):
            self.assertTrue(os.path.exists(path), path)
            self.assertEqual(os.stat(path).st_mode & 0o222, 0, path)

    def test_the_rules_cover_every_country_a_vector_names(self):
        rules = a18_run_a.load_rules()
        for v in load_jsonl(VECTORS):
            if v["expected_result"] == "VALID" and \
                    v["applicable_to_iso13616_validator"]:
                self.assertIn(v["country"], rules,
                              "no REF-01 rule for %s" % v["country"])


class TestRunAUnit(unittest.TestCase):
    """RUN-A's parts, before it is pointed at the corpus."""

    @classmethod
    def setUpClass(cls):
        cls.rules = a18_run_a.load_rules()

    def test_normalization_is_the_recorded_one(self):
        self.assertEqual(a18_run_a.normalize(" de89 3704-0044.0532 013000 "),
                         "DE89370400440532013000")

    def test_structure_parsing_reads_multi_digit_lengths(self):
        """`12!c` is twelve characters, not one. See CLAUDE.md section 10."""
        self.assertEqual(a18_run_a.parse_structure("4!n4!n12!c"),
                         [(4, "n"), (4, "n"), (12, "c")])

    def test_a_structure_without_a_fixed_length_is_refused(self):
        for bad in ("4n", "!n", "4!", "4!x", ""):
            with self.assertRaises(a18_run_a.ValidatorError):
                a18_run_a.parse_structure(bad)

    def test_mod97_10_is_computed_without_a_big_integer(self):
        self.assertEqual(
            a18_run_a.mod97_10_streaming("370400440532013000DE89"), 1)
        self.assertNotEqual(
            a18_run_a.mod97_10_streaming("370400440532013001DE89"), 1)

    def test_each_failure_reason_is_distinct(self):
        cases = {
            "XX431234": "UNKNOWN_COUNTRY_CODE",
            "DE8937040044053201300": "LENGTH_",
            "DE89370400440532013001": "MOD97_10_REMAINDER_",
            "DEX9370400440532013000": "CHECK_DIGITS_NOT_NUMERIC",
            # "0001" is four characters, so it reaches the country-code test
            # and fails there. The source doctest uses it for the corner case
            # of an empty BBAN with a valid checksum.
            "0001": "COUNTRY_CODE_NOT_ALPHABETIC",
            "DE": "SHORTER_THAN_FOUR_CHARACTERS",
        }
        for value, expected in cases.items():
            result = a18_run_a.validate(value, self.rules)
            self.assertEqual(result["result"], "INVALID", value)
            self.assertIn(expected, result["reason"], value)

    def test_an_invalid_iban_is_an_answer_not_an_exception(self):
        for value in ("", "!!!", "ZZ00", "über"):
            result = a18_run_a.validate(value, self.rules)
            self.assertEqual(result["result"], "INVALID")


class TestRunBIsIndependent(unittest.TestCase):
    def test_run_b_is_available(self):
        ok, why = a18_run_b.available()
        self.assertTrue(ok, why)

    def test_run_b_does_not_import_run_a(self):
        """Asked of the import graph, not of the text.

        The module's own docstring says it does not import RUN-A. A text scan
        matches that sentence and fails the module for explaining itself --
        which is exactly what the first version of this test did. The parse
        tree has no opinions about prose.
        """
        source = os.path.join(ROOT, "automation", "a18_run_b.py")
        with open(source, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.name)
                if node.module:
                    imported.add(node.module)
        self.assertNotIn("a18_run_a", imported)
        self.assertFalse([n for n in imported if "run_a" in n],
                         "RUN-B imports %r" % sorted(imported))

    def test_run_b_never_names_a_run_a_attribute(self):
        source = os.path.join(ROOT, "automation", "a18_run_b.py")
        with open(source, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=source)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("a18_run_a", names)

    def test_run_b_carries_no_validation_logic_of_its_own_in_python(self):
        """RUN-B's decision must be made in the Java process, not here.

        Checked on the code with docstrings removed, so the module may
        describe what it delegates without being accused of doing it.
        """
        source = os.path.join(ROOT, "automation", "a18_run_b.py")
        with open(source, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                body = node.body
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body[0].value.value = ""
        code = ast.unparse(tree)
        for leaked in ("mod97", "MOD97", "% 97", "bban_structure",
                       "CHARACTER_CLASSES"):
            self.assertNotIn(leaked, code,
                             "validation logic leaked into RUN-B's wrapper: %r"
                             % leaked)

    def test_run_b_runs_on_a_different_runtime(self):
        source = os.path.join(ROOT, "tools", "a18_run_b", "src",
                              "WpnoIbanValidateRunB.java")
        self.assertTrue(os.path.exists(source))
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        # A different algorithm, not merely a different file.
        self.assertIn("BigInteger", text)
        self.assertIn("expandStructure", text)

    def test_run_a_and_run_b_use_different_algorithms(self):
        with open(os.path.join(ROOT, "automation", "a18_run_a.py"),
                  encoding="utf-8") as fh:
            run_a = fh.read()
        self.assertIn("mod97_10_streaming", run_a)
        self.assertNotIn("BigInteger", run_a)

    def test_run_b_refuses_to_write_outside_work(self):
        with self.assertRaises(a18_run_b.RunBError):
            a18_run_b.validate_all(["DE89370400440532013000"],
                                   os.path.join(ROOT, "state", "nope"))


class TestBothAgainstTheCorpus(unittest.TestCase):
    """The measurement itself."""

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(WORK, ignore_errors=True)
        cls.vectors = [v for v in load_jsonl(VECTORS)
                       if v["applicable_to_iso13616_validator"]]
        cls.rules = a18_run_a.load_rules()
        cls.run_a = [a18_run_a.validate(v["iban_raw"], cls.rules)
                     for v in cls.vectors]
        cls.run_b, _ = a18_run_b.validate_all(
            [v["iban_raw"] for v in cls.vectors], WORK)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(WORK, ignore_errors=True)

    def test_the_corpus_is_not_trivially_one_sided(self):
        outcomes = {v["expected_result"] for v in self.vectors}
        self.assertEqual(outcomes, {"VALID", "INVALID"})
        self.assertGreaterEqual(
            sum(1 for v in self.vectors if v["expected_result"] == "INVALID"), 6)

    def test_run_a_matches_every_source_declared_outcome(self):
        wrong = [(v["iban"], v["expected_result"], r["result"], r["reason"])
                 for v, r in zip(self.vectors, self.run_a)
                 if r["result"] != v["expected_result"]]
        self.assertEqual(wrong, [])

    def test_run_b_matches_every_source_declared_outcome(self):
        wrong = [(v["iban"], v["expected_result"], r["result"], r["reason"])
                 for v, r in zip(self.vectors, self.run_b)
                 if r["result"] != v["expected_result"]]
        self.assertEqual(wrong, [])

    def test_the_two_runs_agree(self):
        disagreements = [(a["normalized"], a["result"], b["result"])
                         for a, b in zip(self.run_a, self.run_b)
                         if a["result"] != b["result"]]
        self.assertEqual(disagreements, [])

    def test_the_two_runs_agree_on_the_reason_as_well(self):
        differing = [(a["normalized"], a["reason"], b["reason"])
                     for a, b in zip(self.run_a, self.run_b)
                     if a["reason"] != b["reason"]]
        self.assertEqual(differing, [])

    def test_every_vector_was_evaluated_by_both(self):
        self.assertEqual(len(self.run_a), len(self.vectors))
        self.assertEqual(len(self.run_b), len(self.vectors))

    def test_both_report_their_phase_and_method(self):
        for r in self.run_a:
            self.assertEqual(r["run_phase"], "RUN-A")
            self.assertIn("PYTHON", r["method"])
        for r in self.run_b:
            self.assertEqual(r["run_phase"], "RUN-B")
            self.assertIn("JAVA", r["method"])


class TestTheValidatorsCanActuallyFail(unittest.TestCase):
    """The counter-check. Agreement means nothing if disagreement is impossible.

    Both validators are handed a deliberately corrupted REF-01 rule set. If
    either still returns the same answers, it is not consulting the rules and
    its agreement with the other proves nothing about either.
    """

    def setUp(self):
        self.sabotage_dir = os.path.join(WORK, "sabotage")
        os.makedirs(self.sabotage_dir, exist_ok=True)
        self.bad_rules = os.path.join(self.sabotage_dir, "bad_rules.jsonl")
        records = load_jsonl(RULES)
        changed = 0
        with open(self.bad_rules, "w", encoding="utf-8") as fh:
            for r in records:
                if r["country_code"] == "DE":
                    r["iban_length"] = 21   # the real value is 22
                    changed += 1
                fh.write(json.dumps(r, sort_keys=True) + "\n")
        self.changed = changed

    def tearDown(self):
        shutil.rmtree(self.sabotage_dir, ignore_errors=True)

    def test_the_sabotage_actually_changed_something(self):
        """Zero changed bytes is a measurement error, not a passing test."""
        self.assertEqual(self.changed, 1)
        self.assertNotEqual(hashing.sha256_file(self.bad_rules),
                            hashing.sha256_file(RULES))

    def test_run_a_notices_the_corrupted_rules(self):
        good = a18_run_a.validate("DE89370400440532013000",
                                  a18_run_a.load_rules())
        bad = a18_run_a.validate("DE89370400440532013000",
                                 a18_run_a.load_rules(self.bad_rules))
        self.assertEqual(good["result"], "VALID")
        self.assertEqual(bad["result"], "INVALID",
                         "RUN-A is not consulting the REF-01 length rule")
        self.assertIn("LENGTH_", bad["reason"])

    def test_run_b_notices_the_corrupted_rules(self):
        good, _ = a18_run_b.validate_all(["DE89370400440532013000"],
                                         os.path.join(self.sabotage_dir, "g"))
        bad, _ = a18_run_b.validate_all(["DE89370400440532013000"],
                                        os.path.join(self.sabotage_dir, "b"),
                                        rules_path=self.bad_rules)
        self.assertEqual(good[0]["result"], "VALID")
        self.assertEqual(bad[0]["result"], "INVALID",
                         "RUN-B is not consulting the REF-01 length rule")
        self.assertIn("LENGTH_", bad[0]["reason"])

    def test_an_empty_input_is_answered_by_both_and_not_dropped(self):
        """RUN-B once returned three answers for four inputs."""
        rules = a18_run_a.load_rules()
        inputs = ["", "DE89370400440532013000", "", "XX431234"]
        results_a = [a18_run_a.validate(v, rules) for v in inputs]
        results_b, _ = a18_run_b.validate_all(
            inputs, os.path.join(self.sabotage_dir, "empty"))
        self.assertEqual(len(results_b), len(inputs))
        self.assertEqual([r["result"] for r in results_a],
                         [r["result"] for r in results_b])
        self.assertEqual(results_b[0]["result"], "INVALID")

    def test_neither_validator_returns_valid_for_everything(self):
        rules = a18_run_a.load_rules()
        nonsense = ["", "ZZ00", "DE00000000000000000000", "!!!!"]
        results_a = [a18_run_a.validate(v, rules)["result"] for v in nonsense]
        results_b, _ = a18_run_b.validate_all(
            nonsense, os.path.join(self.sabotage_dir, "n"))
        self.assertEqual(set(results_a), {"INVALID"})
        self.assertEqual({r["result"] for r in results_b}, {"INVALID"})


if __name__ == "__main__":
    unittest.main()
