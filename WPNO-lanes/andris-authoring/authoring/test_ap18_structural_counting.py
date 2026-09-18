#!/usr/bin/env python3
"""Focused synthetic controls for the A4 structural citation identity rule."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import AP18_referenzpruefung as ap18  # noqa: E402

pruefen = ap18.pruefen


REFERENCE = {
    "_stand": "synthetic-control",
    "_pruefweg": "",
    "belegt": {
        "I ZR 1/20": {"geprueft": "synthetic-control"},
        "IX ZR 1/20": {"geprueft": "synthetic-control"},
    },
    "nachweislich_nicht_vorhanden": {},
}


class AP18StructuralCountingTests(unittest.TestCase):
    def inspect(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            document = os.path.join(tmp, "synthetic-control.txt")
            reference = os.path.join(tmp, "synthetic-reference.json")
            with open(document, "w", encoding="utf-8") as handle:
                handle.write(text)
            with open(reference, "w", encoding="utf-8") as handle:
                json.dump(REFERENCE, handle)
            return pruefen(document, reference)[0]

    @staticmethod
    def counted(result):
        return sum(
            len(values)
            for key, values in result.items()
            if key != "nicht_strukturell"
        )

    def test_bare_candidate_only_designators_are_not_counted_as_citations(self):
        result = self.inspect(
            "BGH, Urteil vom 01.01.2020 - I ZR 1/20\n"
            "IX ZR 170/18\nIX ZR 49/13\nIX ZR 78/20\n"
        )
        self.assertEqual(1, self.counted(result), result)
        self.assertEqual(["I ZR 1/20"], result["belegt"])
        self.assertCountEqual(
            ["IX ZR 170/18", "IX ZR 49/13", "IX ZR 78/20"],
            result.get("nicht_strukturell", []),
        )

    def test_court_date_and_docket_must_share_one_paragraph_and_distance(self):
        result = self.inspect(
            "BGH, Urteil vom 01.01.2020 - IX ZR 1/20\n"
            "BGH, Urteil vom 02.02.2021\n- IX ZR 2/21\n"
            "BGH " + ("x" * 81) + " 03.03.2022 - IX ZR 3/22\n"
        )
        self.assertEqual(1, self.counted(result), result)
        self.assertCountEqual(
            ["IX ZR 2/21", "IX ZR 3/22"],
            result.get("nicht_strukturell", []),
        )

    def test_identity_is_normalized_court_date_and_docket(self):
        result = self.inspect(
            "BGH, Urteil vom 01.01.2020 - IX ZR 1/20\n"
            "BGH, Urteil vom 01.01.2020 - IX ZR 1/20\n"
            "BGH, Urteil vom 02.02.2020 - IX ZR 1/20\n"
        )
        self.assertEqual(2, self.counted(result), result)
        self.assertEqual(["IX ZR 1/20", "IX ZR 1/20"], result["belegt"])

    def test_structured_foreign_court_is_counted_as_not_bgh(self):
        result = self.inspect(
            "OLG Koeln, Urteil vom 07.12.2023 - 24 U 66/23\n"
        )
        self.assertEqual(1, self.counted(result), result)
        self.assertEqual(["24 U 66/23"], result["fremdes_gericht"])

    def test_broad_scanner_mutation_is_detected(self):
        def broad_mutant(text):
            return [
                (az, context, "BGH", "01.01.2020")
                for az, context in ap18.aktenzeichen_finden(text)
            ]

        with mock.patch.object(
            ap18, "strukturierte_aktenzeichen_finden", side_effect=broad_mutant
        ):
            result = self.inspect(
                "BGH, Urteil vom 01.01.2020 - I ZR 1/20\n"
                "IX ZR 170/18\nIX ZR 49/13\nIX ZR 78/20\n"
            )
        self.assertEqual(4, self.counted(result), result)
        self.assertEqual([], result["nicht_strukturell"])


if __name__ == "__main__":
    unittest.main()
