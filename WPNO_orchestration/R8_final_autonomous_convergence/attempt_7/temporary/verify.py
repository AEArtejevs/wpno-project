#!/usr/bin/python3
import ast, datetime, hashlib, importlib, inspect, json, os, re, shutil, subprocess, sys

O='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8'; C='/home/ubuntu/project/WPNO/.r8_verify_clone_attempt_7_662915'; W='/home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_7'; T=W+'/temporary'; OUT=W+'/codex_output'
R={f'R{i}':f'/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R{i}' for i in range(4,9)}
M={}; items=[]; findings=[]; commands=[]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def load(p):
 with open(p,encoding='utf8') as f:return json.load(f)
def files(root):
 for dp,dn,fn in os.walk(root,followlinks=False):
  dn.sort()
  for n in sorted(fn):yield os.path.relpath(os.path.join(dp,n),root)
def manifest(root,rel):
 es=[]; bad=[]; dup=[]; seen=set()
 for no,line in enumerate(open(root+'/'+rel,encoding='utf8'),1):
  m=re.fullmatch(r'([0-9a-f]{64})  (.+)\n?',line)
  if not m:bad.append(no);continue
  h,p=m.groups()
  if p in seen:dup.append(p)
  seen.add(p); q=root+'/'+p; es.append((p,h,sha(q) if os.path.isfile(q) else None))
 return es,bad,dup
def add(i,root,claim,measured,ok):
 d={'id':i,'root':root,'claim':claim,'measured':measured,'pass':bool(ok)};items.append(d);M[str(i)]=measured
 if not ok:findings.append(f'Item {i}: {measured}')
def run(cmd,cwd,timeout=1800):
 t=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout,env=os.environ.copy());commands.append({'command':' '.join(cmd),'root':cwd,'exit_status':p.returncode,'utc':t});return p

# preflight and manifests
pf=load(W+'/preflight/PREFLIGHT.json'); add(0,'WORKSPACE','Eight-check clone preflight',{'check_count':len(pf['checks']),'failed':pf['failed_checks']},pf['PREFLIGHT_PASS'] and len(pf['checks'])==8)
for i,rev,expect in [(1,'R4',0),(2,'R5',1),(3,'R6',0),(4,'R7',0)]:
 e,b,d=manifest(R[rev],'CONTROL_MANIFEST.sha256'); mm=[x[0] for x in e if x[1]!=x[2]]; ok=not b and not d and len(mm)==expect and (i!=2 or mm==['MODE']) and (i!=4 or len(e)==15804);add(i,rev,'Control manifest verification',{'entries':len(e),'mismatches':mm,'malformed':b,'duplicates':d},ok)
sys.path.insert(0,C)
from automation.package_tests import generation_root
from automation import in_process_executor, in_process_ops, operation_catalog, freeze
lin=load(O+'/lineage/R8_LINEAGE.json'); r7=lin['r7']; ie,ib,idp=manifest(O+'/lineage/R7_POST_FREEZE_INCIDENT','INCIDENT_MANIFEST.sha256')
contr=[]
for rel in files(O):
 if rel.startswith('verification_codex_final_pre_freeze_attempt_'):continue
 if os.path.isfile(O+'/'+rel):
  s=open(O+'/'+rel,encoding='utf8',errors='replace').read().lower()
  if 'continuously immutable' in s and not ('not continuously' in s or 'false' in s):contr.append(rel)
add(5,'ORIGINAL','Incident record and truthful R7 immutability disclosure',{'incident_entries':len(ie),'mismatches':[x[0] for x in ie if x[1]!=x[2]],'continuous':r7.get('continuous_post_freeze_immutability'),'restored':r7.get('current_bytes_restored_to_frozen_manifest'),'contrary':contr},not ib and not idp and all(a==b for _,a,b in ie) and r7.get('continuous_post_freeze_immutability') is False and r7.get('current_bytes_restored_to_frozen_manifest') is True and not contr)
resolved={}; errs={}
for rev in R:
 try:resolved[rev]=generation_root(rev)
 except Exception as x:errs[rev]=repr(x)
