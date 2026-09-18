#!/usr/bin/env python3.11
"""S11_CONTENT_STATE_GATE — echte Trennung CONTENT_GATE / STATE_GATE (CPR-001).

CONTENT_GATE liest die Bytes AUSSCHLIESSLICH aus der Git-Objektdatenbank (git cat-file) des zu
committenden Candidate-Trees — nie aus dem veraenderlichen Working Tree (CPR-002/003). Der Validator-
Code selbst laeuft aus dem vertrauenswuerdigen aktuellen Prozess (Trusted Runner), NICHT aus dem
Kandidaten. STATE_GATE prueft den Repo-Zustand (HEAD/Parent/Remote/Snapshot) im echten Repo.

Scope-Guard V3 (F3): vergleicht Produktreferenz gegen den CANDIDATE-TREE (nicht HEAD).
"""
import os, re, subprocess, hashlib

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(args, cwd=None):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _blob_bytes(tree, path):
    """Bytes eines Pfads aus dem Candidate-Tree — direkt aus der Objektdatenbank."""
    r = subprocess.run(['git', 'cat-file', 'blob', '%s:%s' % (tree, path)], cwd=REPO, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _tree_paths(tree, prefix=''):
    c, out, _ = git(['ls-tree', '-r', '--name-only', tree] + ([prefix] if prefix else []))
    return [p for p in out.splitlines() if p.strip()] if c == 0 else []


# --- CONTENT_GATE: Falldaten-/Render-Freiheit der SPEC-Artefakte aus Git-Blobs ---
FORBIDDEN_MAGIC = [b'PK\x03\x04', b'%PDF', b'\x89PNG', b'\xd0\xcf\x11\xe0', b'GIF8', b'<svg', b'%!PS', b'8BPS']
CASE_SIG = [re.compile(rb'\d{1,3}(\.\d{3})+,\d{2}'), re.compile(rb'\b\d{2}\.\d{2}\.\d{4}\b'),
            re.compile(rb'\bDE\d{2} ?\d{4}'), re.compile(rb'\bGmbH\b|\bAG\b')]


def content_gate(candidate_tree, spec_prefixes=('reports/',)):
    """Return (verdict, findings). Liest NUR Git-Blobs des Candidate-Trees. Fail-closed."""
    findings = []
    # 006D-SPEC-Artefakte aus dem Tree (Namensmuster der Produktschicht)
    spec = [p for p in _tree_paths(candidate_tree)
            if os.path.basename(p).startswith(('TAX_LIABILITIES_VISUALIZATION', 'S11_SV_CONTRIBUTION_VISUALIZATION',
                                               'S11_TAX_SV_VISUALIZATION_SPEC', 'S11_TAX_SV_VALUATION_FIELD'))
            and p.endswith('.csv')]
    for p in spec:
        b = _blob_bytes(candidate_tree, p)
        if b is None:
            findings.append((p, 'BLOB_UNREADABLE_FAILCLOSED'))
            continue
        head = b.lstrip(b' \t\r\n\xef\xbb\xbf')
        for sig in FORBIDDEN_MAGIC:
            if head.startswith(sig):
                findings.append((p, 'FORBIDDEN_MAGIC'))
        # RT-Breaker: CASE_SIG war toter Code -> Klartext-Falldaten (Betrag/Datum/IBAN/Firmierung) pruefen
        for rx in CASE_SIG:
            if rx.search(b):
                findings.append((p, 'CASE_DATA_SIGNATURE:' + rx.pattern.decode('latin1')[:20]))
                break
    verdict = 'GREEN' if not findings else 'RED'
    return verdict, findings


# --- STATE_GATE: Repo-Zustand (real) ---
def state_gate(candidate_tree, parent_expected):
    findings = []
    c, out, _ = git(['remote'])
    if out.strip():
        findings.append(('remote', 'REMOTE_PRESENT'))
    c, head, _ = git(['rev-parse', 'HEAD'])
    if parent_expected and head.strip() != parent_expected:
        findings.append(('parent', 'PARENT_MOVED expected=%s head=%s' % (parent_expected[:8], head.strip()[:8])))
    return ('GREEN' if not findings else 'RED'), findings


# --- Scope-Guard V3 (F3): Candidate-Tree gegen Produktreferenz, nicht HEAD ---
FORBIDDEN_PRODUCT = [
    'zitate_register/_s11_006d_spec_validator.py',
    'zitate_register/visualization/S11_PS861_006D_SPEC_ONLY_SCHEMA.json',
    'zitate_register/check_s11_tax_sv_visualization_model_spec_only.py',
    'zitate_register/_f9r1_common.py', 'zitate_register/check_006d_',
    'reports/TAX_LIABILITIES_VISUALIZATION_REGISTER.csv',
    'reports/S11_SV_CONTRIBUTION_VISUALIZATION_REGISTER.csv',
    'reports/S11_TAX_SV_VISUALIZATION_SPEC.csv',
    'reports/S11_TAX_SV_VALUATION_FIELD_DECISION_CLASS_MAP.csv',
    'tests/test_s11_ps861006d_tax_sv_public_creditor_visualization_model.py',
    'tests/test_s11_ps861_006d_allowlist_hardening.py',
]


def _is_product_path(p):
    """Strukturelle Produkt-Fachlogik-Erkennung (RT-Breaker: enumerierte Denylist ist unvollstaendig).
    Faengt neue/Unterordner-/Praefix-Produktdateien."""
    b = os.path.basename(p)
    if any(p == f or p.startswith(f) for f in FORBIDDEN_PRODUCT):
        return True
    if b.startswith('check_006d_') or b.startswith('check_s11_tax_sv'):
        return True
    if b.startswith(('test_s11_ps861006d', 'test_s11_ps861_006d')):
        return True
    if 'VISUALIZATION' in p and p.endswith('.csv') and p.startswith('reports/'):
        return True
    if p.startswith('zitate_register/visualization/') and 'S11_PS861_006D' in p:
        return True
    return False


def scope_guard_candidate_tree(candidate_tree, product_reference):
    """Diff Produktreferenz..Candidate-Tree auf Produkt-Fachlogik (strukturell). Prueft den TREE, nicht HEAD."""
    c, out, _ = git(['diff', '--name-only', product_reference, candidate_tree])
    changed = [p for p in out.splitlines() if p.strip()]
    viol = [p for p in changed if _is_product_path(p)]
    return (not viol), viol, changed


if __name__ == '__main__':
    import sys, json
    tree = sys.argv[1] if len(sys.argv) > 1 else git(['rev-parse', 'HEAD^{tree}'])[1].strip()
    cg, cf = content_gate(tree)
    sg, sf = state_gate(tree, None)
    print(json.dumps({'content_gate': cg, 'content_findings': cf[:5], 'state_gate': sg, 'state_findings': sf[:5]}))
