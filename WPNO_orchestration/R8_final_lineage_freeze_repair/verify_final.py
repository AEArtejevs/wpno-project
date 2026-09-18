#!/usr/bin/python3
import ast, datetime, hashlib, importlib.util, json, os, re, stat, subprocess, sys

WS=os.path.abspath(os.path.dirname(__file__)); OUT=os.path.join(WS,'codex_output')
O='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8'; C='/home/ubuntu/project/WPNO/.r8_lineage_verify_clone_702826'
ROOTS={f'R{i}':f'/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R{i}' for i in range(4,9)}
os.makedirs(OUT,exist_ok=True)
for n in os.listdir(OUT):
 p=os.path.join(OUT,n)
 if os.path.isfile(p): os.unlink(p)
open(os.path.join(OUT,'ITEM_RESULTS.jsonl'),'w').close(); open(os.path.join(OUT,'COMMAND_LOG.jsonl'),'w').close()
items=[]; findings=[]; measurements={}
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def load(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def emit(i,root,claim,m,ok):
 row={'id':i,'root':root,'claim':claim,'measured':m,'pass':bool(ok)}
 with open(os.path.join(OUT,'ITEM_RESULTS.jsonl'),'a') as f:f.write(json.dumps(row,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 items.append(row);measurements[i]=m
 if not ok:findings.append(f'{i}: {claim}: {m}')
def run(argv,cwd):
 st=now(); p=subprocess.run(argv,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); rec={'argv':argv,'cwd':cwd,'started_utc':st,'finished_utc':now(),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 with open(os.path.join(OUT,'COMMAND_LOG.jsonl'),'a') as f:f.write(json.dumps(rec,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 return rec
def suite(rec):
 s=rec['stdout']+'\n'+rec['stderr']; m=re.search(r'Ran (\d+) tests?',s); return {'tests_run':int(m.group(1)) if m else None,'failures':len(re.findall(r'^FAIL:',s,re.M)),'errors':len(re.findall(r'^ERROR:',s,re.M)),'skips':int((re.search(r'OK \(skipped=(\d+)\)',s) or [None,0])[1]),'returncode':rec['returncode']}
def files(root):
 for dp,dn,fn in os.walk(root,followlinks=False):
  dn.sort();fn.sort()
  for n in fn:yield os.path.relpath(os.path.join(dp,n),root)
def manifest(root,rel):
 rows=[];bad=[];dup=[];seen=set()
 with open(os.path.join(root,rel),encoding='utf-8') as f:
  for no,line in enumerate(f,1):
   m=re.fullmatch(r'([0-9a-f]{64})  (.+)\n?',line)
   if not m:bad.append(no);continue
   d,p=m.groups();dup += [p] if p in seen else [];seen.add(p);q=os.path.join(root,p);rows.append((p,d,sha(q) if os.path.isfile(q) else None))
 return rows,bad,dup

# Import only from clone.
sys.path.insert(0,C)
from automation import freeze, operation_catalog

rels=freeze.required_predecessor_lineage_artifacts(); detail=[]
for r in rels:
 s=os.lstat(os.path.join(O,r));detail.append({'path':r,'regular':stat.S_ISREG(s.st_mode),'symlink':stat.S_ISLNK(s.st_mode)})
emit('A1','ORIGINAL','declared compact lineage pair exists as regular non-symlink files',{'declared':list(rels),'kind':freeze.PACKAGE_LINEAGE_MODEL.get('kind'),'files':detail},rels==('lineage/R7_BASELINE_MANIFEST.json','lineage/R8_LINEAGE.sha256') and all(x['regular'] and not x['symlink'] for x in detail))
arts=freeze.lineage_artifacts(); bases=[x for x in arts if x.get('role')==freeze.LINEAGE_ROLE_PREDECESSOR_BASELINE]
emit('A2','ORIGINAL (automation imported from CLONE)','declared baseline is the path load_predecessor_baseline reads',{'declared':bases[0].get('rel') if len(bases)==1 else None,'constant':freeze.PREDECESSOR_BASELINE_REL},len(bases)==1 and bases[0].get('rel')==freeze.PREDECESSOR_BASELINE_REL)

# AST occurrence classification and archive inertness.
occ=[]; executable=[]
for rel in files(O):
 if not rel.endswith('.py'):continue
 p=os.path.join(O,rel); src=open(p,encoding='utf-8',errors='replace').read()
 if 'PREDECESSOR_BASELINE_REL.split' not in src:continue
 tree=ast.parse(src)
 for no,line in enumerate(src.splitlines(),1):
  if 'PREDECESSOR_BASELINE_REL.split' in line:occ.append({'path':rel,'line':no,'text':line.strip(),'classification':'text/comment pending AST'})
 for n in ast.walk(tree):
  seg=ast.get_source_segment(src,n) or ''
  if isinstance(n,ast.Assign) and 'PREDECESSOR_BASELINE_REL.split' in seg:
   target_names=[t.id for t in n.targets if isinstance(t,ast.Name)]
   cl='permitted_test_constant' if 'DEFECTIVE_DERIVATION' in target_names else ('archived_incident_evidence' if rel.startswith('lineage/') else 'live_executable')
   executable.append({'path':rel,'line':n.lineno,'classification':cl,'targets':target_names})
incroot=os.path.join(O,'lineage/R7_POST_FREEZE_INCIDENT'); ir,ib,idup=manifest(incroot,'INCIDENT_MANIFEST.sha256'); imap={p:(a,b) for p,a,b in ir}
arch=[x for x in executable if x['classification']=='archived_incident_evidence']; archived_ok=all(os.path.relpath(os.path.join(O,x['path']),incroot) in imap and imap[os.path.relpath(os.path.join(O,x['path']),incroot)][0]==imap[os.path.relpath(os.path.join(O,x['path']),incroot)][1] for x in arch) and not ib and not idup and all(a==b for _,a,b in ir)
loaders=[]
for top in ('automation','build'):
 for rel0 in files(os.path.join(O,top)):
  if not rel0.endswith('.py'):continue
  rel=f'{top}/{rel0}';src=open(os.path.join(O,rel),encoding='utf-8',errors='replace').read();tree=ast.parse(src)
  for n in ast.walk(tree):
   seg=ast.get_source_segment(src,n) or ''
   if isinstance(n,(ast.Call,ast.Assign,ast.AugAssign)) and re.search(r'(^|[\\/])lineage([\\/]|$)',seg) and ('sys.path' in seg or 'importlib' in seg or 'spec_from_file_location' in seg):loaders.append({'path':rel,'line':n.lineno,'segment':seg[:240]})
test_const=[x for x in executable if x['classification']=='permitted_test_constant'];live=[x for x in executable if x['classification']=='live_executable']
emit('A3','ORIGINAL','defective derivation has only the named test constant and inert archived incident occurrence',{'text_occurrences':occ,'executable_occurrences':executable,'incident_manifest_entries':len(ir),'incident_manifest_mismatches':sum(a!=b for _,a,b in ir),'archive_code_loaders':loaders,'self_test_read':sha(os.path.join(O,'automation/package_tests/test_r8_freeze_lineage.py'))},len(test_const)==1 and not live and bool(arch) and archived_ok and not loaders)
ctl=open(os.path.join(O,'automation/controller.py'),encoding='utf-8').read();tree=ast.parse(ctl);calls=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.get_source_segment(ctl,n)=='freeze.assert_lineage_bound(plan, root)']; arith=[n.lineno for n in ast.walk(tree) if 'PREDECESSOR_BASELINE_REL.split' in (ast.get_source_segment(ctl,n) or '') and not isinstance(n,ast.Expr)]
emit('A4','ORIGINAL','controller step 9 uses shared gate and no lineage path arithmetic',{'gate_call_lines':calls,'path_arithmetic_lines':arith},len(calls)==1 and not arith)
base={'rel':'lineage/base.json','role':freeze.LINEAGE_ROLE_PREDECESSOR_BASELINE,'why':'x'};att={'rel':'lineage/att.sha256','role':freeze.LINEAGE_ROLE_LINEAGE_ATTESTATION,'why':'x'};accepted=[]
for k in (freeze.LINEAGE_KIND_LEGACY_DIRECTORY,freeze.LINEAGE_KIND_COMPACT_FILE):accepted.append(bool(freeze.lineage_artifacts({'kind':k,'artifacts':(base,att)})))
badmodels=[{'kind':'UNKNOWN','artifacts':(base,att)},{'kind':freeze.LINEAGE_KIND_COMPACT_FILE,'artifacts':(dict(base,rel='/x'),att)},{'kind':freeze.LINEAGE_KIND_COMPACT_FILE,'artifacts':(dict(base,rel='../x'),att)},{'kind':freeze.LINEAGE_KIND_COMPACT_FILE,'artifacts':(att,)},{'kind':freeze.LINEAGE_KIND_COMPACT_FILE,'artifacts':(base,)}]; refused=[]
for m in badmodels:
 try:freeze.lineage_artifacts(m);refused.append(False)
 except freeze.FreezeError:refused.append(True)
emit('A5','CLONE_IMPORT','legacy and compact models work and malformed models fail',{'accepted':accepted,'refused':refused},all(accepted+refused))

src=open(os.path.join(O,'automation/package_tests/test_r8_freeze_lineage.py'),encoding='utf-8').read();rec=run(['/usr/bin/python3','-B','-m','unittest','automation.package_tests.test_r8_freeze_lineage'],C);sm=suite(rec)
emit('B1','CLONE','focused repaired-lineage regression suite',sm,sm=={'tests_run':43,'failures':0,'errors':0,'skips':0,'returncode':0})
actual='python3 -m automation.controller freeze-level1' in src
emit('B2','ORIGINAL source; CLONE execution','end-to-end test invokes actual controller command in disposable package',{'actual_command':actual,'disposable_fixture':'DisposableR8FreezeFixture' in src},actual and 'DisposableR8FreezeFixture' in src)
proofnames=['test_the_lineage_gate_was_reached_and_passed','test_mode_became_frozen','test_the_control_manifest_verifies_from_disk','test_the_manifest_mode_entry_matches_frozen','test_both_baselines_are_nonempty','test_the_verified_record_names_the_lineage_artefacts_it_required','test_the_token_was_consumed_exactly_once','test_replay_of_the_same_token_is_refused','test_no_audit_phase_was_started','test_the_original_r8_package_was_not_written']; proofs={x:x in src for x in proofnames}
emit('B3','ORIGINAL source; CLONE execution','end-to-end assertions cover all required freeze outcomes',{'assertions':proofs,'suite':sm},all(proofs.values()) and sm['returncode']==0)
emit('B4','ORIGINAL source; CLONE execution','old impossible filename binding is refused',{'old_path': 'lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256' in src,'error':'FREEZE_LINEAGE_UNBOUND' in src,'suite':sm},'lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256' in src and 'FREEZE_LINEAGE_UNBOUND' in src and sm['returncode']==0)
osrc=open(os.path.join(O,'automation/package_tests/test_freeze_order_regression.py'),encoding='utf-8').read();orec=run(['/usr/bin/python3','-B','-m','unittest','automation.package_tests.test_freeze_order_regression'],C);osm=suite(orec)
emit('B5','CLONE','freeze-order regression uses declared lineage paths',dict(osm,uses_declaration='freeze.required_predecessor_lineage_artifacts()' in osrc,defective_expression='PREDECESSOR_BASELINE_REL.split' in osrc),osm['returncode']==0 and 'freeze.required_predecessor_lineage_artifacts()' in osrc and 'PREDECESSOR_BASELINE_REL.split' not in osrc)
before={r:{'sha256':sha(os.path.join(O,r)),'mtime_ns':os.lstat(os.path.join(O,r)).st_mtime_ns} for r in rels}; ret=freeze.assert_lineage_bound({'bound_artifacts':{r:before[r]['sha256'] for r in rels}},O);after={r:{'sha256':sha(os.path.join(O,r)),'mtime_ns':os.lstat(os.path.join(O,r)).st_mtime_ns} for r in rels}
emit('B6','ORIGINAL dry read; automation imported from CLONE','real lineage binding passes without writes',{'returned':list(ret),'before':before,'after':after},tuple(ret)==rels and before==after)

c1=run(['/usr/bin/python3','-B','-m','unittest','discover','-s','.','-t','.'],os.path.join(C,'verification/selftest_runtime'));m1=suite(c1);emit('C1','CLONE','controller/unit suite',m1,m1=={'tests_run':503,'failures':0,'errors':0,'skips':0,'returncode':0})
c2=run(['/usr/bin/python3','-B','-m','unittest','discover','-s','automation/package_tests','-t','.'],C);m2=suite(c2);newtests=sm['tests_run'];emit('C2','CLONE','package suite and lineage regression count',dict(m2,lineage_module_tests=newtests,prior_count=361,count_delta=(m2['tests_run'] or 0)-361),m2=={'tests_run':405,'failures':0,'errors':0,'skips':0,'returncode':0} and newtests==43 and m2['tests_run']-361==44)
sd=os.path.join(C,'logs/verify_static');c3=run(['/usr/bin/python3','-B','build/r8_static_safety_review.py','--out-dir',sd],C);generated=load(os.path.join(sd,'R8_STATIC_SAFETY_REPORT.json'));recorded=load(os.path.join(O,'build/R8_STATIC_SAFETY_REPORT.json'));diff=[k for k in sorted(set(generated)|set(recorded)) if k not in ('package_root','reviewed_at_utc') and generated.get(k)!=recorded.get(k)]
emit('C3','CLONE execution; ORIGINAL comparison','static safety clean and matches recorded report',{'returncode':c3['returncode'],'finding_count':generated.get('finding_count'),'clean':generated.get('clean'),'differing_fields':diff},c3['returncode']==0 and generated.get('clean') is True and generated.get('finding_count')==0 and not diff)
mr,mb,md=manifest(O,'build/R8_BUILD_MANIFEST.sha256'); listed={p for p,_,_ in mr}; spec=importlib.util.spec_from_file_location('builder',os.path.join(C,'build/build_r8_build_manifest.py'));builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder);physical={r for r in files(O) if builder.in_scope(r)};mdig=sha(os.path.join(O,'build/R8_BUILD_MANIFEST.sha256'))
emit('C4','ORIGINAL','build manifest verifies and exactly covers builder scope',{'manifest_sha256':mdig,'entries':len(mr),'malformed':mb,'duplicates':md,'mismatches':[p for p,a,b in mr if a!=b],'missing_from_manifest':sorted(physical-listed),'extra_in_manifest':sorted(listed-physical)},mdig=='f7e181a21c902a401c55cd9f97d50c55711fbcef6c5fdf16845ab94bc8db95bb' and len(mr)==728 and not mb and not md and all(a==b for _,a,b in mr) and listed==physical)
tr=load(os.path.join(O,'build/R8_TEST_SUITE_RESULTS.json')); named=[]
def walkdig(x):
 if isinstance(x,dict):
  if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):named.append((x['path'],x['sha256']))
  for v in x.values():walkdig(v)
 elif isinstance(x,list):
  for v in x:walkdig(v)
walkdig(tr);badnamed=[(p,d) for p,d in named if not os.path.isfile(os.path.join(O,p)) or sha(os.path.join(O,p))!=d]
emit('C5','ORIGINAL','recorded suite results and named test digests match disk',{'controller':tr.get('suites',{}).get('controller_suite'),'package':tr.get('suites',{}).get('package_suite'),'named_digest_count':len(named),'bad_named_digests':badnamed},tr.get('all_clean') is True and tr.get('suites',{}).get('controller_suite',{}).get('ran')==503 and tr.get('suites',{}).get('package_suite',{}).get('ran')==405 and not badnamed)
cl=load(os.path.join(O,'build/R8_FINAL_PRE_FREEZE_CLOSURE.json')); emit('C6','ORIGINAL','closure records refusal, defect, repair, regression, and no live execution',{'has_refusal':'refused_freeze_attempt_2' in cl,'defect_keys':sorted(cl.get('lineage_binding_defect',{})),'live_execution':cl.get('live_execution')},'refused_freeze_attempt_2' in cl and all(k in cl.get('lineage_binding_defect',{}) for k in ('what_it_was','repair','regression')) and isinstance(cl.get('live_execution'),str) and cl['live_execution'].startswith('None.'))

cov=load(os.path.join(O,'build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json')); plans=[]
for r in files(os.path.join(O,'build/candidate_plans_r8')):
 if r.endswith('/plan.json'):plans.append(load(os.path.join(O,'build/candidate_plans_r8',r)))
emit('D1','ORIGINAL','43 plans with complete unique known coverage',{'physical_plans':len(plans),'reported':{k:cov.get(k) for k in ('REQUIRED_PLAN_COUNT','CANDIDATE_PLAN_COUNT','MISSING_PLAN_COUNT','DUPLICATE_PLAN_COUNT','UNKNOWN_PLAN_COUNT')}},len(plans)==43 and [cov.get(k) for k in ('REQUIRED_PLAN_COUNT','CANDIDATE_PLAN_COUNT','MISSING_PLAN_COUNT','DUPLICATE_PLAN_COUNT','UNKNOWN_PLAN_COUNT')]==[43,43,0,0,0])
rep=load(os.path.join(O,'work/_rehearsal_r8/REHEARSAL_REPORT.json'));emit('D2','ORIGINAL','rehearsal reports 43/43 PASS_READY',{'required':rep.get('phases_required'),'rehearsed':rep.get('phases_rehearsed'),'all_pass_ready':rep.get('all_pass_ready'),'records':len(rep.get('reports',[])),'non_pass_ready':[r.get('status') for r in rep.get('reports',[]) if r.get('status')!='PASS_READY']},rep.get('phases_required')==rep.get('phases_rehearsed')==43 and len(rep.get('reports',[]))==43 and rep.get('all_pass_ready') is True)
ipr=load(os.path.join(O,'build/IN_PROCESS_COUNT_RECONCILIATION.json')); rows=ipr.get('steps',[]); rowcount=sum(1 for x in rows if x.get('operation') in operation_catalog.IN_PROCESS); planrows=[s for p in plans for s in p.get('steps',[])]; plancount=sum(1 for s in planrows if s.get('operation') in operation_catalog.IN_PROCESS)
emit('D3','ORIGINAL','in-process counts rederive from 311 rows and 43 plans',{'record_rows':len(rows),'row_derived':rowcount,'plan_steps':len(planrows),'plan_derived':plancount,'recorded':ipr.get('R8_IN_PROCESS_HANDLER_INVOCATIONS'),'unique':ipr.get('R8_UNIQUE_IN_PROCESS_PLAN_STEPS'),'rehearsal_invocations':rep.get('IN_PROCESS_HANDLER_INVOCATIONS'),'rehearsal_steps':rep.get('IN_PROCESS_STEP_COUNT'),'note_only':rep.get('NOTE_ONLY_IN_PROCESS_STEPS'),'without_evidence':rep.get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE'),'hollow':rep.get('HOLLOW_PHASES')},len(rows)==311 and rowcount==plancount==ipr.get('R8_IN_PROCESS_HANDLER_INVOCATIONS')==ipr.get('R8_UNIQUE_IN_PROCESS_PLAN_STEPS')==rep.get('IN_PROCESS_HANDLER_INVOCATIONS')==rep.get('IN_PROCESS_STEP_COUNT')==169 and rep.get('NOTE_ONLY_IN_PROCESS_STEPS')==rep.get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE')==0 and rep.get('HOLLOW_PHASES')==[])
anch=re.compile(r'(^|[\\/])automation[\\/](controller|freeze)\.py$'); refs=[]
def scanref(x,loc):
 if isinstance(x,str) and anch.search(x):refs.append((loc,x))
 elif isinstance(x,dict):
  for k,v in x.items():scanref(v,loc+'/'+str(k))
 elif isinstance(x,list):
  for j,v in enumerate(x):scanref(v,loc+'/'+str(j))
for j,p in enumerate(plans):scanref(p,f'plan{j}')
scanref(rep,'rehearsal'); rsrc=open(os.path.join(O,'build/rehearse_candidate_plans.py'),encoding='utf-8').read();branch=[n.lineno for n in ast.walk(ast.parse(rsrc)) if isinstance(n,(ast.If,ast.Match)) and 'freeze' in (ast.get_source_segment(rsrc,n) or '').lower()]
emit('D4','ORIGINAL','plans/rehearsal do not bind repaired files and rehearser has no freeze branch',{'anchored_references':refs,'freeze_branch_lines':branch},not refs and not branch)
cc=load(os.path.join(O,'build/CONTROL_EXPECTATION_COVERAGE.json'));roles={'POSITIVE','NEGATIVE','MUTATION','ORACLE','SABOTAGE'};controls=[s for s in planrows if s.get('control_role') in roles];machine=[s for s in controls if s.get('expectation') or s.get('expected') or s.get('expected_outcome') or s.get('expected_result')]; emit('D5','ORIGINAL','control expectations are fully machine-checkable',{'derived_control_steps':len(controls),'recorded_count':cc.get('CONTROL_ROLE_STEP_COUNT'),'recorded_ratio':cc.get('CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION'),'unenforced':cc.get('CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION'),'simple_derived_expectation_fields':len(machine)},len(controls)==cc.get('CONTROL_ROLE_STEP_COUNT')==122 and cc.get('CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION')=='122/122' and cc.get('CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION')==0)
outside=[(r.get('audit_id'),r.get('run_phase'),s.get('step_id')) for r in rep.get('reports',[]) for s in r.get('steps',[]) if s.get('reads_outside_declared_allowance')];emit('D6','ORIGINAL','no rehearsal step read outside declared allowance',{'nonempty_steps':outside},not outside)
mig=load(os.path.join(O,'build/migration_plan_r7_to_r8/MIGRATION_PLAN.json')); ma=[(x.get('audit_id'),x.get('run_phase')) for x in mig.get('migratable_attempts',[])]; ex=[(x.get('audit_id'),x.get('run_phase'),x.get('reason')) for x in mig.get('excluded_attempts',[])];ml=os.path.join(O,'state/migrations.jsonl');msize=os.path.getsize(ml) if os.path.exists(ml) else 0
emit('D7','ORIGINAL','migration packet has exact attempts, exclusion, route digest, and is unapplied',{'migratable':ma,'excluded':ex,'applied_before_freeze':mig.get('applied_before_freeze'),'route_digest':mig.get('route_module_sha256'),'disk_route_digest':sha(os.path.join(O,'automation/migration.py')),'migration_ledger_size':msize},ma==[('L1-A31','RUN-A'),('L1-A31','RUN-B')] and ex==[('L1-A31','COMPARISON','EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT')] and mig.get('applied_before_freeze') is False and mig.get('route_module_sha256')==sha(os.path.join(O,'automation/migration.py')) and msize==0)

for iid,rev,expect in [('E1','R4',0),('E2','R5',1),('E3','R6',0),('E4','R7',0)]:
 rr,bb,dd=manifest(ROOTS[rev],'CONTROL_MANIFEST.sha256');mm=[p for p,a,b in rr if a!=b];ok=len(mm)==expect and (rev!='R5' or mm==['MODE']) and not bb and not dd and (rev!='R7' or len(rr)==15804);emit(iid,rev,'predecessor control manifest verification',{'entries':len(rr),'mismatches':mm,'malformed':bb,'duplicates':dd},ok)
lin=load(os.path.join(O,'lineage/R8_LINEAGE.json'));contr=[]
for r in files(O):
 if r.startswith('lineage/R7_POST_FREEZE_INCIDENT/'):continue
 p=os.path.join(O,r)
 try:t=open(p,encoding='utf-8').read().lower()
 except (UnicodeDecodeError,OSError):continue
 if re.search(r'r7.{0,80}(was |remained )?continuously immutable',t) and not re.search(r'(not continuously|continuous_post_freeze_immutability.{0,10}false)',t):contr.append(r)
emit('E5','ORIGINAL','incident verifies and lineage truthfully records broken continuity and restored bytes',{'incident_entries':len(ir),'incident_mismatches':sum(a!=b for _,a,b in ir),'continuous':lin.get('r7',{}).get('continuous_post_freeze_immutability'),'restored':lin.get('r7',{}).get('current_bytes_restored_to_frozen_manifest'),'contrary_claims':contr},all(a==b for _,a,b in ir) and not ib and not idup and lin.get('r7',{}).get('continuous_post_freeze_immutability') is False and lin.get('r7',{}).get('current_bytes_restored_to_frozen_manifest') is True and not contr)
full=[]
for dp,dn,fn in os.walk(os.path.join(O,'lineage')):
 if 'CONTROL_MANIFEST.sha256' in fn or 'state' in dn and os.path.isfile(os.path.join(dp,'state/REVISION.json')):full.append(os.path.relpath(dp,O))
r7map={(os.stat(os.path.join(ROOTS['R7'],r)).st_dev,os.stat(os.path.join(ROOTS['R7'],r)).st_ino) for r in files(ROOTS['R7'])}; shared=[r for r in files(O) if not r.startswith('lineage/') and (os.stat(os.path.join(O,r)).st_dev,os.stat(os.path.join(O,r)).st_ino) in r7map]
emit('E6','ORIGINAL+R7','no full predecessor copy and no active inode sharing',{'package_like_lineage_dirs':full,'shared_active_inodes':shared},not full and not shared)
prog=load(os.path.join(O,'state/progress.json'));aud=prog.get('audits',{});ph=[v for a in aud.values() for v in a.values() if isinstance(v,dict) and 'state' in v];emit('E7','ORIGINAL','all 35 audits and 43 phases are NOT_STARTED',{'audits':len(aud),'phases':len(ph),'states':sorted({x.get('state') for x in ph})},len(aud)==35 and len(ph)==43 and all(x.get('state')=='NOT_STARTED' for x in ph))
ap=os.path.getsize(os.path.join(O,'state/approvals.jsonl'));rf=list(files(os.path.join(O,'results')));ef=list(files(os.path.join(O,'evidence')));fa=os.path.join(O,'state/freeze_attempts.jsonl');mode=open(os.path.join(O,'MODE')).read().strip();emit('E8','ORIGINAL','live state is pristine generated-unverified',{'approvals_bytes':ap,'result_files':rf,'evidence_files':ef,'freeze_attempts_exists':os.path.exists(fa),'mode':mode},ap==0 and not rf and not ef and not os.path.exists(fa) and mode=='GENERATED_UNVERIFIED')
trs=[json.loads(x) for x in open(os.path.join(O,'state/transitions.jsonl')) if x.strip()];emit('E9','ORIGINAL','exactly one init-revision transition',{'rows':len(trs),'routes':[x.get('route') for x in trs]},len(trs)==1 and trs[0].get('route')=='init-revision')
r9=os.path.join(os.path.dirname(O),'08.18.26_Level1_Audits_R9');emit('E10','ORIGINAL parent read','no R9 sibling exists',{'path':r9,'exists':os.path.exists(r9)},not os.path.exists(r9))

# F checks before final isolation inventory.
ti=load(os.path.join(WS,'TOOL_INVENTORY.json'));trows=ti.get('tools',ti.get('rows',[]));badtools=[]
for x in trows:
 p=x.get('path') or x.get('file');d=x.get('sha256')
 if p and p!='NOT_USED':
  q=p if os.path.isabs(p) else os.path.join(WS,p)
  if not os.path.isfile(q) or (d and sha(q)!=d):badtools.append({'path':p,'exists':os.path.isfile(q),'expected':d,'actual':sha(q) if os.path.isfile(q) else None})
labels=json.dumps(ti).lower();result_mislabeled=any(('verification_result.json' in str(x.get('path','')).lower() and 'verifier' in str(x.get('role','')).lower()) for x in trows)
emit('F1','WORKSPACE+ORIGINAL','tool inventory is complete, identified, hash-correct, and does not call result a verifier',{'rows':len(trows),'unidentified':ti.get('UNIDENTIFIED_TOOLS'),'bad_rows':badtools,'result_mislabeled':result_mislabeled,'categories_present':{x:(x in labels) for x in ('instructions','runner','schema','freeze.py','token')}},ti.get('UNIDENTIFIED_TOOLS')==0 and not badtools and not result_mislabeled and all(x in labels for x in ('instructions','runner','schema','freeze.py','token')))
b=freeze.build_baseline_from_predecessor(C); dummy=('0'*64,'1'*64,'a'*64);tok=freeze.token_for(*dummy);parsed=freeze.parse_freeze_token(tok);emit('F2','CLONE','freeze can build baselines and dummy token round-trips',{'revision':freeze.PACKAGE_REVISION,'platform':freeze.PACKAGE_PLATFORM,'baseline_member_counts':[len(x.get('members',x)) if hasattr(x,'get') else len(x) for x in b],'dummy_roundtrip':parsed==dummy},freeze.PACKAGE_REVISION=='R8' and freeze.PACKAGE_PLATFORM=='UBUNTU' and all((len(x.get('members',x)) if hasattr(x,'get') else len(x))>0 for x in b) and parsed==dummy)

# /proc writer inspection.
wr=run(['/usr/bin/python3','-B','tools/inspect_writers.py',O,os.path.join(OUT,'WRITER_INSPECTION_POST.json')],WS);wd=load(os.path.join(OUT,'WRITER_INSPECTION_POST.json'));emit('E12','ORIGINAL via /proc','no other writable descriptor below ORIGINAL',{'pids_inspected':wd.get('pids_with_readable_fd_table'),'pids_uninspectable':wd.get('pids_with_unreadable_fd_table'),'uninspectable_reason':wd.get('unreadable_pids_by_uid'),'blocking_writable_descriptors':wd.get('BLOCKING_COUNT'),'pgrep_used':False},wd.get('BLOCKING_COUNT')==0)
# Full final inventory and compare to launcher-created pre-inventory.
run(['/usr/bin/python3','-B','tools/inventory_r8.py',O,os.path.join(OUT,'INVENTORY_POST.json')],WS);run(['/usr/bin/python3','-B','tools/compare_inventories.py',os.path.join(WS,'inventory/INVENTORY_PRE.json'),os.path.join(OUT,'INVENTORY_POST.json'),os.path.join(OUT,'INVENTORY_COMPARE.json')],WS);cmp=load(os.path.join(OUT,'INVENTORY_COMPARE.json'));iso={k:cmp.get(k) for k in ('written_paths','mtimes_changed','modes_changed','symlink_targets_changed','contents_changed','paths_added','paths_removed')};emit('E11','ORIGINAL','full pre/post metadata and byte inventory is unchanged',iso,all(v==0 for v in iso.values()))

# Assemble only from durable JSONL.
items=[json.loads(x) for x in open(os.path.join(OUT,'ITEM_RESULTS.jsonl')) if x.strip()];findings=[f"{x['id']}: {x['claim']}" for x in items if not x['pass']]
result={'schema':'wpno.level1.codex-verification/3','revision':'R8','stage':'PRE_FREEZE_FINAL_AFTER_LINEAGE_REPAIR','verified_utc':now(),'items':items,'manifest_sha256_verified':mdig,'manifest_entries_verified':len(mr),'lineage_defect_resolved':next(x for x in items if x['id']=='A3')['pass'],'old_defective_derivation_present':bool(live),'exact_cmd_freeze_level1_regression':'PASS' if all(next(x for x in items if x['id']==i)['pass'] for i in ('B1','B2','B3','B4')) else 'FAIL','disposable_clone_freeze':'PASS' if next(x for x in items if x['id']=='B3')['pass'] else 'FAIL','package_unchanged_by_this_verification':next(x for x in items if x['id']=='E11')['pass'],'r8_paths_written_during_this_verification':cmp.get('written_paths'),'overall_pass':not findings,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if not findings else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
with open(os.path.join(OUT,'VERIFICATION_RESULT.json'),'w') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
with open(os.path.join(OUT,'MEASUREMENTS.json'),'w') as f:json.dump({'schema':'wpno.level1.codex-measurements/1','items':{x['id']:x['measured'] for x in items}},f,indent=2,sort_keys=True);f.write('\n')
with open(os.path.join(OUT,'VERIFICATION_REPORT.md'),'w') as f:
 f.write('# R8 final independent pre-freeze verification\n\n');f.write(f"Status: **{result['status']}**\n\n")
 for x in items:f.write(f"- {x['id']} — {'PASS' if x['pass'] else 'FAIL'} — root: {x['root']} — {x['claim']}\n")
 if findings:f.write('\n## Unresolved findings\n\n'+''.join(f'- {x}\n' for x in findings))
names=sorted(n for n in os.listdir(OUT) if os.path.isfile(os.path.join(OUT,n)) and n!='VERIFICATION_MANIFEST.sha256')
with open(os.path.join(OUT,'VERIFICATION_MANIFEST.sha256'),'w') as f:
 for n in names:f.write(f'{sha(os.path.join(OUT,n))}  {n}\n')
print(json.dumps({'status':result['status'],'items':len(items),'failures':findings},indent=2))
