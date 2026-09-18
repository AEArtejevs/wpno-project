from payload_scan import scan_payload


def _blocked(value):
    return scan_payload(f"Steuer-ID {value}")["blocked"]


def test_official_structurally_valid_tax_ids_are_detected():
    assert _blocked("36574261809") is True
    assert _blocked("11234567890") is True
    assert _blocked("11123456786") is True


def test_checksum_valid_but_structurally_invalid_tax_ids_are_rejected():
    assert _blocked("12345678903") is False
    assert _blocked("11112345678") is False
    assert _blocked("11223456785") is False
    assert _blocked("36554266806") is False


def test_leading_zero_and_wrong_checksum_are_rejected():
    assert _blocked("01234567896") is False
    assert _blocked("36574261890") is False
