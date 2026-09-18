# Control-Plane — Kandidatenstatus

Maximaler Status dieses Laufs: **CONTROL_PLANE_STAGED_TREE_ATTESTATION_HARDENED_CANDIDATE_PENDING_CROSS_MODEL_REVIEW**. NICHT: L99_READY, QUALITY_CONFIRMED, PRODUCT_BASELINE_CONFIRMED, COURT_READY, BERUFSTRAEGERFREIGEGEBEN, VISUALIZATION_EXECUTION_APPROVED. 670e362 bleibt NOT_ACCEPTED_L99_BLOCKED (kein Produkt-Baseline). Naechster Trigger: S11_CONTROL_PLANE_CROSS_MODEL_DUAL_RECHECK_AFTER_STAGED_TREE_FIX.

## Reparaturzyklen (Fix-eigener Red Team)

Der Kontrollschicht-Fix wurde durch einen eigenen Red Team (5 Gruppen, 28 Erst-Bypaesse) + Verifikations-Red-Team (4 Gruppen) gehaertet:
- **Zyklus 1:** staged-tree-Bindung, TOCTOU/CAS, test-hook (TEST_MODE), Attestierung V2 (HMAC), DEMOTABLE_PHASES, scope-guard-Praefix.
- **Zyklus 2:** V1-Attestierung HMAC-gesichert (forged-v1 -> abgewiesen).
- **Zyklus 3:** self-referential-validator STRUKTURELL geschlossen (gesamte Validierungsflaeche statt Teilliste) -> gate_code_changed erkennt jede Validator-Entschaerfung.

Verifikation: V2 (decoupling) 0 bypassbar, V4 (phase-offswitch/scope) 0 bypassbar, V1-Kernvektoren nach Zyklus 3 geschlossen (deterministisch reproduziert). Residuen (dokumentiert, MEDIUM/LOW): intent-to-add plain-commit-Pfad, Lock-Entfernung durch Dateisystem-Eigentuemer, HMAC-Key auf derselben Maschine lesbar (ehrliche lokale Tamper-Evidenz-Grenze, wie --no-verify). **Dieser Kontrollschicht-Commit selbst ist ATTESTED_GREEN_PENDING_GATECODE_REVIEW** (er aendert Gate-Code) -> Cross-Model-Review ist Voraussetzung, kein Selbst-Final-Green.
