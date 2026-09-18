# Attestation V2 — Schema (abgeleitet aus scripts/ci_gate.py)

Record-Felder (write_attestation_v2): attestation_version, ticket_id, gate_run_id, parent_commit, validated_tree_sha, created_commit_sha, created_commit_tree_sha, tree_match, gate_code_hash, test_manifest_hash, schema_hashes{validator,schema}, result, test_mode, gatecode_review, created_at_utc, status, record_hmac.

Stati (ATT_V2_STATUS): ATTESTED_GREEN_FOR_EXACT_TREE, ATTESTED_RED, ATTESTATION_STALE, ATTESTATION_SCHEMA_MISMATCH, ATTESTATION_TESTSET_SUPERSEDED, UNATTESTED, ATTESTATION_TAMPERED, ATTESTATION_KEY_MISSING, ATTESTED_TEST_MODE, ATTESTED_GREEN_PENDING_GATECODE_REVIEW.

Integritaet: HMAC-SHA256 ueber den kanonischen Record (sortierte Keys, ohne record_hmac). Produktions-Key-Loading-Logik: siehe scripts/ci_gate.py _hmac_key() / _hmac_key_path() (Key off-git 0600, ueber WPNO_ATTEST_HMAC_KEY ueberschreibbar). HINWEIS (Reviewfrage): HMAC ist symmetrisch — wer den Key lesen kann, kann signieren; kein Ed25519/Hardware-Signer, kein Signer-Prozess getrennt. SIGNING_KEY_ACCESSIBLE_TO_PRODUCT_AGENT=ja, SIGNER_PROCESS_SEPARATED=nein.
