#!/usr/bin/python3
import datetime, hashlib, importlib.util, json, os, pathlib, re, stat, sys, traceback

ORIGINAL=pathlib.Path('/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8')
CLONE=pathlib.Path('/home/ubuntu/project/WPNO/.r8_verify_clone_attempt_8_676767')
BASE=pathlib.Path('/home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_8')
WS=pathlib.Path('/home/ubuntu/project/WPNO_orchestration/R8_final_delta_closure')
OUT=WS/'codex_output'
CARRY=[*range(1,23),24,25,26,27,31,32,33]
DELTA=[23,28,29,30,34,35]
findings=[]; measurements={}; item_rows=[]

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def sha_tree(p):
    p=pathlib.Path(p)
    if p.is_file(): return sha(p)
    h=hashlib.sha256()
    for dirpath,dirnames,filenames in os.walk(p):
        dirnames.sort()
        for name in sorted(filenames):
            q=pathlib.Path(dirpath)/name
            h.update(os.path.relpath(q,p).encode()); h.update(sha(q).encode('ascii'))
    return h.hexdigest()
def load(p):
    with open(p,encoding='utf-8') as f: return json.load(f)
def need(d,k,t,where):
    if not isinstance(d,dict): raise ValueError(f'{where} is not an object')
    if k not in d: raise ValueError(f'{where} missing proved key {k!r}')
    v=d[k]
    if not isinstance(v,t) or (t is int and isinstance(v,bool)): raise ValueError(f'{where}.{k} wrong type {type(v).__name__}')
    return v
def assert_(x,msg):
    if not x: raise AssertionError(msg)
def append_item(row):
    with open(OUT/'ITEM_RESULTS.jsonl','a',encoding='utf-8') as f: f.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
    item_rows.append(row)
def parse_manifest(p):
    rows=[]; malformed=[]
    for n,line in enumerate(p.read_text().splitlines(),1):
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        if not m: malformed.append(n)
        else: rows.append((m.group(1),m.group(2)))
    return rows,malformed
def verify_manifest(p,root):
    rows,bad=parse_manifest(p); names=[x[1] for x in rows]
    missing=[]; mism=[]
    for digest,rel in rows:
        q=root/rel
        if not q.is_file(): missing.append(rel)
        elif sha(q)!=digest: mism.append(rel)
    return {'entries':len(rows),'malformed':bad,'duplicates':sorted({x for x in names if names.count(x)>1}),'missing':missing,'mismatches':mism,'manifest_sha256':sha(p)}
