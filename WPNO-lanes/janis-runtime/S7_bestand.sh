#!/bin/bash
# S7_bestand.sh — Was fehlt, damit ChatGPT die Festplatte lesen kann
#
# =====================================================================
# S7 aus dem Stufenplan der Gleichstellung 1.1: lokalen Codex-Lesezugriff
# auf einen begrenzten Ordner einrichten. S7 haengt an O-6: Codex ist
# nicht installiert, das Berechtigungsprofil fehlt.
#
# Dieses Skript richtet nichts ein. Es stellt fest, was fehlt.
# Es schreibt nichts auf die Festplatte und aendert nichts.
#
# Aufruf:  cd
#          bash WPNO/S7_bestand.sh
# Dauer:   unter einer Minute
# =====================================================================

set -u
BER="$HOME/S7_BESTAND_$(date +%Y-%m-%d_%H%M).txt"
exec > >(tee "$BER") 2>&1

FEHLT=0
merke() { echo "   FEHLT: $1"; FEHLT=$((FEHLT+1)); }

echo "S7 BESTANDSAUFNAHME  $(date '+%Y-%m-%d %H:%M')"
echo "======================================================================"

# ---------------------------------------------------------------------
echo
echo "1 · EXTERNE FESTPLATTE"
echo "----------------------------------------------------------------------"
DISK=$(ls -d /Volumes/Klage* 2>/dev/null | head -1)
if [ -z "$DISK" ]; then
  echo "   Volumes vorhanden:"
  ls /Volumes 2>&1 | sed 's|^|      |'
  merke "Platte 'Klage H&R' ist nicht eingebunden — bitte anschliessen"
else
  echo "   Pfad     : $DISK"
  df -h "$DISK" 2>/dev/null | tail -1 | awk '{print "   Groesse  : "$2"   belegt "$3"   frei "$4}'
  echo -n "   Lesetest : "
  if ls "$DISK" >/dev/null 2>&1; then echo "ok"; else echo "FEHLGESCHLAGEN"; merke "Leserecht auf die Platte"; fi
  echo "   Oberste Ebene:"
  ls "$DISK" 2>/dev/null | head -25 | sed 's|^|      |'
fi

# ---------------------------------------------------------------------
echo
echo "2 · DIE ZWEI AKTEN — wo liegen sie?"
echo "----------------------------------------------------------------------"
if [ -n "$DISK" ]; then
  echo "   Kandidaten Gerichtsakte:"
  find "$DISK" -maxdepth 3 -type d \( -iname "*gerichtsakte*" -o -iname "*GA*" \) 2>/dev/null | head -10 | sed 's|^|      |'
  echo "   Kandidaten Rechtsanwaltsakte:"
  find "$DISK" -maxdepth 3 -type d \( -iname "*anwalt*" -o -iname "*handakte*" -o -iname "*schriftsaetze*" \) 2>/dev/null | head -10 | sed 's|^|      |'
  echo "   Vorhandenes Register:"
  ls -la "$DISK/00_REGISTER" 2>&1 | head -15 | sed 's|^|      |'
fi

# ---------------------------------------------------------------------
echo
echo "3 · ZUSTAND DER PLATTE — Stand jetzt, nicht Stand 13.08."
echo "----------------------------------------------------------------------"
if [ -n "$DISK" ]; then
  echo -n "   Nutzdateien       : "; find "$DISK" -type f ! -name "._*" 2>/dev/null | wc -l | tr -d ' '
  echo -n "   AppleDouble-Reste : "; find "$DISK" -type f -name "._*" 2>/dev/null | wc -l | tr -d ' '
  echo -n "   Pfade mit Doppelp.: "; find "$DISK" -name "*:*" 2>/dev/null | wc -l | tr -d ' '
  echo -n "   Pfade mit Und-Z.  : "; find "$DISK" -name "*&*" 2>/dev/null | wc -l | tr -d ' '
  echo -n "   DOCX / PDF / XLSX : "
  echo -n "$(find "$DISK" -iname "*.docx" ! -name "._*" 2>/dev/null | wc -l | tr -d ' ') / "
  echo -n "$(find "$DISK" -iname "*.pdf"  ! -name "._*" 2>/dev/null | wc -l | tr -d ' ') / "
  echo    "$(find "$DISK" -iname "*.xlsx" ! -name "._*" 2>/dev/null | wc -l | tr -d ' ')"
