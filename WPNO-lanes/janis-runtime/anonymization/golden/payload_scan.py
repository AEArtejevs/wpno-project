"""
WPNO -- Anonimizacijas vartu lokala payload parbaude (AP-03 / dokumenta V-6 Stage 1).
Otrais aizsardzibas slanis pirms izejosajiem izsaukumiem (LiteLLM pre_call_hook).
Fail-closed: ja atrasts jebkas aizdomigs, izsaukums tiek BLOKETS (K1 / K4).

PIEZIME: sis implemente V-6 Stage 1 (lokala deterministiska regex parbaude). Stage 2
(Libra ki_anonymize semantiska parbaude, residual_score, post-check scan) SIT NAV
implementets -- tas prasa dzivu Libra MCP pieeju. Tas ir apzinats, dokumentets
atlikums, nevis izlaidums.

AP-03 paplasinajums (2026-07-20): papildus dokumenta 4 pamattipiem (iban, steuid,
az, party) tagad tiek parbauditi: email, phone, bic, name, company, address.
Deterministiska regex parbaude nevar perfekti atpazit VISUS personvardus bez
konteksta (vacu valoda visi lietvardi ir ar lielo burtu) -- "name" tips tapec
strada ar (a) uzrunam/titula prieksvardiem (Herr/Frau/Dr./RA/...) un (b)
party_names.json sarakstu. Pilna semantiska NER paliek Stage 2 (Libra/Presidio).
"""

import os
import re
import json
import sqlite3
import hashlib
import datetime
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# AP-03 Gremium-Audit 2026-07-21: Unicode-/Fail-closed-Haertung.
# Behebt bestaetigte Bypaesse (P1 Homoglyph/Zero-Width/Case, P2 Non-str-raise,
# P2/P5 ReDoS). Detektion laeuft auf normalisiertem Text; Offsets/Spans beziehen
# sich damit auf den NORMALISIERTEN Text (nicht das Original) -- fuer die reine
# BLOCK-Entscheidung des Egress-Gate irrelevant, fuer kuenftiges Stage-2-Redaction
# ausdruecklich zu beachten.
# ---------------------------------------------------------------------------

# SQLite nedrikst dzivot uz single-file bind mount (macOS virtiofs -> "disk I/O error").
# Tapec ledger vienmer atrodas direktorija, kas tiek montets ka direktorijs.
LEDGER_DIR = Path(os.environ.get("WPNO_LEDGER_DIR", str(Path(__file__).parent / "ledger_data")))
LEDGER_DB = LEDGER_DIR / "ledger.db"

PARTY_NAMES_FILE = Path(__file__).parent / "party_names.json"

# Obergrenze fuer die zu scannende Textlaenge. Darueber wird fail-closed
# geblockt (Scan nicht garantierbar). 1 MB Text ~ jenseits jedes Modellkontexts.
MAX_SCAN_CHARS = 1_000_000

# Haeufige Cyrillic-/Greek-Homoglyphen -> Latein (Confusable-Folding fuer die
# Detektion). Kein Anspruch auf Vollstaendigkeit der Unicode-Confusables-Tabelle;
# deckt die im Audit belegten Bypass-Primitive ab.
_CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "ԛ": "q", "ԝ": "w", "н": "h", "к": "k",
    "м": "m", "т": "t", "в": "b",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ј": "J",
    "ο": "o", "Ο": "O", "α": "a", "Α": "A", "ε": "e", "Ε": "E", "ρ": "p",
    "Ρ": "P", "τ": "t", "Τ": "T", "υ": "y", "Υ": "Y", "χ": "x", "Χ": "X",
    "κ": "k", "Κ": "K", "Μ": "M", "Ν": "N", "Β": "B", "Ζ": "Z", "Η": "H",
    "Ι": "I",
}
_CONFUSABLE_TABLE = {ord(k): v for k, v in _CONFUSABLES.items()}


