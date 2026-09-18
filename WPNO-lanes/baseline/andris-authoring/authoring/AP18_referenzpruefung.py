#!/usr/bin/env python3
"""
AP18_referenzpruefung.py — Pruefung zitierter Aktenzeichen.

Testkatalog Kapitel 29, P4: "Jede juristische Fundstelle gegen den Volltext
belegt". Ersetzt die bisherige Behelfsloesung aus AP-17, die nur gegen eine
selbst gepflegte Liste verglich.

=====================================================================
FUENF ZUSTAENDE — und warum es nicht zwei sein duerfen
=====================================================================
Die naheliegende Loesung waere: steht das Aktenzeichen in unserer Liste, ist
es gut, sonst schlecht. Das waere gefaehrlich. Unser Referenzbestand ist
unvollstaendig, und eine gueltige Fundstelle zu blockieren, nur weil wir sie
noch nicht geprueft haben, waere schlimmer als gar nicht zu pruefen — der
Anwender wuerde die Warnungen bald ignorieren.

Deshalb:

  BELEGT        in der Entscheidungsdatenbank nachgewiesen
                -> geht durch

  UNMOEGLICH    die Senatskennung gibt es beim BGH nicht
                -> BLOCKIERT. Haengt an keiner Datenbank und gilt fuer
                   jeden Jahrgang.

  NICHT VORHANDEN   in der Datenbank nachweislich nicht enthalten, und die
                Datenbank deckt diesen Zeitraum ab
                -> BLOCKIERT. Das ist der Fall einer erfundenen Fundstelle.

  AUSSERHALB    die Entscheidung liegt vor dem Beginn der Datenbank (2000)
                -> geht durch, wird ausgewiesen. Hier ist ein "keine Treffer"
                   ohne Aussagewert; nachzuweisen ueber Wolters Kluwer /
                   Libra oder die amtliche Sammlung.

  UNGEPRUEFT    noch nicht nachgeschlagen
                -> geht durch, wird aber ausgewiesen. Der Berufstraeger
                   entscheidet, ob er es vor dem Versand klaeren will.

=====================================================================
WAS DIESE PRUEFUNG NICHT LEISTET
=====================================================================
Sie prueft, ob es die Entscheidung GIBT — nicht, ob sie das traegt, wofuer
sie zitiert wird. Eine echte Entscheidung, die zur falschen These angefuehrt
wird, geht hier als BELEGT durch.

Das ist kein hypothetischer Fall. In einer laufenden Sache stand in der
internen Qualitaetskontrolle bei einer Fundstelle die Anmerkung, der zitierte
Senat sei fuer Bankrecht zustaendig und nicht fuer die Organvertretung einer
Personengesellschaft. Die Entscheidung existiert; sie passt nur nicht. Das
faellt einem Menschen auf, der weiss, welcher Senat wofuer zustaendig ist,
und keiner Datenbankabfrage.

Ebenso ungeprueft bleibt, ob die zitierte PASSAGE im Volltext so steht.
Dafuer ist der Volltextabgleich ueber Wolters Kluwer / Libra vorgesehen.

=====================================================================
WARUM KEIN LIVE-ABRUF
=====================================================================
Technisch waere eine Abfrage bei jedem Lauf moeglich. Fuer ein Gutachten ist
ein oertlicher Referenzbestand aber besser:

  - Reproduzierbar. Dieselbe Pruefung ergibt in sechs Monaten dasselbe
    Ergebnis. Eine Live-Abfrage nicht.
  - Der Referenzbestand ist selbst das Beweismittel: er haelt fest, wann und
    wie geprueft wurde.
  - Keine Abhaengigkeit von Erreichbarkeit oder geaenderten Suchparametern
    der Gerichtsseite.

Der Pruefweg (die URL) steht in der Referenzdatei. Neue Aktenzeichen werden
damit nachgeschlagen und eingetragen.

Aufruf:
    python3 AP18_referenzpruefung.py schriftsatz.docx
    python3 AP18_referenzpruefung.py schriftsatz.docx --referenz bgh_referenz.json
"""

