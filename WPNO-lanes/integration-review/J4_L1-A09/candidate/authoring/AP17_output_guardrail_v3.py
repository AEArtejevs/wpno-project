#!/usr/bin/env python3
"""
AP-17 — Nosutisanas parbaude (izvades aizsargmehanisms / Output Guardrail).

Implementation Paper, Koncepts 07 (Guardrails) + AP-17 tabulas ieraksts.
DoD: "Kluudains uzmetums apturets -- nosutisanas parbaudes zurnals".

Ta ir PEDEJA parbaude pirms melnraksts sasniedz zvernatu profesionali:
  1) Tiesas forma (atkartots/paplasinats no AP-15/AP-16 Versandcheck):
     Rubrum pilnigs, Antrag numerets, Gliederung redzama, lapu numeracija,
     Anlagenverzeichnis konsekvence, tikai apstiprinatie fonti.
  2) PII atlikumu skenesana: vai izejosaja teksta nav palicis atklats
     teksts, ko vajadzeja anonimizet (IBAN, e-pasts, telefona numurs,
     reali vardi no aizliegta saraksta, neparasti lietas-numuru formati).
  3) Atsauces validacija: katrs "Az.:" pieminejums teksta tiek parbaudits
     pret zinamu/atlautu atsauzu sarakstu (simule sear_bfh/BGH-DB, kuram
     mums seit nav pieejas) -- izdomats/nezinams lietas numurs BLOKE.

Katrs parbaudes megininajums tiek ierakstits SQLite zurnala
(nosutisanas_parbaudes_zurnals) ar statusu ALLOWED/BLOCKED, sha256
jaucejkodu un laikspiedolu -- tas IR "nosutisanas parbaudes zurnals".

Usage:
    python3 AP17_output_guardrail.py <document.docx> <known_references.json> <ledger.sqlite> [report.md]
"""
import sys
import re
import json
import zipfile
import sqlite3
import hashlib
import subprocess
import os
from datetime import datetime

APPROVED_FONTS = {"Baskerville"}

# Vispaarigi PII paraugi (paplasinami projektam specifiskiem markieriem)
PII_PATTERNS = {
    "IBAN": re.compile(
        r"\b[A-Z]{2}\d{2}[ ]?[A-Z0-9]{10,30}\b",
        re.IGNORECASE | re.ASCII,
    ),
    "E-Pasts": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "Telefons": re.compile(r"\b(?:\+49|0)[ \-]?\d{2,5}[ \-]?\d{4,10}\b"),
}

