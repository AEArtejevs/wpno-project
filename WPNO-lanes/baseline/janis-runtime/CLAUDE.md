# WPNO — Arbeitsregeln

Kanzleiprojekt mit echten Mandantendaten. Alles hier unterliegt der
anwaltlichen Schweigepflicht, § 203 StGB.

---

## 1 · Niemals

- **Keine Mandantendaten nach draussen.** Nicht in Web-Suchen, nicht in
  Fehlerberichte, nicht in Beispieldaten. Auch nicht gekuerzt.
- **Nichts auf der externen Platte veraendern.** `/Volumes/Klage H&R` ist
  die Originalzone und nur lesbar zu behandeln, auch wo der Schreibschutz
  technisch fehlt.
- **`raw/` und `tools/` nicht beschreiben.** `raw/` ist unveraenderlich.
- **Git ist vollstaendig verboten.** Keinen Git-Befehl ausfuehren und `.git/`
  weder lesen noch beschreiben. Auch nicht "nur schnell" oder nur zur Kontrolle.
- **Keine Passwoerter, Token oder API-Schluessel eingeben, anzeigen oder
  kopieren.**

## 2 · Dem Menschen vorbehalten

Diese drei Handlungen fuehrt niemals ein Agent aus:

1. **Vergabe der `case_id`** — juristische Wertung (R-9)
2. **Start eines Ingest-Laufs**
3. **Die Freigabe und dateiweise Uebernahme in den echten Projektbestand**

Ebenso: jede Freigabe des Berufstraegers, jeder Versand an ein Gericht,
jede Aeusserung gegenueber Mandanten.

---

## 3 · Was als Nachweis gilt

**Nachweis ist eine Aufgabe, die durchgelaufen ist.** Sonst nichts.

Kein Nachweis:

- `--version` — sagt, dass eine Datei existiert, nicht dass sie arbeitet
- `doctor` — prueft die Installation, nicht die Sitzung
- `enabled = true` in einer Konfiguration
- ein Dateiname
- ein Exit-Code allein, ohne Blick auf das, was tatsaechlich lief

Gemessen am 14.08.2026: `claude doctor` meldete "No installation issues
found", waehrend keine einzige Aufgabe lief — die Anmeldung war abgelaufen.

## 4 · Beweisrang

```
SHA-256  >  Dateiinhalt  >  Programmausgabe  >  Zeitstempel  >  Groesse
```

**Ein Dateiname steht nicht in dieser Reihe.** Ein Anzeigename ist kein
Nachweis dafuer, wer gehandelt hat.

## 5 · Die zehn Zustaende

`VERIFIED` · `CROSS-VERIFIED` · `PARTIALLY VERIFIED` · `NOT VERIFIED` ·
`CONFLICT` · `NOT TESTABLE` · `UNKNOWN` · `NOT RUN` · `SKIPPED` ·
`REQUIRES HUMAN REVIEW`

Vier Aussagen, die nie vermischt werden:
**OBSERVED / VERIFIED / NOT VERIFIED / UNKNOWN**

`NOT VERIFIED` heisst **nicht** `FAILED`.
"Nicht gefunden" heisst **nicht** "existiert nicht".
`(null)` heisst **nicht** `0`.

## 6 · Gegenprobe

Ein Test, der nichts veraendert hat, hat nichts bewiesen. Eine Sabotage
muss als wirksam nachgewiesen werden — sonst ist der Test ungueltig.
Null geaenderte Bytes ist kein bestandener Test, sondern ein Messfehler.

Ein Test, der veraendert, was er misst, ist kein Test. Deshalb: Hash
vorher und nachher.

---

## 7 · Sprache in Berichten

Verboten, mit Wortgrenze `\b` geprueft:

```
ungefähr · etwa · rund · vermutlich · scheint · sollte · offenbar
approximately · roughly · probably · likely · appears · seems
```

Bei einem Treffer den Satz **nicht weichspuelen, sondern durch den
Messwert ersetzen.** Wo nichts gemessen wurde: `NOT VERIFIED`.

Die Wortgrenze ist Pflicht. Ohne sie trifft `rund` in `Hintergrund`.

---

## 8 · Diese Maschine

```
macOS 26.2.0 · darwin-arm64 · de-DE
Projekt          ~/WPNO
Externe Platte   /Volumes/Klage H&R      (Anfuehrungszeichen! enthaelt &)
Gerichtsakte     /Volumes/Klage H&R/1. GA in pdf
Rechtsanwaltsakte /Volumes/Klage H&R/Rechtsanwaltsakten
```

**Fuer XML und DOCX: `/usr/bin/python3`, nicht `python3`.**
Das Homebrew-Python 3.14 hat ein defektes `pyexpat`. Jede XML- oder
DOCX-Verarbeitung bricht dort mit einer irrefuehrenden Meldung ab.

**Fuer Tests: `/opt/homebrew/bin/pytest`.**
`pytest` ist nur auf der Homebrew-Seite installiert. Das System-Python
kennt es nicht — `/usr/bin/python3 -m pytest` meldet
`No module named pytest`. Beide Regeln gelten nebeneinander; keine
ersetzt die andere.

