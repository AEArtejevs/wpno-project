from payload_scan import scan_payload


# Verbatim normalized valid vectors selected from the immutable REF-02 corpus.
OFFICIAL_VALID = (
    "ES2121000418450200051331",
    "AT611904300234573201",
    "BG80BNBG96611020345678",
    "CH9300762011623852957",
    "DE89370400440532013000",
    "FR1420041010050500013M02606",
    "GB29NWBK60161331926819",
    "LV80BANK0000435195001",
    "NL91ABNA0417164300",
    "PL61109010140000071219812874",
)


def _with_check_digits(country, bban):
    rearranged = bban + country + "00"
    digits = "".join(
        str(ord(char) - 55) if char.isalpha() else char
        for char in rearranged
    )
    return country + f"{98 - (int(digits) % 97):02d}" + bban


def _blocked(iban):
    return scan_payload(f"IBAN {iban}")["blocked"]


def _mod97(iban):
    rearranged = iban[4:] + iban[:4]
    digits = "".join(
        str(ord(char) - 55) if char.isalpha() else char
        for char in rearranged
    )
    return int(digits) % 97


def test_official_valid_iban_vectors_are_detected():
    for iban in OFFICIAL_VALID:
        assert _blocked(iban) is True, iban


def test_german_iban_reaches_mod97_validator():
    assert _blocked("DE89370400440532013000") is True
    assert _blocked("DE88370400440532013000") is False


def test_check_digit_valid_wrong_country_structure_is_rejected():
    malformed_at = _with_check_digits("AT", "A904300234573201")
    assert _mod97(malformed_at) == 1
    assert _blocked(malformed_at) is False


def test_check_digit_valid_wrong_country_length_is_rejected():
    too_long_at = _with_check_digits("AT", "19043002345732019")
    assert _mod97(too_long_at) == 1
    assert _blocked(too_long_at) is False
