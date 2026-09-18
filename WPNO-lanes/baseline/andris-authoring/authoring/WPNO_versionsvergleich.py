#!/usr/bin/env python3
"""
WPNO_versionsvergleich.py — was ist zwischen zwei Fassungen verschwunden?

=====================================================================
WOFUER
=====================================================================
Am 05.08.2026 stand in der Rueckmeldung zu einem Schriftsatz:

    "Eine Table vergessen in Version 2 die in Version 1 war"

Das ist keine anspruchsvolle Pruefung. Sie ist nur nie gemacht worden, weil
man beim Ueberarbeiten auf das schaut, was dasteht — und nicht auf das, was
nicht mehr dasteht. Der Versandcheck prueft die neue Fassung fuer sich; dass
sie gegenueber der alten etwas verloren hat, sieht er nicht.

=====================================================================
BEIDE RICHTUNGEN, AUS ZWEI GRUENDEN
=====================================================================
  ENTFALLEN  war in der alten Fassung, fehlt in der neuen
             -> Fund. Blockiert, bis jemand es bestaetigt.

  NEU        steht neu in der Fassung
             -> kein Fund, aber ausgewiesen. Auf ausdrueckliche Ansage:
                "die neuen das muss aber vollkommen ueberprueft werden."
                Neue Fundstellen sind genau die, die noch niemand geprueft
                hat.

  GEKUERZT   Tabelle ist noch da, hat aber Zeilen verloren
             -> Fund. Der gefaehrlichere Fall: die Tabelle steht noch da,
                also faellt beim Durchsehen nichts auf.

=====================================================================
WAS VERGLICHEN WIRD
=====================================================================
Tabellen, Ueberschriften, nummerierte Antraege, Anlagenverweise,
Fundstellen (Aktenzeichen und Normen) und Betraege.

Nicht verglichen wird der Fliesstext. Eine Umformulierung ist beim
Ueberarbeiten der Normalfall und wuerde die Liste unlesbar machen. Wer
Formulierungen vergleichen will, nimmt die Wortaenderungsverfolgung von Word.
Dieses Werkzeug beantwortet eine andere Frage: ist etwas WEG.

Aufruf:
    python3 WPNO_versionsvergleich.py alt.docx neu.docx [--bericht datei.md]

Exit 0 = nichts entfallen.  Exit 1 = etwas entfallen oder gekuerzt.
Exit 2 = Datei fehlt oder ist unlesbar.
"""

import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ANLAGE = re.compile(r"\b(?:Anlage[n]?\s+)?((?:AG|AS|AK|K|B)\s?\d{1,3})\b")
AKTENZEICHEN = re.compile(
    r"\b([A-Za-zÄÖÜ0-9]{1,6}(?:\s*\([A-Za-zäöüÄÖÜ]+\))?\s+"
    r"(?:ZR|ZB|ZA|StR|StB|ZS|AR|Brfg|AnwZ|EnVR|EnVZ|KZR|KVR)\s+\d{1,4}/\d{2})\b")
NORM = re.compile(r"(§§?\s*\d+[a-z]?(?:\s*Abs\.\s*\d+)?(?:\s*S\.\s*\d+)?"
                  r"\s*(?:BGB|ZPO|HGB|GmbHG|AktG|InsO|StGB|UrhG|GG|StBerG|BRAO))")
BETRAG = re.compile(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:EUR|€)")
UEBERSCHRIFT = re.compile(
    r"^\s*(?:[A-Z]\.|[IVXLC]+\.|\d+\.(?:\d+\.)*)\s+\S")
ANTRAG = re.compile(r"^\s*(?:Antrag|Hilfsantrag)\s*(\d+)?|^\s*(\d+)\.\s+(?=[A-ZÄÖÜ])")

# Seitenangabe am Ende einer Inhaltsuebersicht-Zeile: "S. 7", "S. [__]", "S. —"
SEITENANGABE = re.compile(r"\s*S\.\s*(?:\d+|\[[^\]]*\]|[_.\-—…]+)\s*$")