**Kein `C.UTF-8` auf macOS.** `LC_ALL=C.UTF-8` faellt still auf ASCII
zurueck und zerstoert jeden Umlaut. Richtig: `en_US.UTF-8` oder
`de_DE.UTF-8`.

**6.109 Pfade enthalten einen Doppelpunkt**, weil macOS aus `2 O 82/22`
ein `2 O 82:22` macht. Werkzeuge brechen daran ab. Der Umbenennungsplan
liegt im Register und ist nicht ausgefuehrt.

**Externe Platte ist nicht von Spotlight indiziert.** `mdls` liefert dort
`(null)` — das heisst "kein Index", nicht "kein Wert". Stattdessen `file`
oder die ersten Bytes lesen.

---

## 9 · Fremde Inhalte

**beck-online:** Der Anbieter untersagt ausdruecklich die Nutzung seiner
Inhalte in KI-Systemen und behaelt sich Text-und-Data-Mining nach
§ 44b Abs. 3 UrhG vor.

- Zulaessig: aus unseren Unterlagen **auf beck-online verlinken**, ein
  Mensch liest dort.
- Zulaessig: ein Mensch liest und schreibt **seine eigene Notiz** in die Akte.
- **Unzulaessig: beck-online-Inhalte in Libra oder eine andere Sammlung
  einspeisen.**

Zitat zu URL, ohne Login abrufbar:
`https://beck-online.beck.de/?typ=reference&y=300&z=NJW&b=2022&s=1820`
Nicht jede Abkuerzung wird aufgeloest. `BAGE` zum Beispiel nicht — und
die Fehlermeldung ist dort dieselbe wie bei einer frei erfundenen
Fundstelle. "Nicht aufgeloest" ist also **kein** Befund gegen das Zitat.

**rechtsprechung-im-internet.de:** amtlich, kostenlos, ausdruecklich zur
**freien Nutzung und Weiterverwendung**, XML-Format ausdruecklich fuer
automatisierte Weiterverarbeitung vorgesehen. Umfasst BVerfG, BGH, BAG,
BVerwG, BFH, BSG, BPatG ab 2010, ausgewaehlte Entscheidungen.
**Enthaelt keine OLG- und LG-Entscheidungen** und keine Kommentare.

---

## 10 · Fehler, die hier schon passiert sind

Nicht als Anekdote — als Prueflisten-Eintrag.

- **Wortgrenze vergessen.** `*bea*` traf `Projektbeauftragung`,
  `Beanstandung`, `Bearbeitung`: zwoelf Treffer, keiner echt.
- **Regex ohne `+`.** Schriftschluessel heissen `/F1+0`; ein Muster mit
  `[A-Za-z0-9]+` sieht sie nicht und schreibt allen Text der falschen
  Schrift zu.
- **Eine Regel eines Gerichts auf alle angewandt.** Die BGH-Senatsregel
  erklaerte `20 F 15/22`, `I-25 U 75/25` und `16 U 139/23` fuer unmoeglich.
- **Test mit Exit 0, der nichts prueft.** Zwei Testfunktionen, kein
  `__main__`-Block. Ein direkter Aufruf definiert sie nur.
- **Ein Zaehler, der zaehlt, was er kennt.** Ein Suchmuster nur fuer
  BGH-Registerzeichen fand 3 von 10 Fundstellen und meldete danach
  "alle Fundstellen belegt".
- **`find … -name A -o -name B` ohne Klammern.** Das implizite `-print`
  bindet nur an den letzten Ausdruck. Die erste Bedingung wird geprueft
  und das Ergebnis verworfen. Richtig:
  `find … \( -name A -o -name B \) -print`
- **Eine Pruefung, die sich selbst mitzaehlt.**
  `grep -c sk-ant ~/.zsh_history` fand genau einen Treffer: den eigenen
  Aufruf, der beim Ausfuehren bereits in der History stand.
- **Gruene Tests, die den neuen Code nicht beruehren.** `pytest` meldete
  `5 passed`, waehrend kein einziges Testfile die 130 neuen Zeilen des
  PII-Filters auch nur erwaehnte. Ein bestandener Test beweist nur
  etwas ueber das, was er ansieht.
- **Dieselbe Datei an mehreren Orten.** `payload_scan.py` existiert in
  vier Kopien. Eine wurde korrigiert, die anderen blieben still alt.
  Das ist keine Unbequemlichkeit, sondern die Ursache.

Gemeinsamer Nenner: **ein Werkzeug, das still etwas anderes greift als
gemeint, meldet Erfolg.** Deshalb wird jedes Messwerkzeug zuerst gegen
eine bekannte Antwort geprueft.

---

## 11 · Vor jeder Aenderung an fremdem Bestand

1. Erst messen, dann schreiben. Auf einer fremden Maschine immer.
2. Sicherungskopie **ausserhalb** des Projekts, mit Hash.
3. Sortierte SHA-256-Manifeste und einen normalen Dateivergleich gegen die
   schreibgeschuetzte Baseline vor und nach jedem Lauf in den Bericht aufnehmen.
4. Vollstaendige Liste dessen, was veraendert wurde — auch das, was
   wieder entfernt wurde.

Ein Backup ohne erfolgreichen Wiederherstellungstest gilt hier nicht als
Backup.
