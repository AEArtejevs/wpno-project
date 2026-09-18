#!/usr/bin/env python3
"""
payload_scan_golden_test.py — Golden-Set fuer payload_scan.py.

Testkatalog P0 "Anonymisierung: keine PII in der ausgehenden Nutzlast" und
29.1 "Aufruf mit Rest-PII wird blockiert".

Aus dem Premortem (Kap. 30.2): "Golden-Set mit 200 bekannten PII-Strings als
CI-Test: 0 Treffer in der protokollierten ausgehenden Nutzlast."

=====================================================================
WAS DIESER TEST AM 04.08. GEFUNDEN HAT
=====================================================================
payload_scan.py war zu diesem Zeitpunkt zweimal auditiert und galt als fertig.
Gegen das Golden-Set gemessen rutschten trotzdem 34 von 200 Nutzlasten durch:

  Steuer-ID       0 von 20 erkannt — das Muster "steuid" trifft die
                  STEUERNUMMER (12/345/67890), nicht die elfstellige
                  Steuer-Identifikationsnummer. Zwei verschiedene Formate.
  Parteinamen    16 von 30 erkannt — "L@th@m 8 W@tkins" und auseinander-
                  gezogene Schrift gehen durch. Genau der Fall aus dem
                  Premortem.
  IBAN            nur DE gedeckt — ein lettisches oder Schweizer Konto war
                  unsichtbar.

Keiner dieser Punkte war durch Lesen des Codes zu sehen. Sie wurden durch
Messen gefunden. Das ist der Grund, warum dieser Test existiert.

=====================================================================
BEIDE RICHTUNGEN
=====================================================================
Teil 1: 200 PII-Nutzlasten muessen blockiert werden.
Teil 2: unverdaechtige Nutzlasten muessen durchgehen.

Teil 2 ist die schwerere Haelfte. Ein Waechter, der alles blockiert, besteht
Teil 1 vollstaendig und wird in der ersten Woche abgeschaltet.

Vier Faelle in Teil 2 sind ABSICHTLICH als bekannte Abweichung markiert und
zaehlen nicht als Fehler: payload_scan blockiert Datumsangaben und
Aktenzeichen von Bauart wegen. Das ist eine Richtlinienfrage, keine Panne —
und sie ist Martin vorgelegt. Solange sie offen ist, wird sie hier
ausgewiesen statt stillschweigend weggelassen.

ALLE DATEN SIND SYNTHETISCH. Die IBANs sind rechnerisch gueltig, gehoeren
aber zu keinem Konto.

Aufruf:
    python3 payload_scan_golden_test.py [pfad/zu/payload_scan.py]
"""

import json
import os
import random
import sys
import tempfile

ZUFALL = random.Random(20260804)


def iban_bauen(land, bban):
    umgestellt = bban + land + "00"
    ziffern = "".join(str(ord(c) - 55) if c.isalpha() else c for c in umgestellt)
    return f"{land}{98 - (int(ziffern) % 97):02d}{bban}"


def steuer_id_bauen():
    while True:
        kern = "".join(str(ZUFALL.randint(0, 9)) for _ in range(10))
        if kern[0] == "0":
            continue
        produkt = 10
        for z in kern:
            summe = (int(z) + produkt) % 10
            produkt = ((summe or 10) * 2) % 11
        return kern + str((11 - produkt) % 10)


SPERRNAMEN = ["Hansen & Reimers GmbH", "Latham & Watkins", "Bernd Osterloh",
              "Ingrid Waldkirch", "Nordsee Beteiligungs AG"]


def golden_set():
    f = []
    for _ in range(30):
        bban = "".join(str(ZUFALL.randint(0, 9)) for _ in range(18))
        f.append(("IBAN DE", f"Ueberweisung auf {iban_bauen('DE', bban)} erbeten."))
    for land, laenge in (("LV", 17), ("AT", 16), ("CH", 17)):
        for _ in range(4):
            bban = "".join(ZUFALL.choice("0123456789") for _ in range(laenge))
            f.append((f"IBAN {land}", f"Konto {iban_bauen(land, bban)}"))
    for _ in range(20):
        bic = ("".join(ZUFALL.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(4))
               + "DE" + "".join(ZUFALL.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                                for _ in range(2)))
        f.append(("BIC", f"BIC: {bic}"))
    for i in range(30):
        f.append(("E-Mail", f"Kontakt: kanzlei{i}@beispiel-recht.de"))
    for i in range(30):
        f.append(("Telefon", f"Rueckruf unter +49 40 {3000000 + i * 137}"))
    for _ in range(20):
        f.append(("Steuer-ID", f"Steuer-ID {steuer_id_bauen()}"))
    for i in range(30):
        f.append(("Aktenzeichen", f"Verfahren {2 + i % 9} O {80 + i}/2{i % 6}"))
    for i in range(30):
        name = SPERRNAMEN[i % len(SPERRNAMEN)]
        if i % 4 == 1:
            name = name.replace("a", "@").replace("&", "8")     # OCR
        elif i % 4 == 2:
            name = " ".join(name)                                # auseinander
        elif i % 4 == 3:
            name = name.replace("&", "&amp;")                    # XML-Entitaet
        f.append(("Parteiname", f"Die Partei {name} traegt vor:"))
    return f


