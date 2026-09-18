"""Enforce one canonical payload scanner for tests and the Docker mount."""
from pathlib import Path


def test_docker_path_points_to_canonical_scanner():
    root = Path(__file__).resolve().parent.parent
    canonical = root / "anonymization" / "payload_scan.py"
    docker_entry = root / "docker" / "litellm" / "payload_scan.py"
    compose = (root / "docker" / "litellm" / "docker-compose.yml").read_text()

    assert docker_entry.is_symlink()
    assert docker_entry.resolve() == canonical.resolve()
    assert "../../anonymization/payload_scan.py:/app/payload_scan.py:ro" in compose
    assert "./payload_scan.py:/app/payload_scan.py" not in compose


def test_golden_scanner_remains_a_distinct_labeled_test_asset():
    root = Path(__file__).resolve().parent.parent
    canonical = root / "anonymization" / "payload_scan.py"
    golden = root / "anonymization" / "golden" / "payload_scan.py"

    assert golden.parent.name == "golden"
    assert golden.read_bytes() != canonical.read_bytes()


if __name__ == "__main__":
    import sys
    try:
        test_docker_path_points_to_canonical_scanner()
        test_golden_scanner_remains_a_distinct_labeled_test_asset()
        print("CANONICAL-SCANNER: PASS")
        sys.exit(0)
    except AssertionError as e:
        print(f"COPY-SYNC: FAIL - {e}")
        sys.exit(1)