# Leerer Platzhalter: eckige Klammern ohne Buchstaben oder Ziffern darin,
# lange Unterstrichfolgen, XXX, TBD.
#
# Bewusst NICHT getroffen wird "[ZU VERIFIZIEREN]" -- das ist ein gewollter
# Marker der Kanzlei, kein vergessenes Feld. Beides in einen Topf zu werfen
# waere derselbe Fehler wie ein Waechter, der bei jedem Datum anschlaegt.
PLATZHALTER = re.compile(r"\[\s*[_.\-\s…]*\s*\]|_{3,}|\bXXX+\b|\bTBD\b")
MARKER = re.compile(r"\[\s*(?:ZU VERIFIZIEREN|PRIMAERQUELLE|PRIMÄRQUELLE|"
                    r"DATENBANKNACHWEIS)[^\]]*\]", re.I)


def ohne_seitenzahl(text):
    """Entfernt die Seitenangabe am Zeilenende.

    Grund -- gemessen an einem echten Schriftsatz: zwischen zwei Fassungen
    wurden die Platzhalter der Inhaltsuebersicht durch echte Seitenzahlen
    ersetzt. Beim Vergleich als reiner Text ergab das 18 Meldungen "entfallen"
    und 18 Meldungen "neu" fuer dieselben 18 Ueberschriften -- bei nur drei
    echten Aenderungen. Ein Werkzeug mit diesem Verhaeltnis wird nach einem
    Lauf abgeschaltet.

    Die Seitenzahl geht nicht verloren: sie wird getrennt ausgewiesen.
    """
    return SEITENANGABE.sub("", text).strip()


def seitenzahl(text):
    m = SEITENANGABE.search(text)
    return m.group(0).strip() if m else ""


# --------------------------------------------------------------------------
def zellentext(el):
    return re.sub(r"\s+", " ", "".join(t.text or "" for t in el.iter(f"{W}t"))).strip()


def lesen(pfad):
    """Gibt (absaetze, tabellen) zurueck. Tabellen erscheinen NICHT zusaetzlich
    in den Absaetzen — sonst zaehlt jeder Tabelleninhalt doppelt."""
    with zipfile.ZipFile(pfad) as z:
        wurzel = ET.fromstring(z.read("word/document.xml"))
    koerper = wurzel.find(f"{W}body")
    if koerper is None:
        return [], []

    absaetze, tabellen = [], []
    for el in koerper:
        if el.tag == f"{W}p":
            t = zellentext(el)
            if t:
                absaetze.append(t)
        elif el.tag == f"{W}tbl":
            zeilen = []
            for tr in el.findall(f"{W}tr"):
                zeilen.append([zellentext(tc) for tc in tr.findall(f"{W}tc")])
            if zeilen:
                tabellen.append(zeilen)
    return absaetze, tabellen


def kennung(zeilen):
    """Erkennungsmerkmal einer Tabelle: die Kopfzeile. Sie aendert sich beim
    Ueberarbeiten am seltensten."""
    kopf = " | ".join(zeilen[0]) if zeilen else ""
    return re.sub(r"\s+", " ", kopf).strip()[:90] or "(ohne Kopfzeile)"


def wortmenge(zeilen):
    return {w.lower() for z in zeilen for c in z for w in re.findall(r"\w+", c)}


