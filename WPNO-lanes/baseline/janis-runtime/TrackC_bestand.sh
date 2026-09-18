#!/bin/bash
# TrackC_bestand.sh — Existieren die Tatsachen, auf die Track C angewiesen ist?
#
# =====================================================================
# Track C (§§ 233 ff. ZPO, Wiedereinsetzung) kann Rechtsprechung sammeln,
# aber nichts entscheiden, solange die Tatsachen aus der Akte fehlen.
# Das Aufgabenpapier nennt sie selbst unter "What Libra cannot answer".
#
# Dieses Skript beantwortet nur EINE Frage je Punkt: existiert die Datei.
# Es oeffnet nichts, es liest keinen Inhalt, es aendert nichts.
#
# Aufruf:  cd
#          bash WPNO/TrackC_bestand.sh
# Dauer:   wenige Minuten
# =====================================================================

set -u
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

BER="$HOME/TRACKC_BESTAND_$(date +%Y-%m-%d_%H%M).txt"
exec > >(tee "$BER") 2>&1

D=$(ls -d /Volumes/Klage* 2>/dev/null | head -1)

echo "TRACK C — TATSACHENBESTAND  $(date '+%Y-%m-%d %H:%M')"
echo "======================================================================"
if [ -z "$D" ]; then
  echo "ABBRUCH: Festplatte nicht eingebunden."
  exit 2
fi
echo "Festplatte: $D"
echo
echo "Nur Dateinamen und Pfade. Kein Inhalt wird gelesen."
echo

# Hilfsfunktion: sucht, zaehlt, zeigt bis zu 12 Treffer
suche() {
  local titel="$1"; shift
  echo "----------------------------------------------------------------------"
  echo "$titel"
  local tmp; tmp=$(mktemp)
  find "$D" -type f ! -name "._*" "$@" 2>/dev/null > "$tmp"
  local n; n=$(wc -l < "$tmp" | tr -d ' ')
  if [ "$n" -eq 0 ]; then
    echo "   NICHT GEFUNDEN"
  else
    echo "   GEFUNDEN: $n"
    head -12 "$tmp" | sed "s|$D/|      |"
    [ "$n" -gt 12 ] && echo "      ... $((n-12)) weitere"
  fi
  rm -f "$tmp"
  echo
}

# ---------------------------------------------------------------------
echo "1 · beA — Nachrichtenexport, OSCI, Pruefprotokoll, Signatur"
echo "======================================================================"
echo "Ohne diese Dateien ist weder Eingangszeit noch Format beweisbar."
echo
suche "1a · Signaturdateien (.p7s / .pkcs7 / .sig)" -iname "*.p7s" -o -iname "*.pkcs7" -o -iname "*.sig"
suche "1b · Dateien mit beA im Namen"              -iname "*bea*"
suche "1c · OSCI-Container"                        -iname "*osci*" -o -iname "*_osci*"
suche "1d · Pruef- oder Uebermittlungsprotokoll"   -iname "*pruefprotokoll*" -o -iname "*prüfprotokoll*" -o -iname "*uebermittlungsprotokoll*" -o -iname "*übermittlungsprotokoll*" -o -iname "*sendeprotokoll*" -o -iname "*eingangsbestaetigung*" -o -iname "*eingangsbestätigung*"
suche "1e · Nachrichtenexport / Zustellung"        -iname "*nachrichtenexport*" -o -iname "*zustellung*" -o -iname "*empfangsbekenntnis*" -o -iname "*eeb*"

# ---------------------------------------------------------------------
echo "2 · Berufungsbegruendung — Erst- und Nachreichung"
echo "======================================================================"
echo "Entscheidend ist das FORMAT. Gleicher Name, .docx und .pdf nebeneinander"
echo "waere der Kern des Falls."
echo
suche "2a · Berufungsbegruendung"  -iname "*berufungsbegr*"
suche "2b · Berufung allgemein"    -iname "*berufung*" ! -iname "*berufungsbegr*"
suche "2c · Nachreichung / Wiederholung" -iname "*nachreich*" -o -iname "*erneut*" -o -iname "*korrigiert*" -o -iname "*neu_*"

