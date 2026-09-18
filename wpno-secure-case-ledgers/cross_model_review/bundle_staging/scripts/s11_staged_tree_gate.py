#!/usr/bin/env python3.11
"""S11_STAGED_TREE_GATE — validiere den EXAKTEN gestagten Git-Tree, nicht die Working-Tree-Ansicht.

P0-Kern von S11_PS861_006D_STAGED_BLOB_AND_TOCTOU_BINDING_FIX. Bisher lasen die Guards B.repdir()
(Working Tree), waehrend git den Index/Staged-Blob committet -> ein sauberer Working-Tree konnte
gruen sein, waehrend ein boeser Blob committet wurde. Diese Komponente materialisiert den Index-Tree
git-nativ in einen detached Worktree und laesst das Gate GEGEN DIESEN TREE laufen.

Leitsatz: VALIDIERE DEN GIT-OBJEKTBAUM, NICHT DIE ZUFAELLIGE WORKING-TREE-ANSICHT.

Nur lokal, keine Rechtsarbeit. Exit 0 = staged Tree gruen, 1 = rot/Fehler.
"""
import os, subprocess, sys, tempfile, shutil, json, hashlib, time

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_PY = os.path.join('scripts', 'run_precommit_quality_gate.py')


def git(args, cwd=None, check=False):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError('git %s: %s' % (' '.join(args), r.stderr.strip()))
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def staged_tree_oid(repo=None):
    """Der EXAKT zu committende Tree = git write-tree ueber den aktuellen Index."""
    code, out, err = git(['write-tree'], cwd=repo)
    if code != 0:
        raise RuntimeError('git write-tree: ' + err)
    return out


def head_oid(repo=None):
    code, out, _ = git(['rev-parse', 'HEAD'], cwd=repo)
    return out if code == 0 else None


def materialize_worktree(tree, repo=None):
    """Detached Worktree exakt auf `tree` (git-nativ, shared object db). Return (path, temp_commit)."""
    repo = repo or REPO
    parent = head_oid(repo)
    args = ['commit-tree', tree, '-m', 'STAGED_TREE_GATE materialization']
    if parent:
        args += ['-p', parent]
    code, commit, err = git(args, cwd=repo)
    if code != 0:
        raise RuntimeError('git commit-tree: ' + err)
    dest = tempfile.mkdtemp(prefix='s11_stagedtree_')
    # Worktree-Verzeichnis muss beim add leer/nicht existent sein
    shutil.rmtree(dest, ignore_errors=True)
    code, _, err = git(['worktree', 'add', '--detach', dest, commit], cwd=repo)
    if code != 0:
        raise RuntimeError('git worktree add: ' + err)
    return dest, commit


def cleanup_worktree(dest, repo=None):
    git(['worktree', 'remove', '--force', dest], cwd=repo)
    shutil.rmtree(dest, ignore_errors=True)
    git(['worktree', 'prune'], cwd=repo)


def run_gate_in(dest):
    """Fuehrt das volle Pre-Commit-Gate GEGEN den materialisierten Staged-Tree aus.

    Sicherheit (RT-G1/G3): die leichte Gate-Attrappe WPNO_STAGEDTREE_GATE_CMD wird NUR im expliziten
    Testmodus (WPNO_STAGEDTREE_TEST_MODE=1) beachtet — in Produktion laeuft IMMER das echte Gate, damit
    kein per-env untergeschobener Trivial-Gate den Staged-Tree gruen faerbt. Ein Testmodus-Lauf wird als
    solcher markiert und ergibt NIE eine Produktions-Gruen-Attestierung (siehe Broker/Attestation)."""
    if os.environ.get('WPNO_STAGEDTREE_TEST_MODE') == '1':
        gate_cmd = os.environ.get('WPNO_STAGEDTREE_GATE_CMD')
        if gate_cmd:
            r = subprocess.run(gate_cmd, cwd=dest, shell=True, capture_output=True, text=True)
            return r.returncode == 0, '[TEST_MODE] ' + r.stdout + r.stderr
    env = dict(os.environ)
    env['WPNO_CI_REPO'] = dest
    env.pop('WPNO_BL02_REPORTS', None)  # Guards sollen dest/reports lesen, nicht ueberschrieben
    r = subprocess.run([sys.executable, GATE_PY], cwd=dest, capture_output=True, text=True, env=env)
    ok = r.returncode == 0 and 'GATE GRUEN' in r.stdout
    return ok, r.stdout + ('\n' + r.stderr if r.stderr.strip() else '')


# Explizite Nicht-.py-Kontrolldateien (Registry/Kandidaten/Hooks), die die Gate-Semantik steuern.
EXPLICIT_CONTROL_FILES = frozenset({
    'reports/S11_GATE_PHASE_REGISTRY.csv', 'memory/PRODUCT_CANDIDATE_REGISTRY.yaml',
    'memory/PRODUCT_CANDIDATE_REGISTRY.csv', 'memory/S11_GATE_PHASE_LIFECYCLE_RULE.csv',
})


