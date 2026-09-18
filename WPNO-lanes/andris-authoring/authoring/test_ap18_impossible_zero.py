#!/usr/bin/env python3
"""Focused synthetic controls for A3 AP18 senate and zero-citation handling."""

import json
import os
import subprocess
import sys
import tempfile
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "AP18_referenzpruefung.py")
sys.path.insert(0, HERE)

from AP18_referenzpruefung import MOEGLICH, UNMOEGLICH, senat_befund  # noqa: E402


class AP18ImpossibleAndZeroCitationTests(unittest.TestCase):
    def run_control(self, text, target=TARGET):
        with tempfile.TemporaryDirectory() as tmp:
            document = os.path.join(tmp, "synthetic-control.txt")
            reference = os.path.join(tmp, "synthetic-reference.json")
            with open(document, "w", encoding="utf-8") as handle:
                handle.write(text)
            with open(reference, "w", encoding="utf-8") as handle:
                json.dump({
                    "_stand": "synthetic-control",
                    "_pruefweg": "",
                    "belegt": {
                        "I ZR 130/25": {"geprueft": "synthetic-control"},
                    },
                    "nachweislich_nicht_vorhanden": {},
                }, handle)
            return subprocess.run(
                [sys.executable, target, document, "--referenz", reference],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_impossible_senate_forms_are_rejected(self):
        self.assertEqual(UNMOEGLICH, senat_befund("IIII ZR 1/20"))
        self.assertEqual(UNMOEGLICH, senat_befund("14 StR 1/20"))
        self.assertEqual(MOEGLICH, senat_befund("IV ZR 1/20"))
        self.assertEqual(MOEGLICH, senat_befund("6 StR 1/20"))

    def test_impossible_forms_block_across_formatting_variants(self):
        variants = (
            "BGH, Beschluss: IIII ZR 1/20.",
            "BGH, Beschluss - IIII   ZR   1/20",
            "BGH, Beschluss - IIII\u00a0ZR\u00a01/20",
            "BGH, Beschluss - IIII\nZR\n1/20",
            "BGH, Beschluss (14 StR 1/20).",
            "BGH, Beschluss - 14\u00a0StR\u00a01/20",
            "BGH, Beschluss - 14\nStR\n1/20",
        )
        for text in variants:
            with self.subTest(text=text):
                result = self.run_control(text)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("BLOCKIERT", result.stdout)
                self.assertIn("UNMOEGLICHE SENATSKENNUNG", result.stdout)

    def test_zero_citations_are_reported_as_not_examined(self):
        result = self.run_control("Dieser Kontrolltext enthaelt kein Aktenzeichen.")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("KEINE AKTENZEICHEN GEFUNDEN", result.stdout)
        self.assertIn("NICHTS GEPRUEFT", result.stdout)
        self.assertNotIn("alle BGH-Fundstellen belegt", result.stdout)

    def test_known_valid_control_remains_allowed(self):
        result = self.run_control("BGH, Urteil vom 30.07.2026 - I ZR 130/25")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("alle BGH-Fundstellen belegt", result.stdout)
        self.assertNotIn("BLOCKIERT", result.stdout)

    def test_broad_roman_numeral_mutation_is_detected(self):
        with open(TARGET, encoding="utf-8") as handle:
            source = handle.read()
        strict = (
            'ROEMISCH = re.compile(\n'
            '    r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII)[a-z]?$"\n'
            ')'
        )
        broad = 'ROEMISCH = re.compile(r"^[IVXLCDM]+[a-z]?$")'
        self.assertIn(strict, source)
        with tempfile.TemporaryDirectory() as tmp:
            mutant = os.path.join(tmp, "AP18_referenzpruefung.py")
            with open(mutant, "w", encoding="utf-8") as handle:
                handle.write(source.replace(strict, broad, 1))
            result = self.run_control("BGH, Beschluss: IIII ZR 1/20.", mutant)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("NICHT ALS ENTSCHEIDUNGSZITAT GEZAEHLT", result.stdout)
        self.assertNotIn("UNMOEGLICHE SENATSKENNUNG", result.stdout)

    def test_zero_citation_success_mutation_is_detected(self):
        with open(TARGET, encoding="utf-8") as handle:
            source = handle.read()
        original = "    if gesamt == 0:\n"
        mutant_line = "    if False and gesamt == 0:\n"
        self.assertIn(original, source)
        with tempfile.TemporaryDirectory() as tmp:
            mutant = os.path.join(tmp, "AP18_referenzpruefung.py")
            with open(mutant, "w", encoding="utf-8") as handle:
                handle.write(source.replace(original, mutant_line, 1))
            result = self.run_control("Dieser Kontrolltext enthaelt kein Aktenzeichen.", mutant)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("KEINE AKTENZEICHEN GEFUNDEN", result.stdout)
        self.assertIn("alle BGH-Fundstellen belegt", result.stdout)


if __name__ == "__main__":
    unittest.main()