# ---------------------------------------------------------------------
echo "3 · Gerichtlicher Hinweis nach § 130a Abs. 6 ZPO"
echo "======================================================================"
suche "3a · Hinweis / Verfuegung"  -iname "*hinweis*" -o -iname "*verfuegung*" -o -iname "*verfügung*"
suche "3b · Schreiben OLG Hamm"    -iname "*olg*" -o -iname "*hamm*" -o -iname "*25 U*" -o -iname "*25U*"

# ---------------------------------------------------------------------
echo "4 · Der Screenshot 0 von 0 Seiten"
echo "======================================================================"
suche "4a · Bilddateien"           -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.tiff" -o -iname "*screenshot*" -o -iname "*bildschirm*"

# ---------------------------------------------------------------------
echo "5 · Teilurteil und OLG Koeln"
echo "======================================================================"
suche "5a · Teilurteil"            -iname "*teilurteil*" -o -iname "*teil-urteil*"
suche "5b · Koeln"                 -iname "*koeln*" -o -iname "*köln*"

# ---------------------------------------------------------------------
echo "6 · Wiedereinsetzung — gibt es schon Entwuerfe?"
echo "======================================================================"
suche "6a · Wiedereinsetzung"      -iname "*wiedereinsetz*" -o -iname "*233*" -o -iname "*glaubhaftmach*"

# ---------------------------------------------------------------------
echo "7 · FORMATVERGLEICH — derselbe Name als DOCX und als PDF"
echo "======================================================================"
echo "Wenn ein Schriftsatz doppelt vorliegt, einmal .docx und einmal .pdf,"
echo "ist das der Ansatzpunkt fuer Erst- gegen Nachreichung."
echo
/usr/bin/python3 - "$D" <<'PYEOF'
import os, sys, collections
wurzel = sys.argv[1]
stamm = collections.defaultdict(set)
pfade = collections.defaultdict(list)
for dirpath, dirnames, filenames in os.walk(wurzel):
    for f in filenames:
        if f.startswith("._"):
            continue
        name, ext = os.path.splitext(f)
        ext = ext.lower()
        if ext in (".docx", ".pdf", ".doc"):
            stamm[name.lower()].add(ext)
            pfade[name.lower()].append(os.path.join(dirpath, f).replace(wurzel + "/", ""))

treffer = {k: v for k, v in stamm.items() if len(v) > 1}
print(f"   Namen, die als DOCX und PDF vorliegen: {len(treffer)}")
print()
interessant = [k for k in treffer if any(w in k for w in
               ("berufung", "begr", "schriftsatz", "ss_", "erwiderung", "antrag"))]
if interessant:
    print(f"   Davon mit Bezug zu Schriftsatz oder Berufung: {len(interessant)}")
    for k in sorted(interessant)[:20]:
        print(f"   * {k}   {sorted(stamm[k])}")
        for p in pfade[k][:4]:
            print(f"       {p}")
else:
    print("   Keiner davon mit Bezug zu Schriftsatz oder Berufung.")
PYEOF

# ---------------------------------------------------------------------
echo
echo "======================================================================"
echo "Bericht: $BER"
echo "======================================================================"
echo
cat <<'GRENZE'
GRENZE DIESES BEFUNDS

Geprueft wurde ausschliesslich, OB eine Datei mit passendem Namen auf der
Platte liegt. NICHT geprueft wurde, was darin steht.

Ein Dateiname ist kein Beweis. Ein Treffer bedeutet: es lohnt sich
hineinzusehen. Kein Treffer bedeutet: unter diesem Namen liegt hier nichts
-- die Datei kann anders heissen oder ausserhalb der Platte liegen, etwa
im beA-Postfach selbst.

Der wichtigste moegliche Befund ist Abschnitt 1. Fehlen beA-Export, OSCI
und Signatur vollstaendig, dann entscheidet keine Rechtsprechung den Fall,
solange niemand diese Dateien aus dem beA holt. Das hat eine Frist.
GRENZE