def normalize_for_scan(text):
    """NFKC + Zero-Width-/Format-Strip + Confusable-Folding.

    NFKC faltet Fullwidth/Kompatibilitaetszeichen (ＤＥ８９ -> DE89). Danach
    werden Zero-Width-/Format-Zeichen (Unicode-Kategorie Cf, inkl. U+200B/C/D,
    U+FEFF, U+2060) und der Soft-Hyphen U+00AD entfernt, die Regex-`\\s` NICHT
    matcht und die sonst IBAN/Telefon zerbrechen. Zuletzt Homoglyph-Folding.
    """
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ch in text:
        if ch == "­" or unicodedata.category(ch) == "Cf":
            continue  # Soft-Hyphen + Format/Zero-Width-Zeichen verwerfen
        out.append(ch)
    text = "".join(out)
    return text.translate(_CONFUSABLE_TABLE)


_PARTY_RAW = []


def _load_party_names():
    """party_names.json (ja eksiste) + dokumenta hardcoded fallback saraksts."""
    names = ["H&R", "Hoffmann & Reuter", "Latham & Watkins"]
    try:
        raw = PARTY_NAMES_FILE.read_text(encoding="utf-8-sig")
        extra = json.loads(raw).get("names", [])
        for n in extra:
            if n and n not in names:
                names.append(n)
    except (OSError, ValueError):
        pass
    # garakos vispirms, lai "H&R Group" uzvar pret "H&R"
    names.sort(key=len, reverse=True)
    global _PARTY_RAW
    _PARTY_RAW = list(names)
    alternation = "|".join(re.escape(n).replace(r"\ ", r"\s?") for n in names)
    return re.compile(r"\b(?:" + alternation + r")\b", re.IGNORECASE)


# Uzrunas/tituli, kas ievada personvardu (name-tipa trigeris)
_TITLES = (
    r"Herr(?:n)?|Frau|Dr\.|Prof\.|RA|RAin|StB|WP|"
    r"Rechtsanwalt|Rechtsanw[aä]ltin|Steuerberater(?:in)?|"
    r"Wirtschaftspr[uü]fer(?:in)?|Gesch[aä]ftsf[uü]hrer(?:in)?|"
    r"Notar(?:in)?|Richter(?:in)?|Zeug(?:e|in)|Mandant(?:in)?|Insolvenzverwalter(?:in)?"
)

# Vacu juridiskas formas (company-tipa enkurs)
_LEGAL_FORMS = (
    r"GmbH\s*&\s*Co\.?\s*KG(?:aA)?|gGmbH|GmbH|mbH|AG|SE|KGaA|KG|OHG|oHG|"
    r"UG(?:\s*\(haftungsbeschr[aä]nkt\))?|e\.\s?K\.|e\.\s?V\.|eG|GbR|mbB|"
    r"PartG(?:G)?(?:\s?mbB)?|Rechtsanwaltsgesellschaft|Steuerberatungsgesellschaft|"
    r"Wirtschaftspr[uü]fungsgesellschaft"
)

# Latein-Buchstabenklassen inkl. akzentuierter Zeichen (P1-1: FR/ES/PT/skand./
# poln. Diakritika). Gross-/Kleinbuchstaben getrennt fuer die Namensheuristik.
_U = "A-ZÄÖÜÀ-ÖØ-Þ"           # Latin-1/Latin-Extended Grossbuchstaben-Bereiche
_L = "a-zäöüßà-öø-ÿ"          # Latein-Kleinbuchstaben inkl. Akzente
_APOS = "'’ʼ"                 # ASCII + typografischer Apostroph + modifier letter

# IGNORECASE: IBAN/BIC/name/az werden case-insensitiv gematcht (P1-2).
_IC = re.IGNORECASE