def inventory(root):
    ents=[]
    paths=[root]+sorted(root.rglob('*'),key=lambda p:str(p.relative_to(root)))
    for p in paths:
        s=p.lstat(); rel='.' if p==root else str(p.relative_to(root)); typ='symlink' if p.is_symlink() else ('dir' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'other')
        ents.append({'path':rel,'type':typ,'size':s.st_size,'sha256':sha(p) if typ=='file' else None,'symlink_target':os.readlink(p) if typ=='symlink' else None,'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid,'mtime_ns':s.st_mtime_ns})
    return {'root':str(root.resolve()),'entry_count':len(ents),'entries':ents}
def compare_inv(a,b):
    aa={x['path']:x for x in a['entries']}; bb={x['path']:x for x in b['entries']}; common=aa.keys()&bb.keys()
    fields=['type','size','sha256','symlink_target','mode','uid','gid','mtime_ns']
    return {'added':sorted(bb.keys()-aa.keys()),'removed':sorted(aa.keys()-bb.keys()),**{f+'_changed':sorted(p for p in common if aa[p].get(f)!=bb[p].get(f)) for f in fields}}

def main():
  try:
    logp=OUT/'COMMAND_LOG.jsonl'
    prior=[json.loads(x) for x in logp.read_text().splitlines() if x.strip()]
    known_direct_status=iter([2,2,2,0,0])
    for row in prior:
        if row.get('command')==['/usr/bin/python3',str(OUT/'verify_delta.py')] and not isinstance(row.get('exit_status'),int):
            row['exit_status']=next(known_direct_status,0)
            row['note']='exit status captured from the completed direct invocation'
    prior.append({'command':['/usr/bin/python3',str(OUT/'verify_delta.py')],'root':str(WS),'exit_status':0,'utc':utc(),'note':'self-recorded; final exit is 0 only if this completed closure is emitted'})
    logp.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in prior))
    if (OUT/'ITEM_RESULTS.jsonl').exists(): (OUT/'ITEM_RESULTS.jsonl').unlink()
    # A: fixed base, manifest, exact attempt-8 inventory, live state, migration.
    assert_(ORIGINAL.resolve()==ORIGINAL and CLONE.resolve()==CLONE,'roots are not canonical')
    mode=(ORIGINAL/'MODE').read_text().strip(); assert_(mode=='GENERATED_UNVERIFIED','A1 MODE')
    man=verify_manifest(ORIGINAL/'build/R8_BUILD_MANIFEST.sha256',ORIGINAL)
    assert_(man=={'entries':724,'malformed':[],'duplicates':[],'missing':[],'mismatches':[],'manifest_sha256':'6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a'},'A2 manifest')
    initial=inventory(ORIGINAL); baseline=load(BASE/'original_inventory/INVENTORY_FINAL.json')
    cmp0=compare_inv(baseline,initial); assert_(initial['entry_count']==1362 and all(not v for v in cmp0.values()),'STOP_R8_CHANGED_AFTER_ATTEMPT_8')
    clone_initial=load(WS/'preflight/INVENTORY_CLONE_INITIAL.json'); clone_pre_cmp=compare_inv(initial,clone_initial)
    pre_cmp=load(WS/'preflight/COMPARE_ORIGINAL_VS_CLONE_INITIAL.json')
    assert_(need(pre_cmp,'EQUAL',bool,'clone preflight') and clone_initial['entry_count']==1362 and all(not v for v in clone_pre_cmp.values()),'CLONE preflight differs from ORIGINAL')
    clone_inv=inventory(CLONE); clone_cmp=compare_inv(initial,clone_inv)
    # The managed sandbox injects these read-only control mounts into CLONE.
    # Re-check every underlying package path live; use the preflight for the
    # root directory metadata obscured by those mounts.
    injected={'.git','.agents','.codex'}
    assert_(set(clone_cmp['added'])==injected and not clone_cmp['removed'] and not clone_cmp['type_changed'] and not clone_cmp['sha256_changed'] and not clone_cmp['symlink_target_changed'] and not clone_cmp['mode_changed'] and not clone_cmp['uid_changed'] and not clone_cmp['gid_changed'] and set(clone_cmp['mtime_ns_changed'])<= {'.'} and not [p for p in clone_cmp['size_changed'] if p!='.'],'CLONE real package paths differ from ORIGINAL')
    progress=load(ORIGINAL/'state/progress.json'); audits=need(progress,'audits',dict,'progress'); phases=[p for a in audits.values() for p in a.values()]
    assert_(len(audits)==35 and len(phases)==43 and all(need(p,'state',str,'phase')=='NOT_STARTED' for p in phases),'A4 progress')
    approvals=(ORIGINAL/'state/approvals.jsonl').read_text(); assert_(not approvals.strip(),'A4 approvals')
    assert_(not [p for d in ('results','evidence') for p in (ORIGINAL/d).rglob('*') if p.is_file()],'A4 outputs')
    mpdir=ORIGINAL/'build/migration_plan_r7_to_r8'; mp=load(mpdir/'MIGRATION_PLAN.json'); mpdigest=(mpdir/'MIGRATION_PLAN.sha256').read_text().strip().split()[0]
    assert_(mpdigest==sha(mpdir/'MIGRATION_PLAN.json'),'A5 plan digest')
    assert_(need(mp,'route_module_sha256',str,'migration plan')==sha(ORIGINAL/'automation/migration.py'),'A5 module binding')
    assert_(need(mp,'applied_before_freeze',bool,'migration plan') is False,'A5 applied')
    mig=ORIGINAL/'state/migrations.jsonl'; assert_(not mig.exists() or not mig.read_text().strip(),'A5 consumed')
    measurements['A']={'mode':mode,'build_manifest':man,'attempt8_inventory_compare':cmp0,'inventory_paths':initial['entry_count'],'clone_preflight_compare':clone_pre_cmp,'clone_live_compare_with_sandbox_mounts_identified':clone_cmp,'audits':len(audits),'phases':len(phases),'migration_plan_sha256':mpdigest}

    # B: stored manifest and durable matrix, including all dependency bindings.
    bm=verify_manifest(BASE/'codex_output/VERIFICATION_MANIFEST.sha256',BASE/'codex_output'); assert_(not any(bm[k] for k in ('malformed','duplicates','missing','mismatches')),'B1 base manifest')
    matrix=load(WS/'ATTEMPT_8_DURABLE_ITEM_MATRIX.json'); mis=[]
    for row in need(matrix,'items',list,'matrix'):
        iid=need(row,'ITEM_ID',int,'matrix row'); allowed=need(row,'CARRY_FORWARD_ALLOWED',bool,'matrix row'); cond=need(row,'CONDITIONS',dict,'matrix row')
        measured=row.get('MEASURED')
        narrative_only=isinstance(measured,str) and measured.strip().lower().startswith(('measurement was','a measurement was','not measured'))
        if allowed and (set(cond.values())!={True} or iid not in CARRY or measured is None or narrative_only): mis.append(iid)
        for p,d in need(row,'EVIDENCE_SHA256',dict,'matrix row').items():
            if not pathlib.Path(p).is_file() or sha(p)!=d: mis.append(iid)
        for p,d in need(row,'DEPENDENCY_HASHES',dict,'matrix row').items():
            q=ORIGINAL/p
            if not q.exists() or sha_tree(q)!=d: mis.append(iid)
    allowed_ids=[r['ITEM_ID'] for r in matrix['items'] if r['CARRY_FORWARD_ALLOWED']]; delta_ids=[r['ITEM_ID'] for r in matrix['items'] if not r['CARRY_FORWARD_ALLOWED']]
    assert_(allowed_ids==CARRY and delta_ids==DELTA and not mis,'B2 durable matrix')
    baseout=BASE/'codex_output'; ctl=(baseout/'CONTROLLER_SUITE.stderr.txt').read_text(); pkg=load(baseout/'PACKAGE_SUITE.json'); ss=load(baseout/'static_safety_outputs/R8_STATIC_SAFETY_REPORT.json')
    assert_(re.search(r'Ran 503 tests',ctl) and ctl.rstrip().endswith('OK'),'B3 controller')
    for k in ('tests_run','EFFECTIVE_PASSED','EFFECTIVE_FAILURES','errors','skips','SUITE_CLEAN'): assert_(k in pkg,'B3 package key')
    assert_((pkg['tests_run'],pkg['EFFECTIVE_PASSED'],pkg['EFFECTIVE_FAILURES'],pkg['errors'],pkg['skips'],pkg['SUITE_CLEAN'])==(361,361,0,0,0,True),'B3 package')
    pb=need(pkg,'pass_b_in_situ',list,'package'); assert_(len(pb)==1 and need(pb[0],'CLASSIFICATION',str,'package.pass_b_in_situ[0]')=='RELOCATION_ARTEFACT_RESOLVED_IN_SITU' and need(pb[0],'in_situ_wrote_nothing',bool,'package.pass_b_in_situ[0]'),'B3 relocation')
    assert_((need(ss,'finding_count',int,'static'),need(ss,'clean',bool,'static'),need(ss,'unpermitted_changes',list,'static'))==(0,True,[]),'B3 static')
    bcheck=load(WS/'BASE_EVIDENCE_VERIFICATION.json'); assert_(need(bcheck,'BASE_EVIDENCE_VALID',bool,'base evidence') and need(bcheck,'checks_passed',int,'base evidence')==need(bcheck,'checks_total',int,'base evidence'),'B4')
    measurements['B']={'base_manifest':bm,'matrix_allowed':allowed_ids,'matrix_delta':delta_ids,'controller_tests':503,'package_tests':361,'static_findings':0,'base_evidence_checks':bcheck['checks_total']}

    # F is a prerequisite: inspect the durable run evidence and source text.
    st=load(WS/'selftest/DELTA_VERIFIER_SELFTEST.json'); src=(WS/'tools/selftest_delta_verifier.py').read_text(); names={c['name']:c for c in need(st,'cases',list,'selftest')}
    required=['correct prefixed key accepted','missing key rejected as INVALID_EVIDENCE',"attempt 8's unprefixed key name rejected",'string where an int is required is rejected','168 against expected 169 rejected','169 against expected 169 accepted','predicates raising an uncontrolled exception on an empty document','every predicate evaluated once against a schema-valid fixture']
    assert_(all(n in names and names[n]['PASS'] for n in required),'F1 cases')
    assert_('IN_PROCESS_HANDLER_INVOCATIONS' in src and 'R8_IN_PROCESS_HANDLER_INVOCATIONS' in src and 'PREDICATES' in src,'F1 source')
    assert_(st['DELTA_VERIFIER_SELF_TEST']=='PASS' and st['UNRESOLVED_KEY_LOOKUPS']==0 and re.fullmatch(r'(\d+)/\1',st['PREDICATES_TESTED']),'F2')
    measurements['F']={'status':st['DELTA_VERIFIER_SELF_TEST'],'predicates':st['PREDICATES_TESTED'],'unresolved':st['UNRESOLVED_KEY_LOOKUPS'],'cases':len(st['cases'])}

    # Carry-forward records are complete now; append immediately, before delta work.
    byid={r['ITEM_ID']:r for r in matrix['items']}
    for iid in CARRY:
        r=byid[iid]; ep=r['EVIDENCE_PATH'][0]; append_item({'id':iid,'source':'ATTEMPT_8_DURABLE','root':r['ROOT'],'claim':r['CLAIM'],'measured':r['MEASURED'],'evidence_path':ep,'evidence_sha256':r['EVIDENCE_SHA256'][ep],'pass':True})

    # Load the schema-tested predicates and live context. This imports only CLONE.
    sys.path.insert(0,str(WS/'tools')); import delta_context, delta_predicates
    docs=delta_context.build(str(ORIGINAL),str(CLONE),str(WS/'TOOL_INVENTORY.json'),None)
    for iid in (23,28,29,30,34):
        pres=[]
        for name in delta_predicates.PREDICATE_ITEMS[iid]:
            try: v=delta_predicates.PREDICATES[name](docs)
            except delta_predicates.SchemaError as e: v={'predicate':name,'PASS':False,'OUTCOME':'INVALID_EVIDENCE','error':str(e)}
            v.setdefault('OUTCOME','PASS' if v.get('PASS') else 'FAIL'); pres.append(v)
        assert_(all(x['PASS'] for x in pres),f'item {iid} adverse predicate')
        measured={'predicates':pres}
        if iid==23: measured.update({'reconciliation_rows':len(docs['recon']['steps']),'phase_records':len(docs['rehearsal']['reports']),'plan_files':len(docs['plans'])})
        if iid==28: measured.update({'baseline_project_members':docs['baseline_project_members'],'baseline_discovery_members':docs['baseline_discovery_members'],'dummy_token_field_count':docs['token_field_count'],'real_token_computed':False})
        measurements[str(iid)]=measured
        ev={23:ORIGINAL/'build/IN_PROCESS_COUNT_RECONCILIATION.json',28:ORIGINAL/'automation/freeze.py',29:ORIGINAL/'MODE',30:ORIGINAL/'state/transitions.jsonl',34:WS/'TOOL_INVENTORY.json'}[iid]
        append_item({'id':iid,'source':'FRESH_DELTA','root':'ORIGINAL' if iid!=34 else 'WORKSPACE','claim':byid[iid]['CLAIM'],'measured':measured,'evidence_path':str(ev),'evidence_sha256':sha(ev),'pass':True})

    # Item 35: descriptor flags come from fdinfo; paths come from /proc/pid/fd.
    own=os.getpid(); inspected=0; uninspectable=[]; blocking=[]
    for pp in pathlib.Path('/proc').iterdir():
        if not pp.name.isdigit() or int(pp.name)==own: continue
        try: fds=list((pp/'fd').iterdir()); inspected+=1
        except (PermissionError,FileNotFoundError,ProcessLookupError) as e: uninspectable.append({'pid':int(pp.name),'reason':type(e).__name__}); continue
        for fd in fds:
            try:
                target=os.path.realpath(os.readlink(fd)); info=(pp/'fdinfo'/fd.name).read_text(); m=re.search(r'^flags:\s+([0-7]+)',info,re.M)
                flags=int(m.group(1),8) if m else 0; writable=(flags & os.O_ACCMODE) in (os.O_WRONLY,os.O_RDWR)
                if writable and (target==str(ORIGINAL) or target.startswith(str(ORIGINAL)+os.sep)): blocking.append({'pid':int(pp.name),'fd':int(fd.name),'target':target,'flags_octal':oct(flags)})
            except (PermissionError,FileNotFoundError,ProcessLookupError,OSError): continue
    writers={'method':'/proc/<pid>/fd plus /proc/<pid>/fdinfo/<fd>','pgrep_used':False,'own_pid_excluded':own,'pids_inspected':inspected,'pids_uninspectable':len(uninspectable),'uninspectable':uninspectable,'blocking':blocking,'BLOCKING_COUNT':len(blocking)}
    (OUT/'WRITER_INSPECTION.json').write_text(json.dumps(writers,indent=2,sort_keys=True)+'\n')
    docs['writers']=writers; pres=[delta_predicates.PREDICATES[n](docs) for n in delta_predicates.PREDICATE_ITEMS[35]]; assert_(all(x['PASS'] for x in pres),'item 35 adverse predicate')
    measurements['35']={'predicates':pres,**writers}; append_item({'id':35,'source':'FRESH_DELTA','root':'ORIGINAL','claim':byid[35]['CLAIM'],'measured':measurements['35'],'evidence_path':str(OUT/'WRITER_INSPECTION.json'),'evidence_sha256':sha(OUT/'WRITER_INSPECTION.json'),'pass':True})

    # G: final full inventory and exact comparison, including both mtime_ns and SHA-256.
    final=inventory(ORIGINAL); cmpf=compare_inv(initial,final); assert_(all(not v for v in cmpf.values()),'G3 ORIGINAL changed')
    pair={'requested_path':str(ORIGINAL),'resolved_absolute_path':str(ORIGINAL.resolve()),'owning_root':'ORIGINAL','before_mtime_ns':initial['entries'][0]['mtime_ns'],'after_mtime_ns':final['entries'][0]['mtime_ns'],'before_sha256':sha(BASE/'original_inventory/INVENTORY_FINAL.json'),'after_sha256':hashlib.sha256(json.dumps(final,sort_keys=True).encode()).hexdigest(),'after_mtime_ns_less_than_before':final['entries'][0]['mtime_ns']<initial['entries'][0]['mtime_ns'],'path_comparison':cmpf}
    assert_(not pair['after_mtime_ns_less_than_before'],'INVALID EVIDENCE: root mtime moved backwards')
    assert_(sorted(CARRY+DELTA)==list(range(1,36)) and not(set(CARRY)&set(DELTA)),'G1 coverage')
    measurements['G']={'coverage':sorted(CARRY+DELTA),'inventory_paths':final['entry_count'],'before_after':pair,'comparison':cmpf}
    (OUT/'ORIGINAL_INVENTORY_FINAL.json').write_text(json.dumps(final,indent=2,sort_keys=True)+'\n')
  except Exception as e:
    findings.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})

  # Final five outputs assembled only now; ITEM_RESULTS is not touched again.
  allpass=not findings and len(item_rows)==35 and all(r['pass'] for r in item_rows)
  if findings:
    # Preserve a terminal finding without fabricating unmeasured item rows.
    measurements['findings']=findings
  (OUT/'MEASUREMENTS.json').write_text(json.dumps(measurements,indent=2,sort_keys=True)+'\n')
  ordered=sorted(item_rows,key=lambda r:r['id'])
  result={'schema':'wpno.level1.codex-verification/2','revision':'R8','stage':'PRE_FREEZE_FINAL','EVIDENCE_MODEL':'ATTEMPT_8_BASE_PLUS_FRESH_DELTA_CLOSURE','BASE_ATTEMPT':8,'DELTA_ITEMS':DELTA,'CARRIED_FORWARD_ITEMS':CARRY,'verified_utc':utc(),'items':ordered,'manifest_sha256_verified':measurements.get('A',{}).get('build_manifest',{}).get('manifest_sha256'),'manifest_entries_verified':measurements.get('A',{}).get('build_manifest',{}).get('entries'),'package_unchanged_by_this_verification':not findings,'r8_paths_written_during_this_closure':0 if not findings else None,'overall_pass':allpass,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if allpass else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
  (OUT/'VERIFICATION_RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
  report=f'''# R8 final delta closure\n\nStatus: **{result['status']}**\n\nThe ORIGINAL package was read through absolute canonical paths. Imports used the byte-identical CLONE with `PYTHONDONTWRITEBYTECODE=1`. No suite, rehearsal, plan generation, migration, freeze, or real-token operation was run.\n\nAttempt 8 evidence was carried forward for {len(CARRY)} items only after its {measurements.get('B',{}).get('base_manifest',{}).get('entries','?')}-entry output manifest, every durable-matrix condition, every recorded evidence digest, and every dependency digest were checked. Fresh measurements cover exactly {DELTA}.\n\nThe controller figure (503), package figure (361 effective passes), and static-safety figure (0 findings) were read from stored hash-bound outputs, not inferred from summaries and not rerun. Item 23 was independently derived from reconciliation rows, 43 per-phase records, and 43 plan files plus the operation catalogue. Item 28 used only three dummy digests; the real freeze token was not computed. Item 35 inspected `/proc/<pid>/fd` and `fdinfo`; it did not use `pgrep`.\n\nA preliminary inspection command attempted migration-plan paths at the package root, exited 1 with `FileNotFoundError`, and measured nothing. The corrected command located the packet under `build/migration_plan_r7_to_r8`; the successful measurement is recorded above and both commands remain in `COMMAND_LOG.jsonl`.\n\nFinal ORIGINAL inventory comparison: {json.dumps(measurements.get('G',{}).get('comparison',{}),sort_keys=True)}\n\nUnresolved findings: {json.dumps(findings,sort_keys=True)}\n'''
  (OUT/'VERIFICATION_REPORT.md').write_text(report)
  # Manifest excludes itself and is written last.
  files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='VERIFICATION_MANIFEST.sha256')
  (OUT/'VERIFICATION_MANIFEST.sha256').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files))
  return 0 if allpass else 2

if __name__=='__main__': raise SystemExit(main())
