"""
Committee audit 2026-07-21 -- regression test for the confirmed bypasses.
Synthetic data only. Verifies that payloads previously allowed through
fail-open are now blocked (blocked=True) and that the fail-closed edges
hold. Assertion failure on any remaining leak.
"""
import sys
import time
from payload_scan import scan_payload, local_scan, normalize_for_scan

def test_audit_hardening():
    fail = 0

    def must_block(label, text):
        nonlocal fail
        r = scan_payload(text)
        ok = r["blocked"] is True
        if not ok:
            fail += 1
        print(f"  [{label}] -> {'BLOCK ok' if ok else '** LEAK (not blocked) **'} findings={r['findings']}")

    def must_pass(label, text):
        nonlocal fail
        r = scan_payload(text)
        ok = r["blocked"] is False
        if not ok:
            fail += 1
        print(f"  [{label}] -> {'CLEAN ok' if ok else '** FALSE POSITIVE **'} findings={r['findings']}")

    print("=" * 72)
    print("P1 — Homoglyphen (kyrillisch/griechisch) muessen jetzt blocken")
    print("=" * 72)
    must_block("homoglyph-email-cyr-r", "Kontakt mueller@kanzlei-hр.de bitte")   # р
    must_block("homoglyph-email-cyr-a", "mаndant@example.de schreibt")            # а
    must_block("homoglyph-company-cyr", "Die Оtten GmbH klagt")                   # О
    must_block("homoglyph-party-cyr",   "Mandat Н&R laeuft")                       # Н&R

    print("=" * 72)
    print("P1 — Zero-Width / Soft-Hyphen in IBAN/Phone muessen jetzt blocken")
    print("=" * 72)
    must_block("zwsp-iban",    "IBAN DE89​3704004405320130​00 vorgemerkt")
    must_block("softhyph-iban","IBAN DE89­370400440532013000 vorgemerkt")
    must_block("zwsp-phone",   "Tel +49 211 49​33-0 erreichbar")

    print("=" * 72)
    print("P1 — Case-Evasion (IBAN/BIC/company lowercase) muessen jetzt blocken")
    print("=" * 72)
    must_block("iban-lower",    "iban de89370400440532013000 heute")
    must_block("bic-lower",     "bic deutdeff nutzen")
    must_block("company-lower", "die mandant gmbh zahlt nicht")
    must_block("name-allcaps",  "HERR KLAUS MUSTERMANN unterschreibt")

    print("=" * 72)
    print("P1 — Internationale/akzentuierte Namen (mit Titel) muessen blocken")
    print("=" * 72)
    must_block("name-jose",     "Herr José García erscheint")     # José García
    must_block("name-anais",    "Frau Anaïs Muster sagt aus")          # Anaïs
    must_block("name-francois", "Herr François Dubois klagt")          # François
    must_block("name-obrien",   "Herr O’Brien ruft an")                # O’Brien
    must_block("name-nina",     "Frau Niña Muster erscheint")          # Niña
    must_block("name-vonderheide","Herr Klaus von der Heide bestellt")

    print("=" * 72)
    print("P2/P5 — Fail-closed-Raender")
    print("=" * 72)
    must_block("nonstr-None",  None)
    must_block("nonstr-int",   1234567890)
    must_block("nonstr-bytes", b"IBAN DE89370400440532013000")
    must_block("oversize",     "x" * 1_000_001)

    print("=" * 72)
    print("Regression — echte deutsche Standardfaelle bleiben korrekt")
    print("=" * 72)
    must_block("plain-iban",   "Zahlung auf DE89 3704 0044 0532 0130 00")
    must_block("plain-name",   "Herr Mueller kommt")
    must_pass("clean-prose",   "Der Anspruch folgt aus dem Werkvertrag und ist begruendet.")
    must_pass("clean-die-ag",  "Die AG haftet nach dem Aktiengesetz.")

    print("=" * 72)
    print("P2 — ReDoS-Schranke: adversariale Phone/Company-Eingabe unter Zeitlimit")
    print("=" * 72)
    adv_phone = "+49 " + "1" * 500 + "/"
    adv_comp = "A" + " A" * 4000 + " GmbH"
    for lbl, payload in (("adv-phone-14kB", adv_phone * 300), ("adv-company-8k", adv_comp)):
        t0 = time.perf_counter()
        scan_payload(payload[:1_000_000])
        dt = time.perf_counter() - t0
        ok = dt < 2.0
        if not ok:
            fail += 1
        print(f"  [{lbl}] len={len(payload)} -> {dt*1000:.0f} ms {'ok' if ok else '** TOO SLOW **'}")

    print("=" * 72)
    print(f"OVERALL: {'PASS' if fail == 0 else f'FAIL ({fail} problem(s))'}")
    assert fail == 0, f"{fail} audit-hardening check(s) failed (see output above)"


if __name__ == "__main__":
    import sys
    try:
        test_audit_hardening()
        sys.exit(0)
    except AssertionError as e:
        print(f"EXIT 1: {e}")
        sys.exit(1)
