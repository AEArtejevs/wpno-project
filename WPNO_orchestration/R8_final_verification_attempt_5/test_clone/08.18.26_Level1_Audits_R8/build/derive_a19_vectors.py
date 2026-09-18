#!/usr/bin/env python3
"""Derive the L1-A19 tax-ID vector corpus from the accepted REF-03 and REF-04 bytes.

The corpus is not invented. Every vector records where its expected answer
comes from, and the two provenances are kept apart rather than blended:

  REF-04_DOCUMENTED
      The vector and its outcome are written down in REF-04's own doctests or
      module docstring. These are the vectors this build did not decide.

  DERIVED_BY_RULE_FROM_REF-04
      The vector is constructed here, and its expected answer follows from a
      rule REF-04 states in prose - the length rule, the leading-zero rule,
      the first-ten-digit repetition rule, or the MOD 11,10 check digit. The
      rule is named per vector in `rule`, so a reader can check the derivation
      rather than trust it.

Nothing here consults the implementation under audit. The corpus exists to
test that implementation, and a corpus derived from it would agree with it by
construction - which is the failure CLAUDE.md section 10 records as "a counter
that counts what it knows".

The ISO item in REF-03 is an eleven-page iTeh preview and is recorded as such.
It establishes that MOD 11,10 is the designated hybrid system; it does not
contain the operational clauses. The operational calculation is the official
ELSTER specification's, corroborated by REF-04's independent implementation.
That limitation is carried into the corpus metadata and must not be softened.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import hashing, path_policy  # noqa: E402

REF03 = {
    "iso_preview": os.path.join(ROOT, "references",
                                "REF-03_ISO_IEC_7064_2003.pdf"),
    "elster": os.path.join(
        ROOT, "references",
        "REF-03_ELSTER_Pruefung_Steueridentifikationsnummer_2026-04-15.pdf"),
    "bzst": os.path.join(ROOT, "references",
                         "REF-03_BZSt_German_IdNr_Issuer_Specification.pdf"),
    "source_map": os.path.join(ROOT, "references", "REF-03_SOURCE_MAP.txt"),
}
REF04 = {
    "idnr": os.path.join(ROOT, "references", "REF-04_idnr.py"),
    "doctest": os.path.join(ROOT, "references",
                            "REF-04_test_de_idnr.doctest"),
}

OUT_JSONL = os.path.join(ROOT, "corpora", "R7_REF04_IDNR_VECTORS.jsonl")
OUT_META = os.path.join(ROOT, "corpora", "R7_REF04_IDNR_VECTORS.meta.json")


# --------------------------------------------------------------- the rules
#
# Written from the official ELSTER calculation and checked, before use,
# against every outcome REF-04 documents. A rule implementation that has not
# been run against a known answer is not a rule, it is a guess.

def mod_11_10_check_digit(first_ten):
    """ISO/IEC 7064 MOD 11,10 over the first ten digits."""
    p = 10
    for ch in first_ten:
        m = (int(ch) + p) % 10
        if m == 0:
            m = 10
        p = (2 * m) % 11
    return (11 - p) % 10


def repetition_rule_satisfied(number):
    """Exactly one of the first ten digits repeats, twice or three times."""
    counter = defaultdict(int)
    for ch in number[:10]:
        counter[ch] += 1
    counts = [c for c in counter.values() if c > 1]
    return len(counts) == 1 and counts[0] in (2, 3)


def reference_outcome(raw):
    """The outcome REF-04's stated rules give for `raw`, as a category.

    The order is REF-04's own: compact, length, digits, leading zero,
    repetition, then check digit. Order matters - a value can violate two
    rules, and the category names the one REF-04 would report.
    """
    if raw is None:
        return "INVALID_NOT_A_STRING"
    compacted = raw
    for sep in (" ", "-", ".", "/", ","):
        compacted = compacted.replace(sep, "")
    compacted = compacted.strip()
    if len(compacted) != 11:
        return "INVALID_LENGTH"
    if not compacted.isdigit() or not compacted.isascii():
        return "INVALID_FORMAT_NON_DIGIT"
    if compacted.startswith("0"):
        return "INVALID_FORMAT_LEADING_ZERO"
    if not repetition_rule_satisfied(compacted):
        return "INVALID_FORMAT_REPETITION"
    if mod_11_10_check_digit(compacted[:10]) != int(compacted[10]):
        return "INVALID_CHECKSUM"
    return "VALID"


# ------------------------------------------------- REF-04's own known answers
#
# Transcribed from REF-04_idnr.py's module docstring and
# REF-04_test_de_idnr.doctest. Each carries the exact locator so the
# transcription can be checked against the accepted bytes.

REF04_DOCUMENTED = [
    ("36 574 261 809", "VALID", "REF-04_idnr.py docstring", "separators are stripped before validation"),
    ("36574261890", "INVALID_CHECKSUM", "REF-04_idnr.py docstring", "InvalidChecksum"),
    ("36554266806", "INVALID_FORMAT_REPETITION", "REF-04_idnr.py docstring", "more digits repeated -> InvalidFormat"),
    ("116574261809", "INVALID_LENGTH", "REF-04 doctest", "twelve digits -> InvalidLength"),
    ("A6574261809", "INVALID_FORMAT_NON_DIGIT", "REF-04 doctest", "non-digit -> InvalidFormat"),
    ("01234567896", "INVALID_FORMAT_LEADING_ZERO", "REF-04 doctest", "leading zero -> InvalidFormat"),
    ("1234567890 3", "INVALID_FORMAT_REPETITION", "REF-04 doctest", "each digit once -> InvalidFormat"),
    ("1123456789 0", "VALID", "REF-04 doctest", "one digit twice"),
    ("1112345678 6", "VALID", "REF-04 doctest", "one digit three times"),
    ("1111234567 8", "INVALID_FORMAT_REPETITION", "REF-04 doctest", "one digit four times -> InvalidFormat"),
    ("1122345678 5", "INVALID_FORMAT_REPETITION", "REF-04 doctest", "two digits more than once -> InvalidFormat"),
]


def derived_vectors():
    """Vectors this build constructs, each with the rule that decides it."""
    out = []

    def add(raw, scope, rule, note=None, applicable=True):
        out.append({"raw": raw, "scope": scope, "rule": rule, "note": note,
                    "applicable": applicable})

    # A known-valid identifier with its check digit stepped by one. The
    # repetition rule still holds, so the only thing that can fail is the
    # check digit - which is what makes it a check-digit test rather than a
    # format test.
    for base in ("36574261809", "11234567890", "11123456786"):
        stem, last = base[:10], int(base[10])
        add("%s%d" % (stem, (last + 1) % 10), "CHECK_DIGIT_PLUS_ONE",
            "MOD_11_10", "stepped from documented-valid %s" % base)

    # Structure violated, check digit correct. This separates the two verdict
    # dimensions the specification insists on keeping apart.
    for stem in ("1234567890", "1111234567"):
        add("%s%d" % (stem, mod_11_10_check_digit(stem)),
            "REPETITION_VIOLATED_CHECK_DIGIT_CORRECT", "REPETITION",
            "check digit computed correctly for a stem the repetition rule rejects")

    # Length, on both sides of eleven.
    add("3657426180", "WRONG_LENGTH_10", "LENGTH", "ten digits")
    add("365742618090", "WRONG_LENGTH_12", "LENGTH", "twelve digits")

    # Separator and whitespace handling. REF-04 compacts ' -./,' and strips.
    add("36-574-261-809", "SEPARATORS_HYPHEN", "COMPACTION")
    add("36.574.261.809", "SEPARATORS_DOT", "COMPACTION")
    add("36/574/261/809", "SEPARATORS_SLASH", "COMPACTION")
    add("36,574,261,809", "SEPARATORS_COMMA", "COMPACTION")
    add("  36574261809  ", "SURROUNDING_WHITESPACE", "COMPACTION")

    # Text around the value. REF-04 does not strip letters, so these stay
    # invalid; the audit's question is whether the target's pattern extracts
    # a value here that the validator then answers differently.
    add("Steuer-ID 36574261809", "LEADING_TEXT", "COMPACTION")
    add("36574261809 ist die Nummer", "TRAILING_TEXT", "COMPACTION")

    # Degenerate inputs.
    add("", "EMPTY_INPUT", "LENGTH", "the empty string is an input with an answer")
    add(None, "NONE_INPUT", "NOT_A_STRING", "not a string at all", applicable=True)
    add("3" * 4000, "VERY_LONG_INPUT", "LENGTH", "4000 characters")
    add("11111111111", "ALL_IDENTICAL_DIGITS", "REPETITION")

    # Edge cases the specification names.
    add("11123456786", "MAX_ALLOWED_REPETITION", "REPETITION",
        "one digit three times, the maximum the rule allows")
    stem = "1123456789"
    if mod_11_10_check_digit(stem) == 0:
        add("%s0" % stem, "CHECK_DIGIT_COMPUTES_TO_ZERO", "MOD_11_10")
    else:
        for candidate in ("1123456789", "1213456789", "1231456789",
                          "1234156789", "1234516789", "1234561789",
                          "1234567189", "1234567819", "1234567891",
                          "1132456789", "1123465789", "1123456879"):
            if (mod_11_10_check_digit(candidate) == 0
                    and repetition_rule_satisfied(candidate + "0")):
                add("%s0" % candidate, "CHECK_DIGIT_COMPUTES_TO_ZERO",
                    "MOD_11_10", "search over repetition-valid stems")
                break
    add("01123456789", "LEADING_ZERO", "LEADING_ZERO")

    # Eleven characters from a different scheme. A Belgian national number is
    # eleven digits and is not an IdNr; it must not be accepted merely for
    # having the right length.
    add("85073003328", "FOREIGN_SCHEME_SAME_LENGTH", "MOD_11_10",
        "eleven digits, Belgian national-number shape, not an IdNr")

    # Valid under a different ISO 7064 variant. MOD 11,2 produces a check
    # character over a different modulus; a value built for it is not valid
    # here, and a validator that accepts it is using the wrong variant.
    add("36574261803", "OTHER_ISO7064_VARIANT", "MOD_11_10",
        "same stem, a check digit that is not the MOD 11,10 one")
    return out


def main():
    parser = argparse.ArgumentParser(prog="derive-a19-vectors")
    parser.add_argument("--check-only", action="store_true",
                        help="verify the derivation without writing")
    args = parser.parse_args()

    for label, path in list(REF03.items()) + list(REF04.items()):
        if not os.path.isfile(path):
            raise SystemExit("accepted reference absent: %s (%s)" % (path, label))

    # The rule implementation is checked against every answer REF-04 states,
    # before it is used to decide anything this build constructs.
    self_check = []
    for raw, expected, locator, why in REF04_DOCUMENTED:
        got = reference_outcome(raw)
        self_check.append({"raw": raw, "expected": expected, "computed": got,
                           "agrees": got == expected, "locator": locator})
    disagreements = [c for c in self_check if not c["agrees"]]
    if disagreements:
        raise SystemExit(
            "the derivation rules disagree with REF-04's own documented "
            "answers, so they may not be used to derive anything: %s"
            % json.dumps(disagreements, indent=2))

    vectors = []
    for raw, expected, locator, why in REF04_DOCUMENTED:
        vectors.append({
            "raw": raw,
            "expected_result": expected,
            "expected_result_provenance": "REF-04_DOCUMENTED",
            "rule": None,
            "locator": locator,
            "note": why,
            "scope": "REF04_DOCUMENTED",
            "applicable_to_idnr_validator": True,
        })
    for item in derived_vectors():
        vectors.append({
            "raw": item["raw"],
            "expected_result": reference_outcome(item["raw"]),
            "expected_result_provenance": "DERIVED_BY_RULE_FROM_REF-04",
            "rule": item["rule"],
            "locator": None,
            "note": item["note"],
            "scope": item["scope"],
            "applicable_to_idnr_validator": item["applicable"],
        })

    seen = {}
    for v in vectors:
        key = json.dumps(v["raw"])
        seen.setdefault(key, []).append(v["scope"])
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}

    counts = defaultdict(int)
    for v in vectors:
        counts[v["expected_result"]] += 1
    if counts["VALID"] == 0 or sum(counts.values()) - counts["VALID"] == 0:
        raise SystemExit("a corpus with only one answer tests nothing")

    meta = {
        "schema": "wpno.level1.a19-idnr-vectors/1",
        "revision": "R8",
        "derived_by": "build/derive_a19_vectors.py",
        "vector_count": len(vectors),
        "documented_vector_count": len(REF04_DOCUMENTED),
        "derived_vector_count": len(vectors) - len(REF04_DOCUMENTED),
        "expected_result_counts": dict(sorted(counts.items())),
        "duplicate_raw_values": duplicates,
        "rule_self_check_against_ref04": self_check,
        "rule_self_check_disagreements": 0,
        "references": {
            "REF-03": {k: {"path": os.path.relpath(p, ROOT),
                           "sha256": hashing.sha256_file(p)}
                       for k, p in sorted(REF03.items())},
            "REF-04": {k: {"path": os.path.relpath(p, ROOT),
                           "sha256": hashing.sha256_file(p)}
                       for k, p in sorted(REF04.items())},
        },
        "ref03_limitation": (
            "The ISO/IEC 7064 item is an eleven-page iTeh preview containing "
            "normative pages 1-5. It establishes that MOD 11,10 is the "
            "designated hybrid system with one check digit. It does not "
            "contain clauses 9 and 10 and must not be described as the "
            "complete ISO standard. The operational calculation is taken from "
            "the official ELSTER specification and corroborated by REF-04."),
        "oracle_note": (
            "No expected value in this corpus was produced by the "
            "implementation under audit. The documented vectors are REF-04's "
            "own; the derived vectors follow named rules whose implementation "
            "was first checked against every documented vector."),
    }

    if args.check_only:
        print(json.dumps({"vectors": len(vectors),
                          "self_check_disagreements": 0,
                          "duplicates": len(duplicates)}, indent=2))
        return 0

    lines = [json.dumps(v, sort_keys=True) for v in vectors]
    with open(path_policy.assert_writable(OUT_JSONL), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")
    with open(path_policy.assert_writable(OUT_META), "w",
              encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "vectors": os.path.relpath(OUT_JSONL, ROOT),
        "vectors_sha256": hashing.sha256_file(OUT_JSONL),
        "meta": os.path.relpath(OUT_META, ROOT),
        "meta_sha256": hashing.sha256_file(OUT_META),
        "vector_count": len(vectors),
        "expected_result_counts": dict(sorted(counts.items())),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
