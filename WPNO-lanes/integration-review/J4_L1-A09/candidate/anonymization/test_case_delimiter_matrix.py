from payload_scan import local_scan, scan_payload


def _types(text):
    return {hit["type"] for hit in local_scan(text)}


def test_phone_allows_standard_punctuation_delimiters():
    for left, right in ((",", " "), (".", " "), (",", ","), (".", ".")):
        assert "phone" in _types(f"{left}030 12345678{right}")


def test_iban_country_prefix_case_variants_are_detected():
    for iban in ("de89370400440532013000", "De89370400440532013000"):
        assert scan_payload(f"IBAN {iban}")["blocked"] is True


def test_address_case_variants_are_detected():
    for address in ("musterstraße 12", "MUSTERSTRASSE 12", "mUsTeRsTrAßE 12"):
        assert "address" in _types(f",{address}.")
    for locality in ("12345 berlin", "12345 BERLIN", "12345 BeRlIn"):
        assert "address" in _types(f",{locality}.")


def test_clean_delimiter_controls_remain_clean():
    for text in ("Hinweis, 030.", "Die musterstraße, berlin.",
                 "Postfach 12345, Berlin.", "Kontomuster, de89."):
        assert not _types(text), text
