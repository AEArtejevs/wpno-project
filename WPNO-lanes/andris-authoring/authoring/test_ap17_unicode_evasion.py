#!/usr/bin/env python3
"""Focused regression tests for the sealed L1-A08 name-evasion findings."""
import unittest

import AP17_output_guardrail_v3 as guard


FORBIDDEN = "José Müller"


def detects(text):
    return FORBIDDEN in guard.scan_pii(text, [FORBIDDEN]).get(
        "Aizliegti_vardi", []
    )


class UnicodeEvasionTests(unittest.TestCase):
    def assert_detected(self, *variants):
        for label, text in variants:
            with self.subTest(label=label):
                self.assertTrue(detects(text), label)

    def test_exact_name_is_detected(self):
        self.assertTrue(detects(FORBIDDEN))

    def test_canonical_equivalence_is_detected(self):
        self.assert_detected(("NFD", "Jose\u0301 Mu\u0308ller"))

    def test_format_controls_and_read_through_period_are_detected(self):
        self.assert_detected(
            ("soft-hyphen", "Jo\u00adsé Müller"),
            ("zero-width-joiner", "Jo\u200dsé Müller"),
            ("embedded-period", "Jo.sé Müller"),
        )

    def test_whitespace_equivalents_are_detected(self):
        self.assert_detected(
            ("NBSP", "José\u00a0Müller"),
            ("NNBSP", "José\u202fMüller"),
            ("tab", "José\tMüller"),
        )

    def test_line_break_equivalents_are_detected(self):
        self.assert_detected(
            ("LF", "José\nMüller"),
            ("CRLF", "José\r\nMüller"),
            ("paragraph-join", "José Müller"),
        )

    def test_confirmed_cyrillic_homoglyphs_are_detected(self):
        self.assert_detected(
            ("Cyrillic-o", "J\u043esé Müller"),
            ("Cyrillic-e", "Jos\u0435\u0301 Müller"),
        )

    def test_clean_counterparts_remain_clear(self):
        clean = (
            "Cafe\u0301 Mu\u0308ller",
            "Jo\u00adnas Müller",
            "José\u00a0Meier",
            "José\nMeier",
            "J\u043enas Müller",
        )
        for text in clean:
            with self.subTest(text=text):
                self.assertFalse(detects(text))


if __name__ == "__main__":
    unittest.main()
