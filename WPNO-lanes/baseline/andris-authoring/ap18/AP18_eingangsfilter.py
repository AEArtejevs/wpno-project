#!/usr/bin/env python3
"""
AP18_eingangsfilter.py — Eingangsfilter fuer fremde PDF-Dokumente.

Zweck (Kapitel 11, Konzept 07 Guardrails; Testkatalog Kapitel 29, P4):
Gegnerische Schriftsaetze kommen als PDF ins Haus und werden maschinell
gelesen. Ein Gegner koennte darin Text verstecken, der wie eine Anweisung an
das System aussieht. Dieser Filter prueft eingehende PDFs, bevor ihr Inhalt
weiterverarbeitet wird.

GRUNDSATZ, der wichtiger ist als jeder Filter:
Fremde Inhalte sind DATEN, niemals Anweisungen. Der Filter ersetzt diesen
Grundsatz nicht, er ergaenzt ihn — und er macht dem Menschen sichtbar, dass
jemand etwas versucht hat.

Zwei unabhaengige Signale werden geprueft:

  1. VERSTECKTER TEXT — unsichtbare Schrift, Schriftgroesse unter 3pt, Text
     ausserhalb der Seite, unsichtbarer Rendermodus, Text nur in Metadaten.
     In einem Schriftsatz gibt es keinen legitimen Grund, Text zu verstecken.
     Deshalb ist das Verstecken fuer sich genommen schon ein Befund.

  2. ANWEISUNGSFORMULIERUNGEN — Wendungen, die sich an ein System richten,
     nicht an ein Gericht.

Bewertung:
  BLOCKIERT  versteckter Text UND Anweisungsformulierung
  PRUEFEN    eines von beidem
  FREI       keines von beidem

Aufruf:
    python3 AP18_eingangsfilter.py datei.pdf
    python3 AP18_eingangsfilter.py datei.docx
    python3 AP18_eingangsfilter.py ordner/
    python3 AP18_eingangsfilter.py ordner/ --journal eingangspruefungen.sqlite

Mit --journal wird jede Pruefung dauerhaft festgehalten: Datei, Pruefsumme,
Urteil, Befunde, Zeitpunkt. Ohne Journal gibt es spaeter keinen Nachweis,
dass geprueft wurde — und eine Pruefung, die man nicht belegen kann, ist im
Streitfall keine.

Exit-Code 1, sobald mindestens eine Datei BLOCKIERT ist. Damit laesst sich der
Filter als Tor vor die Aktenuebernahme haengen: bricht er ab, wird das
Dokument nicht uebernommen.
"""

import hashlib
import os
import re
import sqlite3
import sys
from datetime import datetime


# --- Signal 2: Anweisungsformulierungen -----------------------------------
# Bewusst mehrwortig. Einzelne Woerter wie "Anweisung", "System" oder
# "ignoriert" kommen in echten Schriftsaetzen staendig vor; wer darauf filtert,
# blockiert die halbe Akte.
ANWEISUNGSMUSTER = [
    (r"ignorier[ea]?\s+(alle|die)\s+(vorherigen|bisherigen|obigen)", "Ignoriere alle vorherigen ..."),
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instruction", "ignore previous instructions"),
    (r"vergiss\s+(alle|die)\s+(vorherigen|bisherigen)", "Vergiss alle vorherigen ..."),
    (r"forget\s+(all\s+)?(previous|prior)", "forget all previous"),
    (r"disregard\s+(your|all|any|the)\s+(guideline|instruction|rule|previous)", "disregard your guidelines"),
    (r"you\s+are\s+now\s+(a|an|assisting|acting)", "you are now ..."),
    (r"du\s+bist\s+(jetzt|nun)\s+ein", "Du bist jetzt ein ..."),
    (r"\bsystem\s*(hinweis|prompt|nachricht)\s*:", "Systemhinweis:"),
    (r"^\s*system\s*:", "System: (Zeilenanfang)"),
    (r"neue\s+anweisung(en)?\s*:", "Neue Anweisungen:"),
    (r"new\s+instruction(s)?\s*:", "New instructions:"),
    (r"(prompt|system)\s*(override|injection)", "prompt/system override"),
    (r"act\s+as\s+(a|an|the)\s+", "act as a ..."),
    (r"antworte\s+(ab\s+jetzt|nur\s+noch)", "Antworte ab jetzt ..."),
]

