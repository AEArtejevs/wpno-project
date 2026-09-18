import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile


DEFAULT_GUARD = Path(__file__).with_name("AP17_output_guardrail_v3.py")


def guard_path():
    return Path(os.environ.get("AP17_GUARD_PATH", DEFAULT_GUARD))


def write_control_document(path, citation):
    citation_paragraph = ""
    if citation:
        citation_paragraph = (
            "<w:p><w:r><w:t>BGH, Urteil vom 10.02.2026 - "
            f"{citation}</w:t></w:r></w:p>"
        )
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Rubrum"/></w:pPr><w:r><w:t>Rubrum</w:t></w:r></w:p>
<w:p><w:r><w:t>Gericht Landgericht Teststadt, Az.: 12 O 345/26, Klaeger A gegen Beklagte B, Prozessbevollmaechtigte Kanzlei Test, wegen Testforderung</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/></w:pPr><w:r><w:t>Antrag</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Die Klage wird abgewiesen.</w:t></w:r></w:p>
{citation_paragraph}
<w:sectPr/></w:body></w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:styleId="Normal"><w:rPr><w:rFonts w:ascii="Baskerville"/></w:rPr></w:style>
<w:style w:styleId="Gliederung1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
<w:style w:styleId="Gliederung2"><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
</w:styles>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)


def run_guard(tmp_path, citation):
    document = tmp_path / "synthetic-citation.docx"
    write_control_document(document, citation)
    refs = tmp_path / "known-references.json"
    refs.write_text(
        json.dumps(
            {
                "known_references": ["12 O 345/26"],
                "forbidden_names": [],
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.sqlite"
    report = tmp_path / "report.md"
    result = subprocess.run(
        [
            sys.executable,
            str(guard_path()),
            str(document),
            str(refs),
            str(ledger),
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    connection = sqlite3.connect(ledger)
    try:
        ledger_status = connection.execute(
            "SELECT status FROM nosutisanas_parbaudes_zurnals "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    finally:
        connection.close()
    return result, report.read_text(encoding="utf-8"), ledger_status


class CitationBlockingTests(unittest.TestCase):
    def test_declared_nonexistent_citation_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report, ledger_status = run_guard(Path(tmp), "VII ZR 100/12")

        self.assertEqual(result.returncode, 1)
        self.assertIn("VII ZR 100/12", report)
        self.assertIn("nachweislich nicht vorhanden", report)
        self.assertIn("Zitierte Entscheidung existiert nicht", report)
        self.assertEqual(ledger_status, "BLOCKED")

    def test_unverified_citation_is_blocked_pending_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report, ledger_status = run_guard(Path(tmp), "VI ZR 999/24")

        self.assertEqual(result.returncode, 1)
        self.assertIn("VI ZR 999/24", report)
        self.assertIn("ungeprueft", report)
        self.assertIn("Zitierte Entscheidung ungeprueft", report)
        self.assertEqual(ledger_status, "BLOCKED")

    def test_declared_present_citation_remains_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report, ledger_status = run_guard(Path(tmp), "I ZR 130/25")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("belegt: ['I ZR 130/25']", report)
        self.assertIn("## Gesamtergebnis: ALLOWED", report)
        self.assertEqual(ledger_status, "ALLOWED")


if __name__ == "__main__":
    unittest.main()
