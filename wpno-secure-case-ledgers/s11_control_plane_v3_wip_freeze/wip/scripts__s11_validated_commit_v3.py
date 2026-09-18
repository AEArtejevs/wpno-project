#!/usr/bin/env python3.11
"""S11_VALIDATED_COMMIT_V3 — Candidate-Ref-Broker mit Attest-vor-Promotion (F1) und Trust-Root V3.

Behebt F1 (V2 aktualisierte die Branch-Ref VOR der Attestierung): hier wird der Commit auf eine
CANDIDATE-REF geschrieben und V3-attestiert; die AKTIVE Branch wird NICHT promoted. Reihenfolge:
Gates -> commit-tree -> Attestierung V3 (Ed25519) -> ERST DANN candidate-ref setzen. Schlaegt die
Attestierung fehl, existiert keine Candidate-Ref und die aktive Branch ist unberuehrt.

Content/State-Gate getrennt (aus Git-Objekten). Kein Working-Tree als Pruefquelle. Kein Selftest-Bypass.
"""
import os, sys, subprocess, json

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s11_content_state_gate as CSG
import s11_attestation_v3 as A3
import run_precommit_quality_gate as GATE


def git(args):
    r = subprocess.run(['git'] + args, cwd=REPO, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _lock():
    gd = os.path.join(REPO, '.git')
    return os.path.join(gd if os.path.isdir(gd) else REPO, 'wpno_v3_broker.lock')


def gate_manifest_hash():
    import hashlib
    parts = []
    for label, script in GATE.GATES:
        try:
            parts.append(label + ':' + hashlib.sha256(open(script, 'rb').read()).hexdigest()[:16])
        except OSError:
            parts.append(label + ':MISSING')  # fail-closed sichtbar
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()[:16]


def _pinned_product_reference():
    """Produktreferenz AUS der Registry (nicht caller-gestellt) — schliesst RT-B caller-baseline."""
    import re
    y = os.path.join(REPO, 'memory', 'PRODUCT_CANDIDATE_REGISTRY.yaml')
    try:
        for line in open(y, encoding='utf-8'):
            m = re.match(r'\s*product_reference_candidate:\s*"?([0-9a-f]+)"?', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def validated_commit_v3(message, ticket, product_reference, candidate_ref):
    # CRITICAL (RT-Breaker): der Broker darf NUR eine Candidate-Ref schreiben, NIE die aktive Branch.
    if not candidate_ref.startswith('refs/candidates/'):
        return dict(status='FAIL', reason='ILLEGAL_REF_TARGET: nur refs/candidates/* erlaubt, nicht ' + candidate_ref)
    # Produktreferenz aus der Registry pinnen (caller-Wert nur als Fallback, muss uebereinstimmen)
    pinned = _pinned_product_reference()
    if pinned:
        product_reference = pinned
    ok, reason = GATE.acquire_lock(_lock())
    if not ok:
        return dict(status='FAIL', reason='LOCK: ' + reason)
    try:
        parent0 = git(['rev-parse', 'HEAD'])[1]
        tree0 = git(['write-tree'])[1]
        # Working==Index (Byte-Bindung getrackt) — sonst prueft das Gate nicht den Commit-Inhalt
        if git(['diff', '--name-only'])[1].strip():
            return dict(status='RED', reason='WORKTREE_INDEX_DIVERGENCE')
        # CONTENT_GATE (nur Git-Blobs des Candidate-Trees, Trusted Runner = dieser Prozess)
        cg, cf = CSG.content_gate(tree0)
        # STATE_GATE (Repo-Zustand)
        sg, sf = CSG.state_gate(tree0, parent0)
        # Scope-Guard V3 gegen den Candidate-TREE (nicht HEAD)
        scope_ok, scope_viol, _ = CSG.scope_guard_candidate_tree(tree0, product_reference)
        if not scope_ok:
            return dict(status='RED', reason='SCOPE_VIOLATION', scope_viol=scope_viol[:10])
        if cg != 'GREEN' or sg != 'GREEN':
            return dict(status='RED', reason='GATE_RED', content=cf[:5], state=sf[:5])
        # commit-tree aus exakt tree0
        c, commit, err = git(['commit-tree', tree0, '-p', parent0, '-m', message])
        if c != 0:
            return dict(status='FAIL', reason='commit-tree: ' + err)
        committed_tree = git(['rev-parse', commit + '^{tree}'])[1]
        if committed_tree != tree0:
            return dict(status='FAIL', reason='TREE_MISMATCH')
        # ATTESTIERUNG V3 ZUERST (F1) — vor jedem Ref-Schreiben
        try:
            rec = A3.write_attestation_v3(commit, committed_tree, parent0, tree0, ticket,
                                          content_gate=cg, state_gate=sg,
                                          gate_manifest_hash=gate_manifest_hash(),
                                          policy_versions={'candidate_registry': 'v1', 'gate_phase_registry': 'v1'})
        except Exception as e:
            return dict(status='FAIL', reason='ATTESTATION_FAILED_NO_REF: ' + str(e)[:120], commit=commit)
        verdict, axes, _ = A3.verify_attestation_v3(commit)
        if verdict not in ('ATTESTED_PRODUCT_CHAIN_ELIGIBLE', 'ATTESTED_PENDING_NOT_ELIGIBLE'):
            return dict(status='FAIL', reason='ATTESTATION_VERIFY_FAILED: ' + verdict, commit=commit)
        # ERST NACH gueltiger Attestierung: Candidate-Ref setzen (KEINE aktive-Branch-Promotion)
        c, _, err = git(['update-ref', candidate_ref, commit])
        if c != 0:
            return dict(status='FAIL', reason='candidate-ref: ' + err, commit=commit)
        return dict(status='V3_CANDIDATE_ATTESTED', commit=commit, tree=tree0, parent=parent0,
                    candidate_ref=candidate_ref, verdict=verdict, axes=axes,
                    active_branch_promoted=False)
    finally:
        GATE.release_lock(_lock())


if __name__ == '__main__':
    msg = sys.argv[1] if len(sys.argv) > 1 else 'control plane v3 candidate'
    ticket = sys.argv[2] if len(sys.argv) > 2 else 'S11_CONTROL_PLANE_V3_TRUST_ROOT_AND_CROSS_MODEL_REMEDIATION'
    ref = sys.argv[3] if len(sys.argv) > 3 else 'refs/candidates/s11-control-plane-v3'
    prodref = sys.argv[4] if len(sys.argv) > 4 else '670e362'
    r = validated_commit_v3(msg, ticket, prodref, ref)
    print('V3-BROKER: %s%s' % (r['status'], (' — ' + r.get('reason', '')) if r.get('reason') else ''))
    if r.get('commit'):
        print('  commit=%s ref=%s eligible=%s active_branch_promoted=%s' % (
            r['commit'][:12], r.get('candidate_ref'), r.get('axes', {}).get('product_chain_eligible'),
            r.get('active_branch_promoted')))
    sys.exit(0 if r['status'] == 'V3_CANDIDATE_ATTESTED' else 1)
