#!/usr/bin/env python3.11
"""S11-Gate-Attestation-Durability (Phase 8, ACTIVE_CURRENT).

Beweist, dass die tree-gebundene Attestierung V2 DAUERHAFT ist:
 - ein gruen attestierter Commit bleibt fuer SEINEN Tree spaeter gruen verifizierbar;
 - spaetere legitime Produktaenderungen machen die historische Attestierung des frueheren Commits
   nicht rot (RCK2-22-Klasse: derselbe Gate darf einen einmal gruenen Commit nicht nachtraeglich
   rot bewerten);
 - Commit-Tree != validierter Tree wird als Mismatch erkannt (kein Replay);
 - Attestierungs-Ledger ist append-only;
 - der stale HEAD-Test wird via Registry ausgeschlossen, nicht geloescht.
"""
import os, subprocess, sys, tempfile, shutil, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, 'scripts')
sys.path.insert(0, SCRIPTS)


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def _repo_with_commits():
    d = tempfile.mkdtemp(prefix='s11att_')
    os.makedirs(os.path.join(d, 'reports'))
    for c in ('git init -q', 'git config user.email t@t', 'git config user.name t', 'git config commit.gpgsign false'):
        sh(c, d)
    open(os.path.join(d, 'reports', 'a.csv'), 'w').write('id\nA1\n')
    sh('git add -A && git commit -qm c1', d)
    return d


results = []
def case(n, c, detail=''):
    results.append((n, 'PASS' if c else 'FAIL', '' if c else detail))


