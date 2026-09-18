# Control-Plane Targeted Red Team (Erstlauf + Nachhaertung)

5 unabhaengige Breaker-Gruppen, 45 Angriffe, 28 erfolgreiche/partielle Bypaesse GEGEN DIE ERSTE Fix-Fassung. Der Red Team hat die erste Fassung gebrochen -> in DIESEM Lauf nachgehaertet (ein Reparaturzyklus):
- **RT-G1 self-referential-validator (P0):** gestagter Trivial-Validator faerbt sich selbst gruen -> gate_code_changed_vs_head(): Kontrollschicht-Code-Aenderung im Tree -> hoechstens GREEN_PENDING_GATECODE_REVIEW.
- **RT-G1/G3 test-hook (P0):** WPNO_STAGEDTREE_GATE_CMD nur bei WPNO_STAGEDTREE_TEST_MODE=1; Testmodus -> ATTESTED_TEST_MODE (nie Produktionsgruen).
- **RT-G2 gate-commit-decoupling (P0):** Broker erzwingt gate.validated_tree_oid==tree0 (VALIDATED_TREE_MISMATCH).
- **RT-G4 attestation-forgery (P0/CRITICAL, 10/10):** HMAC-SHA256 (off-git-Key) ueber jeden Record; Manipulation/Flip/Replay -> ATTESTATION_TAMPERED/SCHEMA_MISMATCH; _attested_green nutzt V2-HMAC.
- **RT-G5 phase-offswitch (CRITICAL):** DEMOTABLE_PHASES in Code gepinnt (nur recheck-protocol); scope-guard mit Praefix-Matching + unlisted-product-file-Erkennung.

Severity der Erst-Bypaesse: {'P0': 7, 'MEDIUM': 8, 'HIGH': 5, 'CRITICAL': 8}. Nachhaertung durch die Regressionstests (Staged-Tree-Binding 10/10, Attestation-Durability 8/8, Scope-Guard 7/7) + Verifikations-Red-Team belegt. [CSV](S11_CONTROL_PLANE_TARGETED_REDTEAM.csv)
