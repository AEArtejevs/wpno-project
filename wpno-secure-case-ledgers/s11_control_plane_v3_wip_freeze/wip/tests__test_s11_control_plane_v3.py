#!/usr/bin/env python3.11
"""S11-Control-Plane-V3 — Beweistests fuer Trust-Root V3 + F1/F2/F3-Fixes.

Beweist: (a) Ed25519 asymmetrisch — Verifikation ohne Privatkey moeglich, Faelschung ohne Privatkey
unmoeglich; (b) CONTENT_GATE liest Git-Blobs des Candidate-Trees, nicht den Working Tree; (c) Scope-Guard
prueft den Candidate-Tree gegen die Produktreferenz (F3); (d) Broker attestiert VOR dem Ref-Schreiben und
promotet die aktive Branch NICHT (F1); (e) Ledger-Hash-Kette; (f) getrennte Statusachse product_chain_eligible.
"""
import os, sys, subprocess, tempfile, shutil, json, importlib

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
sys.path.insert(0, SCRIPTS)
results = []
def case(n, c, d=''):
    results.append((n, 'PASS' if c else 'FAIL', '' if c else d))


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def sandbox(spec_content=b'id\nX1\n'):
    d = tempfile.mkdtemp(prefix='v3_')
    os.makedirs(os.path.join(d, 'reports'))
    os.makedirs(os.path.join(d, 'memory'))
    for c in ('git init -q', 'git config user.email t@t', 'git config user.name t', 'git config commit.gpgsign false'):
        sh(c, d)
    with open(os.path.join(d, 'reports', 'TAX_LIABILITIES_VISUALIZATION_REGISTER.csv'), 'wb') as f:
        f.write(spec_content)
    sh('git add -A && git commit -qm base', d)
    return d


def v3env(d):
    return {'WPNO_CI_REPO': d, 'WPNO_ATTEST_V3_DIR': os.path.join(d, '.git', 'v3'),
            'WPNO_SIGNER_PRIVKEY': os.path.join(d, 'signer', 'priv.pem'),
            'WPNO_SIGNER_PUBKEY': os.path.join(d, 'memory', 'pub.pem')}


