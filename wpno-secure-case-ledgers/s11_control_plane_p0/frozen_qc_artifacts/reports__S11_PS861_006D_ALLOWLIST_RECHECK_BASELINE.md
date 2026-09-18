# S11-PS861-006D Allowlist Recheck — Baseline

Unabhaengiger, read-only L99-Recheck der gehaerteten Kandidatenbaseline `670e362`. Behaupteter Status `006D_ALLOWLIST_FORMAT_HARDENED_CANDIDATE_PENDING_INDEPENDENT_L99_RECHECK` — GEPRUEFT, nicht uebernommen.

- **current_head**: 670e362
- **commit_670e362_present**: commit
- **commit_080df65_present**: commit
- **commit_9a50f7e_present**: commit
- **commit_ed862a4_present**: commit
- **commit_bb28769_present**: commit
- **working_tree_clean_before_qc**: false (nur reports/ACTIVE_REDTEAM_RUNS.csv=EF-06-Register + memory)
- **index_clean**: true
- **product_files_changed_since_670e362**: 0 (git diff 670e362 -- zitate_register/ tests/ scripts/ = leer)
- **remote_count**: 0
- **ppt001_status**: NOT_STARTED
- **official_count**: 27
- **release_decisions_count**: 0
- **court_ready_status**: GESPERRT
- **freigabe_status**: OFFEN (UNREVIEWED)
- **render_artifact_count**: 0
- **working_tree_vs_index_vs_commit_tree**: GETRENNT GEPRUEFT: Guards lesen B.repdir()=WORKING TREE, nicht git-Index/Commit-Tree -> siehe STAGED_BLOB-Befund

Kein Abbruchgrund aus Baseline (Produkt unveraendert, keine Statushochung, PPT-001 NOT_STARTED, 0 Renderartefakte). Working-Tree/Index/Commit-Tree wurden GETRENNT betrachtet; die Trennung ist selbst Gegenstand des STAGED_BLOB-Befunds.
