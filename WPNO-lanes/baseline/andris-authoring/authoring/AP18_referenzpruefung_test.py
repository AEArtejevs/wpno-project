#!/usr/bin/env python3
"""
AP18_referenzpruefung_test.py — die fuenf Zustaende der Fundstellenpruefung.

=====================================================================
WORAUS DIESER TEST ENTSTANDEN IST
=====================================================================
In einer laufenden Sache wurden fuenf Fundstellen gestrichen, weil sie ueber
die amtlichen Portale nicht auffindbar waren. Zwei davon stammen von 1986 und
1990 und tragen BGHZ- bzw. NJW-Fundstellen — sie sind also amtlich
veroeffentlicht und existieren zweifelsfrei.

Die freie Entscheidungsdatenbank des BGH beginnt am 01.01.2000. Fuer aeltere
Entscheidungen kann sie die Frage gar nicht beantworten; ein "keine Treffer"
heisst dort nicht "erfunden", sondern "ausserhalb der Reichweite".

Die erste Fassung dieses Pruefers haette denselben Fehler gemacht, nur
schneller. Dieser Test haelt fest, dass er ihn nicht mehr macht.

=====================================================================
BEIDE RICHTUNGEN
=====================================================================
Blockieren muss: erfundene Fundstelle im abgedeckten Zeitraum, und ein
Aktenzeichen, das es so gar nicht geben kann.

Durchgehen muss: alles Belegte, alles noch nicht Nachgeschlagene, und —
das ist der neue Teil — alles ausserhalb der Reichweite der Datenbank.

ALLE DATEN SIND SYNTHETISCH bis auf die Aktenzeichen selbst; die sind
oeffentlich und nach § 5 UrhG nicht geschuetzt.

Aufruf:
    python3 AP18_referenzpruefung_test.py
"""

import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

from AP18_referenzpruefung import (pruefen, senat_plausibel,        # noqa: E402
                                    senat_befund, AZ_MUSTER_WEIT,
                                    aktenzeichen_finden,
                                    entscheidungsjahr,
                                    ausserhalb_der_reichweite)

# (Zeile im Dokument, erwarteter Topf, Begruendung fuer den Testbericht)
FAELLE = [
    ("BGH, Urteil vom 30.07.2026 - I ZR 130/25", "belegt",
     "im Referenzbestand nachgewiesen"),
    ("BGH, Urteil vom 09.06.2011 - IX ZR 45/09", "belegt",
     "vor 2000 eingegangen, aber 2011 entschieden und nachgewiesen"),

    ("BGH, Urteil vom 14.02.2013 - VII ZR 100/12", "nicht_vorhanden",
     "erfunden, Zeitraum von der Datenbank abgedeckt"),
    ("Vgl. XY ZR 999/99", "unplausibel",
     "Senatskennung gibt es beim BGH nicht"),

    ("BGH, Urteil vom 03.11.1986 - II ZR 266/85 (BGHZ 99, 41)", "ausserhalb",
     "1986 — Datenbank beginnt 2000"),
    ("BGH, Urteil vom 12.11.1990 - II ZR 218/89 (NJW 1991, 1230)", "ausserhalb",
     "1990 — Datenbank beginnt 2000"),
    ("Siehe ferner II ZR 44/97", "ausserhalb",
     "kein Datum im Text, Eingangsjahr 1997 — Entscheidung vor 2000 zu erwarten"),
    ("Siehe ferner IV ZB 12/99", "ausserhalb",
     "Eingang 1999 — koennte vor oder nach 2000 entschieden sein, nicht entscheidbar"),

    ("BGH, Urteil vom 25.01.2022 - II ZR 50/20", "ungeprueft",
     "existiert vermutlich, aber noch nicht nachgeschlagen"),
]

REFERENZ = {
    "_stand": "2026-08-05",
    "_pruefweg": "https://www.bundesgerichtshof.de/?templateQueryString=%22AKTENZEICHEN%22",
    "belegt": {
        "I ZR 130/25": {"geprueft": "2026-08-04", "weg": "Einzelabfrage"},
        "IX ZR 45/09": {"geprueft": "2026-08-04", "weg": "Einzelabfrage"},
    },
    "nachweislich_nicht_vorhanden": {
        "VII ZR 100/12": {"geprueft": "2026-08-04", "antwort": "Keine Treffer"},
        # Bewusst eingetragen: die Datenbank hat "keine Treffer" gemeldet.
        # Der Pruefer muss diese Angabe VERWERFEN, weil sie aus einer Abfrage
        # stammt, die 1986 gar nicht abdeckt.
        "II ZR 266/85": {"geprueft": "2026-08-04", "antwort": "Keine Treffer"},
        "XY ZR 999/99": {"geprueft": "2026-08-04", "antwort": "Keine Treffer"},
    },
}


