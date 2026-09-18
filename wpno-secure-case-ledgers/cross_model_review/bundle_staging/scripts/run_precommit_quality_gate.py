#!/usr/bin/env python3.11
"""PRE_COMMIT_GUARD_ENFORCEMENT + PRE_COMMIT_CONCURRENCY_LOCK_AND_TIMEOUT_HARDENING.

Laeuft VOR jedem Commit. Blockiert (exit 1), sobald ein zentraler Verifikator/Guard FAIL/TIMEOUT
liefert oder ein paralleler Gate-Lauf aktiv ist.

Haertung gegen den Race, der bei Commit 7876f96 auftrat (zwei parallele Pre-Commit-Prozesse
mutierten gleichzeitig reale Testartefakte, z. B. seed_lock.LOCK -> Premortem 15/16):
  (1) Lockfile mit PID (atomar O_CREAT|O_EXCL), keine zweite Gate-Instanz parallel;
  (2) Stale-Lock-Erkennung (tote PID) mit automatischem Cleanup;
  (3) sauberes Timeout je Hauptphase (subprocess timeout);
  (4) Cleanup Gate-eigener Temp-Artefakte vor und nach dem Lauf;
  (5) klare Fehlermeldung bei Lock-Konflikt / Timeout.

Exit-Codes:
  0  Gate vollstaendig gruen (Commit zulaessig)
  1  Gate-FAIL ODER Timeout ODER Lock-Konflikt (Commit verweigert)

KEINE Rechtsarbeit. Aufruf: python3.11 scripts/run_precommit_quality_gate.py
"""
import os, sys, subprocess, glob, shutil, errno, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZR = os.path.join(REPO, 'zitate_register')


def _git_dir():
    d = os.path.join(REPO, '.git')
    return d if os.path.isdir(d) else REPO


# --- Konfiguration (env-/test-uebersteuerbar) ---
LOCK_PATH = os.environ.get('WPNO_PRECOMMIT_LOCK') or os.path.join(_git_dir(), 'wpno_precommit_gate.lock')
SCRATCH_DIR = os.environ.get('WPNO_GATE_SCRATCH') or os.path.join(_git_dir(), 'wpno_gate_scratch')
PHASE_TIMEOUT = int(os.environ.get('WPNO_PRECOMMIT_PHASE_TIMEOUT', '900'))  # Sekunden je Hauptphase

