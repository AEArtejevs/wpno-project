# J5 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 findings addressed in configuration scope: `L1-A20-RUN-A-F01` through `F04`
- Result: `SUCCESS_CONFIGURATION_SCOPE`

## Red evidence

The new canonical-path test initially failed because
`docker/litellm/payload_scan.py` was an independent regular file and Compose
mounted that duplicate rather than the tested anonymization scanner.

## Change

- Established `anonymization/payload_scan.py` as the canonical implementation.
- Replaced the byte-identical Docker duplicate in the isolated lane with a
  relative symlink to the canonical file.
- Changed Compose to mount the canonical scanner directly and read-only.
- Reworked `anonymization/test_copy_sync.py` to enforce the symlink target,
  canonical Compose mount, and distinct `golden/` test-asset classification.
- The historical golden scanner was not modified or promoted.

## Proof

- Focused Mac J5 suite: 2 passed.
- Focused Ubuntu J5 suite: 2 passed.
- Full Mac lane suite: 21 passed.
- Full Ubuntu lane suite: 21 passed.
- Replacing the symlink with a copied regular file fails the focused suite.
- Restoring the old Compose mount fails the focused suite.
- Server symlink target is exactly `../../anonymization/payload_scan.py`.
- Canonical source and test compile successfully; all changed files remain
  under 500 lines.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- Canonical scanner:
  `97bff976839ace8b6c1d934d7071477d968bdd1be10124fd5123f86c0a865932`.
- `anonymization/test_copy_sync.py`:
  `7d7eedb06368894fa3c14be359a5126afa7dced294e6891c24616e1c418b9a1d`.
- `docker/litellm/docker-compose.yml`:
  `002abe2453eb9a6b71327a37a61df17b77aed3c22da69d195b0836ed1d8d2a5d`.
- Historical golden scanner, unchanged:
  `ab29a4fa3e972f865f0f3dfb10887888a0464922070454e02584a34a4c54ba0a`.

## Limitations

- No container was started. The configuration now identifies one canonical
  source, but `L1-A20-RUN-A-F04` still requires later deployment-time mount
  and in-container hash evidence before a productive-runtime claim is valid.
- This receipt does not alter sealed R9.