# Precizi paterni: dokumenta 4 pamattipi + AP-03 paplasinajums.
PATTERNS = {
    "iban": [re.compile(r"\bDE\d{2}(?:\s?\d){18}\b", _IC)],
    "steuid": [re.compile(r"\b\d{2}/\d{3}/\d{5}\b")],
    # AP-03 fix (2026-08-04, audit F-AP03-04): "steuid" oben trifft die
    # STEUERNUMMER (12/345/67890). Die elfstellige Steuer-IDENTIFIKATIONS-
    # nummer ist ein anderes Format und war damit ungedeckt -- gemessen
    # 0 von 20 im Golden-Set. Eigenes Muster mit Pruefziffer (ISO 7064
    # MOD 11,10); ohne die Pruefziffer waere jeder elfstellige Zeitstempel
    # ein Treffer.
    "steuid11": [re.compile(r"(?<!\d)\d{11}(?!\d)")],
    # AP-03 fix (2026-08-04, audit F-AP03-05): "iban" oben deckt nur DE ab.
    # Ein lettisches, oesterreichisches oder Schweizer Konto blieb unerkannt.
    # Das bestehende DE-Muster bleibt UNVERAENDERT (es blockt auch bei
    # falscher Pruefsumme -- fail-closed). Dieses Muster kommt additiv dazu
    # und verlangt Mod-97, damit Beispiel-IBANs aus Anleitungen nicht
    # dauernd Alarm ausloesen.
    "iban_intl": [re.compile(r"\b(?!DE)[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b", _IC)],
    # AP-03 fix (2026-07-28, audit F-AP03-01): the leading token may be an
    # arabic register number (BVerfG "1 BvR 2/26") OR a Roman-numeral BGH senate
    # ("IX ZR 140/19", "VIII ZR 1/23"). The rigid <token> <letters> <num>/<yy>
    # tail keeps false positives negligible.
    "az": [re.compile(r"\b(?:\d{1,3}|[IVXLCDM]{1,5})\s?[A-Z]{1,3}\s?\d{1,5}/\d{2}\b", _IC)],
    "party": [_load_party_names()],
    # --- AP-03 paplasinajums ---
    # AP-03 fix (2026-07-28, audit F-AP03-02): local part may start with a
    # non-ASCII letter (e.g. "büro@notar.de"); the leading \b before an ASCII
    # class skipped it. Drop the leading \b and widen the local-part class to
    # include accented Latin letters (_L/_U). Fail-closed direction only.
    "email": [re.compile(r"[A-Za-z0-9._%+" + _L + _U + r"-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", _IC)],
    "phone": [
        # ReDoS-gehaertet (P2-2): feste Trennzeichen in der Wiederholung.
        # AP-03 fix (2026-07-28, audit F-AP03-03): accept the German "(0)"
        # national-prefix notation "+49 (0)211 4933-0" (fixed optional group,
        # no new backtracking).
        re.compile(r"(?<![\d/])(?:\+49|0049)[\s\-/]?(?:\(0\)[\s\-/]?)?\(?\d{2,5}\)?(?:[\s\-/]\d{1,8}){1,6}(?![\d/])"),
        re.compile(r"(?<![\d/.,])\(?0\d{2,4}\)?[\s\-/]\d{3,8}(?:[\s\-/]\d{1,6}){0,3}(?![\d/])"),
    ],
    "bic": [re.compile(r"\b([A-Za-z]{4})([A-Za-z]{2})([A-Za-z0-9]{2})(?:[A-Za-z0-9]{3})?\b")],
    "name": [
        re.compile(
            r"\b(?:" + _TITLES + r")\s+(?:(?:Dr\.|Prof\.)\s+){0,2}"
            r"(?:von|van|de|del|della|der|zu|zur|den|ten|ter|di|da|dos|das|le|la|el|bin|al)?\s*"
            r"[" + _U + r"][" + _L + _APOS + r"]+"
            r"(?:[-\s](?:von|van|de|del|della|der|zu|den|ten|ter|di|da|le|la)?\s*[" + _U + r"][" + _L + _APOS + r"]+){0,3}\b",
            _IC,
        ),
    ],
    # company: anker-basierter Python-Detektor (_scan_company) -> garantiert linear.
    "address": [
        # iela + numurs; Wort-Wiederholung hart begrenzt {0,6} gegen quadr. Backtracking.
        re.compile(
            r"\b[" + _U + r"][\w" + _L + r"]*(?:[-\s][" + _U + _L + r"][\w" + _L + r"]*){0,6}[\s-]?"
            r"(?:[Ss]tra[sß]e|[Ss]tr\.|[Ww]eg|[Aa]llee|[Pp]latz|[Gg]asse|[Rr]ing|[Dd]amm|[Uu]fer|[Cc]haussee)"
            r"\s+\d{1,4}\s?[a-hA-H]?\b"
        ),
        re.compile(r"\b\d{5}\s+[" + _U + r"][" + _L + r"]+(?:[-\s][" + _U + r"][" + _L + r"]+){0,2}\b"),
    ],
}