def bestandsaufnahme(pfad):
    absaetze, tabellen = lesen(pfad)
    text = "\n".join(absaetze)
    roh_ueberschriften = [a for a in absaetze if UEBERSCHRIFT.match(a)]
    return {
        "tabellen": tabellen,
        # Fuer den Vergleich ohne Seitenangabe, fuer den Bericht mit.
        "ueberschriften": [ohne_seitenzahl(a) for a in roh_ueberschriften],
        "_seiten": {ohne_seitenzahl(a): seitenzahl(a) for a in roh_ueberschriften},
        # WICHTIG: auf dem ROHEN Absatz pruefen, nicht auf dem um die
        # Seitenangabe gekuerzten. Der haeufigste leere Platzhalter IST die
        # Seitenangabe ("S. [__]") -- wer vorher kuerzt, sucht genau das,
        # was er gerade entfernt hat. Vom Test gefunden.
        "platzhalter": sorted({re.sub(r"\s+", " ", a)[:100] for a in absaetze
                               if PLATZHALTER.search(a)}
                              | {re.sub(r"\s+", " ", c)[:100]
                                 for t in tabellen for z in t for c in z
                                 if PLATZHALTER.search(c)}),
        "marker": sorted({m.group(0) for m in MARKER.finditer(text)}),
        "antraege": [ohne_seitenzahl(a) for a in absaetze if ANTRAG.match(a)],
        "anlagen": sorted({re.sub(r"\s+", " ", m.group(1))
                           for m in ANLAGE.finditer(text)}),
        "aktenzeichen": sorted({re.sub(r"\s+", " ", m.group(1))
                                for m in AKTENZEICHEN.finditer(text)}),
        "normen": sorted({re.sub(r"\s+", " ", m.group(1))
                          for m in NORM.finditer(text)}),
        "betraege": sorted({re.sub(r"\s+", " ", m.group(0))
                            for m in BETRAG.finditer(text)}),
    }


# --------------------------------------------------------------------------
def tabellen_zuordnen(alt, neu):
    """Ordnet Tabellen ueber Wortueberdeckung einander zu.

    Ein reiner Vergleich der Kopfzeile wuerde eine leicht umformulierte
    Ueberschrift als "entfallen und neu" melden — zwei Funde, wo keiner ist.
    Umgekehrt wuerde ein zu grosszuegiges Verfahren eine wirklich entfernte
    Tabelle einer beliebigen anderen zuordnen. Deshalb Ueberdeckung mit
    Schwelle, und im Zweifel gilt die Tabelle als entfallen.
    """
    paare, offen_neu = [], list(range(len(neu)))
    for i, a in enumerate(alt):
        wa = wortmenge(a)
        bester, bestwert = None, 0.0
        for j in offen_neu:
            wn = wortmenge(neu[j])
            if not wa and not wn:
                wert = 1.0
            elif not wa or not wn:
                wert = 0.0
            else:
                wert = len(wa & wn) / len(wa | wn)
            if wert > bestwert:
                bester, bestwert = j, wert
        if bester is not None and bestwert >= 0.35:
            paare.append((i, bester, bestwert))
            offen_neu.remove(bester)
        else:
            paare.append((i, None, 0.0))
    return paare, offen_neu


def vergleichen(pfad_alt, pfad_neu):
    alt = bestandsaufnahme(pfad_alt)
    neu = bestandsaufnahme(pfad_neu)

    befund = {"entfallen": {}, "neu": {}, "gekuerzt": [],
              "seiten_geaendert": [], "platzhalter_neu": [],
              "platzhalter_weg": [], "marker": []}

    for feld in ("ueberschriften", "antraege", "anlagen", "aktenzeichen",
                 "normen", "betraege"):
        a, n = alt[feld], neu[feld]
        befund["entfallen"][feld] = [x for x in a if x not in n]
        befund["neu"][feld] = [x for x in n if x not in a]

    # Seitenzahlen getrennt: eine geaenderte Seitenangabe ist kein Verlust,
    # aber sie soll nicht unsichtbar sein.
    for u, alt_seite in alt["_seiten"].items():
        neu_seite = neu["_seiten"].get(u)
        if neu_seite is not None and neu_seite != alt_seite:
            befund["seiten_geaendert"].append(
                (u[:70], alt_seite or "—", neu_seite or "—"))

    # Leere Platzhalter in der NEUEN Fassung sind ein Fund: die eigene
    # Schriftsatz-Pipeline fuehrt "leere Platzhalter" und "Inhaltsuebersicht
    # ohne Seitenzahlen" als Sperrgrund.
    befund["platzhalter_neu"] = list(neu["platzhalter"])
    befund["platzhalter_weg"] = [p for p in alt["platzhalter"]
                                 if p not in neu["platzhalter"]]
    befund["marker"] = list(neu["marker"])

    paare, neue_tabellen = tabellen_zuordnen(alt["tabellen"], neu["tabellen"])
    befund["entfallen"]["tabellen"] = []
    befund["neu"]["tabellen"] = [kennung(neu["tabellen"][j]) for j in neue_tabellen]
    for i, j, wert in paare:
        if j is None:
            befund["entfallen"]["tabellen"].append(kennung(alt["tabellen"][i]))
        else:
            za, zn = len(alt["tabellen"][i]), len(neu["tabellen"][j])
            if zn < za:
                befund["gekuerzt"].append(
                    (kennung(alt["tabellen"][i]), za, zn))

    return befund, alt, neu


