#!/usr/bin/env python3.11
"""S11_CENTRAL_GATE_AND_ATTESTATION — zentraler/CI-tauglicher Gate-Lauf + Attestierung.

Motivation (ehrlich): Auf einem rein lokalen Repo (kein Remote) laesst sich `git commit --no-verify`
nicht absolut VERHINDERN — der Nutzer besitzt die Maschine. Was wir liefern koennen, ist
TAMPER-EVIDENZ statt Tamper-Proof:
  * Jeder gruene Pre-Commit-Gate-Lauf hinterlegt einen Green-Marker (Index-Tree).
  * Der post-commit-Hook bindet diesen an den Commit (Attestierung), sofern der Tree passt.
  * `ci_gate.py run` ist der UNABHAENGIGE zentrale Lauf (CI-Ersatz): fuehrt das volle Gate auf
    HEAD aus und attestiert nur bei gruen — verlaesst sich NICHT auf den Commit-Hook.
  * `ci_gate.py audit` erkennt jeden Commit OHNE gruene Attestierung (= --no-verify-Umgehung).
  * `ci_gate.py verify` prueft HEAD.

Attestierungen liegen lokal unter <git-dir>/wpno_gate_attest/ (untracked; haelt den Working Tree
sauber). Fuer echten Remote-Schutz: `ci_gate.py run` als pre-receive-Hook / CI-Job verdrahten
(siehe reports/CENTRAL_GATE_AND_ATTESTATION.md).

Exit-Codes: 0 = ok/gruen · 1 = rot/Umgehung erkannt/Fehler.
KEINE Rechtsarbeit.
"""
import os, sys, subprocess, json, csv, hashlib, time

REPO = os.environ.get('WPNO_CI_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_precommit_quality_gate.py')


def _git(args, cwd=None):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _git_dir():
    code, out, _ = _git(['rev-parse', '--git-dir'])
    if code != 0:
        return os.path.join(REPO, '.git')
    return out if os.path.isabs(out) else os.path.join(REPO, out)


def attest_dir():
    return os.environ.get('WPNO_ATTEST_DIR') or os.path.join(_git_dir(), 'wpno_gate_attest')


def ledger_path():
    return os.path.join(attest_dir(), 'ledger.csv')


def green_marker_path():
    return os.environ.get('WPNO_GATE_GREEN_MARKER') or os.path.join(_git_dir(), 'wpno_gate_last_green')


LEDGER_COLS = ['commit', 'tree', 'verdict', 'source', 'gate_hash', 'ts']


def gate_script_hash():
    try:
        return hashlib.sha256(open(GATE_PY, 'rb').read()).hexdigest()[:16]
    except OSError:
        return 'unknown'


def head_commit_tree():
    c1, commit, _ = _git(['rev-parse', 'HEAD'])
    c2, tree, _ = _git(['rev-parse', 'HEAD^{tree}'])
    if c1 != 0 or c2 != 0:
        return None, None
    return commit, tree


