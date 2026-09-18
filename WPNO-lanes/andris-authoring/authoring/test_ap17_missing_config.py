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


def run_guard(tmp_path, refs_text=None, docx_path=None):
    refs = tmp_path / "known-references.json"
    if refs_text is not None:
        refs.write_text(refs_text, encoding="utf-8")

    report = tmp_path / "report.md"
    ledger = tmp_path / "ledger.sqlite"
    result = subprocess.run(
        [
            sys.executable,
            str(guard_path()),
            str(docx_path or (tmp_path / "not-needed.docx")),
            str(refs),
            str(ledger),
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result, report, ledger


def write_clean_control(path):
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="urn:test"><w:body>
<w:p><w:pPr><w:pStyle w:val="Rubrum"/></w:pPr><w:r><w:t>Rubrum</w:t></w:r></w:p>
<w:p><w:r><w:t>Gericht Landgericht Teststadt, Az.: 12 O 345/26, Klaeger A gegen Beklagte B, Prozessbevollmaechtigte Kanzlei Test, wegen Testforderung</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/></w:pPr><w:r><w:t>Antrag</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Antrag"/><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Die Klage wird abgewiesen.</w:t></w:r></w:p>
<w:sectPr/></w:body></w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="urn:test">
<w:style w:styleId="Normal"><w:rPr><w:rFonts w:ascii="Baskerville"/></w:rPr></w:style>
<w:style w:styleId="Gliederung1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
<w:style w:styleId="Gliederung2"><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
</w:styles>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)


def last_ledger_result(ledger):
    with sqlite3.connect(ledger) as connection:
        return connection.execute(
            "SELECT status, details FROM nosutisanas_parbaudes_zurnals "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()


def assert_semantic_config_block(testcase, result, report, ledger, error_type):
    testcase.assertEqual(result.returncode, 1)
    testcase.assertNotIn("Traceback", result.stderr)
    testcase.assertIn("Gesamtergebnis: BLOCKED", result.stdout)
    testcase.assertTrue(report.is_file())
    report_text = report.read_text(encoding="utf-8")
    testcase.assertIn("## Gesamtergebnis: BLOCKED", report_text)
    testcase.assertIn(
        f"Referenzkonfiguration nicht lesbar: {error_type}", report_text
    )
    testcase.assertEqual(
        last_ledger_result(ledger),
        ("BLOCKED", f"Referenzkonfiguration nicht lesbar: {error_type}"),
    )


class MissingConfigurationTests(unittest.TestCase):
    def test_missing_reference_configuration_is_semantically_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report, ledger = run_guard(Path(tmp))
            assert_semantic_config_block(
                self, result, report, ledger, "FileNotFoundError"
            )

    def test_malformed_reference_configuration_is_semantically_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report, ledger = run_guard(Path(tmp), "{")
            assert_semantic_config_block(
                self, result, report, ledger, "JSONDecodeError"
            )

    def test_valid_reference_configuration_reaches_document_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            refs = json.dumps({"known_references": [], "forbidden_names": []})
            result, report, ledger = run_guard(Path(tmp), refs)

            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("ZIP-Integritaet fehlgeschlagen", result.stdout)
            report_text = report.read_text(encoding="utf-8")
            self.assertNotIn("Referenzkonfiguration nicht lesbar", report_text)
            self.assertIn("ZIP-Integritaet FAIL", report_text)
            status, details = last_ledger_result(ledger)
            self.assertEqual(status, "BLOCKED")
            self.assertTrue(details.startswith("ZIP-Integritaet FAIL:"))

    def test_known_good_synthetic_document_remains_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docx_path = tmp_path / "synthetic-clean.docx"
            write_clean_control(docx_path)
            refs = json.dumps(
                {
                    "known_references": ["12 O 345/26"],
                    "forbidden_names": [],
                }
            )
            result, report, ledger = run_guard(tmp_path, refs, docx_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("Gesamtergebnis: ALLOWED", result.stdout)
            self.assertIn(
                "## Gesamtergebnis: ALLOWED",
                report.read_text(encoding="utf-8"),
            )
            self.assertEqual(last_ledger_result(ledger), ("ALLOWED", ""))


if __name__ == "__main__":
    unittest.main()