_BIC_COUNTRIES = {
    "DE", "AT", "CH", "FR", "GB", "NL", "BE", "LU", "IT", "ES", "PT", "PL",
    "CZ", "DK", "SE", "NO", "FI", "IE", "US", "LI", "MT", "CY", "GR", "HU",
    "SK", "SI", "EE", "LV", "LT", "RO", "BG", "HR",
}

_COMPANY_STOPWORDS = {
    "die", "der", "das", "den", "dem", "des", "eine", "einer", "einem",
    "einen", "diese", "dieser", "dieses", "jede", "jeder", "jedes", "keine",
    "als", "zur", "zum", "und", "oder",
}

_ADDRESS_STOPWORDS = {"euro", "eur", "prozent", "stunden", "seiten", "mitarbeiter"}


def _validate_bic(m):
    # AP-03 fix (2026-07-27, revised): the original regex only checked that
    # positions 5-6 of an 8/11-char word form a valid ISO country code,
    # which false-positively matched ordinary German words (e.g. "Wieviele"
    # -> group(2)="ie" -> "IE"). A first attempt required the whole match to
    # be uppercase, but that broke the deliberate case-evasion regression
    # test (a real BIC typed in lowercase, e.g. "bic deutdeff nutzen", must
    # still be blocked). Instead, require a nearby banking-context keyword
    # within a small window -- present in every real BIC mention, absent
    # from incidental German words like "Datenbank" that merely end in a
    # bank-like substring much further away.
    if m.group(2).upper() not in _BIC_COUNTRIES:
        return False
    window_start = max(0, m.start() - 20)
    window_end = min(len(m.string), m.end() + 20)
    context = m.string[window_start:window_end].lower()
    keywords = ("bic", "swift", "iban", "konto", "bankleitzahl", "blz",
                "bank", "ueberweisung", "überweisung")
    return any(kw in context for kw in keywords)


def _validate_steuid11(m):
    """ISO 7064 MOD 11,10 -- die Pruefziffer der deutschen Steuer-ID."""
    k = m.group(0)
    produkt = 10
    for z in k[:10]:
        summe = (int(z) + produkt) % 10
        if summe == 0:
            summe = 10
        produkt = (summe * 2) % 11
    return (11 - produkt) % 10 == int(k[10])


def _validate_iban_intl(m):
    """AP-24 Fix (05.08.2026, Audit F-AP24-03).

    Die Regex ist gierig und schluckt nachfolgende grossgeschriebene Woerter:
    aus "LV80BANK0000435195001 bei der Bank." wird der Treffer
    "LV80BANK0000435195001 bei der Bank" -- Mod-97 scheitert daran, und der
    Fund wird STILL VERWORFEN. Eine echte IBAN mitten im Satz ging so
    unbemerkt hinaus. Das ist die gefaehrlichste Fehlerart, die dieser
    Scanner haben kann: er meldet nicht, dass er unsicher ist, er schweigt.

    Fail-closed heisst hier: Wenn der volle Treffer nicht validiert, wird
    von hinten Stueck fuer Stueck gekuerzt und erneut geprueft. Erst wenn
    KEINE Kuerzung eine gueltige IBAN ergibt, ist es keine.
    """
    if _iban_mod97_ok(m.group(0)):
        return True
    teile = m.group(0).split()
    while len(teile) > 1:
        teile.pop()
        if _iban_mod97_ok(" ".join(teile)):
            return True
    return False


