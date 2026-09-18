#!/usr/bin/env python3.11
"""S11_ATTESTATION_V3 — asymmetrische, hashverkettete, umgebungsgebundene Attestierung.

Behebt gegenueber V2 (HMAC) die symmetrische Vertrauensdomaene (CPR-006/007): Ed25519 mit
PRIVATEM Schluessel im getrennten Signer-Ort (nur der Signer signiert) und OEFFENTLICHEM Schluessel
IM Kontrollrepo (jede Partei kann OHNE Geheimnis verifizieren; Faelschen erfordert den privaten
Schluessel). Zusaetzlich: getrennte Statusachsen (crypto_valid / policy_fresh / product_chain_eligible),
vollstaendige Umgebungs-/Input-Bindung (CPR-004/008) und ein HASHVERKETTETES Ledger (CPR-014).

Ehrliche Restgrenze (CPR-007): auf einer Einzelnutzer-Maschine ist der private Schluessel technisch
erreichbar; echte Domaenentrennung braucht separaten OS-Nutzer/Keychain/Hardware-Token (operativ, nicht
Code). Der Fortschritt ist die ASYMMETRIE: Verifikation ohne Geheimnis, Signieren nur mit Privatkey.
"""
import os, sys, json, hashlib, subprocess, time, platform, locale

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    _ED = True
except Exception:
    _ED = False


def _git(args, cwd=None):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _git_dir():
    c, out, _ = _git(['rev-parse', '--git-dir'])
    return (out if os.path.isabs(out) else os.path.join(REPO, out)) if c == 0 else os.path.join(REPO, '.git')


def attest_dir_v3():
    return os.environ.get('WPNO_ATTEST_V3_DIR') or os.path.join(_git_dir(), 'wpno_attest_v3')


def ledger_path_v3():
    return os.path.join(attest_dir_v3(), 'ledger_chain.jsonl')


# --- Getrennter Signer: privater Key off-git (Signer-Ort), oeffentlicher Key im Repo ---
def signer_privkey_path():
    return (os.environ.get('WPNO_SIGNER_PRIVKEY')
            or os.path.join(os.path.expanduser('~/wpno-secure-case-ledgers/signer'), 'ed25519_private.pem'))


def repo_pubkey_path():
    return os.environ.get('WPNO_SIGNER_PUBKEY') or os.path.join(REPO, 'memory', 'attestation_v3_ed25519_pubkey.pem')