def _is_validation_surface(p):
    """True, wenn p vom Gate/Verifikator ALS VALIDIERUNGSCODE ausgefuehrt wird. STRUKTURELL statt
    Allowlist (RT-V1 P0: eine enumerierte Liste deckt nie alle ~70 Phasen/hunderte check_*.py ab).
    Jede Python-Datei unter scripts/, tests/, zitate_register/, s11_core/ sowie Hooks + Steuer-CSV/YAML
    zaehlen als Kontrollschicht-Code; ihre Aenderung im gestagten Tree darf nicht self-attestierend gruen sein."""
    if p in EXPLICIT_CONTROL_FILES:
        return True
    if p.endswith('.sh') and p.startswith('scripts/'):
        return True
    if p.endswith('.py') and p.split('/', 1)[0] in ('scripts', 'tests', 'zitate_register', 's11_core'):
        return True
    return False


def gate_code_changed_vs_head(tree, repo):
    """Return (changed, [files]) — jede VALIDIERUNGS-Datei (voller ausgefuehrter Gate-/Verifikator-Code,
    nicht nur eine Teilliste), die im gestagten Tree gegenueber HEAD abweicht. Fail-closed: laesst sich
    der Diff nicht bilden, gilt der Tree als veraendert."""
    parent = head_oid(repo)
    if not parent:
        code, out, _ = git(['ls-tree', '-r', '--name-only', tree], cwd=repo)
        paths = out.splitlines() if code == 0 else None
    else:
        code, out, _ = git(['diff', '--name-only', parent, tree], cwd=repo)
        paths = out.splitlines() if code == 0 else None
    if paths is None:
        return True, ['<diff-failed:fail-closed>']
    changed = sorted({p for p in paths if _is_validation_surface(p)})
    return bool(changed), changed


def worktree_index_diverged(repo):
    """Getrackte Dateien mit UNSTAGED Aenderung (Working Tree != Index). Ist diese Menge leer, ist der
    Working Tree byte-identisch mit dem Index-Tree -> das Gate gegen den Working Tree validiert EXAKT den
    zu committenden Index-Tree (schliesst staged-blob: sauberer WT + boeser Index ist genau eine Divergenz).
    Der Materialisierungsweg (Detached-Worktree) ist untauglich, weil das Gate ~15 HEAD-/Repo-ZUSTANDS-
    Checks enthaelt (Snapshot-Freshness, no-remote, Reproduzierbarkeit), die nur im echten Repo-Kontext
    sinnvoll sind; die Working==Index-Invariante liefert dieselbe Inhalts-Bindung ohne Zustands-Bruch."""
    code, out, _ = git(['diff', '--name-only'], cwd=repo)  # Working Tree vs Index (getrackt)
    if code != 0:
        return ['<diff-failed:fail-closed>']
    return [f for f in out.splitlines() if f.strip()]


def gate_staged_tree(repo=None, verbose=True):
    """Validiert den zu committenden Index-Tree. Bindung: Working Tree MUSS == Index sein (sonst
    WORKTREE_INDEX_DIVERGENCE -> RED), dann validiert das echte Gate (echter HEAD/Repo-Zustand) exakt den
    Commit-Inhalt. Aendert der Tree Kontrollschicht-Code, ist das Ergebnis hoechstens
    GREEN_PENDING_GATECODE_REVIEW — ein gestagter Trivial-Validator kann sich nicht selbst final gruen faerben."""
    repo = repo or REPO
    tree = staged_tree_oid(repo)
    parent = head_oid(repo)
    cc, cc_files = gate_code_changed_vs_head(tree, repo)
    diverged = worktree_index_diverged(repo)
    if diverged:
        result, log = 'RED', 'WORKTREE_INDEX_DIVERGENCE: ' + ' '.join(diverged[:8])
    else:
        ok, log = run_gate_in(repo)  # echter Repo-Kontext: Zustands-Checks sehen den echten HEAD
        if not ok:
            result = 'RED'
        elif cc:
            result = 'GREEN_PENDING_GATECODE_REVIEW'
        else:
            result = 'GREEN'
    res = dict(validated_tree_oid=tree, parent_commit_oid=parent, gate_result=result,
               gate_code_changed=cc, gate_code_changed_files=cc_files[:20],
               worktree_index_diverged=diverged[:8],
               gate_log_tail='\n'.join(str(log).strip().splitlines()[-3:]), created_at_utc=int(time.time()))
    if verbose:
        print('STAGED-TREE-GATE tree=%s parent=%s -> %s%s' % (
            tree[:12], (parent or 'none')[:12], result, (' (gate-code changed: %d)' % len(cc_files)) if cc else ''))
        print(res['gate_log_tail'])
    return res


if __name__ == '__main__':
    r = gate_staged_tree()
    print(json.dumps({k: v for k, v in r.items() if k != 'gate_log_tail'}))
    sys.exit(0 if r['gate_result'] == 'GREEN' else 1)