import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Aktenzeichen des BGH, z. B.:  I ZR 130/25 · 3 StR 79/26 · AnwZ (Brfg) 24/24
# Aufbau: Senatskennung, Registerzeichen, laufende Nummer / Jahr
#
# WICHTIG — die Senatskennung ist bewusst WEIT gefasst.
# Ein erster Entwurf liess nur gueltige Kennungen zu (roemische Ziffern,
# Zahlen, bekannte Kuerzel). Folge: ein erfundenes Aktenzeichen mit
# unsinniger Kennung wurde gar nicht erst als Fundstelle erkannt und lief
# unbemerkt durch — genau der Fall, den diese Pruefung verhindern soll.
# Lieber zu viel erkennen und als "ungeprueft" ausweisen, als etwas
# uebersehen. Ueber Gueltigkeit entscheidet der Referenzbestand, nicht das
# Muster.
AZ_MUSTER = re.compile(
    r"\b("
    r"[A-Za-zÄÖÜ0-9]{1,6}"                      # Senatskennung, weit gefasst
    r"(?:\s*\([A-Za-zäöüÄÖÜ]+\))?"              # optional: (Brfg)
    r"\s+"
    r"(?:ZR|ZB|ZA|StR|StB|ZS|AR|Brfg|AnwZ|EnVR|EnVZ|KZR|KVR)"   # Registerzeichen
    r"\s+"
    r"\d{1,4}/\d{2}"                            # laufende Nummer / Jahr
    r")\b"
)

# ==========================================================================
# ZWEITES MUSTER — was diese Pruefung NICHT ansieht
# ==========================================================================
# Gemessen am 17.08.2026: in einem Probetext mit neun Aktenzeichen fand das
# Muster oben drei. Die anderen sechs -- 6 AZR 499/21, 20 F 15/22, V R 1/24,
# 1 BvR 1996/24, I-25 U 75/25, 2 O 82/22, 16 U 139/23 -- wurden nicht
# uebersehen, sondern gar nicht erst gesucht: die Liste der Registerzeichen
# oben kennt nur den BGH.
#
# Das ist als Entwurf vertretbar. Diese Pruefung ist eine BGH-Pruefung, sie
# arbeitet gegen bgh_referenz.json und gegen die Suchmaske des BGH.
#
# Nicht vertretbar war die Meldung am Ende: "DURCHGELASSEN — alle
# Fundstellen belegt." Wer das liest, glaubt, alle Zitate seien geprueft.
# Geprueft war ein Drittel. Das ist dieselbe Bauart wie ein "doctor", der
# "keine Probleme" meldet und dabei nur die Installation ansieht.
#
# Deshalb dieses zweite, weite Muster. Es pruef NICHTS. Es zaehlt nur, wie
# viele Aktenzeichen im Text stehen, damit die Differenz sichtbar wird.
AZ_MUSTER_WEIT = re.compile(
    r"\b("
    r"(?:I-)?[A-Za-zÄÖÜ0-9]{1,6}"               # Kennung, ggf. mit "I-" (OLG NRW)
    r"(?:\s*\([A-Za-zäöüÄÖÜ]+\))?"
    r"\s+"
    r"[A-ZÄÖÜ][A-Za-zÄÖÜäöü]{0,4}"              # Registerzeichen, weit gefasst
    r"\s+"
    r"\d{1,4}[/.]\d{2}"                         # 499/21 und auch 2.22 (BVerwG)
    r")\b"
)


# ==========================================================================
# REICHWEITE DER ENTSCHEIDUNGSDATENBANK
# ==========================================================================
# Die freie Entscheidungsdatenbank des BGH beginnt am 01.01.2000. Aeltere
# Entscheidungen sind dort nicht enthalten und muessen gesondert angefordert
# werden.
#
# Daraus folgt etwas, das der erste Entwurf falsch gemacht hat: fuer eine
# Entscheidung von 1986 kann die Datenbank die Frage "gibt es sie?" gar nicht
# beantworten. Ein "keine Treffer" heisst dort NICHT "erfunden", sondern
# "ausserhalb der Reichweite".
#
# Der Unterschied ist nicht theoretisch. In einer laufenden Sache wurden fuenf
# Fundstellen als nicht auffindbar gestrichen; zwei davon stammten von 1986
# und 1990 und tragen BGHZ- bzw. NJW-Fundstellen -- sie sind also amtlich
# veroeffentlicht. Haette dieses Skript dort geurteilt, haette es dasselbe
# gesagt, nur schneller und mit dem Anschein der Pruefung.
#
# Deshalb: ausserhalb der Reichweite gibt es kein NICHT VORHANDEN. Nur
# UNGEPRUEFT, mit dem Hinweis, wo stattdessen zu suchen ist.
PORTAL_AB = 2000