# (Label, auszufuehrendes Script)
GATES = [
    ('S11-PS861-006D-Tax-SV-Public-Creditor-Viz', os.path.join(REPO, 'tests', 'test_s11_ps861006d_tax_sv_public_creditor_visualization_model.py')),
    ('S11-PS861-006D-QC-Protocol', os.path.join(REPO, 'tests', 'test_s11_ps861_006d_qc_protocol.py')),
    ('S11-PS861-006D-Recheck-Protocol', os.path.join(REPO, 'tests', 'test_s11_ps861_006d_recheck_protocol.py')),
    ('S11-Control-Plane-Scope-Guard', os.path.join(REPO, 'tests', 'test_s11_control_plane_scope_guard.py')),
    ('S11-Control-Plane-Staged-Tree-Binding', os.path.join(REPO, 'tests', 'test_s11_control_plane_staged_tree_binding.py')),
    ('S11-Gate-Attestation-Durability', os.path.join(REPO, 'tests', 'test_s11_gate_attestation_durability.py')),
    ('S11-PS861-006D-Allowlist-Hardening', os.path.join(REPO, 'tests', 'test_s11_ps861_006d_allowlist_hardening.py')),
    ('S11-PS861-006C-Source-Agnostic', os.path.join(REPO, 'tests', 'test_s11_ps861006c_source_agnostic_datev_erp_attachment_evidence_model.py')),
    ('Quality-Redesign-Guards',       os.path.join(ZR, 'check_quality_redesign.py')),
    ('Corpus-Guards',                 os.path.join(ZR, 'check_judgment_corpus.py')),
    ('Primary-Source-/Wording-Guards', os.path.join(ZR, 'check_primary_source_verification.py')),
    ('Closure-Guards',                os.path.join(ZR, 'check_judgment_closure.py')),
    ('CSV-Schema-Guard',              os.path.join(ZR, 'check_zitate_register_schema.py')),
    ('Tool-Claims-Guard',             os.path.join(REPO, 'scripts', 'check_no_unproven_tool_claims.py')),
    ('Legal-Infra-Ledger-Guards',     os.path.join(ZR, 'check_legal_infra.py')),
    ('S11-Core-Tests',                os.path.join(REPO, 'tests', 'test_status_machine.py')),
    ('S11-Core-MVP2-Tests',           os.path.join(REPO, 'tests', 'test_status_machine_mvp2.py')),
    ('S11-Truth-Unification-Tests',   os.path.join(REPO, 'tests', 'test_truth_unification.py')),
    ('S11-Reproducible-Tests',        os.path.join(REPO, 'tests', 'test_reproducible_truth.py')),
    ('S11-Official-Inbox-Tests',      os.path.join(REPO, 'tests', 'test_official_primary_inbox.py')),
    ('S11-Official-Release-Repro',    os.path.join(REPO, 'tests', 'test_official_release_reproducibility.py')),
    ('S11-Premortem-Hardening',       os.path.join(REPO, 'tests', 'test_premortem_hardening.py')),
    ('S11-36-Canon-Guard',            os.path.join(REPO, 'tests', 'test_s11_36_canonical_guard.py')),
    ('Precommit-Concurrency-Lock',    os.path.join(REPO, 'tests', 'test_precommit_concurrency_lock.py')),
    ('Central-Gate-Attestation',      os.path.join(REPO, 'tests', 'test_central_gate_attestation.py')),
    ('Status-DB-Reconciliation',      os.path.join(REPO, 'tests', 'test_status_db_reconciliation.py')),
    ('Extended-Manifest-Granularity', os.path.join(REPO, 'tests', 'test_extended_manifest_granularity.py')),
    ('Legacy-Intake-Confidentiality', os.path.join(REPO, 'tests', 'test_legacy_intake_confidentiality.py')),
    ('Drive-API-Large-Blob',          os.path.join(REPO, 'tests', 'test_drive_api_large_blob_downloader.py')),
    ('Legacy-Plan-No-Execution',      os.path.join(REPO, 'tests', 'test_legacy_plan_no_execution.py')),
    ('Legacy-OCR-Pilot',              os.path.join(REPO, 'tests', 'test_legacy_ocr_pilot.py')),
    ('Legacy-Full-OCR',               os.path.join(REPO, 'tests', 'test_legacy_full_ocr.py')),
    ('P0-Safety-Guards',              os.path.join(REPO, 'tests', 'test_p0_safety_guards.py')),
    ('P0-B-MCP-Stop',                 os.path.join(REPO, 'tests', 'test_p0b_mcp_mandate_stop.py')),
    ('P0-C-Status-Truth',             os.path.join(REPO, 'tests', 'test_p0c_status_truth.py')),
    ('P0-D-Retrieved-At',             os.path.join(REPO, 'tests', 'test_p0d_retrieved_at.py')),
    ('P0-E-Confidential-Redaction',   os.path.join(REPO, 'tests', 'test_p0e_confidential_redaction.py')),
    ('P0-F1-OCR-Cap-Dedup',           os.path.join(REPO, 'tests', 'test_p0f1_ocr_cap_dedup.py')),
    ('Council-S11-Extreme-Intake',    os.path.join(REPO, 'tests', 'test_council_s11_extreme_intake.py')),
    ('P0-G-Backup-Restore',           os.path.join(REPO, 'tests', 'test_p0g_backup_restore.py')),
    ('BL-02-Formula-Register',        os.path.join(REPO, 'tests', 'test_bl02_formula_register.py')),
    ('F9-Invariants',                 os.path.join(REPO, 'tests', 'test_f9_invariants.py')),
    ('F9-R1-Review-Package',          os.path.join(REPO, 'tests', 'test_f9_r1_review_package.py')),
    ('Builder-Merge-Logic',           os.path.join(REPO, 'tests', 'test_builder_merge_logic.py')),
    ('System-Protocol-Governance',    os.path.join(REPO, 'tests', 'test_system_protocol_governance.py')),
    ('P0-G-Hardening',                os.path.join(REPO, 'tests', 'test_p0g_hardening.py')),
    ('Tax-SV-Premortem',              os.path.join(REPO, 'tests', 'test_tax_sv_premortem.py')),
    ('Liability-Universe-Premortem',  os.path.join(REPO, 'tests', 'test_liability_universe_premortem.py')),
    ('Tax-SV-Liability-Master',       os.path.join(REPO, 'tests', 'test_tax_sv_liability_master.py')),
    ('P0-G-Backup-Restore-Hardening', os.path.join(REPO, 'tests', 'test_p0g_backup_restore_hardening.py')),
    ('Berufstraeger-Freigabe-Gate',   os.path.join(REPO, 'tests', 'test_berufstraeger_freigabe_gate.py')),
    ('Evidence-First-Protocol',       os.path.join(REPO, 'tests', 'test_evidence_first_protocol.py')),
    ('Snapshot-Freshness',            os.path.join(REPO, 'tests', 'test_snapshot_freshness_gate.py')),
    ('PPT-Adoption',                  os.path.join(REPO, 'tests', 'test_coding_data_prompt_pattern_adoption.py')),
    ('DDR-Tier1-Data-Room',           os.path.join(REPO, 'tests', 'test_s11_tier1_agentic_data_room_architecture.py')),
    ('DDR-002-Access-Read-Proof',     os.path.join(REPO, 'tests', 'test_ddr002_access_ledger_and_read_proof.py')),
    ('DDR-010-Forensic-Ledger',      os.path.join(REPO, 'tests', 'test_ddr010_forensic_ledger_integrity.py')),
    ('DDR-003-Structured-Data',      os.path.join(REPO, 'tests', 'test_ddr003_structured_data_schema_and_control_totals.py')),
    ('S11-PS861-001-Product-Model',  os.path.join(REPO, 'tests', 'test_s11_ps861001_product_operating_model.py')),
    ('S11-PS861-002-Access-Enforce', os.path.join(REPO, 'tests', 'test_s11_ps861002_controlled_productive_access.py')),
    ('S11-PS861-003-Connector-Harden',os.path.join(REPO, 'tests', 'test_s11_ps861003_connector_hardening.py')),
    ('S11-PS861-003-Blocking-Subfix', os.path.join(REPO, 'tests', 'test_s11_ps861003_blocking_subfix.py')),
    ('S11-PS861-003R-Structural',    os.path.join(REPO, 'tests', 'test_s11_ps861003r_defect_004_005_structural_redesign.py')),
    ('S11-PS861-005-Human-Review',   os.path.join(REPO, 'tests', 'test_s11_ps861005_human_review_gate.py')),
    ('S11-PS861-005-Remediation',    os.path.join(REPO, 'tests', 'test_s11_ps861005_remediation_qc_005_01_04_06.py')),
    ('DDR-004-PDF-Table-Extraction', os.path.join(REPO, 'tests', 'test_ddr004_semi_structured_pdf_table_extraction.py')),
    ('DDR-004-Parser-Integration',   os.path.join(REPO, 'tests', 'test_ddr004_parser_integration_run.py')),
    ('DDR-004-Productive-Ledger',    os.path.join(REPO, 'tests', 'test_ddr004_productive_ledger_binding.py')),
]