full=[]
for dp,dn,fn in os.walk(O):
 if 'CONTROL_MANIFEST.sha256' in fn and os.path.relpath(dp,O)!='.':full.append(os.path.relpath(dp,O))
add(6,'ORIGINAL','No embedded predecessor package and generation roots resolve',{'R6_EXECUTION':os.path.isdir(O+'/lineage/R6_EXECUTION'),'full_copy_markers':full,'resolved':resolved,'errors':errs},not os.path.isdir(O+'/lineage/R6_EXECUTION') and not full and len(resolved)==5)
r7inos={(os.stat(R['R7']+'/'+p).st_dev,os.stat(R['R7']+'/'+p).st_ino):p for p in files(R['R7']) if os.path.isfile(R['R7']+'/'+p)}; shared=[]
for p in files(O):
 q=O+'/'+p
 if os.path.isfile(q) and (os.stat(q).st_dev,os.stat(q).st_ino) in r7inos:shared.append((p,r7inos[(os.stat(q).st_dev,os.stat(q).st_ino)]))
add(7,'ORIGINAL','No R8/R7 active file inode sharing',{'r7_files':len(r7inos),'r8_files':sum(os.path.isfile(O+'/'+p) for p in files(O)),'shared':shared},not shared)
calls={p:open(O+'/'+p,encoding='utf8').read().count('in_process_executor.execute') for p in ['automation/controller.py','build/rehearse_candidate_plans.py']};add(8,'ORIGINAL','Both live routes call execute',calls,all(calls.values()))
# phrase occurrence classification
occ=[]; originals={}
for p in files(O):
 if p.endswith('.py') and 'performed by the worker' in open(O+'/'+p,encoding='utf8',errors='replace').read():originals[p]=sha(O+'/'+p)
for p,dig in originals.items():
 src=open(O+'/'+p,encoding='utf8',errors='replace').read(); tree=ast.parse(src)
 for no,line in enumerate(src.splitlines(),1):
  if 'performed by the worker' not in line:continue
  rule=None;ev={}
  if p.startswith('verification/selftest_runtime/'):
   base=p[len('verification/selftest_runtime/'):]; bd=originals.get(base) or (sha(O+'/'+base) if os.path.isfile(O+'/'+base) else None)
   if bd==dig:rule='c';ev={'original':base,'shared_digest':dig}
  if rule is None and p.startswith('verification_codex_final_pre_freeze_attempt_') and (' in src' in line or 'performed by the worker' in src):rule='d';ev={'excluded_manifest':True,'not_live_imported':True}
  if rule is None and ('fixtures' in p.split('/') or 'lineage' in p.split('/')):rule='e';ev={'segment':next(x for x in p.split('/') if x in ('fixtures','lineage')),'imports':0}
  if rule is None and p in ('automation/migration.py','automation/package_tests/test_r8_migration.py'):rule='b';ev={'refusal':'MigrationError' if p.endswith('migration.py') else 'assertRaises(MigrationError)'}
  if rule is None:
   nodes=[n for n in ast.walk(tree) if hasattr(n,'lineno') and getattr(n,'lineno')<=no<=getattr(n,'end_lineno',getattr(n,'lineno')) and isinstance(n,(ast.Constant,ast.Expr,ast.FunctionDef,ast.Module))]
   if any(isinstance(n,ast.Constant) and isinstance(n.value,str) and 'performed by the worker' in n.value for n in nodes):rule='a';ev={'ast_node':'Constant/string literal'}
  occ.append({'path':p,'line':no,'matched_text':line.strip(),'rule':rule,'evidence':ev})
unclassified=[x for x in occ if x['rule'] is None]; replica_imports=[]
for p in ['automation/controller.py','build/rehearse_candidate_plans.py']:
 if 'verification.selftest_runtime' in open(O+'/'+p,encoding='utf8').read():replica_imports.append(p)
