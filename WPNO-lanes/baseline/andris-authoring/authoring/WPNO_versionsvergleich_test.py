#!/usr/bin/env python3
"""
WPNO_versionsvergleich_test.py

Baut zwei Fassungen eines synthetischen Schriftsatzes. Die zweite hat genau
die Veraenderungen, die am 05.08.2026 gemeldet wurden oder die daneben
liegen: eine Tabelle fehlt ganz, eine hat Zeilen verloren, ein Antrag ist
weg, eine Anlage wird nicht mehr erwaehnt, eine Fundstelle ist neu, und der
Fliesstext ist umformuliert.

Die letzte Aenderung ist die wichtigste im Test: Umformulieren ist beim
Ueberarbeiten der Normalfall und darf KEINEN Fund erzeugen. Ein Werkzeug, das
bei jeder umgestellten Formulierung anschlaegt, wird beim zweiten Schriftsatz
abgeschaltet.

ALLE DATEN SIND SYNTHETISCH.
"""

import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

from WPNO_versionsvergleich import vergleichen                  # noqa: E402

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def absatz(t):
    return f'<w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'


def tabelle(zeilen):
    tr = ""
    for z in zeilen:
        tc = "".join(f'<w:tc>{absatz(c)}</w:tc>' for c in z)
        tr += f"<w:tr>{tc}</w:tr>"
    return f"<w:tbl>{tr}</w:tbl>"


def docx_bauen(pfad, teile):
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document {W}><w:body>' + "".join(teile) + '</w:body></w:document>')
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


RELATIONSMATRIX = [
    ["Pruefungspunkt", "Beleglage", "Ergebnis"],
    ["Zulaessigkeit", "Verfuegung vom 24.07.2026", "entscheidungsreif"],
    ["Beschlussfassung", "Zugestaendnis 27.07.2026", "entscheidungsreif"],
    ["Verfuegungsgrund", "Zeitablauf 01.04. bis 23.07.2026", "entscheidungsreif"],
]

FUNDSTELLEN = [
    ["Fundstelle", "Verwendung", "Status"],
    ["II ZR 50/20", "Begriff der actio pro socio", "bestaetigt"],
    ["II ZR 85/23", "Gegenentscheidung", "bestaetigt"],
]

KOSTEN = [
    ["Posten", "Betrag"],
    ["Gegenstandswert", "25.000,00 EUR"],
]

# Nur in der neuen Fassung. Sie steht hier, damit die Zuordnungsschwelle
# ueberhaupt geprueft wird: ohne eine neue Tabelle gibt es nichts, dem die
# entfallene Kostentabelle faelschlich zugeordnet werden koennte, und eine zu
# grosszuegige Schwelle bliebe unbemerkt. Genau das ist beim ersten Lauf
# passiert -- die Negativprobe mit Schwelle 0 blieb gruen.
OFFENE_PUNKTE = [
    ["Nr.", "Punkt", "Einstufung"],
    ["1", "Mandanteninstruktion", "Sperrvotum"],
    ["2", "Briefbogen und Signatur", "Formalie"],
    # "Betrag" steht hier absichtlich: es ist das einzige Wort, das auch in
    # der entfallenen Kostentabelle vorkommt. Die Ueberdeckung liegt damit bei
    # rund 5 % -- deutlich unter der Schwelle. Ohne diese eine gemeinsame
    # Vokabel haetten die beiden Tabellen gar keine Beruehrung, die Schwelle
    # waere unerheblich, und eine zu grosszuegige Einstellung bliebe
    # unbemerkt. Beim ersten Anlauf war genau das der Fall: die Negativprobe
    # mit Schwelle 0 blieb zweimal gruen.
    ["3", "Betrag der Sicherheitsleistung", "Ermessen"],
]


# Aus dem echten Lauf am 05.08.2026: in der aelteren Fassung stand in der
# Inhaltsuebersicht ueberall "S. [__]", in der neueren die echten Seitenzahlen.
# Der Vergleich als reiner Text meldete daraufhin 18 Ueberschriften als
# entfallen UND 18 als neu -- bei drei echten Aenderungen. Diese acht Zeilen
# halten den Fall fest.
INHALT_ALT = [
    "A. Antraege S. [__]",
    "B. Einleitung — Vorstrukturierung — Perspektive S. [__]",
    "C. Sach- und Streitstand S. [__]",
    "D. Rechtliche Wuerdigung S. [__]",
]
INHALT_NEU = [
    "A. Antraege S. 2",
    "B. Einleitung — Vorstrukturierung — Perspektive S. 2",
    "C. Sach- und Streitstand S. 4",
    "D. Rechtliche Wuerdigung S. 9",
]


