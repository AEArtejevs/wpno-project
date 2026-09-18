"""Redaction of confidential material before it reaches a report.

Client documents enter some audits as operator-supplied references. Their
content must not leave the evidence directory. Enforced here, in code, rather
than by remembering.

Redaction is deliberately blunt. A redactor that tries to be clever produces
output that is sometimes still readable, and 'sometimes' is not a property a
confidentiality control may have.

Stability of the output is part of the contract. The predecessor package ran
one regular expression after another over the whole text, so the IBAN rule
wrote `[REDACTED:IBAN]` and the BIC rule, arriving later, matched the eight
capital letters of the word REDACTED inside it and produced
`[[REDACTED:BIC]:IBAN]`. A marker that a later rule rewrites is not a marker.

Two properties are therefore enforced here:

* **One pass.** All patterns live in a single alternation with named groups and
  a callback. Nothing this function writes is ever examined again in the same
  pass, because the pass has already moved past it.
* **Markers are inert.** An already-written marker is the first alternative in
  the alternation and is returned verbatim. Running redaction twice therefore
  yields exactly what running it once yielded.
"""

import re

MARKER_TEMPLATE = "[REDACTED:%s]"

# The exact markers the rest of the package, its tests and its reports depend
# on. They are listed rather than derived so a change to one of them is a
# visible change to this tuple.
MARKERS = (
    "[REDACTED:IBAN]",
    "[REDACTED:TAXID]",
    "[REDACTED:BIC]",
    "[REDACTED:EMAIL]",
    "[REDACTED:PHONE]",
    "[REDACTED:LONGDIGIT]",
)

# Order matters: longer, more specific patterns first, so a broader pattern
# does not consume part of a match a narrower one would have caught whole.
# Within one alternation Python tries the alternatives left to right at each
# starting position, so this ordering has exactly the meaning it had when the
# patterns were applied one after another.
PATTERNS = (
    ("IBAN", r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b"),
    ("TAXID", r"\b\d{11}\b"),
    ("BIC", r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ("PHONE", r"(?<![\w-])\+?\d[\d\s/().-]{7,17}\d(?![\w-])"),
    ("LONGDIGIT", r"\b\d{9,}\b"),
)

KINDS = tuple(kind for kind, _ in PATTERNS)

# The marker guard is first on purpose. Everything after it is a rule that
# rewrites text; this one alone hands text back unchanged.
_MARKER_GROUP = "MARKER"
_MARKER_PATTERN = r"\[REDACTED:[A-Z]+\]"

COMBINED = re.compile(
    "|".join(
        ["(?P<%s>%s)" % (_MARKER_GROUP, _MARKER_PATTERN)]
        + ["(?P<%s>%s)" % (kind, pattern) for kind, pattern in PATTERNS]
    )
)

MAX_QUOTE_CHARS = 120


class RedactionError(Exception):
    pass


def redact(text):
    """Return (redacted_text, counts_by_kind).

    One pass over the input. The callback never inspects what it has already
    written, and an existing marker is copied through untouched, so the result
    is idempotent: redacting a redacted string returns that string.
    """
    if text is None:
        return None, {}
    if not isinstance(text, str):
        raise RedactionError("redact expects str, got %r" % type(text))

    counts = {}

    def replace(match):
        kind = match.lastgroup
        if kind == _MARKER_GROUP:
            return match.group(0)
        counts[kind] = counts.get(kind, 0) + 1
        return MARKER_TEMPLATE % kind

    out = COMBINED.sub(replace, text)
    return out, counts


def redact_structure(obj):
    """Redact every string in a nested structure, keys included."""
    if isinstance(obj, str):
        return redact(obj)[0]
    if isinstance(obj, list):
        return [redact_structure(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(redact_structure(x) for x in obj)
    if isinstance(obj, dict):
        return {redact_structure(k): redact_structure(v) for k, v in obj.items()}
    return obj


def safe_quote(text, limit=MAX_QUOTE_CHARS):
    """A bounded, redacted excerpt for a report.

    Truncation is always marked. An excerpt that looks complete and is not is
    worse than no excerpt.
    """
    redacted, _ = redact(text or "")
    if len(redacted) <= limit:
        return redacted
    return redacted[:limit] + "… [TRUNCATED, full text in evidence]"


def assert_clean(text):
    """Raise if anything the patterns recognise survives in the text."""
    _, counts = redact(text)
    if counts:
        raise RedactionError(
            "text still contains material matching %s" % sorted(counts))
    return True
