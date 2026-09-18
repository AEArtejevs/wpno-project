"""Redaction.

Client material enters some audits as an operator-supplied reference. Its
content must not reach a report. These tests check that the redactor removes
what it claims to remove, marks every truncation, and never silently returns
something that still reads as the original.

The marker-stability section carries the VF-004 regressions. In the predecessor
package the IBAN rule wrote `[REDACTED:IBAN]` and the BIC rule then matched the
eight capital letters of REDACTED inside it, yielding `[[REDACTED:BIC]:IBAN]`.
The expectation is not relaxed anywhere below; the implementation was rebuilt as
a single pass instead.
"""

import unittest

from automation import redaction


class TestRedactionCoverage(unittest.TestCase):
    def test_iban_is_removed(self):
        out, counts = redaction.redact("Konto DE02120300000000202051 bitte")
        self.assertNotIn("DE02120300000000202051", out)
        self.assertIn("IBAN", counts)

    def test_spaced_iban_is_removed(self):
        out, counts = redaction.redact("DE02 1203 0000 0000 2020 51")
        self.assertNotIn("1203 0000", out)
        self.assertIn("IBAN", counts)

    def test_eleven_digit_identifier_is_removed(self):
        out, counts = redaction.redact("SteuerID 12345678901 vermerkt")
        self.assertNotIn("12345678901", out)
        self.assertIn("TAXID", counts)

    def test_email_is_removed(self):
        out, counts = redaction.redact("Kontakt: name.surname@example.com")
        self.assertNotIn("@example.com", out)
        self.assertIn("EMAIL", counts)

    def test_long_digit_run_is_removed(self):
        out, counts = redaction.redact("Vorgang 563203462123 abgelegt")
        self.assertNotIn("563203462123", out)
        self.assertTrue(counts)

    def test_ordinary_prose_is_untouched(self):
        text = "Der Waechter hat den Bericht zurueckgewiesen."
        out, counts = redaction.redact(text)
        self.assertEqual(out, text)
        self.assertEqual(counts, {})

    def test_short_numbers_are_not_over_redacted(self):
        text = "Abschnitt 10, Zeile 158, Fassung 3"
        out, _ = redaction.redact(text)
        self.assertEqual(out, text)


class TestRedactionStructure(unittest.TestCase):
    def test_nested_structures_are_redacted_throughout(self):
        payload = {"a": ["DE02120300000000202051",
                         {"b": "kontakt@example.com"}],
                   "c": ("12345678901",)}
        out = redaction.redact_structure(payload)
        rendered = repr(out)
        self.assertNotIn("DE02120300000000202051", rendered)
        self.assertNotIn("kontakt@example.com", rendered)
        self.assertNotIn("12345678901", rendered)

    def test_non_strings_pass_through_unchanged(self):
        self.assertEqual(redaction.redact_structure(42), 42)
        self.assertEqual(redaction.redact_structure(None), None)
        self.assertEqual(redaction.redact_structure(True), True)

    def test_dictionary_keys_are_redacted_too(self):
        out = redaction.redact_structure({"DE02120300000000202051": "x"})
        self.assertNotIn("DE02120300000000202051", repr(out))


class TestSafeQuote(unittest.TestCase):
    def test_short_text_is_returned_whole(self):
        self.assertEqual(redaction.safe_quote("kurz"), "kurz")

    def test_long_text_is_marked_as_truncated(self):
        quoted = redaction.safe_quote("a" * 500)
        self.assertIn("TRUNCATED", quoted)
        self.assertIn("evidence", quoted)

    def test_quote_is_redacted_before_truncation(self):
        quoted = redaction.safe_quote("DE02120300000000202051 " + "x" * 500)
        self.assertNotIn("DE02120300000000202051", quoted)

    def test_none_is_handled(self):
        self.assertEqual(redaction.safe_quote(None), "")


class TestAssertClean(unittest.TestCase):
    def test_clean_text_passes(self):
        self.assertTrue(redaction.assert_clean("nichts Vertrauliches hier"))

    def test_dirty_text_raises_and_names_the_kind(self):
        with self.assertRaises(redaction.RedactionError) as ctx:
            redaction.assert_clean("DE02120300000000202051")
        self.assertIn("IBAN", str(ctx.exception))

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(redaction.RedactionError):
            redaction.redact(12345)