def write_attestation(commit, tree, verdict, source, ts=None):
    d = attest_dir()
    os.makedirs(d, exist_ok=True)
    ts = int(ts if ts is not None else time.time())
    rec = dict(commit=commit, tree=tree, verdict=verdict, source=source,
               gate_hash=gate_script_hash(), ts=ts)
    try:
        rec['record_hmac'] = _record_hmac(rec)  # V1 ebenfalls integritaetsgesichert (RT-V3 forged-v1)
    except Exception:
        pass
    with open(os.path.join(d, commit + '.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    lp = ledger_path()
    new = not os.path.exists(lp)
    with open(lp, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(LEDGER_COLS)
        w.writerow([rec[c] for c in LEDGER_COLS])
    return rec


def read_attestation(commit):
    p = os.path.join(attest_dir(), commit + '.json')
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --- Attestation V2: tree-gebunden + dauerhaft (S11_GATE_ATTESTATION_V2) ----
def _sha256_file(path):
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]
    except OSError:
        return 'missing'


def test_manifest_hash():
    """Hash ueber die aktive Gate-Phasenliste + die Datei-Hashes der registrierten Tests/Guards.
    Aenderung an Gate-Zusammensetzung ODER an einem Testinhalt -> anderer Hash -> Attestierung stale."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import run_precommit_quality_gate as G
        parts = []
        for label, script in G.GATES:
            parts.append(label + ':' + _sha256_file(script))
        blob = '\n'.join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:16]
    except Exception:
        return 'unknown'


def schema_hashes():
    v = os.path.join(REPO, 'zitate_register', '_s11_006d_spec_validator.py')
    s = os.path.join(REPO, 'zitate_register', 'visualization', 'S11_PS861_006D_SPEC_ONLY_SCHEMA.json')
    return {'validator': _sha256_file(v), 'schema': _sha256_file(s)}


ATT_V2_STATUS = ('ATTESTED_GREEN_FOR_EXACT_TREE', 'ATTESTED_RED', 'ATTESTATION_STALE',
                 'ATTESTATION_SCHEMA_MISMATCH', 'ATTESTATION_TESTSET_SUPERSEDED', 'UNATTESTED',
                 'ATTESTATION_TAMPERED', 'ATTESTATION_KEY_MISSING', 'ATTESTED_TEST_MODE',
                 'ATTESTED_GREEN_PENDING_GATECODE_REVIEW')


def _hmac_key_path():
    return (os.environ.get('WPNO_ATTEST_HMAC_KEY')
            or os.path.join(os.path.expanduser('~/wpno-secure-case-ledgers/s11_control_plane_p0'), 'attest_hmac.key'))


def _hmac_key():
    """Off-git HMAC-Schluessel (0600). Fehlt er, wird er einmalig erzeugt. Ein Angreifer OHNE diesen
    Schluessel kann keine gueltige Attestierung faelschen (Tamper-Evidenz; keine Tamper-Proofness auf
    einer Maschine, deren Besitzer den Schluessel lesen kann — dieselbe ehrliche Grenze wie --no-verify)."""
    p = _hmac_key_path()
    try:
        return open(p, 'rb').read().strip()
    except OSError:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        key = hashlib.sha256(os.urandom(32)).hexdigest().encode()
        fd = os.open(p, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(fd, key)
        os.close(fd)
        return key


def _canonical(rec):
    body = {k: rec[k] for k in sorted(rec) if k not in ('record_hmac',)}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _record_hmac(rec):
    import hmac
    return hmac.new(_hmac_key(), _canonical(rec), hashlib.sha256).hexdigest()


def write_attestation_v2(commit, commit_tree, parent, validated_tree, ticket, gate_result, gate_run_id,
                         ts=None, test_mode=None, gatecode_review=False):
    """Schreibt eine tree-gebundene, HMAC-integritaetsgesicherte V2-Attestierung. Endgueltig gruen NUR
    wenn commit_tree == validated_tree UND kein Testmodus UND keine unreviewte Kontrollschicht-Code-
    Aenderung. Manipuliertes Record -> ATTESTATION_TAMPERED bei verify."""
    d = attest_dir()
    os.makedirs(d, exist_ok=True)
    ts = int(ts if ts is not None else time.time())
    if test_mode is None:
        test_mode = os.environ.get('WPNO_STAGEDTREE_TEST_MODE') == '1'
    tree_match = (commit_tree == validated_tree)
    if test_mode:
        status = 'ATTESTED_TEST_MODE'
    elif not (tree_match and gate_result == 'GREEN'):
        status = 'ATTESTED_RED'
    elif gatecode_review:
        status = 'ATTESTED_GREEN_PENDING_GATECODE_REVIEW'  # Kontrollschicht-Code geaendert -> nicht final
    else:
        status = 'ATTESTED_GREEN_FOR_EXACT_TREE'
    rec = dict(attestation_version=2, ticket_id=ticket, gate_run_id=gate_run_id, parent_commit=parent,
               validated_tree_sha=validated_tree, created_commit_sha=commit, created_commit_tree_sha=commit_tree,
               tree_match=tree_match, gate_code_hash=gate_script_hash(), test_manifest_hash=test_manifest_hash(),
               schema_hashes=schema_hashes(), result=gate_result, test_mode=bool(test_mode),
               gatecode_review=bool(gatecode_review), created_at_utc=ts, status=status)
    rec['record_hmac'] = _record_hmac(rec)
    with open(os.path.join(d, commit + '.v2.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    # V1-Marker nur bei echter Produktions-Gruenattestierung (kein Testmodus) — sonst RED
    write_attestation(commit, commit_tree, 'GREEN' if status == 'ATTESTED_GREEN_FOR_EXACT_TREE' else 'RED',
                      'VALIDATED_COMMIT_BROKER', ts=ts)
    return rec


def read_attestation_v2(commit):
    p = os.path.join(attest_dir(), commit + '.v2.json')
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def verify_attestation_v2(commit):
    """Re-validiert eine V2-Attestierung. Reihenfolge: (1) HMAC-Integritaet (Faelschung/Tamper ->
    ATTESTATION_TAMPERED); (2) Commit-Tree == Record-Tree UND tree_match (sonst SCHEMA_MISMATCH);
    (3) Testmodus -> ATTESTED_TEST_MODE (nie Produktionsgruen); (4) Gate-/Testmanifest-Drift -> STALE.
    Ein spaeter veraendertes Working-Tree-Artefakt beeinflusst das Ergebnis NICHT (nur der Commit-Tree)."""
    a = read_attestation_v2(commit)
    if not a:
        return 'UNATTESTED', {}
    # (1) Integritaet: HMAC ueber den kanonischen Record
    supplied = a.get('record_hmac')
    if not supplied:
        return 'ATTESTATION_TAMPERED', a  # V2 ohne HMAC = manipuliert/ungueltig
    try:
        import hmac
        if not hmac.compare_digest(supplied, _record_hmac(a)):
            return 'ATTESTATION_TAMPERED', a
    except FileNotFoundError:
        return 'ATTESTATION_KEY_MISSING', a
    # (2) Tree-Bindung gegen das echte Commitobjekt
    _, ctree, _ = _git(['rev-parse', commit + '^{tree}'])
    if ctree != a.get('created_commit_tree_sha') or not a.get('tree_match') \
            or a.get('validated_tree_sha') != a.get('created_commit_tree_sha'):
        return 'ATTESTATION_SCHEMA_MISMATCH', a
    # (3) Testmodus ist nie Produktionsgruen
    if a.get('test_mode') or a.get('status') == 'ATTESTED_TEST_MODE':
        return 'ATTESTED_TEST_MODE', a
    # (3b) Kontrollschicht-Code geaendert -> konditionale, nicht finale Attestierung
    if a.get('gatecode_review') or a.get('status') == 'ATTESTED_GREEN_PENDING_GATECODE_REVIEW':
        return 'ATTESTED_GREEN_PENDING_GATECODE_REVIEW', a
    if a.get('result') != 'GREEN' or a.get('status') != 'ATTESTED_GREEN_FOR_EXACT_TREE':
        return 'ATTESTED_RED', a
    # (4) Dauerhaftigkeit: historische Gruen-Attestierung bleibt fuer IHREN Tree gueltig
    live = 'ATTESTED_GREEN_FOR_EXACT_TREE'
    if a.get('gate_code_hash') != gate_script_hash() or a.get('test_manifest_hash') != test_manifest_hash():
        live = 'ATTESTATION_STALE'
    return live, a


def _attested_green(commit, tree):
    """Produktionsgruen NUR mit gueltiger HMAC-V2-Attestierung (ATTESTED_GREEN_FOR_EXACT_TREE).
    Ein V1-Marker allein genuegt NICHT mehr (RT-G4 cmd_verify_bypass_via_forged_v1_record). Fehlt eine
    V2-Attestierung ganz (Alt-Commits vor V2), gilt die konservative V1-Ruueckfallpruefung."""
    if read_attestation_v2(commit) is not None:
        st, _ = verify_attestation_v2(commit)
        return st == 'ATTESTED_GREEN_FOR_EXACT_TREE'
    a = read_attestation(commit)
    if not a or a.get('verdict') != 'GREEN' or a.get('tree') != tree:
        return False
    supplied = a.get('record_hmac')
    if not supplied:
        return False  # unsignierter V1-Marker = legacy/gefaelscht -> nicht vertrauenswuerdig (RT-V3)
    try:
        import hmac
        return hmac.compare_digest(supplied, _record_hmac(a))
    except Exception:
        return False


# --- Subkommandos ----------------------------------------------------------
def run_full_gate():
    """Fuehrt das volle Pre-Commit-Gate aus (dieselbe Autoritaet wie der Hook)."""
    r = subprocess.run([sys.executable, GATE_PY], cwd=REPO, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)
    ok = r.returncode == 0 and 'GATE GRUEN' in r.stdout
    return ok


def cmd_run():
    """Zentraler/CI-Lauf: volles Gate auf HEAD, attestiert nur bei gruen."""
    commit, tree = head_commit_tree()
    if not commit:
        print('CI-GATE: kein HEAD-Commit gefunden.')
        return 1
    print('CI-GATE zentraler Lauf auf %s (tree %s)' % (commit[:12], tree[:12]))
    ok = run_full_gate()
    verdict = 'GREEN' if ok else 'RED'
    write_attestation(commit, tree, verdict, 'CENTRAL_GATE_RUN')
    print('CI-GATE ERGEBNIS: %s — Attestierung geschrieben (%s).' % (verdict, 'gruen' if ok else 'ROT'))
    return 0 if ok else 1


def cmd_attest_head():
    """Vom post-commit-Hook: bindet den Green-Marker an HEAD, wenn der Tree passt. Nie blockierend."""
    commit, tree = head_commit_tree()
    if not commit:
        return 0
    mp = green_marker_path()
    try:
        marker = open(mp, encoding='utf-8').read().strip()
    except OSError:
        # Kein Green-Marker -> Pre-Commit-Gate lief nicht (moegl. --no-verify). Nicht attestieren.
        return 0
    mtree = (marker.split('|') or [''])[0]
    if mtree and mtree == tree:
        write_attestation(commit, tree, 'GREEN', 'PRE_COMMIT_GATE')
        try:
            os.remove(mp)
        except OSError:
            pass
    return 0


def cmd_verify():
    """Prueft, ob HEAD eine gruene Attestierung passend zum Tree hat."""
    commit, tree = head_commit_tree()
    if not commit:
        print('VERIFY: kein HEAD.')
        return 1
    if _attested_green(commit, tree):
        print('VERIFY: HEAD %s GRUEN attestiert.' % commit[:12])
        return 0
    print('VERIFY: HEAD %s NICHT gruen attestiert (moegliche --no-verify-Umgehung).' % commit[:12])
    return 1


def cmd_audit():
    """Listet alle Commits der aktuellen Branch ohne gruene Attestierung."""
    since = None
    if '--since' in sys.argv:
        i = sys.argv.index('--since')
        since = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    rng = ['%s..HEAD' % since] if since else ['HEAD']
    code, out, _ = _git(['rev-list'] + rng)
    if code != 0:
        print('AUDIT: git rev-list fehlgeschlagen.')
        return 1
    commits = [c for c in out.splitlines() if c.strip()]
    unattested = []
    for c in commits:
        _, tree, _ = _git(['rev-parse', c + '^{tree}'])
        if not _attested_green(c, tree):
            unattested.append(c)
    print('AUDIT: %d Commit(s) geprueft, %d ohne gruene Attestierung.' % (len(commits), len(unattested)))
    for c in unattested:
        _, subj, _ = _git(['log', '-1', '--format=%s', c])
        print('  UNATTESTED %s  %s' % (c[:12], subj[:60]))
    if unattested:
        print('AUDIT-BEFUND: Umgehung(en) erkannt — bitte `ci_gate.py run` auf sauberem Stand ausfuehren.')
        return 1
    print('AUDIT: alle Commits gruen attestiert.')
    return 0


USAGE = 'usage: ci_gate.py {run|attest-head|verify|audit [--since <ref>]}'


def main(argv):
    if not argv:
        print(USAGE)
        return 1
    cmd = argv[0]
    return {
        'run': cmd_run,
        'attest-head': cmd_attest_head,
        'verify': cmd_verify,
        'audit': cmd_audit,
    }.get(cmd, lambda: (print(USAGE) or 1))()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