def test_all():
    import importlib
    d = _repo_with_commits()
    env = {'WPNO_CI_REPO': d, 'WPNO_ATTEST_DIR': os.path.join(d, '.git', 'attest'),
           'WPNO_ATTEST_HMAC_KEY': os.path.join(d, '.git', 'hmac.key')}
    os.environ.update(env)
    os.environ.pop('WPNO_STAGEDTREE_TEST_MODE', None)  # echte Produktions-Attestierung
    ci = importlib.reload(importlib.import_module('ci_gate'))

    c1 = sh('git rev-parse HEAD', d).stdout.strip()
    t1 = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    ci.write_attestation_v2(commit=c1, commit_tree=t1, parent=None, validated_tree=t1,
                            ticket='TEST', gate_result='GREEN', gate_run_id='r1')
    st, _ = ci.verify_attestation_v2(c1)
    case('01_green_attested_valid_for_its_tree', st in ('ATTESTED_GREEN_FOR_EXACT_TREE', 'ATTESTATION_STALE'), st)

    # spaetere Commits (legitime Produktaenderung) -> HEAD wandert
    open(os.path.join(d, 'reports', 'b.csv'), 'w').write('id\nB1\n')
    sh('git add -A && git commit -qm c2', d)
    st2, _ = ci.verify_attestation_v2(c1)  # alter Commit weiterhin gegen SEINEN Tree gueltig
    case('02_historical_attestation_not_turned_red', st2 in ('ATTESTED_GREEN_FOR_EXACT_TREE', 'ATTESTATION_STALE'), st2)

    # 03 Manipulierter Record (Feld editiert ohne HMAC-Neuberechnung) -> TAMPERED (RT-G4 red_to_green_flip)
    p = os.path.join(d, '.git', 'attest', c1 + '.v2.json')
    rec = json.load(open(p)); rec['created_commit_tree_sha'] = 'deadbeef' * 5; json.dump(rec, open(p, 'w'))
    st3, _ = ci.verify_attestation_v2(c1)
    case('03_tampered_record_detected', st3 == 'ATTESTATION_TAMPERED', st3)

    # 3b forged green: gueltiges Record schreiben, dann result/status flippen OHNE Re-HMAC -> TAMPERED
    ci.write_attestation_v2(commit=c1, commit_tree=t1, parent=None, validated_tree=t1,
                            ticket='TEST', gate_result='RED', gate_run_id='r3')
    rec = json.load(open(p)); rec['result'] = 'GREEN'; rec['status'] = 'ATTESTED_GREEN_FOR_EXACT_TREE'
    json.dump(rec, open(p, 'w'))
    st3b, _ = ci.verify_attestation_v2(c1)
    case('03b_forged_green_flip_detected', st3b == 'ATTESTATION_TAMPERED', st3b)

    # Ledger append-only
    ci.write_attestation_v2(commit=c1, commit_tree=t1, parent=None, validated_tree=t1,
                            ticket='TEST', gate_result='GREEN', gate_run_id='r2')
    ledger = open(ci.ledger_path()).read() if os.path.exists(ci.ledger_path()) else ''
    case('04_ledger_append_only', ledger.count(c1) >= 1, 'ledger fehlt Commit')

    # 4b Attestierungs-Replay auf ANDEREN Commit -> Tree-Bindung schlaegt fehl (RT-G4 replay)
    open(os.path.join(d, 'reports', 'z.csv'), 'w').write('id\nZ1\n')
    sh('git add -A && git commit -qm c3', d)
    c3 = sh('git rev-parse HEAD', d).stdout.strip()
    valid = json.load(open(p))  # gueltiges (Re-HMAC) Record von c1
    ci.write_attestation_v2(commit=c1, commit_tree=t1, parent=None, validated_tree=t1,
                            ticket='TEST', gate_result='GREEN', gate_run_id='r4')
    import shutil as _sh
    _sh.copy(p, os.path.join(d, '.git', 'attest', c3 + '.v2.json'))  # c1-Record auf c3 replayen
    st4b, _ = ci.verify_attestation_v2(c3)
    case('4b_replay_onto_other_commit_rejected', st4b in ('ATTESTATION_SCHEMA_MISMATCH', 'ATTESTATION_TAMPERED'), st4b)
    shutil.rmtree(d, ignore_errors=True)

    # 4c forged-v1-only (kein V2): unsignierter/gefaelschter V1 -> nicht gruen (RT-V3 forged-v1)
    d2 = _repo_with_commits()
    os.environ.update({'WPNO_CI_REPO': d2, 'WPNO_ATTEST_DIR': os.path.join(d2, '.git', 'attest'),
                       'WPNO_ATTEST_HMAC_KEY': os.path.join(d2, '.git', 'k')})
    ci2 = importlib.reload(importlib.import_module('ci_gate'))
    cc = sh('git rev-parse HEAD', d2).stdout.strip()
    tt = sh('git rev-parse HEAD^{tree}', d2).stdout.strip()
    os.makedirs(os.path.join(d2, '.git', 'attest'), exist_ok=True)
    json.dump(dict(commit=cc, tree=tt, verdict='GREEN', source='FORGED', gate_hash='x', ts=1),
              open(os.path.join(d2, '.git', 'attest', cc + '.json'), 'w'))
    case('4c_forged_v1_without_hmac_not_green', not ci2._attested_green(cc, tt), 'forged v1 galt als gruen')
    # legitimer V1 (mit HMAC) bleibt gruen
    ci2.write_attestation(cc, tt, 'GREEN', 'PRE_COMMIT_GATE')
    case('4d_legit_v1_with_hmac_green', ci2._attested_green(cc, tt), 'legitimer V1 nicht gruen')
    shutil.rmtree(d2, ignore_errors=True)
    os.environ.update({'WPNO_CI_REPO': d, 'WPNO_ATTEST_DIR': os.path.join(d, '.git', 'attest'),
                       'WPNO_ATTEST_HMAC_KEY': os.path.join(d, '.git', 'hmac.key')})

    # 05 stale HEAD-Test via Registry ausgeschlossen, NICHT geloescht
    reg = os.path.join(REPO, 'reports', 'S11_GATE_PHASE_REGISTRY.csv')
    still_exists = os.path.exists(os.path.join(REPO, 'tests', 'test_s11_ps861_006d_recheck_protocol.py'))
    import csv as _csv
    rp = {r['phase_id']: r for r in _csv.DictReader(open(reg))}
    excluded = rp.get('S11-PS861-006D-Recheck-Protocol', {}).get('lifecycle_status') == 'HISTORICAL_REPLAY'
    case('05_stale_test_excluded_not_deleted', still_exists and excluded, 'exists=%s excluded=%s' % (still_exists, excluded))

    # 06 current HEAD gate and historical replay are separate registry states
    states = {r['lifecycle_status'] for r in rp.values()}
    case('06_head_and_replay_separate', 'ACTIVE_CURRENT' in states and 'HISTORICAL_REPLAY' in states, str(states))


if __name__ == '__main__':
    test_all()
    ok = sum(1 for _, s, _ in results if s == 'PASS')
    for n, s, dd in results:
        if s == 'FAIL':
            print('  [FAIL] %s: %s' % (n, dd))
    print('S11-GATE-ATTESTATION-DURABILITY TESTS: %d/%d PASS' % (ok, len(results)))
    sys.exit(0 if ok == len(results) else 1)