# "BGH, Urteil vom 03.11.1986 - II ZR 266/85" -- das Datum steht vor dem
# Aktenzeichen und ist die zuverlaessigere Angabe.
DATUM_MUSTER = re.compile(r"(\d{1,2})\.(\d{1,2})\.((?:19|20)\d{2})")


def entscheidungsjahr(umfeld, az):
    """Gibt (jahr, quelle) zurueck.

    Zuerst wird ein Datum unmittelbar vor dem Aktenzeichen gesucht. Fehlt es,
    dient das zweistellige Jahr im Aktenzeichen als Naeherung -- das ist das
    EINGANGSjahr, nicht das Entscheidungsjahr. Eine 1998 eingegangene Sache
    kann 2001 entschieden worden sein. Deshalb wird diese Naeherung bewusst
    vorsichtig ausgelegt.
    """
    treffer = list(DATUM_MUSTER.finditer(umfeld))
    if treffer:
        return int(treffer[-1].group(3)), "Datum im Text"
    m = re.search(r"/(\d{2})\s*$", az)
    if not m:
        return None, "unbekannt"
    jj = int(m.group(1))
    return (1900 + jj if jj >= 50 else 2000 + jj), "Eingangsjahr im Aktenzeichen"


def ausserhalb_der_reichweite(jahr, quelle):
    """Kann die Datenbank zu dieser Fundstelle ueberhaupt Auskunft geben?"""
    if jahr is None:
        return True, "Jahr nicht bestimmbar"
    if quelle == "Datum im Text":
        if jahr < PORTAL_AB:
            return True, f"Entscheidung von {jahr}, Datenbank ab {PORTAL_AB}"
        return False, ""
    # Naeherung ueber das Eingangsjahr: zwei Jahre Sicherheitsabstand, weil
    # zwischen Eingang und Entscheidung Zeit vergeht.
    if jahr < PORTAL_AB - 2:
        return True, (f"Eingang {jahr}, Entscheidung damit vor {PORTAL_AB} "
                      f"zu erwarten")
    if jahr < PORTAL_AB:
        return True, (f"Eingang {jahr} -- Entscheidung koennte vor oder nach "
                      f"{PORTAL_AB} liegen, nicht entscheidbar")
    return False, ""


# ==========================================================================
# ZWEITER, UNABHAENGIGER SIGNALWEG: IST DIE SENATSKENNUNG UEBERHAUPT MOEGLICH?
# ==========================================================================
# Die Reichweiten-Regel oben hat eine Nebenwirkung, die beim Bauen auffiel:
# ein FREI ERFUNDENES Aktenzeichen mit altem Jahrgang -- "XY ZR 999/99" --
# wuerde jetzt als "ausserhalb der Datenbank" durchgehen, weil die Datenbank
# zu 1999 nichts sagen kann.
#
# Das laesst sich nicht ueber die Datenbank loesen, wohl aber unabhaengig
# davon: die Senatskennung des BGH ist nicht frei waehlbar. Zivilsenate
# tragen roemische Zahlen (mit moeglichem Kleinbuchstaben-Zusatz wie VIa),
# Strafsenate die Ziffern 1 bis 6. "XY" ist beides nicht -- und das gilt
# unabhaengig vom Jahr und unabhaengig von jeder Abfrage.
#
# Zwei voneinander unabhaengige Pruefungen auf dieselbe Frage. Gestern hat
# genau das eine Luecke gefangen, die die naheliegendere Pruefung uebersah.
ROEMISCH = re.compile(r"^[IVXLCDM]+[a-z]?$")

