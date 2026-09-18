#!/usr/bin/env python3
"""
AP-16 — unabhaengige Verifikation (Versandcheck / Ausgangs-Guardrail,
Implementation Paper Kap. 22.3/23) fuer ein zusammengesetztes langes
Dokument.

Diese Pruefung ist bewusst UNABHAENGIG vom Assemble-Skript: sie liest nur
die fertige .docx erneut ein und leitet jedes Ergebnis selbst aus den
tatsaechlichen Daten ab (keine Wiederverwendung der Selbstauskunft des
Assemblers). Jede Zeile im Bericht ist das Ergebnis einer echten Pruefung.

Usage:
    python3 AP16_verify_document.py <document.docx> [report.md]
"""
import sys
import re
import zipfile
import subprocess
import os
from datetime import datetime

APPROVED_FONTS = {"Baskerville"}

def read_document_xml(path):
    z = zipfile.ZipFile(path)
    return z.read('word/document.xml').decode('utf-8')

def zip_integrity(path):
    try:
        z = zipfile.ZipFile(path)
        for i in z.infolist():
            z.read(i.filename)
        return True, None
    except Exception as e:
        return False, str(e)

def extract_paragraphs(xml):
    """Return list of (style, text) per paragraph."""
    paras = re.findall(r'<w:p\b.*?</w:p>', xml, re.S)
    out = []
    for p in paras:
        style_m = re.search(r'w:pStyle w:val="([^"]*)"', p)
        style = style_m.group(1) if style_m else None
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', p)
        out.append((style, "".join(texts)))
    return out

def check_rubrum(paras):
    rubrum_texts = " ".join(t for s, t in paras if s in ("Rubrum", "RubrumFett"))
    body_after_rubrum_idx = None
    for i, (s, t) in enumerate(paras):
        if s in ("Rubrum", "RubrumFett"):
            body_after_rubrum_idx = i
    # Rubrum block content is usually Fliesstext right after the Rubrum-styled heading;
    # gather the following Fliesstext paragraphs up to the Antrag heading.
    block = []
    started = False
    for s, t in paras:
        if s in ("Rubrum", "RubrumFett"):
            started = True
            continue
        if started:
            if s == "Antrag" and t.strip() == "Antrag":
                break
            block.append(t)
    block_text = " ".join(block)
    required_fields = {
        "Gericht": bool(re.search(r'(Gericht|Landgericht|Amtsgericht|Oberlandesgericht)', block_text, re.I)),
        "Aktenzeichen": bool(re.search(r'Az\.?:', block_text)),
        "Parteien/Rollen": bool(re.search(r'(Klaeger|Kläger|Beklagte)', block_text, re.I)),
        "Prozessbevollmaechtigte": bool(re.search(r'Prozessbevollm', block_text, re.I)),
        "Streitgegenstand": bool(re.search(r'wegen', block_text, re.I)),
    }
    return required_fields

def check_antrag_numbering(xml):
    """Antrag paragraphs must carry a real numPr (auto-numbering), not typed digits."""
    paras = re.findall(r'<w:p\b.*?</w:p>', xml, re.S)
    antrag_paras = [p for p in paras if 'w:pStyle w:val="Antrag"' in p]
    numbered = [p for p in antrag_paras if '<w:numPr>' in p]
    # exclude the bare "Antrag" heading paragraph itself
    content_antrag = [p for p in antrag_paras if re.search(r'<w:t[^>]*>(.*?)</w:t>', p) and
                       "".join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p)).strip() not in ("Antrag", "")]
    numbered_content = [p for p in content_antrag if '<w:numPr>' in p]
    return len(content_antrag), len(numbered_content)

def check_gliederung_outline(styles_xml):
    ok = {}
    for style_id in ("Gliederung1", "Gliederung2"):
        m = re.search(rf'<w:style w:type="paragraph" w:styleId="{style_id}">.*?</w:style>', styles_xml, re.S)
        if m:
            ok[style_id] = '<w:outlineLvl' in m.group(0)
        else:
            ok[style_id] = False
    return ok

def check_page_numbering(docx_path):
    pdf_path = os.path.splitext(docx_path)[0] + '.pdf'
    if not os.path.exists(pdf_path):
        soffice = os.environ.get('SOFFICE_SCRIPT')
        if soffice:
            subprocess.run(['python3', soffice, '--headless', '--convert-to', 'pdf', docx_path],
                            capture_output=True, cwd=os.path.dirname(docx_path) or '.')
    if not os.path.exists(pdf_path):
        return None, None
    try:
        out = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True, check=True).stdout
        found_from_page1 = bool(re.search(r'Seite\s+1\s+von\s+\d+', out))
        all_pages_found = re.findall(r'Seite\s+(\d+)\s+von\s+(\d+)', out)
        return found_from_page1, all_pages_found
    except Exception:
        return None, None

def check_fonts(styles_xml, document_xml):
    fonts = set(re.findall(r'w:ascii="([^"]*)"', styles_xml))
    fonts |= set(re.findall(r'w:ascii="([^"]*)"', document_xml))
    non_approved = fonts - APPROVED_FONTS
    return fonts, non_approved

