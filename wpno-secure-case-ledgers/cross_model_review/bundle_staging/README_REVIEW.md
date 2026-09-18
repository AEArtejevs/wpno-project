# Cross-Model Review Bundle — S11 Control Plane (Staged-Tree/TOCTOU/Attestation)

- candidate_commit: 5ebc7adb934e2a57e507e2d767f3b4d0cbec475e
- parent_commit: 670e362a0b3937722213dd78abfaa9661b1f2549
- candidate_tree: 2aa02bba3f45829de1601472740d0cbb276f041a
- attestation_status: ATTESTED_GREEN_PENDING_GATECODE_REVIEW
- control_plane_quality_confirmed: nein
- product_baseline: 670e362 (NOT_ACCEPTED_L99_BLOCKED)
- product_work_allowed: nein · control_plane_review_allowed: ja · cross_model_review_required: true

## Claimed invariants
- committed_tree == validated_tree == HEAD^{tree} (per Broker-Re-Check + Attestierung).
- Working Tree == Index vor Gate (sonst WORKTREE_INDEX_DIVERGENCE -> RED).
- update-ref Compare-and-Swap gegen erwarteten Parent (HEAD-Bewegung -> Abbruch).
- gate_code_changed_vs_head: JEDE Validierungsdatei (scripts/tests/zitate_register/s11_core *.py + Hooks + Steuer-CSV/YAML) veraendert -> hoechstens GREEN_PENDING_GATECODE_REVIEW.
- Attestierung V2 tree-gebunden + HMAC; Manipulation -> ATTESTATION_TAMPERED; Testmodus -> ATTESTED_TEST_MODE.
- DEMOTABLE_PHASES (Code) = {recheck-protocol}; keine andere (Sicherheits-)Phase per Registry abschaltbar.
- Scope-Guard: 0 Produkt-Fachlogik-Diff gegen 670e362 (Praefix-Matching + unlisted-product-file).

## Open questions (unabhaengig zu pruefen)
1. Zwei-Ebenen-Gate NICHT umgesetzt: CONTENT_GATE (nur Candidate-Tree-Blobs aus der Objektdatenbank) und STATE_GATE (HEAD/Parent/Remote/Snapshot/Lock) sind noch NICHT technisch getrennt; stattdessen Working==Index-Invariante.
2. Working==Index != garantierte Byte-Identitaet: .gitattributes/clean-smudge/working-tree-encoding/EOL/ident/LFS/sparse/skip-worktree/assume-unchanged/Submodule koennen Blob != Working-Bytes erzeugen. NICHT geprueft.
3. Untracked/ignored Input-Kanal: git diff --quiet ignoriert untracked Dateien; von Tests/Guards gelesene off-git/generierte/ENV-Inputs sind NICHT in der Attestierung erfasst/gehasht.
4. Mutation waehrend des Gate-Laufs (Mischzustand lesen, dann zuruecksetzen) nur durch kooperativen Lock adressiert; Content-Checks laufen NICHT gegen unveraenderliche Blobs, gelesene Dateimenge wird NICHT vor/nach gehasht.
5. HMAC symmetrisch, Key fuer denselben Nutzer/Agenten lesbar -> keine unabhaengige Vertrauenswurzel (kein Ed25519/Hardware/Signer-Prozess). SIGNING_KEY_ACCESSIBLE_TO_PRODUCT_AGENT=ja, SIGNER_PROCESS_SEPARATED=nein.
6. Attestierungsinputs unvollstaendig: Python/Git-Version, Lockfile, Tool-Hashes, PATH/PYTHONPATH, ENV, Locale/TZ, Schema-/Policy-Versionen, externe Manifeste, Seeds, Timeouts NICHT im Record.
7. V1-Legacy: alte unsignierte V1-Records sind (noch) nicht als LEGACY markiert; Frage ob V1 je einen aktuellen gruenen Status begruenden darf, sobald V2 aktiv ist (aktuell: _attested_green verlangt gueltige V2, sonst HMAC-V1).
8. PENDING_GATECODE_REVIEW blockiert Produktcommits noch nicht HART per Guard (parent_attestation_status != FINAL_GREEN -> PRODUCT_COMMIT_BLOCKED ist NICHT als Guard erzwungen).
9. commit-tree/update-ref umgehen Hooks: der Broker fuehrt NICHT nachweislich alle Hookfunktionen aus (Commit-Message-Regeln, Secret-Scan, Reflog, Signatur, Session-Handoff); direkter git commit/update-ref bleibt lokal moeglich und muesste konsequent als UNATTESTED/NOT_VALID_FOR_PRODUCT_CHAIN behandelt werden.

## Absent-but-listed (ehrlich)
- memory/GATE_ATTESTATION_SCHEMA.md/.csv (Konzept in scripts/ci_gate.py + derived/attestation_v2_schema.md)
- memory/GIT_CANDIDATE_TREE_VALIDATION_CONSTITUTION.md/.csv (Konzept in scripts/s11_staged_tree_gate.py-Docstring + reports/S11_CONTROL_PLANE_VALIDATED_TREE_DESIGN.md)
- memory/S11_GATE_PHASE_REGISTRY.csv (real unter reports/S11_GATE_PHASE_REGISTRY.csv)

## Hinweis Oracle-Unabhaengigkeit
Die unabhaengige Pruefung darf NICHT den Broker/ci_gate als alleinigen Oracle nutzen; git-Objekte (git cat-file/rev-parse/ls-tree) direkt pruefen. Produktions-Key-Loading-Logik in scripts/ci_gate.py; die Beispielattestierung nutzt einen SYNTHETISCHEN Key.

## Secret-Scan
kein echter HMAC-Key enthalten (verifiziert); siehe BUNDLE_MANIFEST.csv contains_secret.