fi

# ---------------------------------------------------------------------
echo
echo "4 · CODEX — installiert?"
echo "----------------------------------------------------------------------"
for w in node npm codex; do
  P=$(command -v $w 2>/dev/null)
  if [ -n "$P" ]; then printf "   %-6s %s\n" "$w" "$P"; else printf "   %-6s FEHLT\n" "$w"; fi
done
[ -z "$(command -v node)" ] && merke "node — ohne node kein Codex CLI"
[ -z "$(command -v codex)" ] && merke "codex CLI — das ist O-6"
command -v codex >/dev/null 2>&1 && { echo -n "   Version: "; codex --version 2>&1 | head -1; }
echo "   Konfiguration:"
ls -la "$HOME/.codex/" 2>&1 | head -10 | sed 's|^|      |'
[ ! -d "$HOME/.codex" ] && merke "Berechtigungsprofil ~/.codex — das ist der zweite Teil von O-6"

# ---------------------------------------------------------------------
echo
echo "5 · CHATGPT DESKTOP — vorhanden?"
echo "----------------------------------------------------------------------"
if [ -d "/Applications/ChatGPT.app" ]; then
  echo -n "   ChatGPT.app  : vorhanden, Version "
  /usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" \
    "/Applications/ChatGPT.app/Contents/Info.plist" 2>/dev/null || echo "unbekannt"
else
  echo "   ChatGPT.app  : FEHLT"
  merke "ChatGPT Desktop — ohne sie kein Modus 'Work locally'"
fi

# ---------------------------------------------------------------------
echo
echo "6 · LIBRA-MCP — laeuft er wirklich?"
echo "----------------------------------------------------------------------"
if [ -d "$HOME/.cache/libra-mcp" ]; then
  echo "   Cache        : vorhanden"
  du -sh "$HOME/.cache/libra-mcp" 2>/dev/null | sed 's|^|      |'
  ls -lt "$HOME/.cache/libra-mcp" 2>/dev/null | head -5 | sed 's|^|      |'
else
  echo "   Cache        : nicht unter ~/.cache/libra-mcp"
  merke "Libra-MCP-Cache am dokumentierten Ort — Angabe aus Anlage A pruefen"
fi
echo "   Prozess:"
ps aux 2>/dev/null | grep -i "libra" | grep -v grep | head -5 | sed 's|^|      |'
echo "   MCP-Konfigurationen:"
find "$HOME" -maxdepth 4 -type f \( -name "*mcp*.json" -o -name "mcp.json" \) 2>/dev/null | grep -v Library/Caches | head -10 | sed 's|^|      |'

# ---------------------------------------------------------------------
echo
echo "7 · WAS NUR MARTIN SELBST TUN KANN"
echo "----------------------------------------------------------------------"
cat <<'HINWEIS'
   Diese zwei Punkte gehen nicht ueber das Terminal. Sie brauchen
   zwei Klicks in den Systemeinstellungen:

   Systemeinstellungen  ->  Datenschutz & Sicherheit
      -> Festplattenvollzugriff   : Terminal aktivieren
      -> Wechseldatentraeger      : Terminal erlauben

   Ohne diese beiden Freigaben liest kein Werkzeug die externe Platte,
   egal wie gut es eingerichtet ist.
HINWEIS

# ---------------------------------------------------------------------
echo
echo "======================================================================"
echo "OFFENE PUNKTE: $FEHLT"
echo "Bericht      : $BER"
echo "======================================================================"