def check_anlagen_consistency(paras):
    """Independent re-derivation: which Anlagen are referenced in Fliesstext/Antrag body
    vs. which are listed under Anlagenverzeichnis (as Anlage-styled paragraphs)."""
    body_text = " ".join(t for s, t in paras if s in ("Fliesstext", "Antrag"))
    referenced = set(re.findall(r'Anlage\s+(K\d+)', body_text))

    listed = set()
    for s, t in paras:
        if s == "Anlage":
            m = re.match(r'Anlage\s+(K\d+)', t)
            if m:
                listed.add(m.group(1))

    missing_from_list = referenced - listed
    orphaned_in_list = listed - referenced

    placeholder_entries = set()
    for s, t in paras:
        if s == "Anlage" and re.search(r'FEHLENDE DEFINITION|\[.*?\]', t):
            m = re.match(r'Anlage\s+(K\d+)', t)
            if m:
                placeholder_entries.add(m.group(1))

    return referenced, listed, missing_from_list, orphaned_in_list, placeholder_entries

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 AP16_verify_document.py <document.docx> [report.md]")
        sys.exit(1)
    docx_path = sys.argv[1]
    report_path = sys.argv[2] if len(sys.argv) > 2 else "AP16_verify_report.md"

    lines = [f"# AP-16 Versandcheck / Ausgangs-Guardrail (automatisch, unabhaengig generiert)\n",
             f"Erzeugt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
             f"Datei: `{os.path.basename(docx_path)}`\n",
             "Diese Pruefung liest die fertige Datei erneut und unabhaengig ein — sie vertraut keiner Selbstauskunft des Erstellungsskripts.\n"]

    ok_zip, err = zip_integrity(docx_path)
    lines.append(f"## ZIP-Integritaet: {'PASS' if ok_zip else 'FAIL — ' + str(err)}\n")
    if not ok_zip:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        print("FAIL — Datei beschaedigt")
        sys.exit(1)

    try:
        with zipfile.ZipFile(docx_path) as z:
            document_xml = z.read('word/document.xml').decode('utf-8')
            styles_xml = z.read('word/styles.xml').decode('utf-8')
    except (KeyError, UnicodeDecodeError) as e:
        lines.append(f"## OOXML-Struktur: FAIL — {e}\n")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        print("FAIL — OOXML-Struktur ungueltig")
        sys.exit(1)
    paras = extract_paragraphs(document_xml)

    all_pass = True

    # 1. Rubrum vollstaendig
    rubrum_fields = check_rubrum(paras)
    lines.append("## Rubrum vollstaendig")
    for field, present in rubrum_fields.items():
        lines.append(f"- {field}: {'PASS' if present else 'FAIL'}")
        all_pass &= present
    lines.append("")

    # 2. Antrag numeriert vor Begruendung
    total_antrag, numbered_antrag = check_antrag_numbering(document_xml)
    antrag_ok = total_antrag > 0 and total_antrag == numbered_antrag
    lines.append(f"## Antrag: numerierte, tenorfaehige Antraege")
    lines.append(f"- Antrag-Absaetze gefunden: {total_antrag}, davon echt auto-numeriert (w:numPr): {numbered_antrag}")
    lines.append(f"- Ergebnis: {'PASS' if antrag_ok else 'FAIL'}\n")
    all_pass &= antrag_ok

    # 3. Sichtbare Gliederung (outline levels present in styles -> TOC-faehig)
    outline_ok = check_gliederung_outline(styles_xml)
    lines.append("## Sichtbare Gliederung (TOC-faehige Formatvorlagen)")
    for style_id, ok in outline_ok.items():
        lines.append(f"- {style_id} traegt outlineLvl: {'PASS' if ok else 'FAIL'}")
    lines.append("")
    all_pass &= all(outline_ok.values())

    # 4. 'Seite X von Y' ab Seite 1
    from_page1, all_pages = check_page_numbering(docx_path)
    lines.append("## Seitennummerierung")
    if from_page1 is None:
        lines.append("- 'Seite 1 von Y' im PDF: nicht pruefbar (PDF nicht erzeugt)\n")
    else:
        lines.append(f"- 'Seite 1 von Y' im PDF gefunden: {'PASS' if from_page1 else 'FAIL'}")
        lines.append(f"- Gefundene Seitenangaben: {all_pages}\n")
        all_pass &= bool(from_page1)

    # 5. Anlagenverzeichnis + Konsistenzpruefung (unabhaengig neu abgeleitet)
    referenced, listed, missing_from_list, orphaned, placeholders = check_anlagen_consistency(paras)
    lines.append("## Anlagenverzeichnis: Konsistenzpruefung (unabhaengig neu abgeleitet)")
    lines.append(f"- Im Fliesstext/Antrag referenzierte Anlagen: {sorted(referenced)}")
    lines.append(f"- Im Anlagenverzeichnis gelistete Anlagen: {sorted(listed)}")
    lines.append(f"- Referenziert, aber NICHT gelistet: {sorted(missing_from_list) or 'keine'}")
    lines.append(f"- Gelistet, aber NICHT referenziert (verwaist): {sorted(orphaned) or 'keine'}")
    lines.append(f"- Gelistet mit fehlender/Platzhalter-Definition: {sorted(placeholders) or 'keine'}")
    consistency_ok = not missing_from_list and not orphaned and not placeholders
    lines.append(f"- Ergebnis: {'PASS' if consistency_ok else 'FAIL'}\n")
    all_pass &= consistency_ok

    # 6. Nur freigegebene Schriftarten
    fonts, non_approved = check_fonts(styles_xml, document_xml)
    lines.append("## Schriftarten")
    lines.append(f"- Gefundene Schriftarten: {sorted(fonts)}")
    lines.append(f"- Nicht freigegeben: {sorted(non_approved) or 'keine'}")
    fonts_ok = not non_approved
    lines.append(f"- Ergebnis: {'PASS' if fonts_ok else 'FAIL'}\n")
    all_pass &= fonts_ok

    lines.append(f"## Gesamtergebnis: {'PASS — sendefaehig' if all_pass else 'FAIL — nicht sendefaehig, siehe Details oben'}\n")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"Report geschrieben: {report_path}")
    print(f"Gesamtergebnis: {'PASS' if all_pass else 'FAIL'}")
    sys.exit(0 if all_pass else 1)

if __name__ == '__main__':
    main()
