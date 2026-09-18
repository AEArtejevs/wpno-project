# S11 Gate-Phase-Registry

Lebenszyklus gate-registrierter Selbsttests. ACTIVE_CURRENT laeuft gegen HEAD; HISTORICAL_REPLAY laeuft gegen die eigene Baseline (nicht gegen HEAD) und blockiert HEAD NICHT; SUPERSEDED braucht Ersatzphase + Begruendung. Keine stille Deaktivierung. Der Pre-Commit-Gate liest diese Registry und fuehrt nur ACTIVE_CURRENT-Phasen gegen HEAD aus.

- **S11-PS861-006D-Recheck-Protocol** -> HISTORICAL_REPLAY (Baseline 080df65), ersetzt durch S11-Control-Plane-Scope-Guard. Grund: RCK2-22 (statischer CAND=9a50f7e wird vom sanktionierten 670e362-Hardening bewusst superseded).
- **S11-Control-Plane-Scope-Guard** -> ACTIVE_CURRENT (Referenz 670e362).