# --- Signal 1: Schwellen fuer verstecken Text -----------------------------
MIN_SCHRIFTGROESSE = 3.0      # darunter mit blossem Auge nicht lesbar
HELL_SCHWELLE = 0.90          # Graustufe, ab der Text auf weiss verschwindet
RENDERMODUS_UNSICHTBAR = 3


# --- Pruefjournal ---------------------------------------------------------
# Gleiche Bauart wie das Versandjournal aus AP-17: eine SQLite-Datei, ein
# Datensatz je Pruefung, mit Pruefsumme der geprueften Datei. Die Pruefsumme
# ist wichtig — sie belegt, dass genau DIESE Fassung geprueft wurde und nicht
# eine spaeter ausgetauschte.

def sha256_datei(pfad):
    h = hashlib.sha256()
    try:
        with open(pfad, "rb") as f:
            for brocken in iter(lambda: f.read(1 << 20), b""):
                h.update(brocken)
        return h.hexdigest()
    except Exception:
        return ""


def journal_anlegen(db_pfad):
    verb = sqlite3.connect(db_pfad)
    verb.execute("""
        CREATE TABLE IF NOT EXISTS eingangspruefungen (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            zeitpunkt TEXT NOT NULL,
            datei     TEXT NOT NULL,
            sha256    TEXT,
            urteil    TEXT NOT NULL,
            versteckt TEXT,
            anweisung TEXT
        )
    """)
    verb.commit()
    return verb


def journal_eintragen(verb, pfad, befund, urteil):
    verb.execute(
        "INSERT INTO eingangspruefungen "
        "(zeitpunkt, datei, sha256, urteil, versteckt, anweisung) "
        "VALUES (?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"),
         os.path.basename(pfad),
         sha256_datei(pfad),
         urteil,
         " | ".join(befund["versteckt"]) or None,
         " | ".join(befund["anweisungen_versteckt"] + befund["anweisungen"]) or None),
    )
    verb.commit()


def farbe_zu_grau(farb_int):
    """PyMuPDF liefert die Farbe als 24-Bit-Integer."""
    r = ((farb_int >> 16) & 255) / 255
    g = ((farb_int >> 8) & 255) / 255
    b = (farb_int & 255) / 255
    return 0.299 * r + 0.587 * g + 0.114 * b


def anweisungen_finden(text):
    treffer = []
    for muster, name in ANWEISUNGSMUSTER:
        if re.search(muster, text, re.IGNORECASE | re.MULTILINE):
            treffer.append(name)
    return treffer