# ==========================================================================
# KORREKTUR vom 17.08.2026 — die Regel galt fuer JEDES Gericht
# ==========================================================================
# Die Regel oben ist eine Regel des BGH. Angewandt wurde sie bis heute auf
# jedes gefundene Aktenzeichen. Gemessen an elf echten Aktenzeichen fielen
# drei durch, und zwar als "UNMOEGLICH — so ein Aktenzeichen gibt es nicht":
#
#   20 F 15/22     BVerwG   -- 20 ist groesser als 13
#   I-25 U 75/25   OLG Hamm -- "I-25" ist keine roemische Zahl
#   16 U 139/23    OLG Koeln
#
# "Unmoeglich" fuehrt in main() zu BLOCKIERT und exit 1. Ein Schriftsatz mit
# einem korrekt zitierten OLG-Aktenzeichen waere also angehalten worden, mit
# der Begruendung, es gebe dieses Aktenzeichen nicht.
#
# Nebenbefund: 9 CN 2.22 (BVerwG) und 6 AZR 499/21 (BAG) kamen nur deshalb
# durch, weil 9 und 6 zufaellig kleiner als 13 sind. Richtig war das
# Ergebnis, richtig war der Weg dorthin nicht.
#
# Die Kennung allein sagt nicht, welches Gericht gemeint ist -- das sagt das
# REGISTERZEICHEN. Deshalb wird die BGH-Regel jetzt nur noch auf
# BGH-Registerzeichen angewandt. Fuer alles andere lautet die Antwort
# NICHT PRUEFBAR, und das ist etwas anderes als unmoeglich.
BGH_REGISTER = {
    "ZR", "ZB", "ZA",                                  # Zivilsenate
    "StR", "StB", "StE", "ARs",                        # Strafsenate
    "KZR", "KZB", "KVR", "KVZ",                        # Kartellsenat
    "EnVR", "EnVZ", "EnZR", "EnZB",                    # Energiesenat
    "LwZR", "LwZB",                                    # Landwirtschaftssenat
    "AnwZ", "AnwSt", "NotZ", "NotSt", "StbSt",         # Berufsgerichtsbarkeit
    "PatAnwZ", "AR",
    "GSSt", "GSZ", "VGS", "RiZ",                       # Grosse Senate u. a.
}

SONDERFORMEN = ("KZR", "KVR", "EnVR", "EnVZ", "AnwZ", "Brfg", "AR",
                "NotZ", "StbSt", "PatAnwZ")

MOEGLICH, UNMOEGLICH, NICHT_PRUEFBAR = "moeglich", "unmoeglich", "nicht_pruefbar"


def senat_befund(az):
    """Drei Antworten, nicht zwei.

    MOEGLICH        BGH-Aktenzeichen, Senatskennung ist moeglich
    UNMOEGLICH      BGH-Aktenzeichen, diese Senatskennung gibt es nicht
    NICHT_PRUEFBAR  kein BGH-Aktenzeichen -- diese Pruefung ist dafuer
                    nicht zustaendig und sagt darum nichts

    Der dritte Zustand ist der eigentliche Inhalt dieser Korrektur. Ohne ihn
    muss die Funktion jedes fremde Gericht entweder freisprechen oder
    verurteilen, und beides waere erfunden.
    """
    teile = az.split()
    if len(teile) < 3:
        return NICHT_PRUEFBAR
    kennung, register = teile[0], teile[1]

    # "AnwZ (Brfg) 24/24" — hier steht die Sonderform vorn, nicht an zweiter
    # Stelle. Der erste Entwurf hat nur das zweite Feld geprueft und diese
    # gueltige Form deshalb als unmoeglich eingestuft.
    if kennung in SONDERFORMEN or register in SONDERFORMEN:
        return MOEGLICH                  # dort gibt es keine Senatskennung

    if register not in BGH_REGISTER:
        return NICHT_PRUEFBAR            # OLG, LG, BAG, BVerwG, BFH, BVerfG

    if kennung.isdigit():
        return (MOEGLICH if (register in ("StR", "StB") or 1 <= int(kennung) <= 13)
                else UNMOEGLICH)
    return MOEGLICH if ROEMISCH.match(kennung) else UNMOEGLICH


def senat_plausibel(az):
    """Nur noch fuer alte Aufrufer. UNMOEGLICH blockiert, alles andere nicht."""
    return senat_befund(az) != UNMOEGLICH


