"""L1-A18 RUN-A: IBAN validation against REF-01, in Python.

The method, stated so RUN-B can be compared against it rather than merely
agree with it:

  * normalization is REF-02's own `compact()` - strip spaces, hyphens and
    dots, then uppercase - applied explicitly and recorded per result;
  * the country code must appear in the REF-01 registry. An unknown country
    is not a validation failure of the check digits; it is a different answer
    and is reported as its own reason;
  * the length must equal the REF-01 `IBAN length` for that country;
  * the BBAN must match the REF-01 `BBAN structure` for that country,
    interpreted token by token;
  * the check digits are verified by ISO/IEC 7064 MOD97-10, computed
    character by character in a streaming fold.

The MOD97-10 fold never materialises the ~30-digit integer. It carries a
remainder below 97 and folds each character into it: one decimal digit
multiplies by 10, one letter expands to two digits and multiplies by 100.
This is deliberately a different shape of computation from RUN-B's, which
builds the expanded digit string and takes one big-integer modulus. Two
implementations that agree because they are the same implementation twice
prove nothing.

RUN-A imports nothing from RUN-B, calls nothing in RUN-B, and reads no RUN-B
output. It does not know RUN-B exists.
"""

import json
import os

from . import path_policy

SEPARATORS = " -."
NORMALIZATION = "clean(number, ' -.').strip().upper()"

# REF-01 structure tokens. `!` means a fixed length, not a maximum.
CHARACTER_CLASSES = {
    "n": "0123456789",
    "a": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "c": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
}

RULES_PATH = os.path.join(path_policy.LEVEL1_ROOT, "corpora",
                          "R5_REF01_COUNTRY_RULES.jsonl")


class ValidatorError(Exception):
    pass


def load_rules(path=None):
    """The REF-01 country rules, as an immutable mapping."""
    target = path_policy.assert_readable(path or RULES_PATH)
    rules = {}
    with open(target, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rules[record["country_code"]] = record
    if not rules:
        raise ValidatorError("REF-01 country rules are empty: %s" % target)
    return rules


def normalize(value):
    """REF-02's `compact()`, reproduced. Explicit, never implied."""
    if not isinstance(value, str):
        raise ValidatorError("IBAN must be a string")
    out = value
    for ch in SEPARATORS:
        out = out.replace(ch, "")
    return out.strip().upper()


def parse_structure(structure):
    """`4!n4!n12!c` -> [(4, 'n'), (4, 'n'), (12, 'c')].

    Parsed by walking the string. A regular expression here would need `+` on
    the length group, and a pattern that quietly matched only the first digit
    of a two-digit length would produce a structure that accepts the wrong
    number of characters while looking correct.
    """
    tokens = []
    i = 0
    while i < len(structure):
        digits = ""
        while i < len(structure) and structure[i].isdigit():
            digits += structure[i]
            i += 1
        if not digits:
            raise ValidatorError("structure token has no length: %r" % structure)
        if i >= len(structure) or structure[i] != "!":
            raise ValidatorError("structure token is not fixed-length: %r"
                                 % structure)
        i += 1
        if i >= len(structure):
            raise ValidatorError("structure token has no class: %r" % structure)
        cls = structure[i]
        if cls not in CHARACTER_CLASSES:
            raise ValidatorError("unknown character class %r in %r"
                                 % (cls, structure))
        i += 1
        tokens.append((int(digits), cls))
    if not tokens:
        raise ValidatorError("empty structure")
    return tokens


def matches_structure(value, structure):
    """Walk `value` against the parsed tokens. No regular expression."""
    tokens = parse_structure(structure)
    expected = sum(length for length, _ in tokens)
    if len(value) != expected:
        return False, "length %d does not match structure length %d" % (
            len(value), expected)
    pos = 0
    for length, cls in tokens:
        allowed = CHARACTER_CLASSES[cls]
        for _ in range(length):
            if value[pos] not in allowed:
                return False, ("character %r at position %d is not %s"
                               % (value[pos], pos + 1, cls))
            pos += 1
    return True, "matches %s" % structure


def mod97_10_streaming(value):
    """ISO/IEC 7064 MOD97-10, folded character by character.

    The remainder never exceeds 96, so nothing here depends on arbitrary
    precision arithmetic. A valid IBAN leaves a remainder of 1.
    """
    remainder = 0
    for ch in value:
        if "0" <= ch <= "9":
            remainder = (remainder * 10 + (ord(ch) - 48)) % 97
        elif "A" <= ch <= "Z":
            remainder = (remainder * 100 + (ord(ch) - 55)) % 97
        else:
            raise ValidatorError(
                "character %r cannot appear in a MOD97-10 computation" % ch)
    return remainder


def validate(raw, rules):
    """Return a result dictionary. Never raises on an invalid IBAN.

    An invalid IBAN is the answer, not an error. Raising would make "this
    number is bad" indistinguishable from "the validator broke".
    """
    result = {
        "input": raw,
        "normalization": NORMALIZATION,
        "run_phase": "RUN-A",
        "method": "PYTHON_STREAMING_MOD97_10_WITH_REF01_RULES",
    }
    try:
        iban = normalize(raw)
    except ValidatorError as exc:
        result.update(normalized=None, result="INVALID", reason=str(exc))
        return result
    result["normalized"] = iban

    if len(iban) < 4:
        result.update(result="INVALID", reason="SHORTER_THAN_FOUR_CHARACTERS")
        return result

    for ch in iban:
        if not (("0" <= ch <= "9") or ("A" <= ch <= "Z")):
            result.update(result="INVALID",
                          reason="ILLEGAL_CHARACTER:%r" % ch)
            return result

    country = iban[:2]
    if not country.isalpha():
        result.update(result="INVALID", reason="COUNTRY_CODE_NOT_ALPHABETIC")
        return result
    result["country"] = country

    rule = rules.get(country)
    if rule is None:
        result.update(result="INVALID", reason="UNKNOWN_COUNTRY_CODE")
        return result

    if not (iban[2].isdigit() and iban[3].isdigit()):
        result.update(result="INVALID", reason="CHECK_DIGITS_NOT_NUMERIC")
        return result

    if len(iban) != rule["iban_length"]:
        result.update(result="INVALID",
                      reason="LENGTH_%d_EXPECTED_%d" % (len(iban),
                                                        rule["iban_length"]))
        return result

    ok, detail = matches_structure(iban[4:], rule["bban_structure"])
    if not ok:
        result.update(result="INVALID", reason="BBAN_STRUCTURE:%s" % detail)
        return result

    remainder = mod97_10_streaming(iban[4:] + iban[:4])
    result["mod97_remainder"] = remainder
    if remainder != 1:
        result.update(result="INVALID",
                      reason="MOD97_10_REMAINDER_%d_EXPECTED_1" % remainder)
        return result

    result.update(result="VALID", reason="ALL_REF01_RULES_SATISFIED")
    return result


def validate_all(values, rules=None):
    rules = rules or load_rules()
    return [validate(v, rules) for v in values]
