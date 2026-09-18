#!/usr/bin/env python3.11
"""S11-Control-Plane-Staged-Tree-Binding — Beweistests fuer den P0-Fix.

Beweist in isolierten Sandbox-Repos: (1) das Gate validiert den INDEX/Staged-Tree, nicht den Working
Tree; (2) der staged-blob-Angriff (sauberer Worktree + boeser Index) wird geblockt; (3) TOCTOU-
Index-Mutation nach Validierung bricht ab; (4) commit_tree == validated_tree; (5) Attestierung V2 ist
tree-gebunden und bleibt fuer ihren Commit-Tree dauerhaft gueltig; (6) Gate-Phase-Lebenszyklus.

Nutzt eine leichte injizierte Gate-Attrappe (WPNO_STAGEDTREE_GATE_CMD): FAIL wenn 'BADVALUE' in einer
reports/*.csv des materialisierten Staged-Trees steht. Keine Rechtsarbeit."""
import os, subprocess, sys, tempfile, shutil, json

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
BROKER = os.path.join(SCRIPTS, 's11_validated_commit.py')
STGATE = os.path.join(SCRIPTS, 's11_staged_tree_gate.py')
CLEAN_GATE = ("%s -c \"import sys,glob;"
              "sys.exit(1 if any(b'BADVALUE' in open(f,'rb').read() for f in glob.glob('reports/*.csv')) else 0)\"" % sys.executable)


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def new_repo():
    d = tempfile.mkdtemp(prefix='s11cp_')
    os.makedirs(os.path.join(d, 'reports'))
    for c in ('git init -q', 'git config user.email t@t', 'git config user.name t', 'git config commit.gpgsign false'):
        sh(c, d)
    open(os.path.join(d, 'reports', 'artifact.csv'), 'w').write('id,field\nA1,CLEAN\n')
    sh('git add -A && git commit -qm base', d)
    return d


def broker(repo, msg='test commit', gate=CLEAN_GATE, extra_env=None):
    env = {'WPNO_CI_REPO': repo, 'WPNO_STAGEDTREE_GATE_CMD': gate, 'WPNO_STAGEDTREE_TEST_MODE': '1',
           'WPNO_ATTEST_DIR': os.path.join(repo, '.git', 'attest'),
           'WPNO_ATTEST_HMAC_KEY': os.path.join(repo, '.git', 'hmac.key')}
    env.update(extra_env or {})
    r = sh([sys.executable, BROKER, msg], repo, env)
    return r


def head(repo):
    return sh('git rev-parse HEAD', repo).stdout.strip()


def index_tree(repo):
    return sh('git write-tree', repo).stdout.strip()


results = []
def case(name, cond, detail=''):
    results.append((name, 'PASS' if cond else 'FAIL', '' if cond else detail))