def test_all():
    import s11_attestation_v3 as A3
    import s11_content_state_gate as CSG

    # a) Ed25519 asymmetrisch
    d = sandbox()
    os.environ.update(v3env(d))
    a3 = importlib.reload(A3)
    commit = sh('git rev-parse HEAD', d).stdout.strip()
    tree = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    a3.write_attestation_v3(commit, tree, None, tree, 'T', 'GREEN', 'GREEN', 'gm', {'x': 1})
    case('a1_write_verify', a3.verify_attestation_v3(commit)[0] == 'ATTESTED_PRODUCT_CHAIN_ELIGIBLE')
    os.remove(os.path.join(d, 'signer', 'priv.pem'))
    case('a2_verify_without_privkey', a3.verify_attestation_v3(commit)[0] == 'ATTESTED_PRODUCT_CHAIN_ELIGIBLE')
    p = os.path.join(d, '.git', 'v3', commit + '.v3.json')
    r = json.load(open(p)); r['status_axes']['product_chain_eligible'] = True; r['content_gate'] = 'EVIL'
    json.dump(r, open(p, 'w'))
    case('a3_forge_without_privkey_fails', a3.verify_attestation_v3(commit)[0] == 'ATTESTATION_SIGNATURE_INVALID')
    shutil.rmtree(d, ignore_errors=True)

    # b) CONTENT_GATE liest Git-Blob, nicht Working Tree
    d = sandbox(spec_content=b'%PDF-1.4\nevil\n')  # boeser Blob im Tree
    os.environ.update(v3env(d))
    csg = importlib.reload(CSG)
    tree = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    # Working Tree jetzt "saeubern" — darf das Blob-Ergebnis NICHT beeinflussen
    open(os.path.join(d, 'reports', 'TAX_LIABILITIES_VISUALIZATION_REGISTER.csv'), 'w').write('id\nCLEAN\n')
    cg, cf = csg.content_gate(tree)
    case('b1_content_gate_reads_blob_not_worktree', cg == 'RED' and any('MAGIC' in x[1] for x in cf), str(cf))
    shutil.rmtree(d, ignore_errors=True)

    d = sandbox(spec_content=b'id\nCLEAN\n')
    os.environ.update(v3env(d))
    csg = importlib.reload(CSG)
    tree = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    case('b2_clean_blob_green', csg.content_gate(tree)[0] == 'GREEN')
    shutil.rmtree(d, ignore_errors=True)

    # c) Scope-Guard V3 gegen Candidate-Tree
    d = sandbox()
    os.environ.update(v3env(d))
    csg = importlib.reload(CSG)
    ref_commit = sh('git rev-parse HEAD', d).stdout.strip()
    os.makedirs(os.path.join(d, 'zitate_register'), exist_ok=True)
    open(os.path.join(d, 'zitate_register', 'check_006d_evil.py'), 'w').write('# tamper\n')  # verbotener Praefix
    sh('git add -A', d)
    cand_tree = sh('git write-tree', d).stdout.strip()
    ok, viol, _ = csg.scope_guard_candidate_tree(cand_tree, ref_commit)
    case('c1_scope_guard_candidate_tree_flags_product', (not ok) and any('check_006d_' in v for v in viol), str(viol))
    shutil.rmtree(d, ignore_errors=True)

    # d) Broker F1: Attestierung vor Ref; aktive Branch nicht promoted
    d = sandbox()
    env = v3env(d)
    os.makedirs(os.path.join(d, 'reports'), exist_ok=True)
    open(os.path.join(d, 'reports', 'cp.csv'), 'w').write('id\nV3\n')
    sh('git add -A', d)
    main0 = sh('git rev-parse HEAD', d).stdout.strip()
    r = sh([sys.executable, os.path.join(SCRIPTS, 's11_validated_commit_v3.py'),
            'v3 candidate', 'T', 'refs/candidates/test-v3', main0], d, env)
    main1 = sh('git rev-parse HEAD', d).stdout.strip()
    candref = sh('git rev-parse refs/candidates/test-v3', d).stdout.strip()
    case('d1_broker_attests_and_candidate_ref', 'V3_CANDIDATE_ATTESTED' in r.stdout and candref and candref != main0, r.stdout[-160:])
    case('d2_active_branch_not_promoted', main1 == main0, 'active branch moved!')
    # Attestierung existiert fuer den Candidate-Commit + ist gueltig (in-process auf Sandbox zeigen)
    os.environ.update(env)
    a3 = importlib.reload(A3)
    v, _, _ = a3.verify_attestation_v3(candref)
    case('d3_candidate_attested_valid', v.startswith('ATTESTED_'), v)
    shutil.rmtree(d, ignore_errors=True)

    # e) Ledger-Hash-Kette ueber ZWEI verschiedene Commits (ein Record je Commit)
    d = sandbox()
    os.environ.update(v3env(d))
    a3 = importlib.reload(A3)
    c1 = sh('git rev-parse HEAD', d).stdout.strip()
    t1 = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    a3.write_attestation_v3(c1, t1, None, t1, 'T', 'GREEN', 'GREEN', 'gm', {'x': 1})
    open(os.path.join(d, 'reports', 'b.csv'), 'w').write('y\n2\n')
    sh('git add -A && git commit -qm c2', d)
    c2 = sh('git rev-parse HEAD', d).stdout.strip()
    t2 = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    a3.write_attestation_v3(c2, t2, c1, t2, 'T', 'GREEN', 'GREEN', 'gm', {'x': 2})
    ok, n = a3.verify_ledger_chain()
    case('e1_ledger_chain_valid', ok and n == 2, 'n=%d ok=%s' % (n, ok))
    # Tail-Truncation: neuesten signierten Record entfernen -> Kopf-Anker faengt es
    os.remove(os.path.join(a3.attest_dir_v3(), c2 + '.v3.json'))
    case('e2_truncation_detected', not a3.verify_ledger_chain()[0])
    shutil.rmtree(d, ignore_errors=True)

    # f) getrennte Statusachse: content RED -> product_chain_eligible False, crypto_valid True
    d = sandbox()
    os.environ.update(v3env(d))
    a3 = importlib.reload(A3)
    commit = sh('git rev-parse HEAD', d).stdout.strip()
    tree = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    a3.write_attestation_v3(commit, tree, None, tree, 'T', 'RED', 'GREEN', 'gm', {'x': 1})
    v, axes, _ = a3.verify_attestation_v3(commit)
    case('f1_separate_axes', v == 'ATTESTED_PENDING_NOT_ELIGIBLE' and axes.get('crypto_valid') is True and axes.get('product_chain_eligible') is False, str(axes))
    shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    test_all()
    ok = sum(1 for _, s, _ in results if s == 'PASS')
    for n, s, d in results:
        if s == 'FAIL':
            print('  [FAIL] %s: %s' % (n, d))
    print('S11-CONTROL-PLANE-V3 TESTS: %d/%d PASS' % (ok, len(results)))
    sys.exit(0 if ok == len(results) else 1)
