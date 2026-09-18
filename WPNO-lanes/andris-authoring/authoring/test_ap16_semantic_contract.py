#!/usr/bin/env python3
"""Source-bound semantic contract tests for AP16 verification."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


VERIFIER = Path(__file__).with_name("AP16_verify_document.py")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"

OUTLINE = {
    "rubrum": {
        "gericht": "Landgericht Musterstadt",
        "aktenzeichen": "1 O 1/26",
        "klaeger": "Muster GmbH, Klaegerin",
        "beklagte": "Beispiel AG, Beklagte",
        "prozessbevollmaechtigte_klaeger": "Kanzlei Alpha",
        "prozessbevollmaechtigte_beklagte": "Kanzlei Beta",
        "streitgegenstand": "wegen synthetischem Testanspruch",
    },
    "antraege": ["Die Beklagte wird verurteilt."],
    "sections": [
        {"level": 1, "heading": "I. Sachverhalt",
         "paragraphs": ["Die synthetische Ausgangslage ist vollstaendig. Anlage K1."]},
        {"level": 2, "heading": "1. Einzelheit",
         "paragraphs": ["Eine synthetische Einzelheit wird beschrieben."]},
    ],
    "anlagen_definitionen": {"K1": "Synthetischer Beleg"},
}


def paragraph(style, text, numbered=False, relationship_id=None):
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    num_xml = '<w:numPr><w:numId w:val="100"/></w:numPr>' if numbered else ""
    run = f'<w:r><w:t>{escape(text)}</w:t></w:r>'
    if relationship_id:
        run = f'<w:hyperlink r:id="{relationship_id}">{run}</w:hyperlink>'
    return f'<w:p><w:pPr>{style_xml}{num_xml}</w:pPr>{run}</w:p>'


def write_docx(path, body=None, heading=None, toc=None, broken_rel=False,
               numbered=True):
    body = body or OUTLINE["sections"][0]["paragraphs"][0]
    heading = heading or OUTLINE["sections"][0]["heading"]
    toc = toc or "I. Sachverhalt 1. Einzelheit"
    rubrum = OUTLINE["rubrum"]
    parts = [
        paragraph("RubrumFett", "Rubrum"),
        paragraph("Fliesstext", rubrum["gericht"]),
        paragraph("Fliesstext", f'Az.: {rubrum["aktenzeichen"]}'),
        paragraph("Fliesstext", "In dem Rechtsstreit"),
        paragraph("Fliesstext", rubrum["klaeger"]),
        paragraph("Fliesstext", "Prozessbevollmaechtigte: Kanzlei Alpha"),
        paragraph("Fliesstext", "gegen"),
        paragraph("Fliesstext", rubrum["beklagte"]),
        paragraph("Fliesstext", "Prozessbevollmaechtigte: Kanzlei Beta"),
        paragraph("Fliesstext", rubrum["streitgegenstand"]),
        paragraph("Antrag", "Antrag"),
        paragraph("Fliesstext", "Namens und in Vollmacht der Klaegerin wird beantragt,"),
        paragraph("Antrag", OUTLINE["antraege"][0], numbered=numbered),
        ('<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr>'
         '<w:fldSimple w:instr="TOC"><w:r><w:t>' + escape(toc) +
         '</w:t></w:r></w:fldSimple></w:p>'),
        paragraph("Gliederung1", heading),
        paragraph("Fliesstext", body),
        paragraph("Gliederung2", "1. Einzelheit"),
        paragraph("Fliesstext", "Eine synthetische Einzelheit wird beschrieben."),
    ]
    if broken_rel:
        parts.append(paragraph(None, "Verweis", relationship_id="rIdMissing"))
    parts.append(paragraph("Anlage", "Anlage K1 - Synthetischer Beleg"))
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>'
        + "".join(parts) + '<w:sectPr/></w:body></w:document>'
    )
    styles = (
        f'<w:styles xmlns:w="{W}">'
        '<w:style w:type="paragraph" w:styleId="Gliederung1"><w:pPr>'
        '<w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts '
        'w:ascii="Baskerville"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Gliederung2"><w:pPr>'
        '<w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts '
        'w:ascii="Baskerville"/></w:rPr></w:style></w:styles>'
    )
    rels = f'<Relationships xmlns="{PR}"></Relationships>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/_rels/document.xml.rels", rels)


def run_verifier(mutator=None, include_outline=True, malformed_outline=False):
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        document = directory / "case.docx"
        options = mutator or {}
        write_docx(document, **options)
        outline = directory / "outline.json"
        outline.write_text(
            json.dumps({} if malformed_outline else OUTLINE), encoding="utf-8"
        )
        report = directory / "report.md"
        argv = [sys.executable, str(VERIFIER), str(document), str(report)]
        if include_outline:
            argv.extend(["--outline", str(outline)])
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        return result, report.read_text(encoding="utf-8")


class SemanticContractTests(unittest.TestCase):
    def test_matching_document_and_outline_pass(self):
        result, report = run_verifier()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Semantischer Vertrag: PASS", report)

    def test_unrelated_or_changed_body_fails(self):
        for body in ("Ein synthetisches Kochrezept. Anlage K1.",
                     "Die Ausgangslage wurde um einen Satz geaendert. Anlage K1."):
            with self.subTest(body=body):
                result, _ = run_verifier({"body": body})
                self.assertNotEqual(0, result.returncode)

    def test_changed_heading_fails(self):
        result, _ = run_verifier({"heading": "I. Umbenannter Sachverhalt"})
        self.assertNotEqual(0, result.returncode)

    def test_stale_toc_fails(self):
        result, _ = run_verifier({"toc": "Nicht vorhandene Ueberschrift"})
        self.assertNotEqual(0, result.returncode)

    def test_unresolved_relationship_fails(self):
        result, _ = run_verifier({"broken_rel": True})
        self.assertNotEqual(0, result.returncode)

    def test_missing_contract_cannot_pass_as_semantically_verified(self):
        result, report = run_verifier(include_outline=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Semantischer Vertrag: FAIL", report)

    def test_malformed_contract_is_controlled_failure(self):
        result, report = run_verifier(malformed_outline=True)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("Semantischer Vertrag: FAIL", report)

    def test_existing_structural_failure_still_returns_nonzero(self):
        result, _ = run_verifier({"numbered": False})
        self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
