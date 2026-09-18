# J6 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 findings: `L1-A26-RUN-A-F02`, `L1-A26-RUN-A-F03`
- Result: `SUCCESS`

## Red evidence

The initial five-test suite had two semantic controls pass and two source
guards fail: TrackC still used broad `*bea*` matching and ungrouped shared
predicates, while all three S7 disjunctions were ungrouped.

## Change

- Replaced broad beA substring matching with bounded filename-token patterns
  that accept standalone/delimited beA forms but reject `Bearbeitung`.
- Wrapped all TrackC caller predicates so shared file-type and AppleDouble
  exclusions apply to every `-o` branch.
- Grouped all three S7 `find` disjunctions so depth/type rules apply to every
  branch; the MCP search now also requires a regular file.
- Added `anonymization/test_shell_find_safety.py` with source-bound guards and
  executable delimiter/type/exclusion controls.

## Proof

- Focused macOS/BSD-find J6 suite: 5 passed.
- Focused Ubuntu/GNU-find J6 suite: 5 passed.
- Full Mac lane suite: 26 passed.
- Full Ubuntu lane suite: 26 passed.
- Both shell scripts pass `bash -n` on macOS and Ubuntu.
- Broad-glob and grouping rollback mutant: three focused tests fail.
- All changed files remain under 500 lines.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- `S7_bestand.sh`: baseline
  `c9f9ffb56066fa677d063051a00155576bb3bc58818e97307aaa6299e90aad04`,
  final `2bcad08f96e5593ad6b374c9a6b7f3dbe50315adb7b1208f1bd40ee64f9e4712`.
- `TrackC_bestand.sh`: baseline
  `bcf32c86afe4cb8f667d0c51ca5e0bd812700b3df3921d31024aa08959d65614`,
  final `075506cf411ce1b091d185918b1c61797e66d82007e53b6eb99103e6188c8611`.
- `anonymization/test_shell_find_safety.py`: baseline absent, final
  `dca6cab394d6824a6658b67d40d04f4d73afb8c6145b13639109439f79e732e9`.

## Limitations

- The inventory scripts were not pointed at Martin's external drive. J6 proves
  their search semantics with controlled files on both supported find
  implementations; productive inventory use remains a later operator action.
- This receipt does not alter sealed R9.
