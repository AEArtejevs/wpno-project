from AP17_output_guardrail_v3 import scan_pii


def _has_iban(text):
    return "IBAN" in scan_pii(text, [])


def test_ap17_iban_case_variants_are_detected():
    for value in (
        "DE89370400440532013000",
        "de89370400440532013000",
        "De89370400440532013000",
        "dE89370400440532013000",
    ):
        assert _has_iban(f",{value}.") is True


def test_ap17_iban_word_boundaries_and_ascii_scope_remain_strict():
    for value in (
        "xDE89370400440532013000",
        "DE89370400440532013000_",
        "de89",
        "Kontomuster de89.",
        "İE89370400440532013000",
    ):
        assert _has_iban(value) is False
