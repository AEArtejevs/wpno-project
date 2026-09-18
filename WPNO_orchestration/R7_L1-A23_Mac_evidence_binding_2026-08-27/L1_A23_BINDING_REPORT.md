# L1-A23 Mac evidence binding report

Date: 2026-08-27  
Mode: `TARGETED_L1_A23_MAC_EVIDENCE_BINDING_ONLY`

## Outcome

The transferred Mac evidence package is valid for focused L1-A23 readiness and is accepted as current-Mac-reality evidence. L1-A23 moved from BLOCKED to READY_FOR_PLANNING. With no unrelated status change, readiness moved arithmetically from 32/35 to 33/35.

The two remaining gates are L1-A11 and L1-A24. L1-A14, L1-A17, and L1-A29 were not reopened.

## Package validation

- All required core records exist, are regular non-zero-byte files, and are not symlinks.
- No symlink or zero-byte regular evidence file exists anywhere in the transferred package.
- All JSON records parse.
- `REF14_MAC_REALITY.json` contains 14 file records, 14 matching crosswalk records, and 38 session-metadata records.
- File/crosswalk canonical paths, roles, and SHA-256 values are internally consistent.
- Required coverage includes the global `/Users/martinotten/.claude/CLAUDE.md`, project `/Users/martinotten/WPNO/CLAUDE.md`, relevant Docker configuration paths, `/Users/martinotten/WPNO/mcp/mcp.registry.json`, symlink status, and recorded Claude/Codex working directories.
- Secret-bearing fields are represented only by boolean indicators in the focused report; no secret values are reproduced here.
- No complete package-local manifest existed. `MAC_EVIDENCE_INTAKE_MANIFEST.sha256` was created as authorized over all 14 pre-existing regular evidence files, excluding itself, and then validated successfully.
- The package-local manifest SHA-256 is `85a35beda513939934966fd08190c8593d40262785a09a35572b803ce4e3fe57`.
- A final revalidation confirmed that every hash-bound transferred evidence file remained unchanged during this task.

## Authoritative requirement and lawful scope

The current `prompts/L1-A23.md` requires an exhaustive future comparison of checkable project `CLAUDE.md` claims against independent machine reality, with canonical paths, hashes, actual configuration evidence, working-directory context, and explicit treatment of uncheckable or unproven claims. The transferred package supplies the Mac-reality dependency needed to plan that audit; it does not execute the audit or assign claim-level verdicts.

The imported REF-14 Mac record preserves these distinctions:

- current Mac reality: evidence-backed and accepted;
- operator-produced measurement: identified as such;
- current-server REF-14 evidence: remains separately scoped to closed L1-A17;
- historical production identity and continued use: not proven;
- historical byte identity: not proven;
- session paths: evidence of recorded Claude/Codex working directories, not automatic proof of production use.

## Focused updates

Only the L1-A23/REF-14 binding and readiness surface was updated:

- `bindings/L1-A23.binding.json`
- four raw focused Mac evidence copies under `references/`
- `references/REF-14_MAC_MANIFEST.sha256`
- `references/manifest.json`
- `build/all_level1_scope/R7_ALL35_INPUT_READINESS.json`
- `build/all_level1_scope/R7_ALL35_INPUT_READINESS.md`
- `build/R7_CHANGED_FILES.sha256`
- package-local `MAC_EVIDENCE_INTAKE_MANIFEST.sha256`

Focused schema/invariant validation passed. The focused architecture does not require rehearsal before planning, so `FOCUSED_REHEARSAL=NOT_REQUIRED`. No shared executable code, controller state, audit progress, L1-A17 record, or freeze state changed.

R7 L1-A23 MAC EVIDENCE BINDING COMPLETE

MAC_EVIDENCE_PACKAGE_VALID:
YES

MAC_EVIDENCE_MANIFEST_VALID:
YES

REF14_L1_A23_STATUS:
ACCEPTED

L1_A23_READINESS:
READY

FOCUSED_REHEARSAL:
NOT_REQUIRED

AUDITS_READY_FOR_PLANNING:
33/35

REMAINING_GATES:
L1-A11 — human BGH period/provenance decision; L1-A24 — human external-launch-directory decision

SHARED_CONTROLLER_EXECUTABLE_CHANGED:
NO

FULL_CONTROLLER_SUITE_RERUN:
NO

R7_MODIFIED:
YES

R7_FROZEN:
NO

LIVE_AUDIT_PHASE_ADVANCED:
NO

NEXT_REQUIRED_ACTION:
Record the human BGH period/provenance decision for L1-A11.

FINAL_STATUS:
R7_L1_A23_CLOSED