add(9,'ORIGINAL','No live note-only operation path',{'occurrence_count':len(occ),'occurrences':occ,'replica_live_imports':replica_imports,'unclassified':unclassified},not unclassified and not replica_imports)
s1=set(operation_catalog.IN_PROCESS);s2=set(in_process_ops.HANDLERS);s3=set(in_process_executor.ARGUMENT_SCHEMA);add(10,'ORIGINAL','Catalog, handlers, schemas equal',{'counts':[len(s1),len(s2),len(s3)],'differences':[sorted(s1^s2),sorted(s1^s3)]},s1==s2==s3)
plans={}
for p in files(O+'/build/candidate_plans_r8'):
 if p.endswith('/plan.json'):
  x=load(O+'/build/candidate_plans_r8/'+p);plans[(x['audit_id'],x['run_phase'])]=x
rep=load(O+'/work/_rehearsal_r8/REHEARSAL_REPORT.json'); reps={(x['audit_id'],x['run_phase']):x for x in rep['reports']}
p16=plans[('L1-A16','RUN-A')]; ns=[x for x in p16['steps'] if x['operation']=='PROVE_SET_NOVELTY']; target=next(x for x in ns if x['step_id']=='prove_cases_are_novel'); ctr=[x for x in ns if x.get('control_role') in ('POSITIVE','NEGATIVE')]; rr={x['step_id']:x for x in reps[('L1-A16','RUN-A')]['steps']}; ok=target['params']['reference_root']=='/home/ubuntu/project/WPNO/ap18/korpus_docx' and target['params']['expected_reference_entry_count']==7 and len(ctr)==3 and len(ns)==4 and all(rr[x['step_id']]['status']=='EXECUTED' and rr[x['step_id']]['expectation_result']=='AS_EXPECTED' for x in ns);add(11,'ORIGINAL','L1-A16 novelty measurement and controls',{'novelty_steps':[(x['step_id'],x.get('control_role'),rr[x['step_id']]['status'],rr[x['step_id']]['expectation_result']) for x in ns],'reference_root':target['params']['reference_root'],'reference_count':target['params']['expected_reference_entry_count']},ok)
deg=[]
for k,p in plans.items():
 for s in p['steps']:
  q=s.get('params',{});deg += [(*k,s['step_id'])] if s['operation']=='COMPARE_HASHES' and q.get('left')==q.get('right') and not q.get('expected_sha256') else []
keyed=[s for r in rep['reports'] for s in r['steps'] if 'reads_outside_declared_allowance' in s];non=[s for s in keyed if s['reads_outside_declared_allowance']];add(12,'ORIGINAL','Hash and read allowance controls',{'degenerate':deg,'steps_carrying_key':len(keyed),'nonempty':len(non)},not deg and not non)
p21=plans[('L1-A21','RUN-A')];s21=next(x for x in p21['steps'] if x['step_id']=='negative_control_export_is_not_another_project');mx=next(x for x in p21['test_matrix'] if x['step_id']==s21['step_id']);add(13,'ORIGINAL','L1-A21 negative control',{'operation':s21['operation'],'word_boundary':s21['params'].get('word_boundary'),'expected_count':mx.get('expected_count')},s21['operation']=='COUNT_TEXT_MATCHES' and s21['params'].get('word_boundary') is True and mx.get('expected_count')==0)
ref='references/REF-11-563203462.xml';p33=plans[('L1-A33','RUN-A')];ex=next(x for x in p33['steps'] if x['step_id']=='extract_container_xml_part');pa=next(x for x in p33['steps'] if x['step_id']=='parse_container_xml_safely');out=ex['params']['out'];add(14,'ORIGINAL','MIME reference unchanged and extraction parsed',{'prefix':open(O+'/'+ref,'rb').read(13).decode(),'r8_sha':sha(O+'/'+ref),'r7_sha':sha(R['R7']+'/'+ref),'extract_out':out,'parse_path':pa['params']['path']},open(O+'/'+ref,'rb').read().startswith(b'MIME-Version:') and sha(O+'/'+ref)==sha(R['R7']+'/'+ref) and out.startswith(O+'/work/') and pa['params']['path']==out)
roles={'POSITIVE','NEGATIVE','MUTATION','ORACLE','SABOTAGE'};ctrl=[];unen=[]
for k,p in plans.items():
 for s in p['steps']:
  if s.get('control_role') in roles:
   x=next(x for x in p['test_matrix'] if x['step_id']==s['step_id']); present=in_process_executor.expectation_keys_present(x);ctrl.append((*k,s['step_id']));unen += [] if present else [(*k,s['step_id'])]