def text_aus_docx(pfad):
    """Absaetze werden mit Zeilenumbruch getrennt, Textteile innerhalb eines
    Absatzes ohne Trennung aneinandergehaengt.

    Die erste Fassung hat ALLE Textteile ohne Trennzeichen verbunden. Damit
    lief das Ende eines Absatzes unmittelbar in den Anfang des naechsten:

        "... - I ZR 130/25" + "BGH, Urteil vom ..."  ->  "...130/25BGH, ..."

    Das Muster fuer Aktenzeichen endet auf eine Wortgrenze. Zwischen "5" und
    "B" liegt keine — ein Aktenzeichen am Absatzende wurde deshalb gar nicht
    erst gefunden und lief stumm durch. In einem Schriftsatz steht die
    Fundstelle sehr oft genau dort.

    Gefunden vom eigenen Test am 05.08.2026, nicht durch Lesen des Codes.
    """
    with zipfile.ZipFile(pfad) as z:
        xml = z.read("word/document.xml")
    wurzel = ET.fromstring(xml)
    absaetze = []
    for p in wurzel.iter(f"{W_NS}p"):
        absaetze.append("".join(el.text or "" for el in p.iter(f"{W_NS}t")))
    return "\n".join(absaetze)


def text_aus_datei(pfad):
    endung = os.path.splitext(pfad)[1].lower()
    if endung == ".docx":
        return text_aus_docx(pfad)
    if endung in (".txt", ".md"):
        with open(pfad, encoding="utf-8", errors="replace") as f:
            return f.read()
    raise ValueError(f"Nicht unterstuetztes Format: {endung}")


def normalisieren(az):
    """Mehrfache Leerzeichen vereinheitlichen, damit der Vergleich greift."""
    return re.sub(r"\s+", " ", az).strip()


def aktenzeichen_finden(text):
    """Gibt Paare (aktenzeichen, umfeld) zurueck. Das Umfeld sind die 90
    Zeichen davor -- dort steht in der Kanzleischreibweise das Datum."""
    gefunden, gesehen = [], set()
    for treffer in AZ_MUSTER.finditer(text):
        az = normalisieren(treffer.group(1))
        if az not in gesehen:
            gesehen.add(az)
            umfeld = text[max(0, treffer.start() - 90):treffer.start()]
            gefunden.append((az, umfeld))
    return gefunden


def referenz_laden(pfad):
    with open(pfad, encoding="utf-8") as f:
        daten = json.load(f)
    belegt = {normalisieren(k): v for k, v in daten.get("belegt", {}).items()}
    fehlt = {normalisieren(k): v for k, v in
             daten.get("nachweislich_nicht_vorhanden", {}).items()}
    return belegt, fehlt, daten


