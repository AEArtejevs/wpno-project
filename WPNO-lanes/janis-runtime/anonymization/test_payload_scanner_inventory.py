import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
DETECTOR = ROOT / "scripts" / "payload_scanner_inventory.py"


def _run(root):
    return subprocess.run(
        [sys.executable, str(DETECTOR), "--root", str(root)],
        text=True, capture_output=True, check=False,
    )


def _minimal_tree(tmp_path):
    (tmp_path / "anonymization" / "golden").mkdir(parents=True)
    (tmp_path / "docker" / "litellm").mkdir(parents=True)
    shutil.copy2(ROOT / "anonymization" / "payload_scan.py",
                 tmp_path / "anonymization" / "payload_scan.py")
    shutil.copy2(ROOT / "anonymization" / "golden" / "payload_scan.py",
                 tmp_path / "anonymization" / "golden" / "payload_scan.py")
    (tmp_path / "docker" / "litellm" / "payload_scan.py").symlink_to(
        "../../anonymization/payload_scan.py")


def test_inventory_declares_all_six_audited_roles():
    result = _run(ROOT)
    report = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr + result.stdout
    assert report["ok"] is True
    assert len(report["copies"]) == 6
    assert {item["role"] for item in report["copies"]} == {
        "active_canonical", "active_alias", "golden_test_asset",
        "backup_anonymization", "backup_docker", "historical_before_fix",
    }
    assert not report["unexpected"]


def test_active_alias_drift_fails(tmp_path):
    _minimal_tree(tmp_path)
    alias = tmp_path / "docker" / "litellm" / "payload_scan.py"
    alias.unlink()
    alias.write_text("diverged active scanner\n")

    result = _run(tmp_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_declared_historical_differences_are_reported_not_failed(tmp_path):
    _minimal_tree(tmp_path)
    (tmp_path / "docs" / "Test_07.28.26" / "AP-03" / "logs").mkdir(parents=True)
    (tmp_path / "anonymization" / "payload_scan.py.ALT.2026-08-05.bak").write_text("old A\n")
    (tmp_path / "docker" / "litellm" / "payload_scan.py.ALT.2026-08-05.bak").write_text("old A\n")
    (tmp_path / "docs" / "Test_07.28.26" / "AP-03" / "logs" /
     "payload_scan.py.before_F-AP03").write_text("older\n")

    result = _run(tmp_path)
    report = json.loads(result.stdout)

    assert result.returncode == 0
    assert report["ok"] is True
    non_active = [item for item in report["copies"]
                  if item["role"].startswith("backup_") or
                  item["role"] == "historical_before_fix"]
    assert all(item["status"] == "INTENTIONAL_NON_ACTIVE_DIFFERENCE"
               for item in non_active)


def test_undeclared_scanner_copy_fails(tmp_path):
    _minimal_tree(tmp_path)
    (tmp_path / "payload_scan.py.rogue").write_text("rogue\n")

    result = _run(tmp_path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["unexpected"] == ["payload_scan.py.rogue"]


def test_immutable_audit_package_copies_are_not_source_candidates(tmp_path):
    _minimal_tree(tmp_path)
    audit_copy = (tmp_path / "08.18.26_Level1_Audits_R9" / "work" /
                  "fixture" / "payload_scan.py")
    audit_copy.parent.mkdir(parents=True)
    audit_copy.write_text("sealed fixture\n")

    result = _run(tmp_path)
    report = json.loads(result.stdout)

    assert result.returncode == 0
    assert report["unexpected"] == []
