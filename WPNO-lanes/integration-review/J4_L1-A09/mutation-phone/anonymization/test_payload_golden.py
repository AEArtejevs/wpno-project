import os
from pathlib import Path
import subprocess
import sys


ANON_DIR = Path(__file__).resolve().parent
GOLDEN_PROGRAM = ANON_DIR / "golden" / "payload_scan_golden_test.py"
CANONICAL_SCANNER = ANON_DIR / "payload_scan.py"
IBAN_VALIDATION = ANON_DIR / "iban_validation.py"
GOLDEN_PARTY_NAMES = ANON_DIR / "golden" / "party_names.json"
_LV_SOURCE = (
    '            bban = "".join(ZUFALL.choice("0123456789") '
    'for _ in range(laenge))\n'
)
_LV_CORRECTION = (
    '            if land == "LV":\n'
    '                bban = "BANK" + "".join(\n'
    '                    ZUFALL.choice("0123456789") '
    'for _ in range(laenge - 4)\n'
    '                )\n'
    '            else:\n'
    '                bban = "".join(ZUFALL.choice("0123456789") '
    'for _ in range(laenge))\n'
)
_TAX_SOURCE = '''def steuer_id_bauen():
    while True:
        kern = "".join(str(ZUFALL.randint(0, 9)) for _ in range(10))
        if kern[0] == "0":
            continue
        produkt = 10
        for z in kern:
            summe = (int(z) + produkt) % 10
            produkt = ((summe or 10) * 2) % 11
        return kern + str((11 - produkt) % 10)
'''
_TAX_CORRECTION = '''def steuer_id_bauen():
    while True:
        repeated = ZUFALL.choice("0123456789")
        repeat_count = ZUFALL.choice((2, 3))
        rest = [d for d in "0123456789" if d != repeated]
        digits = [repeated] * repeat_count + ZUFALL.sample(rest, 10 - repeat_count)
        ZUFALL.shuffle(digits)
        if digits[0] == "0":
            continue
        kern = "".join(digits)
        produkt = 10
        for z in kern:
            summe = (int(z) + produkt) % 10
            produkt = ((summe or 10) * 2) % 11
        return kern + str((11 - produkt) % 10)
'''


def _run_golden(program: Path, scanner: Path, ledger_dir: Path):
    env = os.environ.copy()
    env["WPNO_LEDGER_DIR"] = str(ledger_dir)
    return subprocess.run(
        [sys.executable, str(program), str(scanner)],
        cwd=ANON_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _stage_scanner(directory: Path, source: str) -> Path:
    directory.mkdir()
    scanner = directory / "payload_scan.py"
    scanner.write_text(source, encoding="utf-8")
    (directory / "iban_validation.py").write_bytes(IBAN_VALIDATION.read_bytes())
    (directory / "party_names.json").write_bytes(GOLDEN_PARTY_NAMES.read_bytes())
    return scanner


def _stage_current_golden_program(path: Path) -> Path:
    source = GOLDEN_PROGRAM.read_text(encoding="utf-8")
    assert source.count(_LV_SOURCE) == 1
    assert source.count(_TAX_SOURCE) == 1
    source = source.replace(_LV_SOURCE, _LV_CORRECTION)
    path.write_text(source.replace(_TAX_SOURCE, _TAX_CORRECTION), encoding="utf-8")
    return path


def test_payload_golden_program_passes(tmp_path):
    source = CANONICAL_SCANNER.read_text(encoding="utf-8")
    scanner = _stage_scanner(tmp_path / "candidate", source)
    program = _stage_current_golden_program(tmp_path / "golden-program.py")
    result = _run_golden(program, scanner, tmp_path / "ledger")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ERGEBNIS: bestanden. 202 PII-Nutzlasten blockiert." in result.stdout


def test_payload_golden_detects_allow_all_mutation(tmp_path):
    source = CANONICAL_SCANNER.read_text(encoding="utf-8")
    decision = "    blocked = len(hits) > 0\n"
    assert source.count(decision) == 1

    mutant_scanner = _stage_scanner(
        tmp_path / "allow-all-mutant",
        source.replace(decision, "    blocked = False\n"),
    )
    program = _stage_current_golden_program(tmp_path / "golden-program.py")

    result = _run_golden(program, mutant_scanner, tmp_path / "mutant-ledger")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "ERGEBNIS: 202 Fall/Faelle nicht bestanden." in result.stdout
