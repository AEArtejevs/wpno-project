#!/usr/bin/env python3
"""Canonical fail-closed operator gate for WPNO AP18 -> AP16 -> AP17."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


COMPONENTS = {
    "AP18 input filter": (
        Path("ap18/AP18_eingangsfilter.py"),
        "2d098cc9109fa832e7885bf157d8135fd773ceb0b17a143ff493fe3acb6e1957",
    ),
    "AP16 verifier": (
        Path("authoring/AP16_verify_document.py"),
        "fe528a72f4b75a377f7735698f33628aa1f26607eb0f8ec62279a570954c2c54",
    ),
    "AP17 output guard": (
        Path("authoring/AP17_output_guardrail_v3.py"),
        "d606c9504642b212dfaa14684964f401f74881f2816f513d73e248b7c64775ae",
    ),
    "AP18 reference classifier": (
        Path("authoring/AP18_referenzpruefung.py"),
        "fd665e38687f14fe53ba45e9a9b8c3461ed7198a9bbd006d4718001ae84b647d",
    ),
    "AP18 reference data": (
        Path("authoring/bgh_referenz.json"),
        "d2451fa5720643cceb84605538a7979709ef90a44de4770e7aee06cc33579880",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str, exit_code: int = 64) -> int:
    print(f"PIPELINE ERROR: {message}", file=sys.stderr)
    return exit_code


def validate_file(path: Path, label: str, suffix: str | None = None) -> str | None:
    if not path.is_file():
        return f"{label} not found: {path}"
    if suffix and path.suffix.lower() != suffix:
        return f"{label} must use {suffix}: {path}"
    return None


def run_stage(name: str, argv: list[str], project_root: Path) -> int:
    print(f"PIPELINE STAGE: {name}", flush=True)
    completed = subprocess.run(argv, cwd=project_root, check=False)
    if completed.returncode:
        print(
            f"PIPELINE STOP: {name} returned {completed.returncode}",
            file=sys.stderr,
        )
    return completed.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Run untrusted-input filtering, semantic output verification, "
            "and the final output guard in fail-closed order. The final DOCX "
            "must already have its Word fields/TOC updated."
        )
    )
    result.add_argument(
        "--incoming", action="append", required=True,
        help="Untrusted input file or directory; repeat for multiple inputs.",
    )
    result.add_argument("--document", required=True, help="Final updated DOCX.")
    result.add_argument("--outline", required=True, help="Exact AP16 outline JSON.")
    result.add_argument(
        "--known-references", required=True,
        help="AP17 proceeding-reference and forbidden-name JSON.",
    )
    result.add_argument("--input-journal", required=True, help="AP18 SQLite journal.")
    result.add_argument("--output-ledger", required=True, help="AP17 SQLite ledger.")
    result.add_argument(
        "--report-dir", required=True,
        help="Existing empty destination for AP16/AP17 reports.",
    )
    return result


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv[1:])
    project_root = Path(__file__).resolve().parents[1]

    resolved = {}
    for label, (relative, expected_hash) in COMPONENTS.items():
        path = project_root / relative
        if not path.is_file():
            return fail(f"{label} missing: {path}", 69)
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            return fail(
                f"{label} hash mismatch (expected {expected_hash}, "
                f"got {actual_hash})",
                69,
            )
        resolved[label] = path

    document = Path(args.document).expanduser().resolve()
    outline = Path(args.outline).expanduser().resolve()
    known = Path(args.known_references).expanduser().resolve()
    input_journal = Path(args.input_journal).expanduser().resolve()
    output_ledger = Path(args.output_ledger).expanduser().resolve()
    report_dir = Path(args.report_dir).expanduser().resolve()
    incoming = [Path(item).expanduser().resolve() for item in args.incoming]

    for path, label, suffix in (
        (document, "final document", ".docx"),
        (outline, "outline contract", ".json"),
        (known, "known-references configuration", ".json"),
    ):
        error = validate_file(path, label, suffix)
        if error:
            return fail(error, 66)
    if any(not path.exists() for path in incoming):
        return fail("at least one incoming path does not exist", 66)
    if not report_dir.is_dir():
        return fail(f"report directory not found: {report_dir}", 73)
    if not input_journal.parent.is_dir() or not output_ledger.parent.is_dir():
        return fail("journal/ledger parent directory not found", 73)
    if input_journal == output_ledger:
        return fail("AP18 journal and AP17 ledger must be separate files")

    ap16_report = report_dir / "AP16_verify_report.md"
    ap17_report = report_dir / "AP17_guardrail_report.md"
    if ap16_report.exists() or ap17_report.exists():
        return fail("report destination is not empty; refusing to overwrite", 73)

    for path in incoming:
        code = run_stage(
            f"AP18 input filter ({path.name})",
            [sys.executable, str(resolved["AP18 input filter"]), str(path),
             "--journal", str(input_journal), "--fail-on-review"],
            project_root,
        )
        if code:
            return code

    code = run_stage(
        "AP16 semantic verifier",
        [sys.executable, str(resolved["AP16 verifier"]), str(document),
         str(ap16_report), "--outline", str(outline)],
        project_root,
    )
    if code:
        return code

    code = run_stage(
        "AP17 output guard with AP18 reference classification",
        [sys.executable, str(resolved["AP17 output guard"]), str(document),
         str(known), str(output_ledger), str(ap17_report)],
        project_root,
    )
    if code:
        return code

    print("PIPELINE PASS: AP18 input, AP16 semantic, and AP17 output gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