def pdf_pruefen(pfad):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("FEHLER: PyMuPDF fehlt.  pip3 install pymupdf")
        sys.exit(1)

    befund = {
        "datei": os.path.basename(pfad),
        "versteckt": [],
        "anweisungen": [],
        "anweisungen_versteckt": [],
        "fehler": None,
    }

    try:
        dok = fitz.open(pfad)
    except Exception as e:
        befund["fehler"] = f"nicht lesbar: {e}"
        return befund

    # --- Metadaten ---
    meta_text = " ".join(str(v) for v in (dok.metadata or {}).values() if v)
    meta_treffer = anweisungen_finden(meta_text)
    if meta_treffer:
        befund["versteckt"].append("Anweisungstext in den Metadaten")
        befund["anweisungen_versteckt"].extend(meta_treffer)

    for nr, seite in enumerate(dok, start=1):
        seiten_rect = seite.rect
        sichtbarer_text = seite.get_text()
        roher_text = seite.get_text("text", clip=fitz.INFINITE_RECT())

        # Unsichtbarer Textrender-Modus (PDF-Operator "3 Tr").
        # Der Text ist dann im Dokument vorhanden und wird extrahiert, aber
        # nicht dargestellt — fuer den Leser also nicht vorhanden.
        # PyMuPDF gibt den Modus nicht ueber die Span-Daten heraus, deshalb
        # wird der Contentstream direkt gelesen.
        try:
            contentstream = seite.read_contents()
            modi = {int(m) for m in re.findall(rb"(\d)\s+Tr\b", contentstream)}
            if RENDERMODUS_UNSICHTBAR in modi:
                befund["versteckt"].append(
                    f"Seite {nr}: unsichtbarer Textrender-Modus (3 Tr)")
                befund["anweisungen_versteckt"].extend(
                    anweisungen_finden(roher_text))
        except Exception:
            pass

        # Text ausserhalb des Seitenbereichs
        if len(roher_text.strip()) > len(sichtbarer_text.strip()) + 20:
            zusatz = roher_text.replace(sichtbarer_text, "")
            befund["versteckt"].append(f"Seite {nr}: Text ausserhalb des Seitenbereichs")
            befund["anweisungen_versteckt"].extend(anweisungen_finden(zusatz))

        # Spans einzeln pruefen: Farbe, Groesse, Rendermodus
        try:
            roh = seite.get_text("rawdict", clip=fitz.INFINITE_RECT())
        except Exception:
            roh = seite.get_text("rawdict")

        for block in roh.get("blocks", []):
            for zeile in block.get("lines", []):
                for span in zeile.get("spans", []):
                    inhalt = "".join(z.get("c", "") for z in span.get("chars", []))
                    if not inhalt.strip():
                        continue
                    gruende = []

                    if span.get("size", 12) < MIN_SCHRIFTGROESSE:
                        gruende.append(f"Schriftgroesse {span['size']:.1f}pt")

                    if farbe_zu_grau(span.get("color", 0)) > HELL_SCHWELLE:
                        gruende.append("nahezu weisse Schrift")

                    # Der unsichtbare Rendermodus wird nicht hier geprueft,
                    # sondern weiter oben am Contentstream — PyMuPDF gibt ihn
                    # ueber die Span-Daten nicht heraus.

                    span_rect = fitz.Rect(span.get("bbox"))
                    if not seiten_rect.intersects(span_rect):
                        gruende.append("ausserhalb der Seite")

                    if gruende:
                        kurz = inhalt.strip()[:60]
                        befund["versteckt"].append(
                            f"Seite {nr}: {', '.join(gruende)} — \"{kurz}...\"")
                        befund["anweisungen_versteckt"].extend(anweisungen_finden(inhalt))

        # Anweisungen im normal sichtbaren Text
        befund["anweisungen"].extend(anweisungen_finden(sichtbarer_text))

    dok.close()

    # Duplikate raus, Reihenfolge erhalten
    for schluessel in ("anweisungen", "anweisungen_versteckt", "versteckt"):
        gesehen, sauber = set(), []
        for x in befund[schluessel]:
            if x not in gesehen:
                gesehen.add(x)
                sauber.append(x)
        befund[schluessel] = sauber

    return befund


# --------------------------------------------------------------------------
# Word-Dokumente
# --------------------------------------------------------------------------
# Ein Gegner kann genauso gut .docx schicken wie PDF. Dort ist Verstecken
# sogar einfacher, und es gibt einen Weg, den es im PDF gar nicht gibt:
# Word kennt ein eigenes Attribut fuer ausgeblendeten Text (<w:vanish/>).
# Der Text steht dann im Dokument, wird aber nicht angezeigt und nicht
# gedruckt — fuer den Leser existiert er nicht.
#
# Geprueft werden:
#   W1  <w:vanish/>            ausgeblendeter Text
#   W2  <w:color w:val="FFFFFF"> weisse Schrift
#   W3  <w:sz w:val="N">       Schriftgroesse unter 3pt (w:sz zaehlt halbe Punkte)
#   W4  Dokumenteigenschaften  Titel, Thema, Stichwoerter, Kommentar
#   W5  Kommentare, Fuss- und Endnoten

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MIN_HALBPUNKTE = int(MIN_SCHRIFTGROESSE * 2)   # w:sz ist in halben Punkten