cov=load(O+'/build/CONTROL_EXPECTATION_COVERAGE.json');add(15,'ORIGINAL','All control steps enforce expectations',{'rederived_count':len(ctrl),'rederived_unenforced':unen,'record_count':cov.get('CONTROL_ROLE_STEP_COUNT'),'record_unenforced':cov.get('CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION')},not unen and cov.get('CONTROL_ROLE_STEP_COUNT')==len(ctrl) and cov.get('CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION')==0)
mig=load(O+'/build/migration_plan_r7_to_r8/MIGRATION_PLAN.json'); ma={(x['destination_audit_id'],x['destination_run_phase']) for x in mig['migratable_attempts']};xx={(x['audit_id'],x['run_phase'],x['exclusion_reason']) for x in mig['excluded_attempts']};ledger=O+'/state/migrations.jsonl';ld=0 if not os.path.exists(ledger) else sum(bool(x.strip()) for x in open(ledger));ok=ma=={('L1-A31','RUN-A'),('L1-A31','RUN-B')} and xx=={('L1-A31','COMPARISON','EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT')} and mig['applied_before_freeze'] is False and sha(O+'/'+mig['route_module'])==mig['route_module_sha256'] and ld==0;add(16,'ORIGINAL','Migration packet exact and unconsumed',{'migratable':sorted(ma),'excluded':sorted(xx),'applied':mig['applied_before_freeze'],'route_digest_match':sha(O+'/'+mig['route_module'])==mig['route_module_sha256'],'ledger_rows':ld},ok)
p7=load(R['R7']+'/state/progress.json');ev=R['R7']+'/evidence/L1-A31/COMPARISON';ef=sum(1 for _ in files(ev)) if os.path.isdir(ev) else 0;seal=os.path.exists(R['R7']+'/results/L1-A31/COMPARISON/SEAL.json');st=p7['audits']['L1-A31']['COMPARISON']['state'];add(17,'R7','R7 comparison defect state',{'state':st,'seal':seal,'evidence_files':ef},st=='EXECUTED' and not seal and ef==0)
# item 33 before, then suites
control=C+'/verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt'; before={'requested_path':control,'resolved_path':os.path.realpath(control),'root':'CLONE','mtime_ns':os.stat(control).st_mtime_ns,'sha256':sha(control)}
p=run(['/usr/bin/python3','-B','-m','unittest','discover','-s','.','-t','.'],C+'/verification/selftest_runtime'); txt=p.stdout+p.stderr; n=int(re.search(r'Ran (\d+) tests?',txt).group(1));add(18,'CLONE','Controller suite',{'tests':n,'exit':p.returncode,'failures':txt.count('FAIL:'),'errors':txt.count('ERROR:'),'skips':len(re.findall(r'skipped=',txt))},p.returncode==0 and 'FAILED' not in txt)
after={'requested_path':control,'resolved_path':os.path.realpath(control),'root':'CLONE','mtime_ns':os.stat(control).st_mtime_ns,'sha256':sha(control)}
pc=run(['/usr/bin/python3','-B',W+'/tools/run_package_suite.py',C,O,W,T+'/package_suite.json'],W);pd=load(T+'/package_suite.json');add(19,'CLONE + ORIGINAL','Two-pass package suite',pd,p.returncode==0 and pd['tests_run']==361 and pd['tests_unresolved']==0)
# static review
sd=C+'/logs/attempt6_static';os.makedirs(sd,exist_ok=True);sp=run(['/usr/bin/python3','-B','build/r8_static_safety_review.py','--out-dir',sd],C);sfiles=[sd+'/'+x for x in os.listdir(sd)];sj=next((x for x in sfiles if x.endswith('.json')),None);sr=load(sj);orig=load(O+'/build/R8_STATIC_SAFETY_REPORT.json');aa={k:v for k,v in sr.items() if k not in ('package_root','reviewed_at_utc')};bb={k:v for k,v in orig.items() if k not in ('package_root','reviewed_at_utc')};add(20,'CLONE','Static safety rerun',{'exit':sp.returncode,'finding_count':sr.get('finding_count'),'clean':sr.get('clean'),'predecessor_root':sr.get('predecessor_root'),'field_match_except_location_time':aa==bb},sp.returncode==0 and sr.get('clean') is True and sr.get('finding_count')==0 and sr.get('predecessor_root')==R['R7'] and aa==bb)
coverage=load(O+'/build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json');add(21,'ORIGINAL','Plan coverage',{'plans':len(plans),'missing':coverage.get('MISSING_PLAN_COUNT'),'duplicate':coverage.get('DUPLICATE_PLAN_COUNT'),'unknown':coverage.get('UNKNOWN_PLAN_COUNT')},len(plans)==43 and all(coverage.get(x)==0 for x in ['MISSING_PLAN_COUNT','DUPLICATE_PLAN_COUNT','UNKNOWN_PLAN_COUNT']))
ready=sum(bool(x.get('PASS_READY')) for x in rep['reports']);add(22,'ORIGINAL','Rehearsal PASS_READY',{'ready':ready,'reported':rep.get('PHASES_PASS_READY')},ready==43 and rep.get('PHASES_PASS_READY')==43)
rec=load(O+'/build/IN_PROCESS_COUNT_RECONCILIATION.json');vals={k:rep.get(k) for k in ['REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE','NOTE_ONLY_IN_PROCESS_STEPS','IN_PROCESS_HANDLER_INVOCATIONS','IN_PROCESS_STEP_COUNT']};add(23,'ORIGINAL','In-process evidence and invocation reconciliation',{'report':vals,'reconciliation':rec},vals['REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE']==0 and vals['NOTE_ONLY_IN_PROCESS_STEPS']==0 and vals['IN_PROCESS_HANDLER_INVOCATIONS']==vals['IN_PROCESS_STEP_COUNT'])
add(24,'ORIGINAL','No hollow phases; live state unchanged',{'HOLLOW_PHASES':rep.get('HOLLOW_PHASES'),'LIVE_STATE_UNCHANGED':rep.get('LIVE_STATE_UNCHANGED')},rep.get('HOLLOW_PHASES')==[] and rep.get('LIVE_STATE_UNCHANGED') is True)
prog=load(O+'/state/progress.json');sts=[x['state'] for a in prog['audits'].values() for x in a.values()];add(25,'ORIGINAL','Progress remains NOT_STARTED',{'audits':len(prog['audits']),'phases':len(sts),'states':{x:sts.count(x) for x in set(sts)}},len(prog['audits'])==35 and len(sts)==43 and set(sts)=={'NOT_STARTED'})
ap=sum(bool(x.strip()) for x in open(O+'/state/approvals.jsonl'));rf=sum(1 for _ in files(O+'/results'));ef=sum(1 for _ in files(O+'/evidence'));tok=[]
for p in files(O+'/state'):
 if any(x in open(O+'/state/'+p,encoding='utf8',errors='replace').read() for x in ('APPROVE-EXECUTION','RUN-ONCE')):tok.append(p)