def _iban_mod97_ok(roh):
    s = re.sub(r"\s", "", roh).upper()
    if not 15 <= len(s) <= 34:
        return False
    umgestellt = s[4:] + s[:4]
    ziffern = "".join(str(ord(z) - 55) if z.isalpha() else z for z in umgestellt)
    if not ziffern.isdigit():
        return False
    return int(ziffern) % 97 == 1


def _validate_iban_intl_ALT(m):
    """Mod-97 nach ISO 7064."""
    s = re.sub(r"\s", "", m.group(0)).upper()
    if not 15 <= len(s) <= 34:
        return False
    umgestellt = s[4:] + s[:4]
    ziffern = ""
    for z in umgestellt:
        if z.isdigit():
            ziffern += z
        elif z.isalpha():
            ziffern += str(ord(z) - 55)
        else:
            return False
    return int(ziffern) % 97 == 1


def _validate_address(m):
    words = re.split(r"\s+", m.group(0))
    if words and words[0].isdigit() and len(words) > 1:
        if words[1].lower().rstrip(".,") in _ADDRESS_STOPWORDS:
            return False
    return True


def _validate_phone(m):
    digits = re.sub(r"\D", "", m.group(0))
    return 8 <= len(digits) <= 15


_VALIDATORS = {
    "steuid11": _validate_steuid11,
    "iban_intl": _validate_iban_intl,
    "bic": _validate_bic,
    "address": _validate_address,
    "phone": _validate_phone,
}

# Anker fuer company: nur die Rechtsform (linear, selten). Der Namensteil davor
# wird in Python geprueft (bounded, kein Backtracking ueber Positionen) -> P5-F3.
_COMPANY_ANCHOR = re.compile(r"(?:" + _LEGAL_FORMS + r")(?=[\s,.;:)]|$)", _IC)
_COMPANY_WORD = re.compile(r"[" + _U + _L + r"0-9&.\-]+$")


# AP-03 fix (2026-08-04, audit F-AP03-06): der Parteinamen-Abgleich oben ist
# ein exaktes Alternativ-Muster. Er findet den Namen nicht mehr, sobald OCR ihn
# antastet -- gemessen 16 von 30 im Golden-Set. Durchgerutscht sind genau die
# Faelle, die das Premortem (Kap. 30.2) benennt: "Latham&Watkins" -> "Lath@m".
#
# Das Confusable-Folding in normalize_for_scan() hilft hier nicht: es faltet
# kyrillische und griechische Homoglyphen, nicht die Ersetzung eines Buchstabens
# durch ein Sonderzeichen und nicht auseinandergezogene Schrift.
#
# Deshalb ein eigener, linearer Scanner mit eigener Faltung. Er laeuft NUR fuer
# den Namensabgleich -- eine globale Ziffer-zu-Buchstabe-Faltung wuerde IBAN,
# Telefonnummer und Steuer-ID zerstoeren.
_OCR_ERSATZ = str.maketrans({
    "@": "a", "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "6": "g", "7": "t", "8": "b", "9": "g", "|": "l", "!": "i",
    "$": "s", "\u20ac": "e", "\u00a3": "l",
})


