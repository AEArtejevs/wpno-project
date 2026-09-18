#!/usr/bin/env python3
"""Regression tests for the sealed L1-A26 AP17/AP18 integration finding."""
import ast
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


GUARD = Path(__file__).with_name("AP17_output_guardrail_v3.py")


def write_document(path, citation_text):
    citation = ""
    if citation_text:
        citation = f"<w:p><w:r><w:t>{citation_text}</w:t></w:r></w:p>"
    document = f'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Rubrum"/></w:pPr><w:r><w:t>Rubrum</w:t></w:r></w:p>
<w:p><w:r><w:t>Gericht Landgericht Teststadt, Az.: 12 O 345/26, Klaeger A gegen Beklagte B, Prozessbevollmaechtigte Kanzlei Test, wegen Testforderung</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/></w:pPr><w:r><w:t>Antrag</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Die Klage wird abgewiesen.</w:t></w:r></w:p>
{citation}<w:sectPr/></w:body></w:document>'''
    styles = '''<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:styleId="Normal"><w:rPr><w:rFonts w:ascii="Baskerville"/></w:rPr></w:style>
<w:style w:styleId="Gliederung1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
<w:style w:styleId="Gliederung2"><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
</w:styles>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)


def run_guard(citation_text):
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        document = directory / "classification.docx"
        write_document(document, citation_text)
        refs = directory / "known.json"
        refs.write_text(json.dumps({
            "known_references": ["12 O 345/26"], "forbidden_names": []
        }), encoding="utf-8")
        ledger = directory / "ledger.sqlite"
        report = directory / "report.md"
        result = subprocess.run(
            [sys.executable, str(GUARD), str(document), str(refs),
             str(ledger), str(report)],
            capture_output=True, text=True, check=False,
        )
        report_text = report.read_text(encoding="utf-8")
        connection = sqlite3.connect(ledger)
        try:
            status = connection.execute(
                "SELECT status FROM nosutisanas_parbaudes_zurnals"
            ).fetchone()[0]
        finally:
            connection.close()
    return result, report_text, status


class FullReferenceClassificationTests(unittest.TestCase):
    def test_ap17_calls_full_ap18_classifier(self):
        tree = ast.parse(GUARD.read_text(encoding="utf-8"))
        calls = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "refp"
        }
        self.assertIn("pruefen", calls)
        self.assertNotIn("aktenzeichen_finden", calls)

    def test_foreign_court_citation_is_blocked_pending_its_own_evidence(self):
        result, report, status = run_guard(
            "BVerwG, Urteil vom 10.02.2026 - 2 C 1/20"
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual("BLOCKED", status)
        self.assertIn("fremdes_gericht", report)
        self.assertIn("2 C 1/20", report)

    def test_impossible_bgh_senate_is_classified_and_blocked(self):
        result, report, status = run_guard(
            "BGH, Urteil vom 10.02.2026 - 14 StR 1/20"
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual("BLOCKED", status)
        self.assertIn("unplausibel", report)
        self.assertIn("14 StR 1/20", report)

    def test_wide_nonstructural_docket_is_not_silently_ignored(self):
        result, report, status = run_guard("Siehe auch 2 C 1/20.")
        self.assertEqual(1, result.returncode)
        self.assertEqual("BLOCKED", status)
        self.assertIn("nicht_strukturell", report)
        self.assertIn("2 C 1/20", report)

    def test_structured_proven_bgh_citation_remains_allowed(self):
        result, report, status = run_guard(
            "BGH, Urteil vom 10.02.2026 - I ZR 130/25"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("ALLOWED", status)
        self.assertIn("belegt", report)


if __name__ == "__main__":
    unittest.main()