def _run_text(run):
    return "".join(t.text or "" for t in run.iter(f"{W_NS}t"))


def docx_pruefen(pfad):
    import xml.etree.ElementTree as ET
    import zipfile

    befund = {
        "datei": os.path.basename(pfad),
        "versteckt": [],
        "anweisungen": [],
        "anweisungen_versteckt": [],
        "fehler": None,
    }

    try:
        mappe = zipfile.ZipFile(pfad)
    except Exception as e:
        befund["fehler"] = f"nicht lesbar: {e}"
        return befund

    namen = mappe.namelist()

    # --- W4: Dokumenteigenschaften ---
    for teil in ("docProps/core.xml", "docProps/app.xml"):
        if teil in namen:
            try:
                wurzel = ET.fromstring(mappe.read(teil))
                text = " ".join(e.text or "" for e in wurzel.iter())
                treffer = anweisungen_finden(text)
                if treffer:
                    befund["versteckt"].append(f"Anweisungstext in {teil}")
                    befund["anweisungen_versteckt"].extend(treffer)
            except Exception:
                pass

    # --- W1/W2/W3: Runs im Haupttext und in Kopf-/Fusszeilen ---
    textteile = [n for n in namen
                 if n.startswith("word/") and n.endswith(".xml")
                 and ("document" in n or "header" in n or "footer" in n)]

    for teil in textteile:
        try:
            wurzel = ET.fromstring(mappe.read(teil))
        except Exception:
            continue
        for run in wurzel.iter(f"{W_NS}r"):
            inhalt = _run_text(run)
            if not inhalt.strip():
                continue
            eigenschaften = run.find(f"{W_NS}rPr")
            if eigenschaften is None:
                continue
            gruende = []

            if eigenschaften.find(f"{W_NS}vanish") is not None:
                gruende.append("ausgeblendeter Text (w:vanish)")

            farbe = eigenschaften.find(f"{W_NS}color")
            if farbe is not None:
                wert = (farbe.get(f"{W_NS}val") or "").upper()
                if wert in ("FFFFFF", "FEFEFE", "FDFDFD"):
                    gruende.append("weisse Schrift")

            groesse = eigenschaften.find(f"{W_NS}sz")
            if groesse is not None:
                try:
                    hp = int(groesse.get(f"{W_NS}val"))
                    if hp < MIN_HALBPUNKTE:
                        gruende.append(f"Schriftgroesse {hp/2:.1f}pt")
                except (TypeError, ValueError):
                    pass

            if gruende:
                kurz = inhalt.strip()[:60]
                befund["versteckt"].append(
                    f"{os.path.basename(teil)}: {', '.join(gruende)} — \"{kurz}...\"")
                befund["anweisungen_versteckt"].extend(anweisungen_finden(inhalt))

    # --- W5: Kommentare, Fuss- und Endnoten ---
    for teil in ("word/comments.xml", "word/footnotes.xml", "word/endnotes.xml"):
        if teil in namen:
            try:
                wurzel = ET.fromstring(mappe.read(teil))
                text = "".join(t.text or "" for t in wurzel.iter(f"{W_NS}t"))
                treffer = anweisungen_finden(text)
                if treffer:
                    befund["versteckt"].append(
                        f"Anweisungstext in {os.path.basename(teil)}")
                    befund["anweisungen_versteckt"].extend(treffer)
            except Exception:
                pass

    # --- sichtbarer Text ---
    if "word/document.xml" in namen:
        try:
            wurzel = ET.fromstring(mappe.read("word/document.xml"))
            sichtbar = "".join(t.text or "" for t in wurzel.iter(f"{W_NS}t"))
            befund["anweisungen"].extend(anweisungen_finden(sichtbar))
        except Exception:
            pass

    mappe.close()

    for schluessel in ("anweisungen", "anweisungen_versteckt", "versteckt"):
        gesehen, sauber = set(), []
        for x in befund[schluessel]:
            if x not in gesehen:
                gesehen.add(x)
                sauber.append(x)
        befund[schluessel] = sauber

    return befund