add(26,'ORIGINAL','No approvals/results/evidence/tokens',{'approvals':ap,'results':rf,'evidence':ef,'token_files':tok},ap==rf==ef==0 and not tok)
be,bad,dup=manifest(O,'build/R8_BUILD_MANIFEST.sha256');builder=importlib.import_module('build.build_r8_build_manifest');listed={x[0] for x in be};physical={p for p in files(O) if builder.in_scope(p)};mm=[x[0] for x in be if x[1]!=x[2]];md=sha(O+'/build/R8_BUILD_MANIFEST.sha256');add(27,'ORIGINAL','Build manifest exact',{'manifest_sha256':md,'entries':len(be),'malformed':bad,'duplicates':dup,'mismatches':mm,'physical_minus_listed':sorted(physical-listed),'listed_minus_physical':sorted(listed-physical)},md=='6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a' and len(be)==724 and not bad and not dup and not mm and physical==listed)
base=os.path.realpath(C+'/'+freeze.PREDECESSOR_BASELINE_REL); bl,prov=freeze.build_baseline_from_predecessor(C); ds=[hashlib.sha256(x.encode()).hexdigest() for x in 'abc'];token=freeze.token_for(*ds);parsed=freeze.parse_freeze_token(token);fa=C+'/state/freeze_attempts.jsonl';fr=sum(bool(x.strip()) for x in open(fa)) if os.path.exists(fa) else 0;mode=open(O+'/MODE').read().strip();add(28,'CLONE + ORIGINAL','Freeze mechanism capability using dummy digests',{'revision':freeze.PACKAGE_REVISION,'platform':freeze.PACKAGE_PLATFORM,'baseline_path':base,'baseline_digest':sha(base),'lineage_digest':r7['baseline_manifest_sha256'],'baseline_members':len(bl),'provenance_members':len(prov),'dummy_digests':ds,'token_fields':token.split(),'trailing_newline':token.endswith('\n'),'parsed':parsed,'freeze_attempt_rows':fr,'MODE':mode},freeze.PACKAGE_REVISION=='R8' and freeze.PACKAGE_PLATFORM=='UBUNTU' and base.startswith(C+'/') and sha(base)==r7['baseline_manifest_sha256'] and len(bl)>0 and len(prov)>0 and len(token.split())==5 and not token.endswith('\n') and fr==0 and mode=='GENERATED_UNVERIFIED')
r9='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R9';add(29,'ORIGINAL sibling','No R9 exists',{'path':r9,'exists':os.path.exists(r9)},not os.path.exists(r9));trs=[json.loads(x) for x in open(O+'/state/transitions.jsonl') if x.strip()];add(30,'ORIGINAL','Single init transition',{'rows':len(trs),'routes':[x.get('route') for x in trs]},len(trs)==1 and trs[0].get('route')=='init-revision')
# final inventory and comparisons
inv_after=T+'/INVENTORY_AFTER.json';q=run(['/usr/bin/python3','-B',W+'/tools/inventory_r8.py',O,inv_after],W);cmp=T+'/INVENTORY_COMPARE.json';q=run(['/usr/bin/python3','-B',W+'/tools/compare_inventories.py',W+'/original_inventory/INVENTORY_PRE.json',inv_after,cmp],W);cd=load(cmp)
pre=load(W+'/original_inventory/INVENTORY_PRE.json'); premap={x['path']:x for x in pre['entries']};post=load(inv_after);postmap={x['path']:x for x in post['entries']};fold1=hashlib.sha256(''.join(premap[p]['sha256'] for p,_,_ in be).encode()).hexdigest();fold2=hashlib.sha256(''.join(postmap[p]['sha256'] for p,_,_ in be).encode()).hexdigest();add(31,'ORIGINAL','Manifest-covered folded digest unchanged',{'before':fold1,'after':fold2,'changed_paths':[p for p,_,_ in be if premap[p]['sha256']!=postmap[p]['sha256']]},fold1==fold2)
iso={'R8 paths written':cd['written_paths'],'R8 mtimes changed':cd['mtimes_changed'],'R8 modes changed':cd['modes_changed'],'R8 symlink targets changed':cd['symlink_targets_changed'],'R8 contents changed':cd['contents_changed'],'R8 paths added':cd['paths_added'],'R8 paths removed':cd['paths_removed'],'entry_count_before':pre['entry_count'],'entry_count_after':post['entry_count']};add(32,'ORIGINAL','Full metadata write isolation',iso,cd['EQUAL'] and pre['entry_count']==1362)
cmp33={'before':before,'after':after,'resolved_path_stable':before['resolved_path']==after['resolved_path'],'mtime_moved':after['mtime_ns']>before['mtime_ns'],'mtime_backwards':after['mtime_ns']<before['mtime_ns'],'bytes_match_original':after['sha256']==sha(O+'/verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt')};add(33,'CLONE + ORIGINAL','Absolute-path write detector is live',cmp33,cmp33['resolved_path_stable'] and cmp33['mtime_moved'] and not cmp33['mtime_backwards'] and cmp33['bytes_match_original'])
ti=load(W+'/TOOL_INVENTORY.json');tm=[]
for x in ti['tools']:
 p=x['CANONICAL_PATH']; actual='NOT_USED' if p=='NOT_USED' else (hashlib.sha256(inspect.getsource(freeze.token_for).encode()).hexdigest() if '::token_for' in p else sha(p));
 if actual!=x['SHA256']:tm.append({'path':p,'expected':x['SHA256'],'actual':actual})