# --- PID / Lock ------------------------------------------------------------
def pid_alive(pid):
    """True, wenn ein Prozess mit dieser PID existiert (auch fremd/EPERM)."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM  # existiert, gehoert aber anderem User
    return True


def read_lock(path=None):
    """PID aus dem Lockfile (Format 'PID|ts|tag'); None wenn nicht lesbar."""
    path = path or LOCK_PATH
    try:
        with open(path) as f:
            return int((f.read().split('|')[0] or '0').strip())
    except (FileNotFoundError, ValueError):
        return None


def acquire_lock(path=None):
    """Atomar erwerben. Return (ok, reason). Stale-Lock (tote PID) wird bereinigt."""
    path = path or LOCK_PATH
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    payload = ('%d|%d|precommit_gate' % (os.getpid(), int(time.time()))).encode()
    for _ in (1, 2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, payload)
            os.close(fd)
            return True, None
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            owner = read_lock(path)
            if owner is None or not pid_alive(owner):
                # Stale-Lock: toter/unlesbarer Halter -> entfernen und erneut versuchen
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                continue
            return False, 'Gate laeuft bereits (PID %d) — paralleler Commit blockiert.' % owner
    return False, 'Lock konnte nicht erworben werden (Race).'


def release_lock(path=None):
    """Nur den EIGENEN Lock loesen (fremde/live Locks bleiben unangetastet)."""
    path = path or LOCK_PATH
    if read_lock(path) == os.getpid():
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# --- Cleanup Gate-eigener Temp-Artefakte -----------------------------------
def _gate_tmp_globs():
    return [
        os.path.join(SCRATCH_DIR, '*'),
        os.path.join(REPO, 'reports', '_gate_tmp_*'),
        os.path.join(REPO, 'exports', '_gate_tmp_*'),
        os.path.join(REPO, 'tests', '_gate_tmp_*'),
    ]


def write_green_marker():
    """Hinterlegt bei gruenem Gate den Index-Tree als Attestierungs-Anker (fuer post-commit).
    Nicht im Selbsttest; Fehler werden verschluckt (z. B. kein git-Repo im Test)."""
    if os.environ.get('WPNO_GATE_SELFTEST'):
        return
    try:
        r = subprocess.run(['git', 'write-tree'], cwd=REPO, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            marker = os.environ.get('WPNO_GATE_GREEN_MARKER') or os.path.join(_git_dir(), 'wpno_gate_last_green')
            with open(marker, 'w') as f:
                f.write('%s|%d|%d' % (r.stdout.strip(), int(time.time()), os.getpid()))
    except Exception:
        pass


def cleanup_temp_artifacts():
    """Entfernt ausschliesslich Gate-eigene Temp-Artefakte. Return Anzahl entfernter Pfade."""
    n = 0
    for pat in _gate_tmp_globs():
        for p in glob.glob(pat):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
                n += 1
            except OSError:
                pass
    return n


# --- Phase-Ausfuehrung mit Timeout -----------------------------------------
def run_phase(label, cmd, cwd=None, timeout=None, success_substr=None):
    """Fuehrt eine Hauptphase aus. Return (ok, tail, timed_out)."""
    timeout = PHASE_TIMEOUT if timeout is None else timeout
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, 'TIMEOUT nach %ss' % timeout, True
    ok = r.returncode == 0
    if success_substr is not None:
        ok = ok and success_substr in r.stdout
    tail = (r.stdout.strip().splitlines() or [''])[-1]
    if not ok and r.stderr.strip():
        tail = (tail + ' | ' + r.stderr.strip().splitlines()[-1]).strip(' |')
    return ok, tail, False


# NUR diese Phasen duerfen per Registry degradiert werden (in CODE gepinnt, nicht in der CSV) —
# schliesst RT-G5 universal_phase_offswitch / security_guard_suppression: eine Registry-Zeile kann
# keine beliebige (Sicherheits-)Phase gegen HEAD stummschalten.
DEMOTABLE_PHASES = frozenset({'S11-PS861-006D-Recheck-Protocol'})


def phase_lifecycle():
    """{phase_id: (lifecycle_status, reason)} aus der Gate-Phase-Registry. Default ACTIVE_CURRENT.
    Eine Degradierung wird NUR fuer in DEMOTABLE_PHASES (Code) gelistete phase_ids wirksam; jeder
    Versuch, eine nicht-degradierbare (Sicherheits-)Phase zu degradieren, wird ignoriert + laut geloggt."""
    import csv as _csv
    reg = os.path.join(REPO, 'reports', 'S11_GATE_PHASE_REGISTRY.csv')
    out = {}
    try:
        for r in _csv.DictReader(open(reg, encoding='utf-8')):
            pid = r['phase_id']
            status = r.get('lifecycle_status', 'ACTIVE_CURRENT')
            if status != 'ACTIVE_CURRENT' and pid not in DEMOTABLE_PHASES:
                print('  [PHASE-DEMOTION-IGNORED] %s: nicht-degradierbare Phase — laeuft trotz Registry gegen HEAD' % pid)
                status = 'ACTIVE_CURRENT'
            out[pid] = (status, r.get('reason', ''))
    except OSError:
        pass
    return out


def _build_phases():
    """Liste (label, cmd, cwd, success_substr). Selbsttest-Modus fuer schnelle Harness-Tests."""
    st = os.environ.get('WPNO_GATE_SELFTEST')
    if st == 'pass':
        return [('SelfTest-OK', [sys.executable, '-c', 'print("SELFTEST OK")'], REPO, None)]
    if st == 'timeout':
        return [('SelfTest-Sleep', [sys.executable, '-c', 'import time; time.sleep(30)'], REPO, None)]
    if st == 'fail':
        return [('SelfTest-FAIL', [sys.executable, '-c', 'import sys; sys.exit(1)'], REPO, None)]
    lifecycle = phase_lifecycle()
    active = []
    for l, s in GATES:
        status, reason = lifecycle.get(l, ('ACTIVE_CURRENT', ''))
        if status != 'ACTIVE_CURRENT':
            print('  [PHASE-%s] %s: nicht gegen HEAD (%s)' % (status, l, reason[:80]))
            continue
        active.append((l, s))
    phases = [(l, [sys.executable, s], os.path.dirname(s), None) for l, s in active if os.path.exists(s)]
    for l, s in active:
        if not os.path.exists(s):
            print('  [SKIP] %s: %s fehlt' % (l, os.path.basename(s)))
    phases.append(('s11_core.cli check', [sys.executable, '-m', 's11_core.cli', 'check'], REPO, None))
    phases.append(('verifikator.py check', [sys.executable, os.path.join(ZR, 'verifikator.py'), 'check'],
                   REPO, 'ALLE KRITISCHEN CHECKS GRUEN'))
    return phases


def run_gate():
    """Fuehrt alle Phasen aus. Return (fails, timeouts)."""
    print('PRE-COMMIT QUALITY GATE (concurrency-locked, per-phase timeout=%ss)' % PHASE_TIMEOUT)
    fails = timeouts = 0
    for label, cmd, cwd, sub in _build_phases():
        ok, tail, to = run_phase(label, cmd, cwd=cwd, success_substr=sub)
        state = 'PASS' if ok else ('TIMEOUT' if to else 'FAIL')
        print('  [%s] %s: %s' % (state, label, tail))
        if not ok:
            fails += 1
            timeouts += int(to)
    return fails, timeouts


def main():
    ok, reason = acquire_lock()
    if not ok:
        print('GATE-LOCK-KONFLIKT: %s' % reason)
        print('COMMIT BLOCKIERT: paralleler Gate-Lauf — Commit verweigert.')
        return 1
    try:
        cleanup_temp_artifacts()          # Altartefakte vor dem Lauf entfernen
        fails, timeouts = run_gate()
    finally:
        cleanup_temp_artifacts()          # Gate-eigene Artefakte nach dem Lauf entfernen
        release_lock()
    if timeouts:
        print('COMMIT BLOCKIERT: %d Phase(n) TIMEOUT — Commit verweigert.' % timeouts)
        return 1
    if fails:
        print('COMMIT BLOCKIERT: %d Gate(s) FAIL — Commit verweigert.' % fails)
        return 1
    write_green_marker()  # Attestierungs-Anker fuer post-commit (Tamper-Evidenz)
    print('GATE GRUEN: alle Verifikatoren/Guards bestanden — Commit zulaessig.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
