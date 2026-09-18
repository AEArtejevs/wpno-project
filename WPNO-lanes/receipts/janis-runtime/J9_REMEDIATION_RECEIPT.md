# J9 Remediation Receipt

- Date: 2026-09-01
- Lane: `/home/ubuntu/project/WPNO-lanes/janis-runtime`
- Human owner: Andris
- Writing agent: Codex
- Result: `SUCCESS_WITH_J8_EXTERNAL_DEPLOYMENT_BLOCKER`

## Matrix

Default collection now contains 40 tests covering the existing payload suite,
golden program, IBAN rules, German tax-ID structure, phone delimiters, address
case variants, clean negatives, canonical source layout, six-role copy
inventory, shell search safety, and offline LiteLLM source/configuration.

Five permanent mutation tests independently prove that the suite observes:

- an allow-all scanner decision;
- bypass of German IBAN validation;
- bypass of tax-ID repetition/leading-zero structure;
- rollback of the phone punctuation boundary;
- rollback of case-insensitive address detection.

The golden wrapper additionally kills its own allow-all mutation; the copy
inventory kills active alias drift and undeclared copies; shell tests kill the
broad beA and ungrouped-find rollback; and readiness tests kill a noncanonical
or writable party-name mount.

## Proof

- Default Mac collection: 40 tests.
- Full Mac regression: 40 passed.
- Default Ubuntu collection: 40 tests.
- Full Ubuntu regression: 40 passed.
- Focused J9 mutation suite on both hosts: 5 passed.
- All current Python files compile; both shell files pass `bash -n`.
- Every edited or newly added source/test file is under 500 lines. The existing
  538-line historical golden scanner was not edited.
- The final ordinary baseline diff has 1,133 lines and SHA-256
  `715075d5f95f36b2b68da1f3bbe4c20bd38ceedc0c2e18f43c0793ab5bc96f7b`.
- Scope diff contains only Janis-owned paths; no authoring, AP18, pytest.ini,
  live WPNO, baseline, R9, raw, tools, credential, or user configuration file
  changed.
- Generated `__pycache__`, `.pytest_cache`, and lane ledger artifacts were
  removed from the working lane after testing.
- No Git command, package install, Internet access, image pull/build, service
  start, container start, or secret read/write occurred.

## Remaining external blocker

J1-J7 and J9 are green in the isolated lane. J8 source/configuration is green,
but productive L1-A21 deployment remains blocked because the Ubuntu Docker
daemon has zero images and zero containers. Image availability, credentials,
build/start authorization, mounted-file identity, and in-container tests remain
the explicit human deployment gate.

## Audit integrity

Sealed R9 remains historical evidence and is not changed by these remediation
tests. Final read-only verification reported `ok=true`, `tampered=[]`, and all
63 sealed attempts intact.
