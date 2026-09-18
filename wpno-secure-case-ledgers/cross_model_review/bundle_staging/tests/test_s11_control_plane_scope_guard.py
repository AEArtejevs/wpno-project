#!/usr/bin/env python3.11
"""S11-Control-Plane-Scope-Guard (ACTIVE_CURRENT).

Zustands-/scope-bewusster Nachfolger des historischen recheck-protocol-Tests (der als HISTORICAL_REPLAY
in reports/S11_GATE_PHASE_REGISTRY.csv gefuehrt wird). Liest den Produkt-Referenzkandidaten und die
forbidden_product_paths aus memory/PRODUCT_CANDIDATE_REGISTRY.csv/.yaml und beweist, dass der aktuelle
Kontrollschicht-Lauf KEINE Produkt-Fachlogik gegenueber diesem Referenzkandidaten aendert.

Kein statisches Commit-Pinning: der Referenzkandidat kommt aus der Registry, nicht aus einer Konstante."""
import os, csv, subprocess, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a):
    return subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True)


def _registry():
    ref, forbidden = '670e362', []
    y = os.path.join(REPO, 'memory', 'PRODUCT_CANDIDATE_REGISTRY.yaml')
    if os.path.exists(y):
        infb = False
        for line in open(y, encoding='utf-8'):
            m = re.match(r'\s*product_reference_candidate:\s*"?([0-9a-f]+)"?', line)
            if m:
                ref = m.group(1)
            if re.match(r'\s*forbidden_product_paths:', line):
                infb = True
                continue
            if infb:
                mm = re.match(r'\s*-\s*(\S+)', line)
                if mm:
                    forbidden.append(mm.group(1))
                elif line.strip() and not line.startswith((' ', '\t')):
                    infb = False
    return ref, forbidden


REF, FORBIDDEN = _registry()


def test_registry_present_and_parsed():
    assert REF and len(REF) >= 7, ('Referenzkandidat nicht gelesen', REF)
    assert FORBIDDEN, 'forbidden_product_paths leer'


def test_reference_candidate_resolvable():
    assert git('cat-file', '-t', REF).returncode == 0, ('Referenzkandidat nicht im Repo', REF)


def test_no_product_fachlogic_changed_vs_reference():
    """Jede gegen die Referenz geaenderte Datei wird gegen die verbotenen Pfade als PREFIX geprueft
    (RT-G5 forbidden_path_prefix_bypass: literaler Pathspec matcht keine Praefixe)."""
    changed_all = git('diff', '--name-only', REF, 'HEAD').stdout.split()
    violations = [f for f in changed_all if any(f == p or f.startswith(p) for p in FORBIDDEN)]
    assert not violations, ('Produkt-Fachlogik gegenueber Referenz veraendert (Scope-Verstoss):', sorted(set(violations)))


def test_no_new_unlisted_product_file():
    """Neue/geaenderte Produkt-Fachdateien ausserhalb der Liste (RT-G5 unlisted_new_product_file):
    jeder check_006d_*-Guard, die SPEC-Register-CSV oder ein 006D-Produkttest zaehlt als Produkt-Fachlogik."""
    changed_all = git('diff', '--name-only', REF, 'HEAD').stdout.split()
    def is_product(f):
        b = os.path.basename(f)
        return (b.startswith('check_006d_') or b.startswith('check_s11_tax_sv')
                or (f.startswith('reports/') and 'VISUALIZATION' in f and f.endswith('.csv'))
                or b.startswith('test_s11_ps861006d') or b.startswith('test_s11_ps861_006d'))
    viols = [f for f in changed_all if is_product(f)]
    assert not viols, ('Produkt-Fachdatei ausserhalb Kontrollschicht-Scope geaendert:', sorted(set(viols)))


def test_no_silent_repin_of_recheck_protocol():
    """Der historische recheck-protocol-Test darf NICHT still auf den neuen Kandidaten umgepinnt werden."""
    p = os.path.join(REPO, 'tests', 'test_s11_ps861_006d_recheck_protocol.py')
    if os.path.exists(p):
        assert "CAND = '9a50f7e'" in open(p, encoding='utf-8').read(), \
            'recheck-protocol CAND wurde umgepinnt statt via Registry supersededt'


def test_phase_registry_documents_supersession():
    reg = os.path.join(REPO, 'reports', 'S11_GATE_PHASE_REGISTRY.csv')
    rows = list(csv.DictReader(open(reg, encoding='utf-8')))
    rp = {r['phase_id']: r for r in rows}
    r = rp.get('S11-PS861-006D-Recheck-Protocol')
    assert r and r['lifecycle_status'] == 'HISTORICAL_REPLAY' and r['superseded_by'] and r['reason'], \
        'stale Recheck-Phase ohne dokumentierte Supersession/Ersatz'
    assert 'S11-Control-Plane-Scope-Guard' in rp and rp['S11-Control-Plane-Scope-Guard']['lifecycle_status'] == 'ACTIVE_CURRENT'


def test_demotable_phase_allowlist_minimal():
    """Nur die bekannte stale Phase darf per Registry degradiert werden (RT-G5 universal_phase_offswitch/
    security_guard_suppression): Sicherheitsphasen sind in Code geschuetzt."""
    import importlib
    sys_scripts = os.path.join(REPO, 'scripts')
    if sys_scripts not in os.sys.path:
        os.sys.path.insert(0, sys_scripts)
    G = importlib.import_module('run_precommit_quality_gate')
    assert G.DEMOTABLE_PHASES == frozenset({'S11-PS861-006D-Recheck-Protocol'}), G.DEMOTABLE_PHASES
    for protected in ('S11-Control-Plane-Scope-Guard', 'S11-Control-Plane-Staged-Tree-Binding',
                      'S11-Gate-Attestation-Durability', 'verifikator.py check'):
        assert protected not in G.DEMOTABLE_PHASES


TESTS = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
if __name__ == '__main__':
    ok = 0
    for t in TESTS:
        try:
            t(); ok += 1
        except AssertionError as e:
            print('  [FAIL]', t.__name__, str(e)[:160])
        except Exception as e:
            print('  [ERROR]', t.__name__, type(e).__name__, str(e)[:160])
    print('S11-CONTROL-PLANE-SCOPE-GUARD TESTS: %d/%d PASS' % (ok, len(TESTS)))
    import sys
    sys.exit(0 if ok == len(TESTS) else 1)
