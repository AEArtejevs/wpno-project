"""P3-5: enforce byte-identity of the two payload_scan.py copies.
The deployed copy (docker/litellm, mounted into the Gateway) and the one
checked by the corpus tests (anonymization) must never diverge."""
import hashlib
from pathlib import Path


def test_copy_sync():
    root = Path(__file__).resolve().parent.parent
    a = root / "anonymization" / "payload_scan.py"
    b = root / "docker" / "litellm" / "payload_scan.py"
    ha = hashlib.sha256(a.read_bytes()).hexdigest()
    hb = hashlib.sha256(b.read_bytes()).hexdigest()
    print(f"anonymization : {ha}")
    print(f"docker/litellm: {hb}")
    assert ha == hb, "COPY-SYNC FAIL: copies diverge -> the gateway is running unverified code"


if __name__ == "__main__":
    import sys
    try:
        test_copy_sync()
        print("COPY-SYNC: PASS (identical)")
        sys.exit(0)
    except AssertionError as e:
        print(f"COPY-SYNC: FAIL - {e}")
        sys.exit(1)
