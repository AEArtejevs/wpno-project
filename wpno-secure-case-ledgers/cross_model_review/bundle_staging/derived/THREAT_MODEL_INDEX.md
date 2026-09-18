# Threat-Model-Index (abgeleitet)

Angriffsklassen aus dem Fix-eigenen + Verifikations-Red-Team (siehe reports/S11_CONTROL_PLANE_TARGETED_REDTEAM*.csv): staged-blob (WT!=Index), TOCTOU/gate-commit-decoupling, self-referential-validator (gesamte Validierungsflaeche), test-hook-injection, attestation-forgery (V1/V2), phase-offswitch/security-guard-suppression, scope-guard-prefix/unlisted-product-file, lock-stealing, intent-to-add. Geschlossen ueber 3 Reparaturzyklen; Residuen (MEDIUM/LOW) dokumentiert.