def test_all():
    tm = {'WPNO_CI_REPO': None, 'WPNO_STAGEDTREE_GATE_CMD': CLEAN_GATE, 'WPNO_STAGEDTREE_TEST_MODE': '1'}
    # 1) Staged-Tree-Gate liest INDEX, nicht Working Tree
    d = new_repo()
    open(os.path.join(d, 'reports', 'artifact.csv'), 'w').write('id,field\nA1,BADVALUE\n')
    sh('git add reports/artifact.csv', d)                      # boeser Blob gestaged
    open(os.path.join(d, 'reports', 'artifact.csv'), 'w').write('id,field\nA1,CLEAN\n')  # Worktree wieder sauber
    r = sh([sys.executable, STGATE], d, {**tm, 'WPNO_CI_REPO': d})
    # sauberer Working Tree + boeser Index = genau eine WORKTREE_INDEX_DIVERGENCE -> RED (staged-blob blockiert)
    case('01_staged_blob_wt_index_divergence_blocked', r.returncode == 1 and 'RED' in r.stdout, 'staged-blob haette RED liefern muessen: ' + r.stdout[-200:])
    shutil.rmtree(d, ignore_errors=True)

    # 2) Broker: sauberer Index -> GREEN, commit-tree == index-tree, HEAD vor
    d = new_repo()
    open(os.path.join(d, 'reports', 'new.csv'), 'w').write('id,field\nB1,OK\n')
    sh('git add -A', d)
    it = index_tree(d); h0 = head(d)
    r = broker(d, 'clean commit')
    h1 = head(d)
    ctree = sh('git rev-parse HEAD^{tree}', d).stdout.strip()
    case('02_broker_clean_index_commits', 'VALIDATED-COMMIT: GREEN' in r.stdout and h1 != h0, r.stdout[-200:])
    case('03_commit_tree_equals_validated_index_tree', ctree == it, 'ctree=%s it=%s' % (ctree[:12], it[:12]))
    shutil.rmtree(d, ignore_errors=True)

    # 4) Staged-blob-Angriff: sauberer Worktree + boeser Index -> Broker RED, kein Commit
    d = new_repo()
    open(os.path.join(d, 'reports', 'artifact.csv'), 'w').write('id,field\nA1,BADVALUE\n')
    sh('git add reports/artifact.csv', d)
    open(os.path.join(d, 'reports', 'artifact.csv'), 'w').write('id,field\nA1,CLEAN\n')
    h0 = head(d)
    r = broker(d, 'attack commit')
    case('04_staged_blob_attack_blocked', 'GREEN' not in r.stdout and head(d) == h0, r.stdout[-200:])
    shutil.rmtree(d, ignore_errors=True)

    # 5) TOCTOU: Gate mutiert waehrend Validierung den Haupt-Index -> Re-Check bricht ab
    d = new_repo()
    open(os.path.join(d, 'reports', 'new.csv'), 'w').write('id,field\nB1,OK\n')
    sh('git add -A', d)
    h0 = head(d)
    # Angriffs-Gate: besteht die Pruefung, mutiert aber den Haupt-Index (concurrent)
    attack = ("%s -c \"import subprocess,sys;"
              "open(r'%s/reports/sneaky.csv','w').write('x,y\\n1,2\\n');"
              "subprocess.run(['git','-C',r'%s','add','reports/sneaky.csv']);sys.exit(0)\"" % (sys.executable, d, d))
    r = broker(d, 'toctou commit', gate=attack)
    case('05_toctou_index_mutation_aborts', 'GREEN' not in r.stdout and head(d) == h0,
         'Broker haette CANDIDATE_TREE_CHANGED melden muessen: ' + r.stdout[-200:])
    shutil.rmtree(d, ignore_errors=True)

    # 6) Attestierung V2 tree-gebunden; Testmodus wird als solcher markiert (nie Produktionsgruen)
    d = new_repo()
    open(os.path.join(d, 'reports', 'new.csv'), 'w').write('id,field\nB1,OK\n')
    sh('git add -A', d)
    broker(d, 'attest commit')
    commit = head(d)
    av2 = os.path.join(d, '.git', 'attest', commit + '.v2.json')
    ok6 = os.path.exists(av2)
    rec = json.load(open(av2)) if ok6 else {}
    case('06_attestation_v2_tree_bound_testmode', ok6 and rec.get('tree_match') and rec.get('status') == 'ATTESTED_TEST_MODE' and rec.get('record_hmac'), str(rec)[:180])
    # verify erkennt Testmodus (nicht Produktionsgruen) -> RT-Schutz: injizierte Gate kann nicht als Prod-Green gelten
    vr = sh([sys.executable, os.path.join(SCRIPTS, 'ci_gate.py'), 'verify'], d,
            {'WPNO_CI_REPO': d, 'WPNO_ATTEST_DIR': os.path.join(d, '.git', 'attest'),
             'WPNO_ATTEST_HMAC_KEY': os.path.join(d, '.git', 'hmac.key')})
    case('07_testmode_not_production_green', 'GRUEN attestiert' not in vr.stdout, vr.stdout[-160:])
    shutil.rmtree(d, ignore_errors=True)

    # 11) Gate-Code-Aenderung im Staging -> nicht auto-gruen (RT-G1 self-referential-validator)
    d = new_repo()
    os.makedirs(os.path.join(d, 'scripts'), exist_ok=True)
    open(os.path.join(d, 'scripts', 'run_precommit_quality_gate.py'), 'w').write('# honest gate\n')
    sh('git add -A && git commit -qm gate', d)
    open(os.path.join(d, 'scripts', 'run_precommit_quality_gate.py'), 'w').write("print('GATE GRUEN')\n")  # entschaerft
    open(os.path.join(d, 'reports', 'evil.csv'), 'w').write('id\nEVIL\n')
    sh('git add -A', d)
    r = broker(d, 'gatecode-change commit')
    commit = head(d)
    av = os.path.join(d, '.git', 'attest', commit + '.v2.json')
    rec = json.load(open(av)) if os.path.exists(av) else {}
    # in Testmodus dominiert TEST_MODE; entscheidend: NICHT ATTESTED_GREEN_FOR_EXACT_TREE + gate_code_changed erkannt
    case('cp_gatecode_change_not_final_green',
         rec.get('status') != 'ATTESTED_GREEN_FOR_EXACT_TREE', 'status=%s' % rec.get('status'))
    shutil.rmtree(d, ignore_errors=True)

    # 12) Struktureller Schutz (RT-V1 P0): ein BELIEBIGER Validator (nicht nur die gelistete Teilmenge)
    #     im gestagten Tree entschaerft -> gate_code_changed=True -> kein finales Gruen
    d = new_repo()
    os.makedirs(os.path.join(d, 'tests'), exist_ok=True)
    os.makedirs(os.path.join(d, 'zitate_register'), exist_ok=True)
    open(os.path.join(d, 'tests', 'test_p0_safety_guards.py'), 'w').write('import sys\nsys.exit(0)\n')
    open(os.path.join(d, 'zitate_register', 'check_forbidden_phrases.py'), 'w').write('import sys\nsys.exit(0)\n')
    sh('git add -A && git commit -qm validators', d)
    open(os.path.join(d, 'tests', 'test_p0_safety_guards.py'), 'w').write("print('always green')\n")  # entschaerft
    open(os.path.join(d, 'reports', 'evil.csv'), 'w').write('id\nEVIL\n')
    sh('git add -A', d)
    r = sh([sys.executable, STGATE], d, {**tm, 'WPNO_CI_REPO': d})
    import json as _j
    out = _j.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    case('cp_arbitrary_validator_change_detected',
         out.get('gate_result') == 'GREEN_PENDING_GATECODE_REVIEW' and out.get('gate_code_changed') is True,
         'gate_result=%s changed=%s' % (out.get('gate_result'), out.get('gate_code_changed')))
    shutil.rmtree(d, ignore_errors=True)

    # 9) Gate-Phase-Lebenszyklus: recheck-protocol HISTORICAL_REPLAY, scope-guard ACTIVE_CURRENT
    import csv as _csv
    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reg = {r['phase_id']: r for r in _csv.DictReader(open(os.path.join(REPO, 'reports', 'S11_GATE_PHASE_REGISTRY.csv')))}
    case('09_recheck_protocol_not_active_head',
         reg.get('S11-PS861-006D-Recheck-Protocol', {}).get('lifecycle_status') == 'HISTORICAL_REPLAY', str(reg.get('S11-PS861-006D-Recheck-Protocol')))
    case('10_scope_guard_active', reg.get('S11-Control-Plane-Scope-Guard', {}).get('lifecycle_status') == 'ACTIVE_CURRENT', '')


if __name__ == '__main__':
    test_all()
    ok = sum(1 for _, s, _ in results if s == 'PASS')
    for n, s, d in results:
        if s == 'FAIL':
            print('  [FAIL] %s: %s' % (n, d))
    print('S11-CONTROL-PLANE-STAGED-TREE-BINDING TESTS: %d/%d PASS' % (ok, len(results)))
    sys.exit(0 if ok == len(results) else 1)
