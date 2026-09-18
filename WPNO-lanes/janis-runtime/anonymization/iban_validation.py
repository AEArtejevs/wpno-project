"""ISO 13616 IBAN validation using SWIFT registry release 102 rules."""

import re


# country: (complete IBAN length, fixed BBAN structure)
RULES = {
    "AD": (24, "4!n4!n12!c"),
    "AE": (23, "3!n16!n"),
    "AL": (28, "8!n16!c"),
    "AT": (20, "5!n11!n"),
    "AZ": (28, "4!a20!c"),
    "BA": (20, "3!n3!n8!n2!n"),
    "BE": (16, "3!n7!n2!n"),
    "BG": (22, "4!a4!n2!n8!c"),
    "BH": (22, "4!a14!c"),
    "BI": (27, "5!n5!n11!n2!n"),
    "BR": (29, "8!n5!n10!n1!a1!c"),
    "BY": (28, "4!c4!n16!c"),
    "CH": (21, "5!n12!c"),
    "CR": (22, "4!n14!n"),
    "CY": (28, "3!n5!n16!c"),
    "CZ": (24, "4!n16!n"),
    "DE": (22, "8!n10!n"),
    "DJ": (27, "5!n5!n11!n2!n"),
    "DK": (18, "4!n9!n1!n"),
    "DO": (28, "4!c20!n"),
    "EE": (20, "2!n14!n"),
    "EG": (29, "4!n4!n17!n"),
    "ES": (24, "4!n4!n1!n1!n10!n"),
    "FI": (18, "3!n11!n"),
    "FK": (18, "2!a12!n"),
    "FO": (18, "4!n9!n1!n"),
    "FR": (27, "5!n5!n11!c2!n"),
    "GB": (22, "4!a6!n8!n"),
    "GE": (22, "2!a16!n"),
    "GI": (23, "4!a15!c"),
    "GL": (18, "4!n9!n1!n"),
    "GR": (27, "3!n4!n16!c"),
    "GT": (28, "4!c20!c"),
    "HN": (28, "4!a20!n"),
    "HR": (21, "7!n10!n"),
    "HU": (28, "3!n4!n1!n15!n1!n"),
    "IE": (22, "4!a6!n8!n"),
    "IL": (23, "3!n3!n13!n"),
    "IQ": (23, "4!a3!n12!n"),
    "IS": (26, "4!n2!n6!n10!n"),
    "IT": (27, "1!a5!n5!n12!c"),
    "JO": (30, "4!a4!n18!c"),
    "KW": (30, "4!a22!c"),
    "KZ": (20, "3!n13!c"),
    "LB": (28, "4!n20!c"),
    "LC": (32, "4!a24!c"),
    "LI": (21, "5!n12!c"),
    "LT": (20, "5!n11!n"),
    "LU": (20, "3!n13!c"),
    "LV": (21, "4!a13!c"),
    "LY": (25, "3!n3!n15!n"),
    "MC": (27, "5!n5!n11!c2!n"),
    "MD": (24, "2!c18!c"),
    "ME": (22, "3!n13!n2!n"),
    "MK": (19, "3!n10!c2!n"),
    "MN": (20, "4!n12!n"),
    "MR": (27, "5!n5!n11!n2!n"),
    "MT": (31, "4!a5!n18!c"),
    "MU": (30, "4!a2!n2!n12!n3!n3!a"),
    "NI": (28, "4!a20!n"),
    "NL": (18, "4!a10!n"),
    "NO": (15, "4!n6!n1!n"),
    "OM": (23, "3!n16!c"),
    "PK": (24, "4!a16!c"),
    "PL": (28, "8!n16!n"),
    "PS": (29, "4!a21!c"),
    "PT": (25, "4!n4!n11!n2!n"),
    "QA": (29, "4!a21!c"),
    "RO": (24, "4!a16!c"),
    "RS": (22, "3!n13!n2!n"),
    "RU": (33, "9!n5!n15!c"),
    "SA": (24, "2!n18!c"),
    "SC": (31, "4!a2!n2!n16!n3!a"),
    "SD": (18, "2!n12!n"),
    "SE": (24, "3!n16!n1!n"),
    "SI": (19, "5!n8!n2!n"),
    "SK": (24, "4!n6!n10!n"),
    "SM": (27, "1!a5!n5!n12!c"),
    "SO": (23, "4!n3!n12!n"),
    "ST": (25, "4!n4!n11!n2!n"),
    "SV": (28, "4!a20!n"),
    "TL": (23, "3!n14!n2!n"),
    "TN": (24, "2!n3!n13!n2!n"),
    "TR": (26, "5!n1!n16!c"),
    "UA": (29, "6!n19!c"),
    "VA": (22, "3!n15!n"),
    "VG": (24, "4!a16!n"),
    "XK": (20, "4!n10!n2!n"),
    "YE": (30, "4!a4!n18!c"),
}

_TOKEN = re.compile(r"(\d+)!([nac])")
_CLASSES = {
    "n": str.isdigit,
    "a": lambda value: value.isascii() and value.isalpha(),
    "c": lambda value: value.isascii() and value.isalnum(),
}


def _matches_structure(bban, structure):
    position = 0
    structure_position = 0
    for match in _TOKEN.finditer(structure):
        if match.start() != structure_position:
            return False
        length = int(match.group(1))
        segment = bban[position:position + length]
        if len(segment) != length or not _CLASSES[match.group(2)](segment):
            return False
        position += length
        structure_position = match.end()
    return structure_position == len(structure) and position == len(bban)


def _mod97(iban):
    remainder = 0
    for char in iban[4:] + iban[:4]:
        digits = char if char.isdigit() else str(ord(char) - 55)
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder


def is_valid_iban(value):
    iban = "".join(value.split()).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", iban):
        return False
    rule = RULES.get(iban[:2])
    if rule is None or len(iban) != rule[0]:
        return False
    return _matches_structure(iban[4:], rule[1]) and _mod97(iban) == 1
