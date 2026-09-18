#!/usr/bin/env python3
"""
AP18_test_injection.py — Testkatalog Kapitel 29, P4: "Manipuliertes PDF
steuert nichts". Deckt inzwischen PDF und Word ab.

Der Test prueft beide Richtungen. Ein Filter, der jede Datei blockiert, wuerde
den Angriffstest bestehen und trotzdem unbrauchbar sein — deshalb muessen
saubere Dateien ebenso zuverlaessig durchgelassen werden.

Zusaetzlich wird geprueft, dass die Angriffe ueberhaupt wirksam sind: wenn der
versteckte Text gar nicht auffindbar waere, wuerde der Test nur beweisen,
dass ein wirkungsloser Angriff nicht wirkt.

Die Erwartung ergibt sich aus dem Dateinamen:
    sauber_*   -> muss FREI sein
    angriff_*  -> muss erkannt werden (BLOCKIERT oder PRUEFEN)
So bleibt der Test gueltig, wenn dem Korpus neue Faelle hinzugefuegt werden,
ohne dass jemand eine Liste im Code nachpflegen muss.

Aufruf:
    python3 AP18_test_injection.py korpus [korpus_docx ...]

Exit-Code 0 = alle Testfaelle bestanden, 1 = mindestens einer nicht.
"""

import os
import sys
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

from AP18_eingangsfilter import datei_pruefen, bewerten   # noqa: E402

try:
    import fitz
except ImportError:
    print("FEHLER: PyMuPDF fehlt.  pip3 install pymupdf")
    sys.exit(1)

# Der eingeschleuste Text muss maschinell erreichbar sein, sonst testet man nichts.
SPUR = ("ignoriere alle vorherigen", "ignore all previous")


def wirksam_pdf(pfad):
    dok = fitz.open(pfad)
    orte = []
    meta = " ".join(str(v) for v in (dok.metadata or {}).values() if v).lower()
    if any(s in meta for s in SPUR):
        orte.append("Metadaten")
    for seite in dok:
        if any(s in seite.get_text().lower() for s in SPUR):
            orte.append("Standardextraktion")
        roh = seite.get_text("text", clip=fitz.INFINITE_RECT()).lower()
        if any(s in roh for s in SPUR):
            orte.append("Extraktion ohne Beschnitt")
    dok.close()
    return sorted(set(orte))


def wirksam_docx(pfad):
    orte = []
    with zipfile.ZipFile(pfad) as z:
        for teil in z.namelist():
            if not teil.endswith(".xml"):
                continue
            roh = z.read(teil).decode("utf8", "replace").lower()
            if any(s in roh for s in SPUR):
                orte.append(os.path.basename(teil))
    return sorted(set(orte))


def wirksam(pfad):
    return wirksam_pdf(pfad) if pfad.lower().endswith(".pdf") else wirksam_docx(pfad)


def dateien_sammeln(ordner_liste):
    dateien = []
    for ordner in ordner_liste:
        if not os.path.isdir(ordner):
            print(f"FEHLER: Korpus nicht gefunden: {ordner}")
            sys.exit(1)
        for f in sorted(os.listdir(ordner)):
            if f.lower().endswith((".pdf", ".docx")) and not f.startswith("~$"):
                dateien.append(os.path.join(ordner, f))
    return dateien


def main():
    ordner_liste = sys.argv[1:] or ["/tmp/ap18/korpus"]
    dateien = dateien_sammeln(ordner_liste)

    if not dateien:
        print("FEHLER: keine Dateien im Korpus.")
        sys.exit(1)

    print("=" * 74)
    print("TESTKATALOG P4 — Injection-Test: manipuliertes Dokument steuert nichts")
    print("=" * 74)
    print(f"Korpus: {', '.join(ordner_liste)}   ({len(dateien)} Dateien)")

    fehler = 0

    print("\nTeil 1 — Wirksamkeit der Angriffe")
    print("-" * 74)
    for pfad in dateien:
        name = os.path.basename(pfad)
        if not name.startswith("angriff"):
            continue
        orte = wirksam(pfad)
        if orte:
            print(f"  wirksam    {name:40} ueber: {', '.join(orte)}")
        else:
            print(f"  UNWIRKSAM  {name:40} <- Angriff greift nicht, Test wertlos")
            fehler += 1

    print("\nTeil 2 — Erkennung durch den Eingangsfilter")
    print("-" * 74)
    for pfad in dateien:
        name = os.path.basename(pfad)
        urteil = bewerten(datei_pruefen(pfad))

        if name.startswith("sauber"):
            ok, erwartet = urteil == "FREI", "FREI"
        elif name.startswith("angriff"):
            ok, erwartet = urteil in ("BLOCKIERT", "PRUEFEN"), "erkannt"
        else:
            print(f"  UEBERSPRUNGEN {name} (Name sagt nichts ueber die Erwartung)")
            continue

        if ok:
            print(f"  PASS       {name:40} -> {urteil}")
        else:
            print(f"  FAIL       {name:40} -> {urteil}  (erwartet: {erwartet})")
            fehler += 1

    print("\n" + "=" * 74)
    if fehler == 0:
        anz_a = sum(1 for d in dateien if os.path.basename(d).startswith("angriff"))
        anz_s = sum(1 for d in dateien if os.path.basename(d).startswith("sauber"))
        print("ERGEBNIS: alle Testfaelle bestanden.")
        print()
        print(f"Damit ist belegt: die {anz_a} nachgebildeten Angriffswege werden erkannt,")
        print(f"und die {anz_s} legitimen Schriftsaetze werden nicht blockiert — auch dann")
        print("nicht, wenn sie Woerter wie \"Anweisung\", \"System\" oder \"ignoriert\"")
        print("im normalen Fliesstext enthalten.")
        print()
        print("Was damit NICHT belegt ist: dass jeder denkbare Angriff erkannt wird.")
        print("Der Filter ist die zweite Verteidigungslinie. Die erste bleibt der")
        print("Grundsatz, dass fremde Inhalte Daten sind und niemals Anweisungen.")
    else:
        print(f"ERGEBNIS: {fehler} Testfall/-faelle nicht bestanden.")
    print("=" * 74)

    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