def datei_pruefen(pfad):
    """Waehlt die Pruefung nach Dateityp."""
    endung = os.path.splitext(pfad)[1].lower()
    if endung == ".pdf":
        return pdf_pruefen(pfad)
    if endung == ".docx":
        return docx_pruefen(pfad)
    return {"datei": os.path.basename(pfad), "versteckt": [], "anweisungen": [],
            "anweisungen_versteckt": [],
            "fehler": f"nicht unterstuetztes Format: {endung}"}


def bewerten(befund):
    if befund["fehler"]:
        return "FEHLER"
    hat_versteckt = bool(befund["versteckt"])
    hat_anweisung = bool(befund["anweisungen"] or befund["anweisungen_versteckt"])
    if hat_versteckt and hat_anweisung:
        return "BLOCKIERT"
    if hat_versteckt or hat_anweisung:
        return "PRUEFEN"
    return "FREI"


def bericht(befund, ausfuehrlich=True):
    urteil = bewerten(befund)
    print(f"\n{urteil:10} {befund['datei']}")
    if befund["fehler"]:
        print(f"           {befund['fehler']}")
        return urteil
    if not ausfuehrlich:
        return urteil
    for v in befund["versteckt"]:
        print(f"           versteckt : {v}")
    for a in befund["anweisungen_versteckt"]:
        print(f"           Anweisung im versteckten Text : {a}")
    for a in befund["anweisungen"]:
        print(f"           Anweisung im sichtbaren Text  : {a}")
    return urteil


def main():
    if len(sys.argv) < 2:
        print("Aufruf: python3 AP18_eingangsfilter.py datei.pdf | ordner/")
        sys.exit(1)

    ziel = sys.argv[1]

    journal = None
    if "--journal" in sys.argv:
        journal_pfad = sys.argv[sys.argv.index("--journal") + 1]
        journal = journal_anlegen(journal_pfad)

    if os.path.isdir(ziel):
        dateien = sorted(os.path.join(ziel, f) for f in os.listdir(ziel)
                         if f.lower().endswith((".pdf", ".docx"))
                         and not f.startswith("~$"))
    else:
        dateien = [ziel]

    ergebnisse = []
    for f in dateien:
        b = datei_pruefen(f)
        urteil = bericht(b)
        ergebnisse.append((os.path.basename(f), urteil))
        if journal:
            journal_eintragen(journal, f, b, urteil)

    print("\n" + "=" * 62)
    print("ZUSAMMENFASSUNG")
    print("=" * 62)
    for name, urteil in ergebnisse:
        print(f"  {urteil:10} {name}")

    blockiert = sum(1 for _, u in ergebnisse if u == "BLOCKIERT")
    pruefen = sum(1 for _, u in ergebnisse if u == "PRUEFEN")
    print(f"\n  blockiert: {blockiert}   zu pruefen: {pruefen}   "
          f"frei: {sum(1 for _,u in ergebnisse if u=='FREI')}")

    if journal:
        anzahl = journal.execute(
            "SELECT COUNT(*) FROM eingangspruefungen").fetchone()[0]
        journal.close()
        print(f"\n  Journal: {anzahl} Eintraege insgesamt in {journal_pfad}")
    print("\nHinweis: Fremde Inhalte bleiben auch nach diesem Filter DATEN,")
    print("niemals Anweisungen. Der Filter ist die zweite Verteidigungslinie,")
    print("nicht die erste.")

    sys.exit(1 if blockiert else 0)


if __name__ == "__main__":
    main()
