#!/usr/bin/env python3.11
"""S11_VALIDATED_COMMIT — TOCTOU-sicherer Commit-Broker.

Erzeugt den Commit aus GENAU dem Tree-Objekt, das zuvor validiert wurde (git commit-tree), und
aktualisiert die Branch-Ref atomar gegen den erwarteten Parent (git update-ref CAS). Damit gilt
zwingend: committed_tree_oid == validated_tree_oid, und ein Index-/HEAD-Wechsel zwischen Pruefung und
Commit bricht ab statt unbemerkt einen anderen Tree zu committen.

Kein --no-verify. Kein Remote. Kein Push. Einziger autorisierter Pfad fuer attestierte Commits.
Leitsatz: GEPRUEFT WIRD DER EXAKTE COMMIT-TREE — NICHT EIN AEHNLICHER WORKING TREE.
"""
import os, sys, subprocess, time

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s11_staged_tree_gate as ST
import run_precommit_quality_gate as GATE  # Lock-Mechanik wiederverwenden
import ci_gate  # Attestation V2


def git(args, cwd=None):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def current_branch_ref():
    code, out, _ = git(['symbolic-ref', 'HEAD'])
    return out if code == 0 else None


def _lock_path():
    # EIGENER Broker-Lock (nicht der Pre-Commit-Gate-Lock): der Broker fuehrt das Gate als Subprozess aus,
    # das seinerseits den Pre-Commit-Lock erwirbt — beide duerfen sich nicht gegenseitig blockieren.
    gd = os.path.join(REPO, '.git')
    if not os.path.isdir(gd):
        gd = REPO
    return os.path.join(gd, 'wpno_validated_commit_broker.lock')


def validated_commit(message, ticket='S11_PS861_006D_STAGED_BLOB_AND_TOCTOU_BINDING_FIX'):
    """Return dict(status, commit, tree, parent, ...). status GREEN nur bei tree_match + gruenem Gate."""
    ref = current_branch_ref()
    if not ref:
        return dict(status='FAIL', reason='detached HEAD — kein Branch-Ref', commit=None)

    # exklusiver Lock (kein paralleler Broker/Gate), repo-scoped
    lock = _lock_path()
    ok, reason = GATE.acquire_lock(lock)
    if not ok:
        return dict(status='FAIL', reason='LOCK: ' + reason, commit=None)
    try:
        parent0 = ST.head_oid(REPO)
        tree0 = ST.staged_tree_oid(REPO)
        if tree0 == (subprocess.run(['git', 'rev-parse', 'HEAD^{tree}'], cwd=REPO,
                                    capture_output=True, text=True).stdout.strip()):
            return dict(status='NOOP', reason='Index-Tree == HEAD-Tree (nichts zu committen)', commit=None,
                        tree=tree0, parent=parent0)

        # Gate GEGEN den materialisierten Staged-Tree
        gate = ST.gate_staged_tree(REPO, verbose=False)
        # BINDUNG (RT-G2): der vom Gate TATSAECHLICH validierte Tree muss == tree0 sein — sonst hat das
        # Gate einen anderen Tree geprueft als committet wird (Decoupling).
        if gate.get('validated_tree_oid') != tree0:
            return dict(status='FAIL', reason='VALIDATED_TREE_MISMATCH: Gate validierte %s, Broker-Tree %s' % (
                (gate.get('validated_tree_oid') or 'none')[:12], tree0[:12]), commit=None, tree=tree0)
        gate_status = gate['gate_result']
        if gate_status == 'RED':
            return dict(status='RED', reason='Staged-Tree-Gate ROT', commit=None,
                        tree=tree0, parent=parent0, gate_log=gate.get('gate_log_tail', ''))
        # gate_status in {GREEN, GREEN_PENDING_GATECODE_REVIEW}: bei Kontrollschicht-Code-Aenderung
        # ist die staged Gate-Ausgabe nicht endgueltig vertrauenswuerdig -> konditionale Attestierung.
        gatecode_review = (gate_status == 'GREEN_PENDING_GATECODE_REVIEW')

        # TOCTOU-Re-Check unmittelbar vor Commit: Index + HEAD unveraendert?
        tree1 = ST.staged_tree_oid(REPO)
        parent1 = ST.head_oid(REPO)
        if tree1 != tree0:
            return dict(status='FAIL', reason='CANDIDATE_TREE_CHANGED (Index nach Validierung mutiert)',
                        commit=None, tree=tree0)
        if parent1 != parent0:
            return dict(status='FAIL', reason='PARENT_CHANGED (HEAD nach Validierung bewegt)',
                        commit=None, tree=tree0)

        # Commit AUS dem validierten Tree
        args = ['commit-tree', tree0, '-m', message]
        if parent0:
            args += ['-p', parent0]
        code, commit, err = git(args)
        if code != 0:
            return dict(status='FAIL', reason='commit-tree: ' + err, commit=None, tree=tree0)

        # atomare Ref-Aktualisierung (compare-and-swap gegen erwarteten Parent)
        cas = ['update-ref', ref, commit] + ([parent0] if parent0 else [])
        code, _, err = git(cas)
        if code != 0:
            return dict(status='FAIL', reason='update-ref CAS: ' + err + ' (HEAD bewegt?)',
                        commit=None, tree=tree0)

        # Verifikation: committed Tree == validierter Tree
        code, committed_tree, _ = git(['rev-parse', commit + '^{tree}'])
        if committed_tree != tree0:
            return dict(status='FAIL', reason='TREE_MISMATCH committed=%s validated=%s' % (committed_tree[:12], tree0[:12]),
                        commit=commit, tree=tree0)

        att = ci_gate.write_attestation_v2(commit=commit, commit_tree=committed_tree, parent=parent0,
                                           validated_tree=tree0, ticket=ticket, gate_result='GREEN',
                                           gate_run_id=str(gate['created_at_utc']),
                                           gatecode_review=gatecode_review)
        return dict(status='GREEN' if not gatecode_review else 'GREEN_PENDING_GATECODE_REVIEW',
                    commit=commit, tree=tree0, parent=parent0, committed_tree=committed_tree,
                    tree_match=True, gate_code_changed=gate.get('gate_code_changed'), attestation=att)
    finally:
        GATE.release_lock(lock)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: s11_validated_commit.py "<message>" [ticket]')
        sys.exit(2)
    msg = sys.argv[1]
    ticket = sys.argv[2] if len(sys.argv) > 2 else 'S11_PS861_006D_STAGED_BLOB_AND_TOCTOU_BINDING_FIX'
    r = validated_commit(msg, ticket)
    print('VALIDATED-COMMIT: %s%s' % (r['status'], (' — ' + r.get('reason', '')) if r.get('reason') else ''))
    if r.get('commit'):
        print('  commit=%s tree=%s parent=%s tree_match=%s' % (
            r['commit'][:12], r['tree'][:12], (r.get('parent') or 'none')[:12], r.get('tree_match')))
    sys.exit(0 if r['status'] in ('GREEN', 'NOOP') else 1)