# (Bezeichnung, Text, bekannte_abweichung)
def sauberes_set():
    return [
        ("Elfstellige Zahl, keine Steuer-ID",
         "Zeitstempel des Laufs: 17548392016 (Unix, gekuerzt).", False),
        ("Belegnummer", "Beleg 20260804001 wurde verbucht.", False),
        ("Betraege", "Der Schaden betraegt 1.284.550,00 EUR zzgl. Zinsen.", False),
        ("Juristischer Fliesstext",
         "Die Klaegerin traegt vor, das Konto sei nicht valutiert gewesen.", False),
        ("Prozentangaben",
         "Die Akte umfasst 4.500 Seiten; die OCR-Konfidenz liegt bei 97,4 %.", False),
        ("Grossbuchstaben, die das BIC-Muster treffen",
         "Status: CONFIRMED, REFUTED, UNVERIFIED, BLOCKED, RESOLVED. "
         "12D: AUDIT TRAIL — NO ANONYMOUS CONCLUSIONS.", False),
        ("Ueberschriften in Grossbuchstaben",
         "21D. MAX-LEVEL OPERATIONAL HARDENING. 10. VERBOTENE OPERATIONEN.", False),
        # --- bekannte Abweichung, Richtlinienfrage, Martin vorgelegt ---
        ("Beispiel-IBAN aus einer Anleitung",
         "Tragen Sie Ihre IBAN im Format DE12 3456 7890 1234 5678 90 ein.", True),
        ("Datumsangaben",
         "Die Lieferung erfolgte am 12.03.2024, die Ruege am 19.03.2024.", True),
        ("Anonymisierter Schriftsatz",
         "In dem Rechtsstreit PARTEI_A gegen PARTEI_B nehmen wir zum "
         "Schriftsatz vom 12.03.2024 Stellung.", True),
        ("Norm- und Fundstellenzitate",
         "Vgl. BGH, Urteil vom 15.01.2020 - VIII ZR 178/19; § 280 BGB.", True),
    ]


def main():
    modulpfad = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "payload_scan.py")
    if not os.path.isfile(modulpfad):
        print(f"FEHLER: payload_scan.py nicht gefunden: {modulpfad}")
        sys.exit(2)

    ordner = os.path.dirname(os.path.abspath(modulpfad))
    sys.path.insert(0, ordner)

    # Die Sperrliste muss die Testnamen enthalten, sonst prueft Teil 1 nichts.
    sperrliste = os.path.join(ordner, "party_names.json")
    vorhanden = os.path.isfile(sperrliste)
    if vorhanden:
        with open(sperrliste, encoding="utf-8-sig") as f:
            namen = set(json.load(f).get("names", []))
        if not set(SPERRNAMEN) <= namen:
            print("HINWEIS: party_names.json enthaelt die Testnamen nicht.")
            print("Der Parteinamen-Teil prueft dann nichts Aussagekraeftiges.")
            print("Fuer den Testlauf eine eigene Sperrliste verwenden.")
            sys.exit(2)
    else:
        print(f"FEHLER: {sperrliste} fehlt — Teil 1 waere ohne Aussage.")
        sys.exit(2)

    import payload_scan as ps

    print("=" * 74)
    print("GOLDEN-SET — payload_scan.py")
    print("=" * 74)
    print(f"Modul: {modulpfad}")

    fehler = 0
    angriffe = golden_set()
    durch = {}
    for art, text in angriffe:
        if not ps.scan_payload(text)["blocked"]:
            durch.setdefault(art, []).append(text)

    print(f"\nTeil 1 — {len(angriffe)} PII-Nutzlasten muessen blockiert werden")
    print("-" * 74)
    for art in sorted({a for a, _ in angriffe}):
        n = sum(1 for a, _ in angriffe if a == art)
        d = len(durch.get(art, []))
        print(f"  {'ok    ' if d == 0 else 'LECK  '} {art:16} {n - d}/{n} blockiert")
        for t in durch.get(art, [])[:2]:
            print(f"            durchgerutscht: {t[:62]}")
        fehler += d

    sauber = sauberes_set()
    print(f"\nTeil 2 — {len(sauber)} unverdaechtige Nutzlasten")
    print("-" * 74)
    for bezeichnung, text, bekannt in sauber:
        r = ps.scan_payload(text)
        if not r["blocked"]:
            print(f"  ok         {bezeichnung}")
        elif bekannt:
            print(f"  bekannt    {bezeichnung}  ->  {r['findings']}")
        else:
            print(f"  FEHLALARM  {bezeichnung}  ->  {r['findings']}")
            fehler += 1

    print("\n" + "=" * 74)
    if fehler == 0:
        print(f"ERGEBNIS: bestanden. {len(angriffe)} PII-Nutzlasten blockiert.")
        print()
        print("Vier Faelle in Teil 2 stehen als bekannte Abweichung: Datum und")
        print("Aktenzeichen blockieren von Bauart wegen. Ob das so bleibt, ist")
        print("eine Richtlinienfrage und liegt bei Martin — kein Testergebnis.")
        print()
        print("Nicht belegt ist, dass jede denkbare PII erkannt wird. Der")
        print("Waechter ist die zweite Schicht. Die erste bleibt die Regel,")
        print("dass echte Mandatsdaten den Rechner nicht verlassen.")
    else:
        print(f"ERGEBNIS: {fehler} Fall/Faelle nicht bestanden.")
    print("=" * 74)
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
