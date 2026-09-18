"""L1-A19 RUN-A: the German IdNr check digit in its generation form.

The scheme is ISO/IEC 7064 MOD 11,10, which REF-03's ISO item identifies as a
hybrid system with one check digit. The ISO item is an eleven-page preview and
does not carry the operational clauses; the calculation implemented here is the
official ELSTER specification's, and REF-04 is the independent corroboration.
That limitation is stated wherever this module's output is used and is not
softened into "the ISO standard says".

Two forms of the same scheme exist, and RUN-A deliberately uses only one.

  GENERATION (here)     fold the first ten digits, produce the eleventh, and
                        compare it against the digit the input carries.

  VERIFICATION (RUN-B)  fold all eleven digits and require the final
                        intermediate to be 1.

They are equivalent in arithmetic and different in expression, which is the
point: a defect in one does not reproduce itself in the other. RUN-B is
written in another language and never imports this module.

Structural validity and check-digit correctness are two questions, and the
specification requires them answered separately. This module answers both and
keeps them in separate fields; it never lets one decide the other.
"""

from collections import defaultdict

SEPARATORS = " -./,"


def compact(value):
    """Strip the separators REF-04 documents, then surrounding whitespace."""
    out = value
    for sep in SEPARATORS:
        out = out.replace(sep, "")
    return out.strip()


def mod_11_10_check_digit(first_ten):
    """The eleventh digit, computed from the first ten. Generation form."""
    p = 10
    for ch in first_ten:
        m = (int(ch) + p) % 10
        if m == 0:
            m = 10
        p = (2 * m) % 11
    return (11 - p) % 10


def repetition_counts(first_ten):
    counter = defaultdict(int)
    for ch in first_ten:
        counter[ch] += 1
    return sorted(c for c in counter.values() if c > 1)


def repetition_rule_satisfied(first_ten):
    """Exactly one digit of the first ten repeats, twice or three times.

    This is a structural rule of the identifier, not part of the check digit.
    It is answered here so that the two can be reported apart.
    """
    counts = repetition_counts(first_ten)
    return len(counts) == 1 and counts[0] in (2, 3)


def validate(value):
    """Answer one input. Returns a record, never a bare boolean.

    Every field is reported even when an earlier field already decides the
    outcome, so that a reader can see which rule fired and which were never
    reached - "not examined" and "examined and passed" are different answers.
    """
    record = {
        "input_is_string": isinstance(value, str),
        "compacted": None,
        "length": None,
        "all_digits": None,
        "leading_zero": None,
        "repetition_counts": None,
        "structurally_valid": None,
        "computed_check_digit": None,
        "carried_check_digit": None,
        "check_digit_correct": None,
        "result": None,
        "deciding_rule": None,
    }
    if not isinstance(value, str):
        record["result"] = "INVALID_NOT_A_STRING"
        record["deciding_rule"] = "NOT_A_STRING"
        return record

    compacted = compact(value)
    record["compacted"] = compacted
    record["length"] = len(compacted)
    if len(compacted) != 11:
        record["result"] = "INVALID_LENGTH"
        record["deciding_rule"] = "LENGTH"
        return record

    record["all_digits"] = compacted.isdigit() and compacted.isascii()
    if not record["all_digits"]:
        record["result"] = "INVALID_FORMAT_NON_DIGIT"
        record["deciding_rule"] = "NON_DIGIT"
        return record

    record["leading_zero"] = compacted.startswith("0")
    if record["leading_zero"]:
        record["result"] = "INVALID_FORMAT_LEADING_ZERO"
        record["deciding_rule"] = "LEADING_ZERO"
        return record

    first_ten = compacted[:10]
    record["repetition_counts"] = repetition_counts(first_ten)
    record["structurally_valid"] = repetition_rule_satisfied(first_ten)

    # The check digit is computed whether or not the structural rule held, so
    # that the two dimensions are both on the record. The result still reports
    # the structural failure, because that is what REF-04 reports.
    record["computed_check_digit"] = mod_11_10_check_digit(first_ten)
    record["carried_check_digit"] = int(compacted[10])
    record["check_digit_correct"] = (
        record["computed_check_digit"] == record["carried_check_digit"])

    if not record["structurally_valid"]:
        record["result"] = "INVALID_FORMAT_REPETITION"
        record["deciding_rule"] = "REPETITION"
        return record
    if not record["check_digit_correct"]:
        record["result"] = "INVALID_CHECKSUM"
        record["deciding_rule"] = "MOD_11_10"
        return record

    record["result"] = "VALID"
    record["deciding_rule"] = "ALL_RULES_SATISFIED"
    return record