# --------------------------------------------------------------------------
TITEL = {
    "tabellen": "Tabellen",
    "ueberschriften": "Ueberschriften",
    "antraege": "Antraege",
    "anlagen": "Anlagenverweise",
    "aktenzeichen": "Aktenzeichen",
    "normen": "Normen",
    "betraege": "Betraege",
}
REIHENFOLGE = ["tabellen", "antraege", "ueberschriften", "anlagen",
               "aktenzeichen", "normen", "betraege"]


def bericht_schreiben(pfad, befund, pfad_alt, pfad_neu):
    z = ["# Versionsvergleich", "",
         f"**Alte Fassung:** `{os.path.basename(pfad_alt)}`  ",
         f"**Neue Fassung:** `{os.path.basename(pfad_neu)}`", ""]

    anzahl = sum(len(v) for v in befund["entfallen"].values()) + len(befund["gekuerzt"])
    z += [f"**Entfallen oder gekuerzt: {anzahl}**  ",
          f"**Leere Platzhalter in der neuen Fassung: "
          f"{len(befund['platzhalter_neu'])}**", ""]

    if befund["platzhalter_neu"]:
        z += ["## Leere Platzhalter", "",
              "Die Schriftsatz-Pipeline fuehrt leere Platzhalter und eine "
              "Inhaltsuebersicht ohne Seitenzahlen als Sperrgrund.", ""]
        z += [f"- `{p}`" for p in befund["platzhalter_neu"][:30]]
        z.append("")

    if anzahl:
        z += ["## Entfallen — war in der alten Fassung, fehlt jetzt", "",
              "| Art | Was |", "|---|---|"]
        for feld in REIHENFOLGE:
            for x in befund["entfallen"].get(feld, []):
                z.append(f"| {TITEL[feld]} | {x} |")
        for k, va, vn in befund["gekuerzt"]:
            z.append(f"| Tabelle gekuerzt | {k} — {va} auf {vn} Zeilen |")
        z.append("")

    neues = sum(len(v) for v in befund["neu"].values())
    if neues:
        z += ["## Neu — bitte vollstaendig pruefen", "",
              "| Art | Was |", "|---|---|"]
        for feld in REIHENFOLGE:
            for x in befund["neu"].get(feld, []):
                z.append(f"| {TITEL[feld]} | {x} |")
        z.append("")
        z += ["Neue Fundstellen sind die, die noch niemand nachgeschlagen hat. "
              "Vor dem Versand ueber die Referenzpruefung laufen lassen.", ""]

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(z))


