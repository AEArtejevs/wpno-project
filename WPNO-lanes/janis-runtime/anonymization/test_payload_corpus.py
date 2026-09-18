"""
AP-03 pilnais sintetiskais testu korpuss: visi PII tipi + tiri negativi.
Katram tipam vairaki paraugi; izdrukats PASS/FAIL per tips.
Visi dati ir SINTETISKI (izdomati) -- nekadu realu mandata datu.
"""

import sys
from payload_scan import local_scan

# type -> list of (description, text) that MUST be detected with that type
POSITIVES = {
    "iban": [
        ("compact", "Zahlung auf Konto DE89370400440532013000 erfolgt."),
        ("spaced print format", "Konto: DE89 3704 0044 0532 0130 00 bei der Bank."),
    ],
    "steuid": [
        ("classic", "Die Steuernummer lautet 12/345/67890."),
    ],
    "az": [
        ("landgericht", "Siehe Urteil im Verfahren 12 O 345/23."),
        ("olg", "Berufung unter I-2 U 8/12 anhaengig." .replace("I-", "")),
    ],
    "party": [
        ("hardcoded", "Mandant ist Hoffmann & Reuter."),
        ("from json", "Gegner ist die H&R Group."),
    ],
    "email": [
        ("plain", "Bitte an max.mustermann@kanzlei-beispiel.de senden."),
        ("subdomain+plus", "CC an m.otten+akte@mail.example-firm.co.uk bitte."),
    ],
    "phone": [
        ("intl +49", "Erreichbar unter +49 211 4933-0 tagsueber."),
        ("intl 0049", "Fax: 0049 211 493301."),
        ("national spaced", "Mobil: 0171 2345678."),
        ("national slash", "Telefon 0211/493300 waehlen."),
    ],
    "bic": [
        ("8-char", "BIC COBADEFF der Commerzbank."),
        ("11-char", "Ueberweisung via MARKDEF1100 an die Bundesbank."),
    ],
    "name": [
        ("herr", "Herr Klaus Mustermann hat den Vertrag unterschrieben."),
        ("frau dr", "Frau Dr. Erika Beispielfrau erschien zum Termin."),
        ("ra", "Rechtsanwalt Jan Testmann vertritt die Beklagte."),
        ("zeuge", "Der Zeuge Peter Probemann sagte aus."),
    ],
    "company": [
        ("gmbh", "Die Musterbau GmbH hat Insolvenz angemeldet."),
        ("gmbh co kg", "Vertrag mit der Nordmilch Handels GmbH & Co. KG."),
        ("ag", "Die Beispielwerke AG zahlte nicht."),
        ("ug", "Gruendung der Testfirma UG (haftungsbeschränkt) in 2024."),
    ],
    "address": [
        ("strasse+nr", "Kanzleisitz: Musterstraße 12 in der Innenstadt."),
        ("str-abbrev", "Zustellung an Berliner Str. 5a erfolgt."),
        ("allee", "Buero auf der Prachtallee 61 gelegen."),
        ("plz+stadt", "Versand nach 40213 Düsseldorf am Montag."),
    ],
}

# texts that must be CLEAN (no hits at all) -- false-positive guard
NEGATIVES = [
    ("plain legal prose", "Der Anspruch folgt aus dem Werkvertrag und ist begruendet."),
    ("article + legal form word alone", "Die AG im Sinne des Aktiengesetzes haftet."),
    ("caps word not bic", "Der VERTRAG und die DEUTSCHE Rechtsprechung gelten."),
    ("amount not plz-city", "Es geht um 50000 Euro Honorar."),
    ("paragraph refs", "Nach § 17 InsO und § 823 BGB ist zu pruefen."),
]

def test_payload_corpus():
    fail = 0
    print("=" * 72)
    print("POSITIVE SAMPLES (each must be detected with the expected type)")
    print("=" * 72)
    for expected_type, samples in POSITIVES.items():
        type_ok = True
        for desc, text in samples:
            hits = local_scan(text)
            found_types = sorted(set(h["type"] for h in hits))
            ok = expected_type in found_types
            if not ok:
                type_ok = False
                fail += 1
            print(f"  [{expected_type}/{desc}] -> {'DETECTED' if ok else '** MISSED **'} (found: {found_types})")
        print(f"TYPE {expected_type.upper()}: {'PASS' if type_ok else 'FAIL'}")
        print("-" * 72)

    print()
    print("=" * 72)
    print("NEGATIVE SAMPLES (must be clean; date hits from EXTRA_PATTERNS ignored)")
    print("=" * 72)
    neg_ok = True
    for desc, text in NEGATIVES:
        hits = [h for h in local_scan(text) if not h["type"].startswith("date_")]
        ok = len(hits) == 0
        if not ok:
            neg_ok = False
            fail += 1
        found_types = sorted(set(h["type"] for h in hits))
        print(f"  [clean/{desc}] -> {'CLEAN' if ok else '** FALSE POSITIVE **'} (found: {found_types})")
    print(f"TYPE CLEAN-NEGATIVES: {'PASS' if neg_ok else 'FAIL'}")
    print("=" * 72)
    print(f"OVERALL: {'PASS' if fail == 0 else f'FAIL ({fail} sample(s) failed)'}")
    assert fail == 0, f"{fail} sample(s) failed"


if __name__ == "__main__":
    import sys
    try:
        test_payload_corpus()
        sys.exit(0)
    except AssertionError as e:
        print(f"EXIT 1: {e}")
        sys.exit(1)
