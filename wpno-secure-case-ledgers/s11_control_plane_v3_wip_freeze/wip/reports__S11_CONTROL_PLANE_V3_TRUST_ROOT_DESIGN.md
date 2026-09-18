# Control-Plane V3 — Trust-Root & Architektur

Leitsatz: Verifikation ohne Geheimnis, Signieren nur mit Privatkey.

**Attestation V3 (scripts/s11_attestation_v3.py):** Ed25519 — privater Key im getrennten Signer-Ort (~/wpno-secure-case-ledgers/signer, 0600), oeffentlicher Key im Repo (memory/attestation_v3_ed25519_pubkey.pem). Jede Partei verifiziert OHNE Geheimnis; Faelschen erfordert den Privatkey (Fortschritt ggue. symmetrischem HMAC). Record bindet candidate_tree, parent, gate_manifest_hash, policy_versions und die Umgebung (python/git-version, PATH/PYTHONPATH-Hash, locale, TZ). GETRENNTE Statusachsen: crypto_valid (Signatur), policy_fresh (Manifest/Policy), product_chain_eligible (tree_match ∧ beide Gates GREEN ∧ policy_fresh). HASHVERKETTETES Ledger (prev_entry_hash) -> Reihenfolge/Einfuegung erkennbar. Signer-Key-Verlust (nur pubkey) ist fail-closed (kein Neuerzeugen).

**Content/State-Gate (scripts/s11_content_state_gate.py):** content_gate liest die Bytes AUSSCHLIESSLICH aus der Git-Objektdatenbank des Candidate-Trees (git cat-file) — nie aus dem veraenderlichen Working Tree; Validator-Code laeuft aus dem vertrauenswuerdigen aktuellen Prozess (Trusted Runner). state_gate prueft den Repo-Zustand (Remote/Parent). scope_guard_candidate_tree difft Produktreferenz gegen den CANDIDATE-TREE (F3).

**Broker V3 (scripts/s11_validated_commit_v3.py):** Reihenfolge Gates -> commit-tree -> Attestierung V3 -> ERST danach Candidate-Ref (refs/candidates/...); die AKTIVE Branch wird NIE promoted (F1). Kein Selftest-Bypass.

**Restpunkte (ehrlich, PARTIAL):** vollstaendige externe-Input-Erfassung (CPR-003/008), harter Produkt-Commit-Eligibility-Guard (CPR-010), Direktbefehl-Detektion/Hook-Aequivalenz (CPR-011/012), OS-Domaenentrennung des Signers (CPR-007), Alt-Gate-Selftest/SKIP (CODE-F2 im Alt-Pfad). Diese bleiben fuer das Cross-Model-Review und Folgezyklen offen.