def alte_fassung():
    return [absatz(z) for z in INHALT_ALT] + [
        absatz("A. Zulaessigkeit"),
        absatz("Die Antragstellerseite traegt vor, der Beitritt sei wirksam."),
        absatz("1. Es wird beantragt, den Antrag zurueckzuweisen."),
        absatz("2. Hilfsweise wird beantragt, die Kosten aufzuerlegen."),
        absatz("Vgl. Anlage AG 3 sowie Anlage AS 15."),
        absatz("B. Begruendetheit"),
        absatz("Vgl. BGH, Urteil vom 25.01.2022 - II ZR 50/20; § 715b BGB."),
        tabelle(RELATIONSMATRIX),
        absatz("C. Fundstellen"),
        tabelle(FUNDSTELLEN),
        absatz("D. Kosten"),
        tabelle(KOSTEN),
        absatz("Der Streitwert betraegt 25.000,00 EUR."),
    ]


def neue_fassung():
    gekuerzt = RELATIONSMATRIX[:-1]          # eine Zeile verloren
    return [absatz(z) for z in INHALT_NEU] + [
        absatz("A. Zulaessigkeit"),
        # umformuliert -- darf keinen Fund erzeugen
        absatz("Nach Auffassung der Antragstellerseite ist der Beitritt "
               "wirksam erfolgt."),
        absatz("1. Es wird beantragt, den Antrag zurueckzuweisen."),
        # Antrag 2 entfallen
        absatz("Vgl. Anlage AG 3."),          # AS 15 nicht mehr erwaehnt
        absatz("B. Begruendetheit"),
        absatz("Vgl. BGH, Urteil vom 25.01.2022 - II ZR 50/20; "
               "ferner BGH, Urteil vom 05.11.2024 - II ZR 85/23; § 715b BGB; "
               "§ 242 BGB."),
        tabelle(gekuerzt),
        absatz("C. Fundstellen"),
        tabelle(FUNDSTELLEN),
        # D. Kosten samt Tabelle vollstaendig entfallen
        absatz("E. Offene Punkte"),
        tabelle(OFFENE_PUNKTE),          # neu hinzugekommen
        absatz("Der Streitwert betraegt 25.000,00 EUR."),
    ]