def ensure_keys():
    """Erzeugt das Ed25519-Schluesselpaar, falls fehlend: privat 0600 im Signer-Ort, oeffentlich im Repo."""
    if not _ED:
        raise RuntimeError('cryptography/ed25519 nicht verfuegbar')
    priv = signer_privkey_path()
    pub = repo_pubkey_path()
    if not os.path.exists(priv):
        if os.path.exists(pub):
            # Pubkey ohne Privkey = verlorener Signer-Key. NICHT neu erzeugen (waere Mismatch) -> fail-closed.
            raise RuntimeError('SIGNER_PRIVKEY_LOST: oeffentlicher Key vorhanden, privater fehlt — kein Neuerzeugen')
        os.makedirs(os.path.dirname(priv), exist_ok=True)
        k = ed25519.Ed25519PrivateKey.generate()
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
        fd = os.open(priv, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(fd, pem)
        os.close(fd)
    if not os.path.exists(pub):
        k = serialization.load_pem_private_key(open(priv, 'rb').read(), password=None)
        os.makedirs(os.path.dirname(pub), exist_ok=True)
        open(pub, 'wb').write(k.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    # out-of-band Fingerprint-Anker im Signer-Ort (einmalig, nicht ueberschreiben)
    anchor = _pubkey_anchor_path()
    if not os.path.exists(anchor):
        fd = os.open(anchor, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(fd, _fp(open(pub, 'rb').read()).encode())
        os.close(fd)
    return priv, pub


def sign(payload: bytes) -> str:
    """SIGNER-Operation (privater Key). In Produktion ein getrennter Prozess/Nutzer."""
    ensure_keys()
    k = serialization.load_pem_private_key(open(signer_privkey_path(), 'rb').read(), password=None)
    return k.sign(payload).hex()


def _pubkey_anchor_path():
    """Fingerabdruck des Pubkeys im GETRENNTEN Signer-Ort (out-of-repo) — Teil-Pinning gegen
    Pubkey-Substitution (RT-Breaker CRITICAL). Der Angreifer muss jetzt ZUSAETZLICH die separate
    Signer-Domaene brechen. RESTPUNKT: echtes Pinning haelt der Reviewer den Fingerprint out-of-band."""
    return os.path.join(os.path.dirname(signer_privkey_path()), 'pubkey.fingerprint')


def _fp(pem_bytes):
    return hashlib.sha256(pem_bytes).hexdigest()


def verify_sig(payload: bytes, sig_hex: str) -> bool:
    """VERIFIKATION ohne Geheimnis: nur der oeffentliche Repo-Key — der aber gegen den out-of-band
    Fingerprint-Anker geprueft wird (Substitution des Repo-Pubkeys allein reicht nicht)."""
    if not _ED or not os.path.exists(repo_pubkey_path()):
        return False
    try:
        pem = open(repo_pubkey_path(), 'rb').read()
        anchor = _pubkey_anchor_path()
        if os.path.exists(anchor):
            if open(anchor).read().strip() != _fp(pem):
                return False  # Repo-Pubkey weicht vom out-of-band Anker ab -> Trust-Anchor-Verletzung
        pub = serialization.load_pem_public_key(pem)
        pub.verify(bytes.fromhex(sig_hex), payload)
        return True
    except Exception:
        return False


# --- Umgebungs-/Input-Bindung (CPR-004/008) ---
def _sha_file(p):
    try:
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
    except OSError:
        return 'missing'


def environment_binding():
    _, gv, _ = _git(['--version'])
    return {
        'python_version': platform.python_version(),
        'git_version': gv,
        'platform': platform.platform(),
        'path_sha16': hashlib.sha256(os.environ.get('PATH', '').encode()).hexdigest()[:16],
        'pythonpath_sha16': hashlib.sha256(os.environ.get('PYTHONPATH', '').encode()).hexdigest()[:16],
        'locale': str(locale.getlocale()),
        'tz': os.environ.get('TZ', 'system'),
    }


def input_binding(candidate_tree, parent_commit, gate_manifest_hash, policy_versions):
    return {
        'candidate_tree': candidate_tree,
        'parent_commit': parent_commit,
        'gate_manifest_hash': gate_manifest_hash,
        'policy_versions': policy_versions,
        'env': environment_binding(),
    }


# --- Hashverkettetes Ledger ---
def _last_chain_hash():
    p = ledger_path_v3()
    if not os.path.exists(p):
        return '0' * 64
    last = None
    for line in open(p):
        line = line.strip()
        if line:
            last = line
    if not last:
        return '0' * 64
    try:
        return json.loads(last).get('entry_hash', '0' * 64)
    except ValueError:
        return '0' * 64


def _canonical(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def write_attestation_v3(commit, commit_tree, parent, validated_tree, ticket, content_gate, state_gate,
                         gate_manifest_hash, policy_versions, ts=None):
    """Schreibt eine Ed25519-signierte, hashverkettete V3-Attestierung mit GETRENNTEN Statusachsen.
    Endgueltig gruen (product_chain_eligible=true) nur wenn beide Gates GREEN, tree-match, kein
    Gate-Code-Review offen. Signatur deckt den kanonischen Record ab -> Faelschung ohne Privatkey unmoeglich."""
    d = attest_dir_v3()
    os.makedirs(d, exist_ok=True)
    ts = int(ts if ts is not None else time.time())
    tree_match = (commit_tree == validated_tree)
    # crypto_valid ist KEIN gespeichertes Feld, sondern wird bei verify durch die Signatur belegt.
    policy_fresh = bool(gate_manifest_hash) and bool(policy_versions)
    both_green = (content_gate == 'GREEN' and state_gate == 'GREEN')
    product_chain_eligible = bool(tree_match and both_green and policy_fresh)
    rec = dict(
        attestation_version=3, ticket_id=ticket, parent_commit=parent,
        validated_tree_sha=validated_tree, created_commit_sha=commit, created_commit_tree_sha=commit_tree,
        tree_match=tree_match, content_gate=content_gate, state_gate=state_gate,
        binding=input_binding(validated_tree, parent, gate_manifest_hash, policy_versions),
        status_axes=dict(policy_fresh=policy_fresh, product_chain_eligible=product_chain_eligible),
        result_summary=('PRODUCT_CHAIN_ELIGIBLE' if product_chain_eligible else 'NOT_ELIGIBLE'),
        created_at_utc=ts,
        prev_entry_hash=_last_chain_hash(),
    )
    body = _canonical(rec)
    rec['signature_ed25519'] = sign(body)
    entry_hash = hashlib.sha256(body + rec['signature_ed25519'].encode()).hexdigest()
    rec['entry_hash'] = entry_hash
    with open(os.path.join(d, commit + '.v3.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    with open(ledger_path_v3(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(commit=commit, entry_hash=entry_hash, prev_entry_hash=rec['prev_entry_hash'],
                                product_chain_eligible=product_chain_eligible, ts=ts), sort_keys=True) + '\n')
    _write_head_anchor(entry_hash)  # signierter Kopf-Anker gegen Tail-Truncation
    return rec


def read_attestation_v3(commit):
    p = os.path.join(attest_dir_v3(), commit + '.v3.json')
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return None


def verify_attestation_v3(commit):
    """Re-Validierung nur aus Commitobjekt + Record + OEFFENTLICHEM Key. Return (verdict, axes, rec)."""
    a = read_attestation_v3(commit)
    if not a:
        return 'UNATTESTED', {}, {}
    sig = a.pop('signature_ed25519', None)
    eh = a.pop('entry_hash', None)
    if not sig:
        return 'ATTESTATION_UNSIGNED', {}, a
    body = _canonical(a)
    if not verify_sig(body, sig):
        return 'ATTESTATION_SIGNATURE_INVALID', {}, a
    if eh != hashlib.sha256(body + sig.encode()).hexdigest():
        return 'ATTESTATION_CHAIN_HASH_INVALID', {}, a
    # Commit-Bindung (RT-Transplant): der Record muss GENAU diesen Commit + dessen realen Parent nennen,
    # nicht nur denselben Tree — sonst gilt eine Attestierung fuer einen anderen Commit mit gleichem Tree.
    if a.get('created_commit_sha') != commit:
        return 'ATTESTATION_COMMIT_MISMATCH', {}, a
    _, real_parents, _ = _git(['log', '--format=%P', '-n', '1', commit])
    real_parent = (real_parents.split() or [None])[0]
    if (a.get('parent_commit') or None) != (real_parent or None):
        return 'ATTESTATION_PARENT_MISMATCH', {}, a
    _, ctree, _ = _git(['rev-parse', commit + '^{tree}'])
    if ctree != a.get('created_commit_tree_sha') or a.get('validated_tree_sha') != a.get('created_commit_tree_sha') \
            or not a.get('tree_match'):
        return 'ATTESTATION_TREE_MISMATCH', {}, a
    axes = dict(a.get('status_axes', {}))
    axes['crypto_valid'] = True  # durch gueltige Signatur belegt (kein gespeichertes Feld)
    verdict = 'ATTESTED_PRODUCT_CHAIN_ELIGIBLE' if axes.get('product_chain_eligible') else 'ATTESTED_PENDING_NOT_ELIGIBLE'
    return verdict, axes, a


def _head_anchor_path():
    return os.path.join(os.path.dirname(signer_privkey_path()), 'ledger_head.anchor')


def _write_head_anchor(entry_hash):
    """Signierter Kopf-Anker (out-of-repo) — macht Tail-Truncation erkennbar (RT-Breaker)."""
    try:
        sig = sign(entry_hash.encode())
        os.makedirs(os.path.dirname(_head_anchor_path()), exist_ok=True)
        json.dump(dict(head=entry_hash, sig=sig), open(_head_anchor_path(), 'w'))
    except Exception:
        pass


def verify_ledger_chain():
    """Rekonstruiert die Kette aus den SIGNIERTEN .v3.json-Records (nicht der unsignierten jsonl) und
    prueft sie gegen den signierten Kopf-Anker. Erkennt Drop/Reorder/Fabrikation/Truncation ohne Privatkey.
    Return (ok, entries)."""
    d = attest_dir_v3()
    if not os.path.isdir(d):
        return True, 0
    by_hash, prevs = {}, {}
    for fn in os.listdir(d):
        if not fn.endswith('.v3.json'):
            continue
        try:
            a = json.load(open(os.path.join(d, fn), encoding='utf-8'))
        except ValueError:
            continue
        sig = a.pop('signature_ed25519', None)
        eh = a.pop('entry_hash', None)
        if not sig or not verify_sig(_canonical(a), sig):
            continue  # ungueltige Signatur -> keine authentische Kette (Fabrikation ignoriert)
        if eh != hashlib.sha256(_canonical(a) + sig.encode()).hexdigest():
            continue
        by_hash[eh] = a.get('prev_entry_hash')
        prevs.setdefault(a.get('prev_entry_hash'), []).append(eh)
    # Kopf-Anker ZUERST (auch bei leerer Record-Menge -> Truncation-to-empty erkennen)
    ap = _head_anchor_path()
    if os.path.exists(ap):
        try:
            an = json.load(open(ap))
            if verify_sig(an['head'].encode(), an['sig']) and an['head'] not in by_hash:
                return False, len(by_hash)  # signierter Kopf nicht in der Kette -> Tail-Truncation
        except Exception:
            return False, len(by_hash)
    if not by_hash:
        return True, 0
    # genau eine Genesis (prev=0*64); jede prev muss existieren (kein Drop); kein Fork
    genesis = [h for h, pv in by_hash.items() if pv == '0' * 64]
    if len(genesis) != 1:
        return False, len(by_hash)
    for h, pv in by_hash.items():
        if pv != '0' * 64 and pv not in by_hash:
            return False, len(by_hash)  # Vorgaenger fehlt (Drop/Truncation der Mitte)
    if any(len(v) > 1 for v in prevs.values()):
        return False, len(by_hash)  # Fork
    return True, len(by_hash)


if __name__ == '__main__':
    ensure_keys()
    ok, n = verify_ledger_chain()
    print(json.dumps({'ed25519': _ED, 'pubkey': repo_pubkey_path(), 'ledger_ok': ok, 'ledger_entries': n}))