def pruefen(pfad_dokument, pfad_referenz):
    text = text_aus_datei(pfad_dokument)
    belegt, nicht_vorhanden, roh = referenz_laden(pfad_referenz)
    zitate = aktenzeichen_finden(text)

    ergebnis = {"belegt": [], "nicht_vorhanden": [], "ungeprueft": [],
                "ausserhalb": [], "unplausibel": [], "fremdes_gericht": []}
    gruende = {}
    for az, umfeld in zitate:
        jahr, quelle = entscheidungsjahr(umfeld, az)
        draussen, grund = ausserhalb_der_reichweite(jahr, quelle)

        if az in belegt:
            # Ein Nachweis bleibt ein Nachweis, egal aus welcher Quelle.
            ergebnis["belegt"].append(az)
            continue

        # Vor der Reichweiten-Frage: kann es dieses Aktenzeichen ueberhaupt
        # geben? Diese Antwort haengt an keiner Datenbank und gilt fuer jeden
        # Jahrgang.
        befund = senat_befund(az)
        if befund == UNMOEGLICH:
            ergebnis["unplausibel"].append(az)
            gruende[az] = ("Senatskennung gibt es beim BGH nicht — "
                           "Zivilsenate roemisch, Strafsenate 1 bis 6")
            continue
        if befund == NICHT_PRUEFBAR and az not in nicht_vorhanden:
            # Kein BGH-Aktenzeichen. Die Senatsregel schweigt hier, und der
            # Referenzbestand deckt diese Gerichte nicht ab. Beides zusammen
            # heisst: diese Pruefung kann nichts sagen -- und sagt das auch,
            # statt zu blockieren oder stillschweigend durchzulassen.
            ergebnis["fremdes_gericht"].append(az)
            gruende[az] = ("kein BGH-Aktenzeichen (Registerzeichen "
                           f"'{az.split()[1] if len(az.split()) > 1 else '?'}') "
                           "— Senatsregel und Referenzbestand gelten hier nicht")
            continue

        if draussen:
            # Hier wird bewusst NICHT geurteilt. Auch dann nicht, wenn der
            # Referenzbestand "nicht vorhanden" sagt -- diese Angabe stammt
            # aus einer Abfrage, die diesen Zeitraum gar nicht abdeckt.
            ergebnis["ausserhalb"].append(az)
            gruende[az] = grund
            continue

        if az in nicht_vorhanden:
            ergebnis["nicht_vorhanden"].append(az)
        else:
            ergebnis["ungeprueft"].append(az)

    # Die Differenz zwischen beidem Muster ist der wichtigste Wert dieser
    # Funktion: sie sagt, wie viele Zitate im Text stehen, die diese Pruefung
    # nie angesehen hat. Ohne diese Zeilen erschien am Ende "alle Fundstellen
    # belegt", obwohl ein Teil nie gesucht wurde.
    gesehen = {az for az, _ in zitate}
    for treffer in AZ_MUSTER_WEIT.finditer(text):
        az = " ".join(treffer.group(1).split())
        if az in gesehen or az in ergebnis["fremdes_gericht"]:
            continue
        ergebnis["fremdes_gericht"].append(az)
        teile = az.split()
        gruende[az] = ("kein BGH-Aktenzeichen (Registerzeichen "
                       f"'{teile[1] if len(teile) > 1 else '?'}') — "
                       "vom Suchmuster dieser Pruefung nicht erfasst")

    return ergebnis, roh, gruende


def pruefweg(roh, az):
    """
    Baut die Nachschlage-URL. Die Vorlage enthaelt die Anfuehrungszeichen
    bereits als %22...%22 — hier duerfen also keine weiteren dazukommen,
    sonst steht das Aktenzeichen doppelt gequotet in der Suche.
    """
    from urllib.parse import quote
    vorlage = roh.get("_pruefweg", "")
    return vorlage.replace("AKTENZEICHEN", quote(az, safe=""))