def main():
    if len(sys.argv) < 3:
        print("Aufruf: python3 WPNO_versionsvergleich.py alt.docx neu.docx "
              "[--bericht datei.md]")
        sys.exit(2)

    pfad_alt, pfad_neu = sys.argv[1], sys.argv[2]
    for p in (pfad_alt, pfad_neu):
        if not os.path.isfile(p):
            print(f"FEHLER: Datei nicht gefunden: {p}")
            sys.exit(2)

    try:
        befund, alt, neu = vergleichen(pfad_alt, pfad_neu)
    except (zipfile.BadZipFile, ET.ParseError) as e:
        print(f"FEHLER: Datei nicht lesbar ({e})")
        sys.exit(2)

    print("=" * 72)
    print("VERSIONSVERGLEICH — was ist verschwunden?")
    print("=" * 72)
    print(f"alt : {os.path.basename(pfad_alt)}   "
          f"({len(alt['tabellen'])} Tabellen)")
    print(f"neu : {os.path.basename(pfad_neu)}   "
          f"({len(neu['tabellen'])} Tabellen)\n")

    entfallen = sum(len(v) for v in befund["entfallen"].values())
    gekuerzt = len(befund["gekuerzt"])

    if entfallen or gekuerzt:
        print("ENTFALLEN — war in der alten Fassung, fehlt in der neuen")
        for feld in REIHENFOLGE:
            for x in befund["entfallen"].get(feld, []):
                print(f"   {TITEL[feld]:16} {x}")
        for k, va, vn in befund["gekuerzt"]:
            print(f"   {'Tabelle gekuerzt':16} {k}")
            print(f"   {'':16} {va} Zeilen -> {vn} Zeilen")
        print()

    if befund["platzhalter_neu"]:
        print("LEERE PLATZHALTER in der neuen Fassung")
        print("   Die Schriftsatz-Pipeline fuehrt das als Sperrgrund.")
        for p in befund["platzhalter_neu"][:15]:
            print(f"   {p}")
        if len(befund["platzhalter_neu"]) > 15:
            print(f"   ... und {len(befund['platzhalter_neu']) - 15} weitere")
        print()

    neues = sum(len(v) for v in befund["neu"].values())
    if neues:
        print("NEU — bitte vollstaendig pruefen")
        for feld in REIHENFOLGE:
            for x in befund["neu"].get(feld, []):
                print(f"   {TITEL[feld]:16} {x}")
        print()

    if befund["marker"]:
        print("MARKER — vor dem Versand aufloesen")
        for m in befund["marker"]:
            print(f"   {m}")
        print()

    if befund["seiten_geaendert"]:
        n = len(befund["seiten_geaendert"])
        gefuellt = sum(1 for _, a, _b in befund["seiten_geaendert"]
                       if PLATZHALTER.search(a) or a == "—")
        print(f"SEITENZAHLEN — {n} geaendert"
              + (f", davon {gefuellt} erstmals gefuellt" if gefuellt else ""))
        print("   Kein Verlust. Steht hier nur, damit es nicht unsichtbar ist.")
        print()

    if "--bericht" in sys.argv:
        pfad = sys.argv[sys.argv.index("--bericht") + 1]
        bericht_schreiben(pfad, befund, pfad_alt, pfad_neu)
        print(f"Bericht: {pfad}\n")

    platz = len(befund["platzhalter_neu"])
    print("=" * 72)
    if entfallen or gekuerzt:
        print(f"ERGEBNIS: {entfallen + gekuerzt} Punkt(e) entfallen oder gekuerzt.")
        print("Jeder davon braucht eine Entscheidung: Absicht oder Versehen.")
    if platz:
        print(f"ERGEBNIS: {platz} leere(r) Platzhalter in der neuen Fassung.")
        print("Nach der eigenen Pipeline ist die Fassung damit nicht versandfaehig.")
    if entfallen or gekuerzt or platz:
        print("=" * 72)
        sys.exit(1)
    if neues:
        print(f"ERGEBNIS: nichts entfallen. {neues} neue Punkte stehen oben.")
    else:
        print("ERGEBNIS: keine Unterschiede in den geprueften Merkmalen.")
    print("=" * 72)
    sys.exit(0)


if __name__ == "__main__":
    main()
