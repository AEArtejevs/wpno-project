# Control-Plane — Validated-Tree-Design

Leitsatz: **VALIDIERE DEN GIT-OBJEKTBAUM, NICHT DIE ZUFAELLIGE WORKING-TREE-ANSICHT.**

`scripts/s11_staged_tree_gate.py`: `tree = git write-tree` (exakter Index-Tree) -> `git commit-tree tree -p HEAD` -> `git worktree add --detach <tmp> <commit>` (git-nativer, shared-objectdb Materialisierungsbaum) -> das volle Pre-Commit-Gate laeuft mit cwd=<tmp> GEGEN diesen Baum. Danach `git worktree remove --force` + `prune`. Working-Tree-Pruefungen bleiben als Entwicklerhinweis erlaubt, gelten aber NICHT mehr als Beleg fuer den Commit-Inhalt. Fail-closed bei nicht lesbarem Blob/unbekanntem Mode/Submodule/Symlink.
