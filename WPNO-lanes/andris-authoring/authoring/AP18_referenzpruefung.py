#!/usr/bin/env python3
"""Prueft zitierte Aktenzeichen gegen einen lokalen Referenzbestand.

Zustaende:
  BELEGT          nachgewiesen; wird durchgelassen
  UNMOEGLICH      ungueltige BGH-Senatskennung; wird blockiert
  NICHT VORHANDEN im abgedeckten Zeitraum widerlegt; wird blockiert
  AUSSERHALB      vor Beginn der Datenbank; braucht einen anderen Nachweisweg
  UNGEPRUEFT      noch nicht nachgeschlagen; wird offen ausgewiesen

Die Pruefung bestaetigt weder die inhaltliche Tragfaehigkeit einer Entscheidung
noch die zitierte Passage. Der lokale Bestand dient der Reproduzierbarkeit und
vermeidet einen nicht reproduzierbaren Live-Abruf.

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

# BGH-Suchmuster: Senatskennung, Registerzeichen, laufende Nummer/Jahr.
# Die Kennung bleibt bewusst weit; ihre Gueltigkeit prueft senat_befund().
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

# Das weite Muster prueft nichts. Es zaehlt nur Nicht-BGH-Aktenzeichen, damit
# der Bericht die begrenzte Zustaendigkeit des engeren BGH-Musters offenlegt.
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

GERICHT_MUSTER = (
    r"(?P<gericht>BVerfG|BVerwG|BAG|BFH|BSG|BGH|EuGH|EGMR|"
    r"(?:OLG|LG|AG|ArbG|LAG|VG|OVG|FG|LSG|SG)\s+"
    r"[A-ZÄÖÜ][\wÄÖÜäöüß.-]+)"
)
STRUKTUR_AZ_MUSTER = (
    r"(?P<aktenzeichen>(?:[A-Z]?\s*)?(?:[IVX]+|\d+|B\s+\d+)?\s*"
    r"[A-ZÄÖÜ]{1,5}\s+\d+/\d+(?:\s+[A-Z])?)"
)
STRUKTUR_ZITAT_MUSTER = re.compile(
    r"\b" + GERICHT_MUSTER + r"\b.{0,80}?"
    r"(?P<datum>\d{1,2}\.\d{1,2}\.\d{2,4})\s*[-–—]\s*"
    + STRUKTUR_AZ_MUSTER + r"\b",
    re.IGNORECASE,
)


# Die freie BGH-Entscheidungsdatenbank beginnt 2000. Bei aelteren
# Entscheidungen bedeutet "keine Treffer" nicht "nicht vorhanden".
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


# Die Senatskennung wird unabhaengig vom Referenzbestand geprueft: zivile
# Senate I-XIII (mit optionalem Zusatz), Strafsenate 1-6.
ROEMISCH = re.compile(
    r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII)[a-z]?$"
)

# BGH-Regeln duerfen nicht auf Aktenzeichen anderer Gerichte angewandt werden.
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
        if register in ("StR", "StB"):
            return MOEGLICH if 1 <= int(kennung) <= 6 else UNMOEGLICH
        return UNMOEGLICH
    return MOEGLICH if ROEMISCH.match(kennung) else UNMOEGLICH


def senat_plausibel(az):
    """Nur noch fuer alte Aufrufer. UNMOEGLICH blockiert, alles andere nicht."""
    return senat_befund(az) != UNMOEGLICH


def text_aus_docx(pfad):
    """Verbindet Runs im Absatz und trennt OOXML-Absaetze durch Zeilenumbrueche."""
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


def strukturierte_aktenzeichen_finden(text):
    """Findet eindeutige Gericht/Datum/Aktenzeichen-Identitaeten je Absatz."""
    gefunden, gesehen = [], set()
    for absatz in text.splitlines():
        for treffer in STRUKTUR_ZITAT_MUSTER.finditer(absatz):
            gericht = normalisieren(treffer.group("gericht"))
            datum = treffer.group("datum")
            az = normalisieren(treffer.group("aktenzeichen"))
            identitaet = (gericht.casefold(), datum, az.casefold())
            if identitaet in gesehen:
                continue
            gesehen.add(identitaet)
            start = treffer.start("aktenzeichen")
            umfeld = absatz[max(0, start - 90):start]
            gefunden.append((az, umfeld, gericht, datum))
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
    ergebnis = {"belegt": [], "nicht_vorhanden": [], "ungeprueft": [],
                "ausserhalb": [], "unplausibel": [], "fremdes_gericht": [],
                "nicht_strukturell": []}
    gruende = {}

    strukturiert = strukturierte_aktenzeichen_finden(text)
    struktur_designatoren = {az.casefold() for az, _, _, _ in strukturiert}
    for az, umfeld, gericht, _ in strukturiert:
        if gericht.split()[0].casefold() != "bgh":
            ergebnis["fremdes_gericht"].append(az)
            gruende[az] = f"ausstellendes Gericht: {gericht} — keine BGH-Pruefung"
            continue

        jahr, quelle = entscheidungsjahr(umfeld, az)
        draussen, grund = ausserhalb_der_reichweite(jahr, quelle)
        if az in belegt:
            ergebnis["belegt"].append(az)
            continue
        befund = senat_befund(az)
        if befund == UNMOEGLICH:
            ergebnis["unplausibel"].append(az)
            gruende[az] = ("Senatskennung gibt es beim BGH nicht — "
                           "Zivilsenate roemisch, Strafsenate 1 bis 6")
            continue
        if befund == NICHT_PRUEFBAR and az not in nicht_vorhanden:
            ergebnis["fremdes_gericht"].append(az)
            gruende[az] = ("kein BGH-Aktenzeichen (Registerzeichen "
                           f"'{az.split()[1] if len(az.split()) > 1 else '?'}') "
                           "— Senatsregel und Referenzbestand gelten hier nicht")
            continue
        if draussen:
            ergebnis["ausserhalb"].append(az)
            gruende[az] = grund
            continue
        if az in nicht_vorhanden:
            ergebnis["nicht_vorhanden"].append(az)
        else:
            ergebnis["ungeprueft"].append(az)

    gesehen = set(struktur_designatoren)
    for az, _ in aktenzeichen_finden(text):
        schluessel = az.casefold()
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        if senat_befund(az) == UNMOEGLICH:
            ergebnis["unplausibel"].append(az)
            gruende[az] = ("Senatskennung gibt es beim BGH nicht — "
                           "Zivilsenate roemisch, Strafsenate 1 bis 6")
        else:
            ergebnis["nicht_strukturell"].append(az)

    for treffer in AZ_MUSTER_WEIT.finditer(text):
        az = normalisieren(treffer.group(1))
        schluessel = az.casefold()
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ergebnis["nicht_strukturell"].append(az)

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
    gesamt = sum(
        len(v) for k, v in ergebnis.items() if k != "nicht_strukturell"
    )
    fremd = len(ergebnis["fremdes_gericht"])
    print(f"gefunden  : {gesamt} Aktenzeichen")
    print(f"davon BGH : {gesamt - fremd}  — nur diese liegen im "
          f"Zustaendigkeitsbereich dieser Pruefung")
    if fremd:
        print(f"uebrige   : {fremd}  — anderes Gericht, hier NICHT geprueft")
    print()

    if ergebnis["nicht_strukturell"]:
        print("NICHT ALS ENTSCHEIDUNGSZITAT GEZAEHLT")
        for az in ergebnis["nicht_strukturell"]:
            print(f"   {az}")
        print("   Es fehlt Gericht + Datum + Gedankenstrich im selben Absatz.")
        print()

    if gesamt == 0:
        print("=" * 70)
        print("ERGEBNIS: KEINE AKTENZEICHEN GEFUNDEN — NICHTS GEPRUEFT.")
        print("Ohne gefundene Aktenzeichen kann diese Pruefung keine Aussage")
        print("ueber vorhandene oder fehlende Fundstellen treffen.")
        print("=" * 70)
        sys.exit(0)

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
             + len(ergebnis["fremdes_gericht"])
             + len(ergebnis["nicht_strukturell"]))
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
        if ergebnis["nicht_strukturell"]:
            print(f"{len(ergebnis['nicht_strukturell'])} Aktenzeichen-Hinweis(e) "
                  "sind keine vollstaendigen strukturellen Entscheidungszitate.")
        print("Offen heisst NICHT falsch — nur, dass diese Pruefung es nicht")
        print("beantworten kann. Die Entscheidung liegt beim Berufstraeger.")
    else:
        print("ERGEBNIS: DURCHGELASSEN — alle BGH-Fundstellen belegt.")
        print("Diese Pruefung sagt nichts ueber Fundstellen anderer Gerichte.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
