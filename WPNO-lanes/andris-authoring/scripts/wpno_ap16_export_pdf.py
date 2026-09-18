#!/usr/bin/env python3
"""Canonical operator launcher for the WPNO AP16 Microsoft Word exporter."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


CANONICAL_EXPORTER = Path("authoring/AP16_export_with_toc_v4.py")
CANONICAL_SHA256 = "b204a8e5e9bd7a7489bd2d69c61242ec9da8c929186b4b3393599a3d120ebdb7"
USAGE = (
    "Usage: /usr/bin/python3 scripts/wpno_ap16_export_pdf.py "
    "INPUT.docx OUTPUT.pdf"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str, exit_code: int) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return exit_code


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(USAGE, file=sys.stderr)
        return 64

    project_root = Path(__file__).resolve().parents[1]
    exporter = project_root / CANONICAL_EXPORTER

    if not exporter.is_file():
        return fail(f"canonical exporter not found: {exporter}", 69)

    exporter_sha256 = sha256_file(exporter)
    if exporter_sha256 != CANONICAL_SHA256:
        return fail(
            "canonical exporter hash mismatch; refusing to run "
            f"(expected {CANONICAL_SHA256}, got {exporter_sha256})",
            69,
        )

    input_docx = Path(argv[1]).expanduser().resolve()
    output_pdf = Path(argv[2]).expanduser().resolve()

    if input_docx.suffix.lower() != ".docx":
        return fail("input must use the .docx extension", 64)
    if output_pdf.suffix.lower() != ".pdf":
        return fail("output must use the .pdf extension", 64)
    if not input_docx.is_file():
        return fail(f"input document not found: {input_docx}", 66)
    if not output_pdf.parent.is_dir():
        return fail(f"output directory not found: {output_pdf.parent}", 73)

    completed = subprocess.run(
        [sys.executable, str(exporter), str(input_docx), str(output_pdf)],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