class TestRedactionIsBlunt(unittest.TestCase):
    """A redactor that leaves a reconstructable remnant has not redacted."""

    def test_replacement_carries_no_original_characters(self):
        original = "DE02120300000000202051"
        out, _ = redaction.redact(original)
        self.assertEqual(out, "[REDACTED:IBAN]")
        for chunk in ("1203", "2020", "0000"):
            self.assertNotIn(chunk, out)

    def test_repeated_occurrences_are_all_removed(self):
        text = " ".join(["DE02120300000000202051"] * 5)
        out, counts = redaction.redact(text)
        self.assertNotIn("DE02", out)
        self.assertEqual(counts["IBAN"], 5)


class TestMarkerStability(unittest.TestCase):
    """VF-004 — a marker this code writes is never rewritten by a later rule."""

    def test_iban_marker_is_exact_and_unchanged(self):
        out, _ = redaction.redact("DE02120300000000202051")
        self.assertEqual(out, "[REDACTED:IBAN]")
        self.assertNotIn("BIC", out)
        self.assertNotIn("[[", out)

    def test_bic_marker_is_exact_and_unchanged(self):
        out, counts = redaction.redact("DEUTDEFF")
        self.assertEqual(out, "[REDACTED:BIC]")
        self.assertEqual(counts, {"BIC": 1})

    def test_mixed_iban_and_bic_are_redacted_independently(self):
        # The comma matters: the IBAN pattern permits a single space between
        # groups, so without a separator its greedy tail would swallow the
        # following token and the test would no longer be measuring two
        # independent redactions.
        out, counts = redaction.redact(
            "IBAN DE02120300000000202051, BIC DEUTDEFF500 Ende")
        self.assertIn("[REDACTED:IBAN]", out)
        self.assertIn("[REDACTED:BIC]", out)
        self.assertNotIn("[[", out)
        self.assertNotIn("DE02120300000000202051", out)
        self.assertNotIn("DEUTDEFF500", out)
        self.assertEqual(counts.get("IBAN"), 1)
        self.assertEqual(counts.get("BIC"), 1)

    def test_a_second_pass_changes_nothing(self):
        for original in ("DE02120300000000202051", "DEUTDEFF",
                         "12345678901", "name.surname@example.com",
                         "IBAN DE02120300000000202051, BIC DEUTDEFF500"):
            once, _ = redaction.redact(original)
            twice, counts = redaction.redact(once)
            self.assertEqual(twice, once, original)
            self.assertEqual(counts, {}, original)

    def test_an_existing_marker_is_not_matched_as_a_bank_code(self):
        for marker in redaction.MARKERS:
            out, counts = redaction.redact(marker)
            self.assertEqual(out, marker)
            self.assertEqual(counts, {})

    def test_marker_set_matches_the_pattern_kinds(self):
        expected = {redaction.MARKER_TEMPLATE % kind
                    for kind in redaction.KINDS}
        self.assertEqual(set(redaction.MARKERS), expected)

    def test_every_kind_has_exactly_one_pattern(self):
        kinds = [kind for kind, _ in redaction.PATTERNS]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertEqual(tuple(kinds), redaction.KINDS)

    def test_redaction_is_a_single_pass_over_the_input(self):
        """One compiled alternation, not a sequence of passes."""
        self.assertEqual(redaction.COMBINED.groups, len(redaction.PATTERNS) + 1)
        names = set(redaction.COMBINED.groupindex)
        self.assertIn("MARKER", names)
        for kind in redaction.KINDS:
            self.assertIn(kind, names)

    def test_no_original_digit_survives_inside_a_marker(self):
        original = "DE02120300000000202051"
        out, _ = redaction.redact(original)
        digits = sorted({c for c in original if c.isdigit()})
        self.assertTrue(digits, "the fixture must contain digits to measure")
        for digit in digits:
            self.assertNotIn(digit, out)
        self.assertEqual(out, "[REDACTED:IBAN]")


if __name__ == "__main__":
    unittest.main()
