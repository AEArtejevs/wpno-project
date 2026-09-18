# 06 — DUPLICATE COPY RECONCILIATION

Level-0 Discovery reports 432 duplicate hash groups across eight scan roots.
This reconciliation resolves only the groups that touch the 35 audits.

## Group 1 — payload scanner (L1-A20, L1-A21, L1-A18, L1-A19)

| sha256 | size | paths |
| --- | --- | --- |
| `99b9e18bde4ff88c271362c4ccdc34e526d043cefea7a35d1b060d5fba25153b` | 21564 | `anonymization/payload_scan.py`, `docker/litellm/payload_scan.py` |
| `ab29a4fa3e972f865f0f3dfb10887888a0464922070454e02584a34a4c54ba0a` | 22831 | `anonymization/golden/payload_scan.py` |
| `7ca517779fbd05a1bf8381b57edac3a15c2b6ccbe00dd06b8dfcc9950cf2aca3` | 16350 | `anonymization/payload_scan.py.ALT.2026-08-05.bak`, `docker/litellm/payload_scan.py.ALT.2026-08-05.bak` |
| `9f466036804d49d0e986d111ea253046dec15e3c8fee2482e42c7ff349744f77` | 15524 | `docs/Test_07.28.26/AP-03/logs/payload_scan.py.before_F-AP03` |

Six files, four distinct contents. The `golden` copy is 1267 bytes larger than
the live copies and differs in content — the audit must say at which comparison
level (bytes, normalized source, AST, functions, regexes, constants,
validation rules, error handling, control flow) it differs, and must not report
"different" without naming the level.

## Group 2 — payload scanner tests

| sha256 | size | paths |
| --- | --- | --- |
| `341549bb566487b5f8db8e1bf34bfb73ada93e3c7e3b36f4db6ecd115234fbd1` | 985 | `anonymization/test_payload_scan.py`, `docker/litellm/test_payload_scan.py` |
| `dc83acf66bdb9aab18f03efaa1b292c1f9a6b1f405439ecc4dd928fd069960b0` | 9268 | `anonymization/golden/payload_scan_golden_test.py` |

## Group 3 — AP16 exporters (L1-A03)

Three distinct files, no duplicates, **no v3**:

| sha256 | size | path |
| --- | --- | --- |
| `e618eb151eb674fe435a967fed7b6e696ac75fbde390db828bd1c99c14e22f0c` | 1763 | `authoring/AP16_export_with_toc.py` |
| `12e6da3ec6289523fc9d8118db8583b8a9ef7649b825a09cd4b26e44f24e6eee` | 1764 | `authoring/AP16_export_with_toc_v2.py` |
| `b204a8e5e9bd7a7489bd2d69c61242ec9da8c929186b4b3393599a3d120ebdb7` | 2325 | `authoring/AP16_export_with_toc_v4.py` |

The unnumbered file and v2 differ by one byte in size and have different
hashes. A one-byte size difference between two versions is exactly the kind of
difference a filename-based or size-based selection would get wrong, which is
why production identity may never be established from a filename, a version
suffix, a modification time or a size.

## Group 4 — AP17 guardrails (L1-A05 to L1-A09)

| sha256 | path | note |
| --- | --- | --- |
| `555ee5164da201864833506a7f9f6f61885f18ff506b1ed4f5f6cddd70f37d37` | `authoring/AP17_output_guardrail_VERALTET.py.txt` | v1 |
| `5f6b3dd78dcb76a924d5961dfc2cfafbc91eccd76ac6f2e0cef22d43b3d8a6d8` | `authoring/AP17_output_guardrail_v2_VERALTET.py.txt` | v2 |
| `dd60dc63437691082b821fe219a7599c1561c757214a0e38eac97367ab2a09ca` | `authoring/AP17_output_guardrail_v3.py` | v3 |

No duplicates. Two of three carry a `.py.txt` extension and a `VERALTET`
(obsolete) marker in the filename. A marker in a filename is documentation, not
evidence. The audit may use the marker as a hypothesis and must not use it as a
conclusion.

## Group 5 — reference checker (L1-A10)

`authoring/AP18_referenzpruefung.py` —
`f5eb5a9cbeb37cada9186ba305b9a307ea40e3012ca0e2e6dd0b2560f4352d74`. One copy
only, across all eight Discovery scan roots. Recorded because a single copy is
the exception in this project, not the rule.

## What this group set says about CLAUDE.md § 10, bullet 9

That bullet states `payload_scan.py` exists in four copies and calls this "the
cause". Today six files carry the name and four contents exist. The claim and
the machine disagree in detail. This is drift entry D-03 and is L1-A26's
subject as well as L1-A20's.