def main():
    fehler = 0

    def pruefe(bedingung, gut, schlecht):
        nonlocal fehler
        if bedingung:
            print(f"  ok        {gut}")
        else:
            print(f"  FEHLER    {schlecht}")
            fehler += 1

    print("=" * 76)
    print("VERSIONSVERGLEICH — Testfall")
    print("=" * 76)

    tmp = tempfile.mkdtemp()
    alt = docx_bauen(os.path.join(tmp, "v1.docx"), alte_fassung())
    neu = docx_bauen(os.path.join(tmp, "v2.docx"), neue_fassung())
    befund, a, n = vergleichen(alt, neu)

    ent = befund["entfallen"]

    print("\nTeil 1 — was entfallen ist, wird gefunden")
    print("-" * 76)
    pruefe(any("Posten" in t for t in ent["tabellen"]),
           f"ganze Tabelle entfallen erkannt: {ent['tabellen']}",
           f"entfallene Tabelle NICHT erkannt — genau der gemeldete Fehler. "
           f"gefunden: {ent['tabellen']}")
    pruefe(any("D. Kosten" in u for u in ent["ueberschriften"]),
           "entfallene Ueberschrift erkannt: D. Kosten",
           f"entfallene Ueberschrift nicht erkannt: {ent['ueberschriften']}")
    pruefe(any(a.startswith("2.") for a in ent["antraege"]),
           "entfallener Antrag 2 erkannt",
           f"entfallener Antrag nicht erkannt: {ent['antraege']}")
    pruefe("AS 15" in ent["anlagen"],
           "nicht mehr erwaehnte Anlage AS 15 erkannt",
           f"Anlage nicht erkannt: {ent['anlagen']}")

    print("\nTeil 2 — die gekuerzte Tabelle, der gefaehrlichere Fall")
    print("-" * 76)
    pruefe(len(befund["gekuerzt"]) == 1 and befund["gekuerzt"][0][1] == 4
           and befund["gekuerzt"][0][2] == 3,
           f"Tabelle steht noch da, hat aber eine Zeile verloren: "
           f"{befund['gekuerzt']}",
           f"gekuerzte Tabelle nicht erkannt: {befund['gekuerzt']}")

    print("\nTeil 3 — Neues wird ausgewiesen, nicht beanstandet")
    print("-" * 76)
    pruefe("II ZR 85/23" in befund["neu"]["aktenzeichen"],
           "neue Fundstelle ausgewiesen — muss noch geprueft werden",
           f"neue Fundstelle nicht ausgewiesen: {befund['neu']['aktenzeichen']}")
    pruefe(any("242" in x for x in befund["neu"]["normen"]),
           "neue Norm ausgewiesen",
           f"neue Norm nicht ausgewiesen: {befund['neu']['normen']}")

    print("\nTeil 4 — Umformulierung erzeugt KEINEN Fund")
    print("-" * 76)
    pruefe(not ent["betraege"],
           "unveraenderter Betrag bleibt unbeanstandet",
           f"Fehlalarm bei Betraegen: {ent['betraege']}")
    pruefe(not any("Auffassung" in x or "traegt vor" in x
                   for x in ent["ueberschriften"] + ent["antraege"]),
           "umformulierter Fliesstext erzeugt keinen Fund",
           "Umformulierung als Verlust gemeldet — das Werkzeug waere unbrauchbar")
    pruefe("II ZR 50/20" not in ent["aktenzeichen"],
           "unveraenderte Fundstelle bleibt unbeanstandet",
           "unveraenderte Fundstelle als entfallen gemeldet")
    pruefe(not any("Fundstelle" in t for t in ent["tabellen"]),
           "unveraenderte Tabelle wird wiedererkannt",
           f"unveraenderte Tabelle als entfallen gemeldet: {ent['tabellen']}")

    print("\nTeil 5 — Seitenzahlen statt Platzhalter sind KEIN Verlust")
    print("-" * 76)
    rausch = [u for u in ent["ueberschriften"]
              if any(u.startswith(i.split(" S.")[0][:12]) for i in INHALT_ALT)]
    pruefe(not rausch,
           f"{len(INHALT_ALT)} Inhaltszeilen mit gefuellten Seitenzahlen "
           f"erzeugen keinen Fund",
           f"Seitenzahl-Aenderung als Verlust gemeldet: {rausch}")
    pruefe(len(befund["seiten_geaendert"]) == len(INHALT_ALT),
           f"stattdessen getrennt ausgewiesen: "
           f"{len(befund['seiten_geaendert'])} Seitenangaben geaendert",
           f"Seitenaenderungen nicht ausgewiesen: {befund['seiten_geaendert']}")

    print("\nTeil 6 — leere Platzhalter werden als Sperrgrund gemeldet")
    print("-" * 76)
    b_rueck, _, _ = vergleichen(neu, alt)     # umgekehrte Richtung
    pruefe(len(b_rueck["platzhalter_neu"]) == len(INHALT_ALT),
           f"{len(b_rueck['platzhalter_neu'])} Platzhalter in der Fassung "
           f"mit S. [__] erkannt",
           f"Platzhalter nicht erkannt: {b_rueck['platzhalter_neu']}")
    pruefe(not befund["platzhalter_neu"],
           "in der Fassung mit echten Seitenzahlen kein Platzhalter",
           f"Fehlalarm: {befund['platzhalter_neu']}")

    print("\nTeil 7 — der Marker [ZU VERIFIZIEREN] ist kein Platzhalter")
    print("-" * 76)
    m1 = docx_bauen(os.path.join(tempfile.mkdtemp(), "m1.docx"),
                    [absatz("Vgl. BGH II ZR 50/20 [ZU VERIFIZIEREN]")])
    b_m, _, _ = vergleichen(m1, m1)
    pruefe(not b_m["platzhalter_neu"],
           "wird nicht als leerer Platzhalter gewertet",
           f"Marker faelschlich als Platzhalter: {b_m['platzhalter_neu']}")
    pruefe(b_m["marker"],
           f"wird getrennt ausgewiesen: {b_m['marker']}",
           "Marker gar nicht ausgewiesen — er muss vor dem Versand auffallen")

    print("\nTeil 8 — zwei gleiche Fassungen ergeben nichts")
    print("-" * 76)
    b2, _, _ = vergleichen(alt, alt)
    leer = (sum(len(v) for v in b2["entfallen"].values()) == 0
            and sum(len(v) for v in b2["neu"].values()) == 0
            and not b2["gekuerzt"])
    pruefe(leer, "identische Fassungen: kein Fund",
           f"Fund bei identischen Fassungen: {b2}")

    print("\n" + "=" * 76)
    if fehler == 0:
        print("ERGEBNIS: alle Faelle bestanden.")
        print()
        print("Belegt ist: entfallene Tabellen, Ueberschriften, Antraege und")
        print("Anlagenverweise werden gefunden, ebenso eine Tabelle, die noch")
        print("dasteht und Zeilen verloren hat — und eine Umformulierung")
        print("erzeugt keinen Fund.")
        print()
        print("Nicht geprueft wird der Fliesstext selbst. Ob ein umformulierter")
        print("Satz noch dasselbe sagt, entscheidet der Berufstraeger.")
    else:
        print(f"ERGEBNIS: {fehler} Fall/Faelle nicht bestanden.")
    print("=" * 76)
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