def docx_bauen(pfad, zeilen):
    absaetze = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{z}</w:t></w:r></w:p>'
        for z in zeilen)
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>' + absaetze +
           '</w:body></w:document>')
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "word"))
    os.makedirs(os.path.join(tmp, "_rels"))
    with open(os.path.join(tmp, "word", "document.xml"), "w",
              encoding="utf-8") as f:
        f.write(xml)
    with open(os.path.join(tmp, "[Content_Types].xml"), "w",
              encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/'
                '2006/content-types"><Default Extension="rels" ContentType='
                '"application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType='
                '"application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document.main+xml"/></Types>')
    with open(os.path.join(tmp, "_rels", ".rels"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships"><Relationship Id="rId1" Type='
                '"http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>')
    if os.path.exists(pfad):
        os.remove(pfad)
    subprocess.run(["zip", "-Xrq", os.path.abspath(pfad), "."], cwd=tmp,
                   check=True)
    return pfad


def main():
    fehler = 0

    def pruefe(bedingung, gut, schlecht):
        nonlocal fehler
        if bedingung:
            print(f"  ok        {gut}")
        else:
            print(f"  FEHLER    {schlecht}")
            fehler += 1

    print("=" * 78)
    print("REFERENZPRUEFUNG — fuenf Zustaende")
    print("=" * 78)

    tmp = tempfile.mkdtemp()
    ref = os.path.join(tmp, "bgh_referenz.json")
    with open(ref, "w", encoding="utf-8") as f:
        json.dump(REFERENZ, f, ensure_ascii=False)
    dok = docx_bauen(os.path.join(tmp, "probe.docx"), [z for z, _, _ in FAELLE])

    ergebnis, roh, gruende = pruefen(dok, ref)
    wo = {}
    for topf, liste in ergebnis.items():
        for az in liste:
            wo[az] = topf

    print(f"\nTeil 1 — {len(FAELLE)} Fundstellen, je ein Zustand")
    print("-" * 78)
    for zeile, erwartet, begruendung in FAELLE:
        az = next((a for a in wo if a in zeile), None)
        tatsaechlich = wo.get(az)
        pruefe(tatsaechlich == erwartet,
               f"{(az or '?'):18} {erwartet:15} {begruendung}",
               f"{(az or zeile[:24]):18} -> {tatsaechlich or 'nicht erkannt'}, "
               f"erwartet {erwartet}")

    print("\nTeil 2 — Der Referenzbestand darf hier nicht das letzte Wort haben")
    print("-" * 78)
    pruefe(wo.get("II ZR 266/85") == "ausserhalb",
           "\"Keine Treffer\" zu 1986 wird verworfen statt uebernommen",
           "die Datenbankantwort zu 1986 wurde uebernommen — genau der Fehler, "
           "der in der laufenden Sache eine BGHZ-Entscheidung gestrichen haette")
    pruefe(wo.get("XY ZR 999/99") == "unplausibel",
           "erfundenes Aktenzeichen mit altem Jahrgang trotzdem blockiert",
           "erfundenes Aktenzeichen rutscht ueber die Reichweiten-Regel durch")

    print("\nTeil 3 — Senatskennung einzeln")
    print("-" * 78)
    for az, erwartet in (("I ZR 130/25", True), ("VIII ZR 1/23", True),
                         ("VIa ZR 782/23", True), ("3 StR 79/26", True),
                         ("AnwZ (Brfg) 24/24", True), ("EnVR 36/23", True),
                         ("XY ZR 999/99", False), ("ABC ZR 1/20", False)):
        pruefe(senat_plausibel(az) == erwartet,
               f"{az:20} {'moeglich' if erwartet else 'unmoeglich'}",
               f"{az:20} falsch eingeordnet")

    print("\nTeil 4 — Jahresbestimmung")
    print("-" * 78)
    for umfeld, az, jahr, quelle in (
            ("BGH, Urteil vom 03.11.1986 - ", "II ZR 266/85", 1986, "Datum im Text"),
            ("Siehe ferner ", "II ZR 44/97", 1997, "Eingangsjahr im Aktenzeichen"),
            ("Siehe ferner ", "I ZR 130/25", 2025, "Eingangsjahr im Aktenzeichen")):
        j, q = entscheidungsjahr(umfeld, az)
        pruefe(j == jahr and q == quelle,
               f"{az:16} -> {j} ({q})",
               f"{az:16} -> {j} ({q}), erwartet {jahr} ({quelle})")

    print("\nTeil 5 — Reichweite")
    print("-" * 78)
    for jahr, quelle, draussen in ((1986, "Datum im Text", True),
                                   (2011, "Datum im Text", False),
                                   (1997, "Eingangsjahr im Aktenzeichen", True),
                                   (1999, "Eingangsjahr im Aktenzeichen", True),
                                   (2020, "Eingangsjahr im Aktenzeichen", False),
                                   (None, "unbekannt", True)):
        d, _ = ausserhalb_der_reichweite(jahr, quelle)
        pruefe(d == draussen,
               f"{str(jahr):>6} / {quelle:28} "
               f"{'ausserhalb' if draussen else 'abgedeckt'}",
               f"{str(jahr):>6} / {quelle} falsch eingeordnet")

    # ==================================================================
    # Teil 6 — die Korrektur vom 17.08.2026
    # ==================================================================
    # Bis dahin wurde die Senatsregel des BGH auf jedes Gericht angewandt.
    # Drei echte Aktenzeichen wurden dadurch als "unmoeglich" gemeldet, was
    # in main() zu BLOCKIERT und exit 1 fuehrt. Zusaetzlich fand das enge
    # Suchmuster diese Aktenzeichen ueberhaupt nicht, und der Bericht meldete
    # trotzdem "alle Fundstellen belegt".
    print("\nTeil 6 — fremde Gerichte: nicht pruefbar, nicht unmoeglich")
    print("-" * 78)
    for az, erwartet, was in (
            ("VI ZR 313/24",  "moeglich",       "BGH, Zivilsenat"),
            ("XY ZR 999/99",  "unmoeglich",     "erfunden, muss weiter fallen"),
            ("20 F 15/22",    "nicht_pruefbar", "BVerwG — meldete frueher unmoeglich"),
            ("I-25 U 75/25",  "nicht_pruefbar", "OLG Hamm — meldete frueher unmoeglich"),
            ("16 U 139/23",   "nicht_pruefbar", "OLG Koeln — meldete frueher unmoeglich"),
            ("9 CN 2.22",     "nicht_pruefbar", "BVerwG — kam frueher zufaellig durch"),
            ("6 AZR 499/21",  "nicht_pruefbar", "BAG — kam frueher zufaellig durch"),
            ("V R 1/24",      "nicht_pruefbar", "BFH"),
            ("1 BvR 1996/24", "nicht_pruefbar", "BVerfG"),
            ("2 O 82/22",     "nicht_pruefbar", "LG Koeln")):
        ergebnis = senat_befund(az)
        pruefe(ergebnis == erwartet,
               f"{az:16} {erwartet:16} {was}",
               f"{az:16} ergab {ergebnis}, erwartet {erwartet}  ({was})")

    print("\nTeil 7 — was das enge Muster nicht ansieht, wird gezaehlt")
    print("-" * 78)
    text = ("BGH 10.02.2026 - VI ZR 313/24; BAG - 6 AZR 499/21; "
            "BVerwG - 20 F 15/22; BFH - V R 1/24; BVerfG - 1 BvR 1996/24; "
            "OLG Hamm - I-25 U 75/25; LG Koeln - 2 O 82/22; "
            "OLG Koeln - 16 U 139/23.")
    eng = {a for a, _ in aktenzeichen_finden(text)}
    weit = {" ".join(t.split()) for t in AZ_MUSTER_WEIT.findall(text)}
    pruefe(len(eng) == 1, f"enges Muster findet {len(eng)} (BGH)",
           f"enges Muster findet {len(eng)}, erwartet 1")
    pruefe(len(weit) == 8, f"weites Muster findet {len(weit)} von 8",
           f"weites Muster findet {len(weit)}, erwartet 8")
    pruefe(len(weit - eng) == 7,
           f"{len(weit - eng)} Fundstellen liegen ausserhalb der Zustaendigkeit",
           f"Differenz {len(weit - eng)}, erwartet 7")

    prosa = ("Der Beklagte zahlte am 3. Januar 2024 einen Betrag von 1.200,00 "
             "Euro. Nach § 130a Abs. 6 ZPO ist in PDF einzureichen. Die Frist "
             "lief am 27.02.2026 ab. Vgl. Musielak/Borth, FamFG, 8. Aufl. 2026.")
    falsch = AZ_MUSTER_WEIT.findall(prosa)
    pruefe(not falsch, "weites Muster erzeugt keine Fehltreffer in Fliesstext",
           f"weites Muster erzeugt Fehltreffer: {falsch}")

    print("\n" + "=" * 78)
    if fehler == 0:
        print("ERGEBNIS: alle Faelle bestanden.")
        print()
        print("Belegt ist: erfundene Fundstellen im abgedeckten Zeitraum und")
        print("unmoegliche Aktenzeichen werden blockiert; Entscheidungen vor")
        print("2000 werden ausgewiesen statt verworfen.")
        print()
        print("Nicht belegt ist, ob eine echte Entscheidung das traegt, wofuer")
        print("sie zitiert wird. Ein richtiges Aktenzeichen zur falschen These")
        print("geht hier als BELEGT durch. Das bleibt beim Berufstraeger.")
    else:
        print(f"ERGEBNIS: {fehler} Fall/Faelle nicht bestanden.")
    print("=" * 78)
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