def main():
    if len(sys.argv) < 2:
        print("Aufruf: python3 AP18_referenzpruefung.py dokument.docx [--referenz datei.json]")
        sys.exit(1)

    dokument = sys.argv[1]
    hier = os.path.dirname(os.path.abspath(__file__))
    referenz = os.path.join(hier, "bgh_referenz.json")
    if "--referenz" in sys.argv:
        referenz = sys.argv[sys.argv.index("--referenz") + 1]

    if not os.path.isfile(dokument):
        print(f"FEHLER: Dokument nicht gefunden: {dokument}")
        sys.exit(2)
    if not os.path.isfile(referenz):
        print(f"FEHLER: Referenzbestand nicht gefunden: {referenz}")
        sys.exit(2)

    ergebnis, roh, gruende = pruefen(dokument, referenz)

    print("=" * 70)
    print("REFERENZPRUEFUNG — zitierte Aktenzeichen")
    print("=" * 70)
    print(f"Dokument  : {os.path.basename(dokument)}")
    print(f"Referenz  : {os.path.basename(referenz)}  (Stand {roh.get('_stand','?')})")
    gesamt = sum(len(v) for v in ergebnis.values())
    fremd = len(ergebnis["fremdes_gericht"])
    print(f"gefunden  : {gesamt} Aktenzeichen")
    print(f"davon BGH : {gesamt - fremd}  — nur diese liegen im "
          f"Zustaendigkeitsbereich dieser Pruefung")
    if fremd:
        print(f"uebrige   : {fremd}  — anderes Gericht, hier NICHT geprueft")
    print()

    if ergebnis["belegt"]:
        print("BELEGT")
        for az in ergebnis["belegt"]:
            print(f"   {az}")
        print()

    if ergebnis["ungeprueft"]:
        print("UNGEPRUEFT — bitte vor dem Versand nachschlagen")
        for az in ergebnis["ungeprueft"]:
            print(f"   {az}")
            print(f"      {pruefweg(roh, az)}")
        print()

    if ergebnis["unplausibel"]:
        print("UNMOEGLICHE SENATSKENNUNG — so ein Aktenzeichen gibt es nicht")
        for az in ergebnis["unplausibel"]:
            print(f"   {az}   ({gruende.get(az, '')})")
        print()

    if ergebnis["fremdes_gericht"]:
        print("NICHT PRUEFBAR — kein BGH-Aktenzeichen")
        for az in ergebnis["fremdes_gericht"]:
            print(f"   {az}   ({gruende.get(az, '')})")
        print()
        print("   Diese Pruefung kennt die Senatsregeln des BGH. Fuer OLG, LG,")
        print("   BAG, BVerwG, BFH und BVerfG sagt sie NICHTS — weder ja noch")
        print("   nein. Nachweis ueber die amtliche Quelle des jeweiligen")
        print("   Gerichts oder ueber rechtsprechung-im-internet.de.")
        print()

    if ergebnis["ausserhalb"]:
        print("AUSSERHALB DER DATENBANK — hier darf nicht geurteilt werden")
        for az in ergebnis["ausserhalb"]:
            print(f"   {az}   ({gruende.get(az, '')})")
        print()
        print("   Diese Fundstellen kann die Entscheidungsdatenbank weder")
        print("   bestaetigen noch widerlegen. Ein 'keine Treffer' heisst hier")
        print("   NICHT, dass es die Entscheidung nicht gibt. Nachweis ueber")
        print("   Wolters Kluwer / Libra oder die amtliche Sammlung (BGHZ,")
        print("   BGHSt) bzw. NJW; Entscheidungen bis 1999 sind beim BGH")
        print("   gesondert anzufordern.")
        print()

    if ergebnis["nicht_vorhanden"]:
        print("NICHT VORHANDEN — Fundstelle existiert nicht")
        for az in ergebnis["nicht_vorhanden"]:
            eintrag = roh["nachweislich_nicht_vorhanden"].get(az, {})
            print(f"   {az}   (geprueft {eintrag.get('geprueft','?')}: "
                  f"{eintrag.get('antwort','?')})")
        print()

    print("=" * 70)
    if ergebnis["nicht_vorhanden"] or ergebnis["unplausibel"]:
        if ergebnis["nicht_vorhanden"]:
            print("ERGEBNIS: BLOCKIERT — mindestens eine Fundstelle existiert nicht.")
        if ergebnis["unplausibel"]:
            print("ERGEBNIS: BLOCKIERT — mindestens ein Aktenzeichen kann es "
                  "so nicht geben.")
        print("=" * 70)
        sys.exit(1)

    offen = (len(ergebnis["ungeprueft"]) + len(ergebnis["ausserhalb"])
             + len(ergebnis["fremdes_gericht"]))
    if offen:
        print("ERGEBNIS: DURCHGELASSEN, mit offenen Punkten.")
        if ergebnis["ungeprueft"]:
            print(f"{len(ergebnis['ungeprueft'])} Fundstelle(n) sind noch nicht "
                  f"nachgeschlagen.")
        if ergebnis["fremdes_gericht"]:
            print(f"{len(ergebnis['fremdes_gericht'])} Fundstelle(n) stammen nicht "
                  f"vom BGH — diese Pruefung ist dafuer nicht zustaendig.")
        if ergebnis["ausserhalb"]:
            print(f"{len(ergebnis['ausserhalb'])} Fundstelle(n) liegen ausserhalb "
                  f"der Datenbank und brauchen einen anderen Nachweisweg.")
        print("Offen heisst NICHT falsch — nur, dass diese Pruefung es nicht")
        print("beantworten kann. Die Entscheidung liegt beim Berufstraeger.")
    else:
        print("ERGEBNIS: DURCHGELASSEN — alle BGH-Fundstellen belegt.")
        print("Diese Pruefung sagt nichts ueber Fundstellen anderer Gerichte.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
