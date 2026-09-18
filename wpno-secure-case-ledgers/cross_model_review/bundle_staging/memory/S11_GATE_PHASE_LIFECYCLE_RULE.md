# S11 Gate-Phase-Lifecycle-Regel (VERBINDLICH)

1. Historische Recheck-/QC-Selbsttests bleiben erhalten und gegen ihre urspruengliche Baseline reproduzierbar (HISTORICAL_REPLAY).
2. Sie duerfen den heutigen HEAD nicht blockieren, wenn sie ausschliesslich die Unveraendertheit einer bewusst spaeter reparierten Kandidatenbaseline pruefen.
3. Eine aktuelle Gate-Phase ist zustands-/scopebezogen (ACTIVE_CURRENT).
4. Keine feste Kandidaten-Commit-ID als globale, dauerhaft aktive HEAD-Regel.
5. Keine stille Deaktivierung; jede Supersession braucht Begruendung UND Ersatzphase (reports/S11_GATE_PHASE_REGISTRY.csv).
6. Gate-Attestierung ist append-only und tree-gebunden.
