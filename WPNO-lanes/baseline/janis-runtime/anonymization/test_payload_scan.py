from payload_scan import scan_payload

SAMPLES_BLOCKED = {
    "iban": "Lieta pardo maksajumu uz kontu DE89370400440532013000.",
    "steuid": "Nodoklu numurs ir 12/345/67890.",
    "aktenzeichen": "Skat. spriedumu lieta Nr. 12 O 345/23 no 2024. gada.",
    "party_hr": "Klients ir H&R.",
    "party_hoffmann": "Klients ir Hoffmann & Reuter.",
    "party_latham": "Preteja puse saja procesa ir Latham & Watkins.",
}
SAMPLE_CLEAN = "Klients luedz izvertet iespejamos riskus saistiba ar iepirkuma ligumu."


def test_payload_scan_blocks_pii():
    for label, text in SAMPLES_BLOCKED.items():
        result = scan_payload(text, akte_id="TEST-001", target="anthropic")
        assert result["blocked"] is True, f"[{label}] expected BLOCKED, got findings={result['findings']}"


def test_payload_scan_allows_clean():
    result = scan_payload(SAMPLE_CLEAN, akte_id="TEST-001", target="anthropic")
    assert result["blocked"] is False, f"expected CLEAN, got findings={result['findings']}"