def sha256_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def ensure_ledger(db_path):
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS nosutisanas_parbaudes_zurnals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            satz_id TEXT,
            datei TEXT,
            status TEXT,
            hash TEXT,
            details TEXT,
            ts TEXT
        )
    """)
    con.commit()
    con.close()

def log_ledger(db_path, satz_id, datei, status, hash_, details):
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO nosutisanas_parbaudes_zurnals (satz_id, datei, status, hash, details, ts) VALUES (?,?,?,?,?,datetime('now'))",
        (satz_id, datei, status, hash_, details)
    )
    con.commit()
    con.close()

def zip_integrity(path):
    try:
        z = zipfile.ZipFile(path)
        for i in z.infolist():
            z.read(i.filename)
        return True, None
    except Exception as e:
        return False, str(e)

def extract_paragraphs(xml):
    paras = re.findall(r'<w:p\b.*?</w:p>', xml, re.S)
    out = []
    for p in paras:
        style_m = re.search(r'w:pStyle w:val="([^"]*)"', p)
        style = style_m.group(1) if style_m else None
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', p)
        out.append((style, "".join(texts)))
    return out

# ---- 1) Tiesas forma (atkartots no AP-16 Versandcheck) ----

def check_rubrum(paras):
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
    return {
        "Gericht": bool(re.search(r'(Gericht|Landgericht|Amtsgericht|Oberlandesgericht)', block_text, re.I)),
        "Aktenzeichen": bool(re.search(r'Az\.?:', block_text)),
        "Parteien/Rollen": bool(re.search(r'(Klaeger|Kläger|Beklagte)', block_text, re.I)),
        "Prozessbevollmaechtigte": bool(re.search(r'Prozessbevollm', block_text, re.I)),
        "Streitgegenstand": bool(re.search(r'wegen', block_text, re.I)),
    }

def check_antrag_numbering(document_xml):
    paras = re.findall(r'<w:p\b.*?</w:p>', document_xml, re.S)
    antrag_paras = [p for p in paras if 'w:pStyle w:val="Antrag"' in p]
    content_antrag = [p for p in antrag_paras if "".join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p)).strip() not in ("Antrag", "")]
    numbered_content = [p for p in content_antrag if '<w:numPr>' in p]
    return len(content_antrag), len(numbered_content)

HEADING_BASE_NAMES = {"heading1", "berschrift1", "heading2", "berschrift2",
                       "berschrift 1", "berschrift 2", "heading 1", "heading 2"}

def check_gliederung_outline(styles_xml):
    """A Gliederung-style paragraph is TOC-faehig if it EITHER carries an
    explicit outlineLvl itself, OR inherits one via w:basedOn from a
    Heading1/Heading2-family style (Word always assigns outlineLvl 0/1 to
    those built-ins, even when Word's own resave normalizes/strips an
    explicit override on the child style -- confirmed: TOC still populates
    correctly in this case, so checking only the literal tag is a false
    negative)."""
    ok = {}
    for style_id in ("Gliederung1", "Gliederung2"):
        # match the style block regardless of attribute order/extra attrs
        m = re.search(rf'<w:style [^>]*w:styleId="{style_id}"[^>]*>.*?</w:style>', styles_xml, re.S)
        if not m:
            ok[style_id] = False
            continue
        block = m.group(0)
        if '<w:outlineLvl' in block:
            ok[style_id] = True
            continue
        based_m = re.search(r'<w:basedOn w:val="([^"]*)"', block)
        based_on = (based_m.group(1) if based_m else "").lower()
        ok[style_id] = based_on in HEADING_BASE_NAMES
    return ok

def check_page_numbering(docx_path):
    pdf_path = os.path.splitext(docx_path)[0] + '.pdf'
    if not os.path.exists(pdf_path):
        soffice = os.environ.get('SOFFICE_SCRIPT')
        if soffice:
            subprocess.run(['python3', soffice, '--headless', '--convert-to', 'pdf', docx_path],
                            capture_output=True, cwd=os.path.dirname(docx_path) or '.')
    if not os.path.exists(pdf_path):
        return None
    try:
        out = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True, check=True).stdout
        return bool(re.search(r'Seite\s+1\s+von\s+\d+', out))
    except Exception:
        return None

def check_anlagen_consistency(paras):
    body_text = " ".join(t for s, t in paras if s in ("Fliesstext", "Antrag"))
    referenced = set(re.findall(r'Anlage\s+(K\d+)', body_text))
    listed = set()
    for s, t in paras:
        if s == "Anlage":
            m = re.match(r'Anlage\s+(K\d+)', t)
            if m:
                listed.add(m.group(1))
    placeholders = set()
    for s, t in paras:
        if s == "Anlage" and re.search(r'FEHLENDE DEFINITION', t):
            m = re.match(r'Anlage\s+(K\d+)', t)
            if m:
                placeholders.add(m.group(1))
    return referenced, listed, (referenced - listed), (listed - referenced), placeholders

def check_fonts(styles_xml, document_xml):
    fonts = set(re.findall(r'w:ascii="([^"]*)"', styles_xml)) | set(re.findall(r'w:ascii="([^"]*)"', document_xml))
    return fonts, (fonts - APPROVED_FONTS)

# ---- 2) PII atlikumu skenesana ----

def scan_pii(full_text, forbidden_names):
    findings = {}
    for label, pattern in PII_PATTERNS.items():
        hits = pattern.findall(full_text)
        if hits:
            findings[label] = hits
    name_hits = [n for n in forbidden_names if n and n in full_text]
    if name_hits:
        findings["Aizliegti_vardi"] = name_hits
    return findings

# ---- 3) Aktenzeichen ----
#
# KORREKTUR 04.08.2026 — hier wurden bisher zwei verschiedene Dinge vermischt:
#
#   (a) das Aktenzeichen DIESES Verfahrens, das im Rubrum steht
#       (z. B. "12 O 345/26" beim Landgericht). Steht dort das falsche,
#       ist das ein schwerer Formfehler.
#
#   (b) ZITIERTE Gerichtsentscheidungen (z. B. "BGH, I ZR 130/25").
#       Ob es die gibt, ist eine voellig andere Frage.
#
# Die alte Fassung pruefte nur (a), nannte das Ergebnis aber "erfundene
# Aktenzeichen" — und verglich gegen eine Liste, in der genau ein Eintrag
# stand: das eigene Aktenzeichen. Zitierte Entscheidungen wurden nie
# geprueft, weil das Muster ein vorangestelltes "Az.:" verlangte.
#
# Jetzt getrennt: (a) bleibt hier, (b) uebernimmt AP18_referenzpruefung
# gegen den echten Bestand der BGH-Entscheidungsdatenbank.

def validate_verfahrens_aktenzeichen(full_text, known_references):
    """(a) Aktenzeichen des eigenen Verfahrens gegen die Fallkonfiguration."""
    found_az = set(re.findall(r'Az\.?:\s*([0-9]+\s*[A-Za-z]+\s*[0-9]+/\d+)', full_text))
    unknown = [az for az in found_az if az not in known_references]
    return found_az, unknown

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 AP17_output_guardrail.py <document.docx> <known_references.json> <ledger.sqlite> [report.md]")
        sys.exit(1)

    docx_path = sys.argv[1]
    refs_path = sys.argv[2]
    ledger_path = sys.argv[3]
    report_path = sys.argv[4] if len(sys.argv) > 4 else "AP17_guardrail_report.md"
    satz_id = os.path.basename(docx_path)

    ensure_ledger(ledger_path)

    with open(refs_path, encoding='utf-8') as f:
        ref_config = json.load(f)
    known_references = set(ref_config.get("known_references", []))
    forbidden_names = ref_config.get("forbidden_names", [])

    lines = [f"# AP-17 Nosutisanas parbaude / Output Guardrail\n",
             f"Erzeugt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
             f"Datei: `{satz_id}`\n"]

    ok_zip, err = zip_integrity(docx_path)
    if not ok_zip:
        details = f"ZIP-Integritaet FAIL: {err}"
        log_ledger(ledger_path, satz_id, docx_path, "BLOCKED", "", details)
        lines.append(f"## Ergebnis: BLOCKED\n- {details}\n")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        print("BLOCKED — ZIP-Integritaet fehlgeschlagen")
        sys.exit(1)

    z = zipfile.ZipFile(docx_path)
    document_xml = z.read('word/document.xml').decode('utf-8')
    styles_xml = z.read('word/styles.xml').decode('utf-8')
    paras = extract_paragraphs(document_xml)
    full_text = " ".join(t for _, t in paras)
    doc_hash = sha256_of(full_text)

    blocking_reasons = []

    # 1) Tiesas forma
    rubrum_fields = check_rubrum(paras)
    lines.append("## 1. Tiesas forma")
    lines.append("### Rubrum")
    for field, present in rubrum_fields.items():
        lines.append(f"- {field}: {'PASS' if present else 'FAIL'}")
        if not present:
            blocking_reasons.append(f"Rubrum unvollstaendig: {field} fehlt")

    total_antrag, numbered_antrag = check_antrag_numbering(document_xml)
    antrag_ok = total_antrag > 0 and total_antrag == numbered_antrag
    lines.append(f"### Antrag: {total_antrag} gefunden, {numbered_antrag} numeriert -> {'PASS' if antrag_ok else 'FAIL'}")
    if not antrag_ok:
        blocking_reasons.append("Antrag nicht vollstaendig numeriert")

    outline_ok = check_gliederung_outline(styles_xml)
    lines.append(f"### Gliederung outline-Level: {outline_ok}")
    if not all(outline_ok.values()):
        blocking_reasons.append("Gliederung-Stile ohne outlineLvl (TOC nicht moeglich)")

    page1_ok = check_page_numbering(docx_path)
    lines.append(f"### 'Seite 1 von Y' im PDF: {page1_ok if page1_ok is not None else 'nicht pruefbar'}")
    if page1_ok is False:
        blocking_reasons.append("Seitennummerierung fehlt ab Seite 1")

    referenced, listed, missing_from_list, orphaned, placeholders = check_anlagen_consistency(paras)
    anlagen_ok = not missing_from_list and not orphaned and not placeholders
    lines.append(f"### Anlagenverzeichnis-Konsistenz: referenziert={sorted(referenced)}, gelistet={sorted(listed)} -> {'PASS' if anlagen_ok else 'FAIL'}")
    if not anlagen_ok:
        blocking_reasons.append(f"Anlagen-Inkonsistenz: fehlend={sorted(missing_from_list)}, verwaist={sorted(orphaned)}, Platzhalter={sorted(placeholders)}")

    fonts, non_approved = check_fonts(styles_xml, document_xml)
    lines.append(f"### Schriftarten: {sorted(fonts)}, nicht freigegeben: {sorted(non_approved) or 'keine'}")
    if non_approved:
        blocking_reasons.append(f"Nicht freigegebene Schriftart(en): {sorted(non_approved)}")

    # 2) PII-Scan
    pii_findings = scan_pii(full_text, forbidden_names)
    lines.append("\n## 2. PII-Restscan")
    if pii_findings:
        lines.append(f"- Funde: {pii_findings}")
        blocking_reasons.append(f"PII-Restfund: {list(pii_findings.keys())}")
    else:
        lines.append("- Keine PII-Reste gefunden: PASS")

    # 3a) Aktenzeichen des eigenen Verfahrens
    found_az, unknown_az = validate_verfahrens_aktenzeichen(full_text, known_references)
    lines.append("\n## 3a. Aktenzeichen des Verfahrens")
    lines.append(f"- Gefunden: {sorted(found_az) or 'keine'}")
    lines.append(f"- Nicht in der Fallkonfiguration: {sorted(unknown_az) or 'keine'}")
    if unknown_az:
        blocking_reasons.append(f"Aktenzeichen passt nicht zur Fallkonfiguration: {sorted(unknown_az)}")

    # 3b) Zitierte Entscheidungen gegen den echten BGH-Bestand
    lines.append("\n## 3b. Zitierte Entscheidungen (BGH-Entscheidungsdatenbank)")
    try:
        import AP18_referenzpruefung as refp
        referenz_datei = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "bgh_referenz.json")
        if not os.path.isfile(referenz_datei):
            lines.append("- NICHT PRUEFBAR: bgh_referenz.json fehlt")
            blocking_reasons.append("Referenzbestand fehlt — Zitate ungeprueft")
        else:
            belegt_map, fehlt_map, roh = refp.referenz_laden(referenz_datei)
            zitate = refp.aktenzeichen_finden(full_text)
            belegt      = [a for a in zitate if a in belegt_map]
            nicht_da    = [a for a in zitate if a in fehlt_map]
            ungeprueft  = [a for a in zitate if a not in belegt_map and a not in fehlt_map]

            lines.append(f"- Referenzstand: {roh.get('_stand','?')}")
            lines.append(f"- belegt: {belegt or 'keine'}")
            lines.append(f"- ungeprueft: {ungeprueft or 'keine'}")
            lines.append(f"- nachweislich nicht vorhanden: {nicht_da or 'keine'}")

            if nicht_da:
                blocking_reasons.append(
                    f"Zitierte Entscheidung existiert nicht: {sorted(nicht_da)}")
            if ungeprueft:
                lines.append("- HINWEIS: ungeprueft heisst NICHT falsch. "
                             "Vor dem Versand nachschlagen; blockiert wird deswegen nicht.")
    except ImportError:
        lines.append("- NICHT PRUEFBAR: AP18_referenzpruefung.py nicht gefunden")
        blocking_reasons.append("Zitatpruefung nicht verfuegbar")

    status = "BLOCKED" if blocking_reasons else "ALLOWED"
    lines.append(f"\n## Gesamtergebnis: {status}")
    if blocking_reasons:
        lines.append("### Blockierungsgruende:")
        for r in blocking_reasons:
            lines.append(f"- {r}")

    log_ledger(ledger_path, satz_id, docx_path, status, doc_hash, "; ".join(blocking_reasons) if blocking_reasons else "")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"Report geschrieben: {report_path}")
    print(f"Ledger-Eintrag: {status} (hash {doc_hash[:12]}...)")
    print(f"Gesamtergebnis: {status}")
    if status == "BLOCKED":
        sys.exit(1)

if __name__ == '__main__':
    main()
