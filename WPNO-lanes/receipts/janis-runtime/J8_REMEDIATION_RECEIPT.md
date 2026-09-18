# J8 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- R9 findings: `L1-A21-RUN-A-F01`, `L1-A21-RUN-A-F02`
- Result: `SOURCE_READY_DEPLOYMENT_BLOCKED_EXTERNAL`

## Red evidence

The initial four-test readiness suite had three checks pass and one fail.
Compose did not mount every runtime source read-only and did not mount the
canonical party-name list used by the scanner.

## Change

- Restored the existing digest-pinned WPNO Dockerfile into the isolated lane;
  it had been absent from the lane copy but was read from the untouched live
  project without reading `.env`.
- Mounted config, callback, canonical scanner, IBAN validator, canonical party
  names, tool gate, and MCP registry read-only.
- Added `anonymization/test_litellm_offline_readiness.py`.
- The test renders Compose with temporary placeholder external values without
  contacting the daemon, then imports the callback through isolated dependency
  stubs and verifies clean pass, PII block 451, and unknown-tool block 403.

## Proof

- Focused Mac J8 suite: 4 passed.
- Focused Ubuntu J8 suite: 4 passed.
- Full Mac lane suite: 35 passed.
- Full Ubuntu lane suite: 35 passed.
- Compose renders successfully offline with placeholder values.
- Dockerfile base reference is digest-pinned.
- Missing canonical/read-only party-name mount mutation fails the focused suite.
- Callback and internal runtime modules compile successfully.
- R9 verification: `ok=true`, `tampered=[]`, `sealed=63`, `intact=63`.

## Hashes

- `docker/litellm/Dockerfile`:
  `05fbf2c570ce65d64fdd7e62920293bda8a1c0cc13c5d2d64961bfabf072692a`.
- `docker/litellm/docker-compose.yml`: J5
  `002abe2453eb9a6b71327a37a61df17b77aed3c22da69d195b0836ed1d8d2a5d`,
  final `b29dbb62da3870266347d9f6f13baadd6d3357343b577c4bc83466dccc1ac5d3`.
- `anonymization/test_litellm_offline_readiness.py`: baseline absent, final
  `6d5a6cba8d0c8caf5f7de60dcdbbb8495f11b9a9c29aec54bb1f8861ba311b34`.

## External deployment blocker

The Ubuntu Docker daemon is healthy but reports zero images and zero
containers. The digest-pinned LiteLLM base, `redis:7`, and the custom WPNO
image are therefore unavailable locally. The Dockerfile also requires its
declared Python dependency during a build. No image was pulled or built, no
network was used, no `.env` or secret was read/copied/created in the lane, and
no container was started. Productive deployment remains the plan's explicit
morning human gate; L1-A21 cannot honestly be marked remediated yet.

## Limitations

- Source/configuration and fail-closed callback wiring are ready. Productive
  image availability, credentials, startup, mount identity, and in-container
  hash validation remain external deployment work.
- This receipt does not alter sealed R9.