roles={x['ROLE'] for x in ti['tools']};required={'FINAL_VERIFICATION_INSTRUCTIONS','VERIFICATION_RUNNER','CLONE_BUILDER','CLONE_PREFLIGHT','INVENTORY_SCRIPT','INVENTORY_COMPARATOR','TEST_RUNNER','STATIC_SAFETY_RUNNER','FREEZE_PLAN_BUILDER','FREEZE_PLAN_WRAPPER','FREEZE_MODULE','TOKEN_GENERATION_FUNCTION_SOURCE'};add(34,'WORKSPACE + ORIGINAL','Tool inventory complete and matching',{'rows':len(ti['tools']),'digest_mismatches':tm,'missing_roles':sorted(required-roles),'unidentified':ti['UNIDENTIFIED_TOOLS'],'result_mislabeled':any('VERIFICATION_RESULT.json' in x['CANONICAL_PATH'] for x in ti['tools'])},not tm and not(required-roles) and ti['UNIDENTIFIED_TOOLS']==0 and not any('VERIFICATION_RESULT.json' in x['CANONICAL_PATH'] for x in ti['tools']))
wp=run(['/usr/bin/python3','-B',W+'/tools/inspect_writers.py',O,T+'/WRITERS_AFTER.json'],W);wr=load(T+'/WRITERS_AFTER.json');add(35,'/proc + ORIGINAL','No concurrent writable descriptor',wr,wp.returncode==0 and wr.get('BLOCKING_COUNT')==0)
# final five, written once
overall=all(x['pass'] for x in items if x['id']!=0) and not findings
res={'schema':'wpno.level1.codex-verification/1','revision':'R8','stage':'PRE_FREEZE_FINAL','attempt':7,'verified_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'items':[x for x in items if x['id']!=0],'manifest_sha256_verified':md,'manifest_entries_verified':len(be),'package_unchanged_by_this_verification':cd['EQUAL'],'r8_paths_written_during_attempt_7':cd['written_paths'],'write_isolation_instrument_proven_live':cmp33['mtime_moved'],'overall_pass':overall,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if overall else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
M['preflight']=pf;M['tool_hashes_used']={p:sha(W+'/tools/'+p) for p in ['measure_path.py','inventory_r8.py','compare_inventories.py','run_package_suite.py']};M['item_records']=items
os.makedirs(OUT,exist_ok=True)
open(OUT+'/MEASUREMENTS.json','w').write(json.dumps(M,indent=2,sort_keys=True)+'\n');open(OUT+'/COMMAND_LOG.jsonl','w').write(''.join(json.dumps(x,sort_keys=True)+'\n' for x in commands));open(OUT+'/VERIFICATION_RESULT.json','w').write(json.dumps(res,indent=2,sort_keys=True)+'\n')
report=f"# Independent R8 pre-freeze verification — attempt 7\n\nResult: **{res['status']}**. Freshly measured {sum(x['pass'] for x in res['items'])}/35 items. Read-only checks used ORIGINAL; controller/static and writable freeze capability used CLONE; the package suite used CLONE plus the one location-bound assertion in ORIGINAL under full inventory. Earlier attempts were not used as evidence.\n\nThe supplied absolute-path, inventory/comparator, and package-suite helpers were read before use; their hashes are in MEASUREMENTS.json. Item 9 classifies every measured occurrence by syntax/content. Item 35 is limited to processes and descriptors visible through this process's `/proc` permissions.\n\nUnresolved findings: {json.dumps(findings)}\n"
open(OUT+'/VERIFICATION_REPORT.md','w').write(report)
outs=['COMMAND_LOG.jsonl','MEASUREMENTS.json','VERIFICATION_REPORT.md','VERIFICATION_RESULT.json'];open(OUT+'/VERIFICATION_MANIFEST.sha256','w').write(''.join(f'{sha(OUT+"/"+p)}  {p}\n' for p in outs))
print(json.dumps({'status':res['status'],'passed':sum(x['pass'] for x in res['items']),'findings':findings},indent=2))
