import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from payload_scan import scan_payload


ANON = Path(__file__).resolve().parent
SOURCE = ANON / "payload_scan.py"


def _mutant_result(tmp_path, replacements, text):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    source = SOURCE.read_text()
    for old, new in replacements:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    (runtime / "payload_scan.py").write_text(source)
    for name in ("iban_validation.py", "party_names.json"):
        shutil.copy2(ANON / name, runtime / name)
    probe = runtime / "probe.py"
    probe.write_text(
        "import json\nfrom payload_scan import scan_payload\n"
        f"print(json.dumps(scan_payload({text!r})))\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime)
    env["WPNO_LEDGER_DIR"] = str(tmp_path / "ledger")
    result = subprocess.run(
        [sys.executable, "-B", str(probe)], cwd=runtime, env=env,
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_allow_all_mutation_is_observable(tmp_path):
    text = "IBAN DE89370400440532013000"
    assert scan_payload(text)["blocked"] is True
    mutant = _mutant_result(
        tmp_path, (("    blocked = len(hits) > 0\n", "    blocked = False\n"),), text)
    assert mutant["blocked"] is False


def test_german_iban_validator_bypass_is_observable(tmp_path):
    text = "IBAN DE88370400440532013000"
    assert scan_payload(text)["blocked"] is False
    mutant = _mutant_result(
        tmp_path, ((('    "iban": _validate_iban,\n'), '    "iban": None,\n'),), text)
    assert mutant["blocked"] is True


def test_tax_id_structure_bypass_is_observable(tmp_path):
    text = "Steuer-ID 12345678903"
    assert scan_payload(text)["blocked"] is False
    old = '    if k[0] == "0" or len(counts) != 1 or counts[0] not in (2, 3):\n'
    mutant = _mutant_result(tmp_path, ((old, "    if False:\n"),), text)
    assert mutant["blocked"] is True


def test_phone_delimiter_rollback_is_observable(tmp_path):
    text = ",030 12345678 "
    assert scan_payload(text)["blocked"] is True
    old = r"(?<![\d/])\(?0\d{2,4}\)?[\s\-/]\d{3,8}"
    new = r"(?<![\d/.,])\(?0\d{2,4}\)?[\s\-/]\d{3,8}"
    mutant = _mutant_result(tmp_path, ((old, new),), text)
    assert mutant["blocked"] is False


def test_address_case_rollback_is_observable(tmp_path):
    text = ",musterstraße 12."
    assert scan_payload(text)["blocked"] is True
    street = '            r"\\s+\\d{1,4}\\s?[a-hA-H]?\\b", _IC\n'
    locality = ('        re.compile(r"\\b\\d{5}\\s+[" + _U + r"][" + _L + '
                'r"]+(?:[-\\s][" + _U + r"][" + _L + r"]+){0,2}\\b", _IC),\n')
    mutant = _mutant_result(
        tmp_path,
        ((street, street.replace(", _IC", "")),
         (locality, locality.replace(", _IC", ""))),
        text,
    )
    assert mutant["blocked"] is False