def _falten(s):
    """Nur Buchstaben, kleingeschrieben, OCR-Ersatzzeichen zurueckuebersetzt.
    Ziffern fallen weg: Namen enthalten keine, und was OCR aus einem "&" macht,
    soll den Namen nicht auseinanderreissen."""
    zerlegt = unicodedata.normalize("NFKD", s)
    ohne = "".join(c for c in zerlegt if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", ohne.lower().translate(_OCR_ERSATZ))


def _scan_party_ocr(text):
    """Findet Parteinamen auch dann, wenn OCR sie verstuemmelt oder die Schrift
    auseinandergezogen ist. Ergaenzt den exakten Abgleich, ersetzt ihn nicht."""
    if not _PARTY_RAW:
        return []
    gefaltet = _falten(text)
    if not gefaltet:
        return []
    treffer = []
    for name in _PARTY_RAW:
        kern = _falten(name)
        # Kurze Eintraege wuerden im zusammengezogenen Buchstabenstrom
        # zufaellig treffen und den Waechter unbrauchbar machen.
        if len(kern) < 6:
            continue
        stelle = gefaltet.find(kern)
        if stelle >= 0:
            treffer.append({"type": "party_ocr", "span": stelle})
            continue
        # Zweiter Anlauf: ein einzelnes verstuemmeltes Zeichen zwischen den
        # Wortteilen ("Latham 8 Watkins") zerreisst den zusammengezogenen
        # Vergleich. Dann muessen alle tragenden Woerter vorkommen, und zwar
        # nahe beieinander -- ohne die Naehebedingung wuerde ein Eintrag schon
        # ausloesen, wenn seine Woerter auf verschiedenen Seiten stehen.
        woerter = [w for w in (_falten(t) for t in name.split()) if len(w) >= 4]
        if len(woerter) < 2:
            continue
        stellen = {}
        for w in woerter:
            gefunden, ab = [], 0
            while True:
                i = gefaltet.find(w, ab)
                if i < 0:
                    break
                gefunden.append(i)
                ab = i + 1
            if not gefunden:
                break
            stellen[w] = gefunden
        if len(stellen) != len(woerter):
            continue
        fenster = 3 * sum(len(w) for w in woerter) + 20
        anker = max(woerter, key=len)
        for pos in stellen[anker]:
            if all(any(abs(q - pos) <= fenster for q in stellen[w])
                   for w in woerter):
                treffer.append({"type": "party_ocr", "span": pos})
                break
    return treffer


def _scan_company(text):
    """Findet Firmennamen linear: Rechtsform als Anker, dann bis zu 6 vorangehende
    namensartige Woerter zurueck. Ersetzt die frueher quadratische company-Regex."""
    hits = []
    for m in _COMPANY_ANCHOR.finditer(text):
        start = m.start()
        if start == 0 or not text[start - 1].isspace():
            continue  # Rechtsform muss durch Trennzeichen vom Vorwort getrennt sein
        prefix = text[:start].rstrip()
        words = prefix.split()
        name_words = []
        for w in reversed(words[-6:]):
            if _COMPANY_WORD.match(w) and w[0].isupper():
                name_words.insert(0, w)
            else:
                break
        while name_words and name_words[0].lower().rstrip(".,") in _COMPANY_STOPWORDS:
            name_words.pop(0)
        if name_words:
            hits.append({"type": "company", "span": max(0, start - 1 - len(" ".join(name_words)))})
    return hits


# PAPILDU paterni, kas NAV dokumenta specifikacija -- skaidri atdaliti.
EXTRA_PATTERNS = {
    "date_de": re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b"),
    "date_iso": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
}


def _init_ledger():
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS anon_ledger(
        id INTEGER PRIMARY KEY, akte_id TEXT, target TEXT,
        payload_hash TEXT, entities TEXT, residual REAL, modell TEXT, decision TEXT, ts TEXT)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS anon_map(
        payload_hash TEXT PRIMARY KEY, mapping_json TEXT)"""
    )
    conn.commit()
    conn.close()


def local_scan(text):
    """Scannt den (bereits normalisierten) Text. Spans beziehen sich auf den
    normalisierten Text -- siehe Modul-Kopf."""
    hits = []
    for label, patterns in PATTERNS.items():
        validator = _VALIDATORS.get(label)
        for pattern in patterns:
            for m in pattern.finditer(text):
                if validator is not None and not validator(m):
                    continue
                hits.append({"type": label, "span": m.start()})
    for label, pattern in EXTRA_PATTERNS.items():
        for m in pattern.finditer(text):
            hits.append({"type": label, "span": m.start()})
    hits.extend(_scan_company(text))  # anker-basiert, linear (P5-F3)
    hits.extend(_scan_party_ocr(text))  # F-AP03-06, eigene Faltung, linear
    return hits


def _sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _write_ledger(akte_id, target, payload_hash, entities, decision):
    """Best-effort-Audit-Log. Ein Fehler hier DARF die Block-Entscheidung nicht
    kippen (P2-4/P5-F4) -- er wird gefangen und nur signalisiert."""
    try:
        _init_ledger()
        conn = sqlite3.connect(LEDGER_DB)
        try:
            conn.execute(
                "INSERT INTO anon_ledger (akte_id, target, payload_hash, entities, residual, modell, decision, ts) VALUES (?,?,?,?,?,?,?,?)",
                (
                    akte_id, target, payload_hash, entities, None,
                    "stage1-local-only", decision,
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def scan_payload(text, akte_id="unknown", target="anthropic"):
    """
    Stage 1 TIKAI (lokala deterministiska parbaude). Stage 2 (Libra ki_anonymize)
    ir atlikts -- skat. moduļa docstring.

    Fail-closed-Vertrag (Gremium-Audit 2026-07-21):
    - Nicht-str / None / bytes / unerwarteter Typ  -> BLOCK (blocked=True), nie raise.
    - Text > MAX_SCAN_CHARS                         -> BLOCK (Scan nicht garantierbar).
    - Text wird VOR dem Scan normalisiert (Unicode/Homoglyph/Zero-Width).
    - Die Block-Entscheidung wird ZUERST bestimmt; das Ledger wird danach
      best-effort geschrieben und kann die Entscheidung nicht mehr aendern.
    """
    if text is None or not isinstance(text, str):
        payload_hash = _sha256(repr(type(text).__name__))
        entities = json.dumps(["__invalid_type__"])
        ledger_ok = _write_ledger(akte_id, target, payload_hash, entities, "BLOCK")
        return {"blocked": True, "findings": entities, "payload_hash": payload_hash,
                "hits": [{"type": "__invalid_type__", "span": 0}], "ledger_ok": ledger_ok}

    payload_hash = _sha256(text)  # Hash ueber Originaltext (Audit-Referenz)

    if len(text) > MAX_SCAN_CHARS:
        entities = json.dumps(["__oversize__"])
        ledger_ok = _write_ledger(akte_id, target, payload_hash, entities, "BLOCK")
        return {"blocked": True, "findings": entities, "payload_hash": payload_hash,
                "hits": [{"type": "__oversize__", "span": 0}], "ledger_ok": ledger_ok}

    scan_text = normalize_for_scan(text)
    hits = local_scan(scan_text)
    blocked = len(hits) > 0
    entities = json.dumps(sorted(set(h["type"] for h in hits)))

    ledger_ok = _write_ledger(akte_id, target, payload_hash, entities,
                              "BLOCK" if blocked else "PASS")

    return {
        "blocked": blocked,
        "findings": entities,
        "payload_hash": payload_hash,
        "hits": hits,
        "ledger_ok": ledger_ok,
    }


def egress_gate(text, akte_id="unknown", target="anthropic"):
    result = scan_payload(text, akte_id, target)
    if result["blocked"]:
        raise PermissionError(
            "ANON_GATE_BLOCK target=" + target + " pre=" + str(len(result["hits"]))
        )
    return text
