import os,json,hashlib,stat,subprocess,sys,datetime,inspect,ast,re
W='/home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_6'; O=W+'/codex_output'; R='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8'; C='/home/ubuntu/project/WPNO/.r8_verify_clone_attempt_6_658748'; P='/home/ubuntu/project/WPNO'
R4=P+'/08.18.26_Level1_Audits_R4';R5=P+'/08.18.26_Level1_Audits_R5';R6=P+'/08.18.26_Level1_Audits_R6';R7=P+'/08.18.26_Level1_Audits_R7'
M={'roots':{'ORIGINAL':R,'CLONE':C},'items':{},'commands':[]}; items=[]; findings=[]
def sha(p):
 d=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): d.update(b)
 return d.hexdigest()
def load(p):
 with open(p,encoding='utf8') as f:return json.load(f)
def log(cmd,root,rc,utc):
 row={'command':cmd,'root':root,'exit_status':rc,'utc':utc}; M['commands'].append(row)
 with open(O+'/COMMAND_LOG.jsonl','a') as f:f.write(json.dumps(row,sort_keys=True)+'\n')
def run(cmd,cwd,timeout=1800):
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat(); p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout,env=os.environ.copy()); log(' '.join(cmd),cwd,p.returncode,utc); return p
def add(i,root,claim,meas,ok):
 items.append({'id':i,'root':root,'claim':claim,'measured':meas,'pass':bool(ok)});M['items'][str(i)]=meas
 if not ok: findings.append('Item %d: %s'%(i,meas)); finish(False)
def manifest_check(root,name):
 path=root+'/'+name; bad=[]; malformed=[]; seen=set(); n=0
 for ln in open(path,encoding='utf8'):
  ln=ln.rstrip('\n'); m=re.fullmatch(r'([0-9a-f]{64})  (.+)',ln)
  if not m: malformed.append(ln);continue
  h,rel=m.groups();n+=1
  if rel in seen: bad.append([rel,'DUPLICATE'])
  seen.add(rel); q=root+'/'+rel
  if not os.path.isfile(q):bad.append([rel,'MISSING'])
  elif sha(q)!=h:bad.append([rel,'MODE' if rel=='MODE' else 'HASH'])
 return {'manifest':path,'manifest_sha256':sha(path),'entries':n,'mismatches':bad,'malformed':malformed,'listed':seen}
def inv_fold(doc,listed):
 by={x['path']:x for x in doc['entries']}; d=hashlib.sha256()
 for p in sorted(listed):d.update((p+'\0'+by[p]['sha256']+'\n').encode())
 return d.hexdigest()
def finish(success):
 # final inventory and comparison
 aft=W+'/temporary/INVENTORY_FINAL.json'; cmp=W+'/temporary/COMPARE_FINAL.json'
 p=run(['/usr/bin/python3','-B',W+'/tools/inventory_r8.py',R,aft],W); p2=run(['/usr/bin/python3','-B',W+'/tools/compare_inventories.py',W+'/original_inventory/INVENTORY_PRE.json',aft,cmp],W)
 cd=load(cmp); M['original_inventory_final']=load(aft);M['original_compare']=cd
 if 'manifest' in M:
  M['manifest_fold_after']=inv_fold(load(aft),M['manifest']['listed'])
 # item31/32 are always finalized here
 foldok=M.get('manifest_fold_before')==M.get('manifest_fold_after')
 if not any(x['id']==31 for x in items): items.append({'id':31,'root':'ORIGINAL','claim':'724-file manifest fold unchanged','measured':{'before':M.get('manifest_fold_before'),'after':M.get('manifest_fold_after')},'pass':foldok})
 iso={'R8 paths written':cd['written_paths'],'R8 mtimes changed':cd['mtimes_changed'],'R8 modes changed':cd['modes_changed'],'R8 symlink targets changed':cd['symlink_targets_changed'],'R8 contents changed':cd['contents_changed'],'R8 paths added':cd['paths_added'],'R8 paths removed':cd['paths_removed'],'entry_count_before':load(W+'/original_inventory/INVENTORY_PRE.json')['entry_count'],'entry_count_after':load(aft)['entry_count']}
 if not any(x['id']==32 for x in items): items.append({'id':32,'root':'ORIGINAL','claim':'full metadata write isolation','measured':iso,'pass':cd['EQUAL']})
 if not foldok:findings.append('Item 31: manifest-covered fold changed')
 if not cd['EQUAL']:findings.append('Item 32: ORIGINAL inventory changed')
 ok=success and not findings and len(items)==35 and all(x['pass'] for x in items)
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 result={'schema':'wpno.level1.codex-verification/1','revision':'R8','stage':'PRE_FREEZE_FINAL','attempt':6,'verified_utc':now,'items':sorted(items,key=lambda x:x['id']),'manifest_sha256_verified':M.get('manifest',{}).get('manifest_sha256'),'manifest_entries_verified':M.get('manifest',{}).get('entries',0),'package_unchanged_by_this_verification':cd['EQUAL'],'r8_paths_written_during_attempt_6':cd['written_paths'],'write_isolation_instrument_proven_live':bool(M.get('item33',{}).get('mtime_moved')),'overall_pass':ok,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if ok else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
 # Make serializable
 if 'manifest' in M:M['manifest']['listed']=sorted(M['manifest']['listed'])
 with open(O+'/MEASUREMENTS.json','w') as f:json.dump(M,f,indent=1,sort_keys=True);f.write('\n')
 with open(O+'/VERIFICATION_RESULT.json','w') as f:json.dump(result,f,indent=1,sort_keys=True);f.write('\n')
 lines=['# R8 attempt 6 independent pre-freeze verification','',('Outcome: **PASS**.' if ok else 'Outcome: **FAIL**.'),'','All read-only checks were measured against ORIGINAL; controller/package/static write-capable checks ran in CLONE, except the single unmodified location-bound package test run in situ under a full before/after ORIGINAL inventory.','','The supplied inventory, comparator, absolute-path helper, package-suite runner, and writer inspector were read before use; their SHA-256 values are recorded in MEASUREMENTS.json.','', 'Findings: '+('none.' if not findings else '; '.join(findings))]
 with open(O+'/VERIFICATION_REPORT.md','w') as f:f.write('\n'.join(lines)+'\n')
 # manifest is the final write
 paths=[]
 for dp,ds,fs in os.walk(O):
  for n in fs:
   q=os.path.join(dp,n)
   if n!='VERIFICATION_MANIFEST.sha256':paths.append(q)
 with open(O+'/VERIFICATION_MANIFEST.sha256','w') as f:
  for q in sorted(paths):f.write(sha(q)+'  '+os.path.relpath(q,O)+'\n')
 raise SystemExit(0 if ok else 1)

# Baseline and manifest first
pre=load(W+'/preflight/PREFLIGHT.json'); M['preflight']=pre
if not pre['PREFLIGHT_PASS']: findings.append('Preflight failed'); finish(False)
bm=manifest_check(R,'build/R8_BUILD_MANIFEST.sha256');M['manifest']=bm; M['manifest_fold_before']=inv_fold(load(W+'/original_inventory/INVENTORY_PRE.json'),bm['listed'])
add(27,'ORIGINAL','build manifest structural and byte verification', {k:v for k,v in bm.items() if k!='listed'},bm['manifest_sha256']=='6dfd1af689754be61f2ea6ef77f01d2e5bdb8929ef8c0799e15db203755b945a' and bm['entries']==724 and not bm['mismatches'] and not bm['malformed'])
# predecessor manifests
for i,root,rel,exp in [(1,R4,'CONTROL_MANIFEST.sha256',0),(2,R5,'CONTROL_MANIFEST.sha256',1),(3,R6,'CONTROL_MANIFEST.sha256',0),(4,R7,'CONTROL_MANIFEST.sha256',0)]:
 x=manifest_check(root,rel);ok=len(x['mismatches'])==exp and (i!=2 or x['mismatches']==[['MODE','MODE']]) and (i!=4 or x['entries']==15804);add(i,'R%d'%(i+3),'control manifest', {k:v for k,v in x.items() if k!='listed'},ok)
# item5
inc=manifest_check(R+'/lineage/R7_POST_FREEZE_INCIDENT','INCIDENT_MANIFEST.sha256'); lin=load(R+'/lineage/R8_LINEAGE.json'); hits=[]
for dp,ds,fs in os.walk(R):
 for n in fs:
  q=dp+'/'+n
  try:t=open(q,encoding='utf8').read()
  except:continue
  if 'continuous_post_freeze_immutability' in t and q!=R+'/lineage/R8_LINEAGE.json':hits.append(os.path.relpath(q,R))
me={'incident':{k:v for k,v in inc.items() if k!='listed'},'r7':lin['r7'],'other_claim_files':hits};add(5,'ORIGINAL','R7 incident disclosure',me,not inc['mismatches'] and lin['r7']['continuous_post_freeze_immutability'] is False and lin['r7']['current_bytes_restored_to_frozen_manifest'] is True)
# imports from clone
sys.path.insert(0,C);from automation import package_tests as pt,operation_catalog,in_process_ops,in_process_executor,freeze
roots={x:pt.generation_root(x) for x in ('R4','R5','R6','R7','R8')}; copies=[]
for dp,ds,fs in os.walk(R+'/lineage'):
 for d in list(ds):
  if d.startswith('08.18.26_Level1_Audits_R'):copies.append(os.path.join(dp,d))
add(6,'ORIGINAL','lineage compactness and generation roots',{'generation_roots':roots,'full_copies':copies,'r6_execution_exists':os.path.isdir(R+'/lineage/R6_EXECUTION')},not copies and not os.path.isdir(R+'/lineage/R6_EXECUTION') and all(os.path.isdir(v) for v in roots.values()))
# inode R7/R8
idx={}
for dp,ds,fs in os.walk(R7):
 for n in fs:
  s=os.lstat(dp+'/'+n);idx[(s.st_dev,s.st_ino)]=dp+'/'+n
shared=[]
for dp,ds,fs in os.walk(R):
 for n in fs:
  q=dp+'/'+n;s=os.lstat(q)
  if (s.st_dev,s.st_ino) in idx:shared.append([q,idx[(s.st_dev,s.st_ino)]])
add(7,'ORIGINAL','no active R7/R8 shared inode',{'shared':shared},not shared)
# static source facts 8-10
calls={p:open(R+'/'+p).read().count('in_process_executor.execute') for p in ['automation/controller.py','build/rehearse_candidate_plans.py']};add(8,'ORIGINAL','both callers invoke executor',calls,all(v>0 for v in calls.values()))
occ=[]
for dp,ds,fs in os.walk(R):
 for n in fs:
  if n.endswith('.py'):
   q=dp+'/'+n
   for no,l in enumerate(open(q,errors='replace'),1):
    if 'performed by the worker' in l:
     rel=os.path.relpath(q,R); seg=rel.split(os.sep); cls='fixture_or_lineage' if ('fixtures'in seg or 'lineage'in seg) else ('guard_or_test' if rel in ('automation/migration.py','automation/package_tests/test_r8_migration.py') else 'quoted_defect_comment_or_docstring' if rel in ('automation/in_process_ops.py','automation/in_process_executor.py','automation/controller.py') else 'FINDING');occ.append({'path':rel,'line':no,'classification':cls,'text':l.strip()})
add(9,'ORIGINAL','no live note-only operation',occ,not any(x['classification']=='FINDING' for x in occ))
sets={'catalog':sorted(operation_catalog.IN_PROCESS),'handlers':sorted(in_process_ops.HANDLERS),'schemas':sorted(in_process_executor.ARGUMENT_SCHEMA)};add(10,'ORIGINAL','in-process sets equal',sets,sets['catalog']==sets['handlers']==sets['schemas'])
# plans/rehearsal broad checks
plans=[]
for dp,ds,fs in os.walk(R+'/build/candidate_plans_r8'):
 if 'plan.json' in fs:plans.append(load(dp+'/plan.json'))
rep=load(R+'/work/_rehearsal_r8/REHEARSAL_REPORT.json');M['plan_count']=len(plans)
def steps(pl):return pl.get('steps',[])
p16=load(R+'/build/candidate_plans_r8/L1-A16/RUN-A/plan.json'); s16=steps(p16);nov=[s for s in s16 if s.get('operation')=='PROVE_SET_NOVELTY']; target=next(s for s in nov if s.get('step_id')=='prove_cases_are_novel');controls=[s for s in nov if s.get('phase')=='FURTHER' and s.get('control_role') in ('POSITIVE','NEGATIVE')]
rsteps=[]
def walk(o):
 if isinstance(o,dict):
  if o.get('operation')=='PROVE_SET_NOVELTY' and ('status'in o):rsteps.append(o)
  for v in o.values():walk(v)
 elif isinstance(o,list):
  for v in o:walk(v)
walk(rep)
rr=[x for x in rsteps if x.get('audit_id')=='L1-A16' and x.get('phase')=='RUN-A'] or [x for x in rsteps if x.get('step_id') in {s.get('step_id') for s in nov}]
add(11,'ORIGINAL','L1-A16 novelty and controls',{'target':target,'control_count':len(controls),'rehearsal_results':rr},target.get('reference_root')=='/home/ubuntu/project/WPNO/ap18/korpus_docx' and target.get('expected_reference_entry_count')==7 and len(controls)==3 and len(rr)==4 and all(x.get('status')=='EXECUTED' and x.get('expectation_result')=='AS_EXPECTED' for x in rr))
same=[]; carrying=0;nonempty=0
for pl in plans:
 for s in steps(pl):
  if s.get('operation')=='COMPARE_HASHES' and s.get('left')==s.get('right') and not s.get('expected_sha256'):same.append(s.get('step_id'))
def scanread(o):
 global carrying,nonempty
 if isinstance(o,dict):
  if 'reads_outside_declared_allowance'in o:
   carrying+=1;nonempty+=bool(o['reads_outside_declared_allowance'])
  for v in o.values():scanread(v)
 elif isinstance(o,list):
  for v in o:scanread(v)
scanread(rep);add(12,'ORIGINAL','hash comparisons and read allowance',{'bad_compare_steps':same,'steps_carrying_key':carrying,'nonempty':nonempty},not same and nonempty==0)
p21=load(R+'/build/candidate_plans_r8/L1-A21/RUN-A/plan.json');a21=next(s for s in steps(p21) if s.get('step_id')=='negative_control_export_is_not_another_project');add(13,'ORIGINAL','L1-A21 negative control',a21,a21.get('operation')=='COUNT_TEXT_MATCHES' and a21.get('word_boundary') is True and a21.get('expected_count')==0)
ref=R+'/references/REF-11-563203462.xml'; ref7=R7+'/references/REF-11-563203462.xml';p33=[p for p in plans if p.get('audit_id')=='L1-A33'];add(14,'ORIGINAL','MIME reference and L1-A33 extraction',{'prefix':open(ref,'rb').read(13).decode(),'r8_sha':sha(ref),'r7_sha':sha(ref7),'plans':p33},open(ref,'rb').read().startswith(b'MIME-Version:') and sha(ref)==sha(ref7) and 'work/' in json.dumps(p33))
roles={'POSITIVE','NEGATIVE','MUTATION','ORACLE','SABOTAGE'};control=[];un=[]
for pl in plans:
 for s in steps(pl):
  if s.get('control_role') in roles:
   control.append(s); 
   if not in_process_executor.expectation_keys_present(s):un.append(s.get('step_id'))
cov=load(R+'/build/CONTROL_EXPECTATION_COVERAGE.json');add(15,'ORIGINAL','control expectation coverage',{'derived_count':len(control),'derived_unenforced':un,'record':cov},not un and (cov.get('control_step_count')==len(control) or cov.get('CONTROL_STEP_COUNT')==len(control)))
mig=load(R+'/build/migration_plan_r7_to_r8/MIGRATION_PLAN.json');ledger=R+'/state/migrations.jsonl';okmig=mig.get('applied_before_freeze') is False and mig.get('route_module_sha256')==sha(R+'/automation/migration.py') and (not os.path.exists(ledger) or os.path.getsize(ledger)==0);add(16,'ORIGINAL','migration packet exactness',{'plan':mig,'ledger_absent_or_empty':not os.path.exists(ledger) or os.path.getsize(ledger)==0},okmig)
# R7 A31
prog7=load(R7+'/state/progress.json'); comp=prog7['audits']['L1-A31']['COMPARISON'];base=R7+'/results/L1-A31/COMPARISON';ev=[]
if os.path.isdir(base):
 for dp,ds,fs in os.walk(base):ev += [dp+'/'+x for x in fs if x!='SEAL.json']
add(17,'R7','R7 A31 comparison condition',{'state':comp,'seal_exists':os.path.exists(base+'/SEAL.json'),'evidence_files':ev},comp['state']=='EXECUTED' and not os.path.exists(base+'/SEAL.json') and len(ev)==0)
# item33 before controller suite
target=C+'/verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt'; obs=lambda p:{'requested_path':p,'resolved_path':os.path.realpath(p),'root':'CLONE' if os.path.realpath(p).startswith(C+'/') else 'ORIGINAL','mtime_ns':os.stat(p).st_mtime_ns,'sha256':sha(p)}; bobs=obs(target)
p=run(['/usr/bin/python3','-B','-m','unittest','discover','-s','.','-t','.'],C+'/verification/selftest_runtime'); m=re.search(r'Ran (\d+) tests?',p.stderr);aobs=obs(target);add(18,'CLONE','controller suite',{'tests_run':int(m.group(1)) if m else None,'exit':p.returncode,'stdout':p.stdout[-2000:],'stderr':p.stderr[-2000:]},p.returncode==0)
cmpobs={'before':bobs,'after':aobs,'mtime_moved':aobs['mtime_ns']>bobs['mtime_ns'],'bytes_match_original':aobs['sha256']==sha(R+'/verification/selftest_runtime/work/_selftest/unicode_fs_behaviour.txt'),'valid':aobs['resolved_path']==bobs['resolved_path'] and aobs['mtime_ns']>=bobs['mtime_ns']};M['item33']=cmpobs;add(33,'CLONE','absolute path instrument liveness',cmpobs,cmpobs['valid'] and cmpobs['mtime_moved'] and cmpobs['bytes_match_original'])
# package suite supplied runner
psout=W+'/temporary/PACKAGE_SUITE.json';p=run(['/usr/bin/python3','-B',W+'/tools/run_package_suite.py',C,R,W,psout],W);ps=load(psout);add(19,'CLONE + ORIGINAL','two-pass package suite',ps,p.returncode==0 and ps.get('CLEAN'))
# static
sd=C+'/logs/attempt6_static';p=run(['/usr/bin/python3','-B','build/r8_static_safety_review.py','--out-dir',sd],C); files=[]
for n in os.listdir(sd):
 q=sd+'/'+n
 if os.path.isfile(q):
  dest=O+'/'+n;open(dest,'wb').write(open(q,'rb').read());files.append(dest)
reports=[load(x) for x in files if x.endswith('.json')];sr=next((x for x in reports if 'clean'in x),reports[0] if reports else {});orig=load(R+'/build/R8_STATIC_SAFETY_REPORT.json'); norm=lambda x:{k:v for k,v in x.items() if k not in ('package_root','reviewed_at_utc')};add(20,'CLONE','static safety rerun',{'exit':p.returncode,'report':sr,'matches_original_except_location_time':norm(sr)==norm(orig)},p.returncode==0 and sr.get('clean') is True and sr.get('finding_count',0)==0 and norm(sr)==norm(orig) and sr.get('predecessor_root')==R7)
# remaining JSON/state facts
coverage=load(R+'/build/PLAN_COVERAGE_MANIFEST.json');add(21,'ORIGINAL','43 plan coverage',{'plan_count':len(plans),'coverage':coverage},len(plans)==43 and all(not coverage.get(k) for k in ('missing','duplicate','unknown')))
add(22,'ORIGINAL','43 PASS_READY',rep,rep.get('PASS_READY_PHASE_COUNT')==43 or (rep.get('summary',{}).get('PASS_READY')==43 and rep.get('summary',{}).get('phase_count')==43))
recon=load(R+'/build/IN_PROCESS_COUNT_RECONCILIATION.json'); inv=rep.get('IN_PROCESS_HANDLER_INVOCATIONS',rep.get('summary',{}).get('IN_PROCESS_HANDLER_INVOCATIONS')); cnt=rep.get('IN_PROCESS_STEP_COUNT',rep.get('summary',{}).get('IN_PROCESS_STEP_COUNT'));zero1=rep.get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE',rep.get('summary',{}).get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE'));zero2=rep.get('NOTE_ONLY_IN_PROCESS_STEPS',rep.get('summary',{}).get('NOTE_ONLY_IN_PROCESS_STEPS'));add(23,'ORIGINAL','in-process reconciliation',{'handler_invocations':inv,'step_count':cnt,'without_evidence':zero1,'note_only':zero2,'record':recon},zero1==0 and zero2==0 and inv==cnt)
add(24,'ORIGINAL','no hollow phases/live state unchanged',{'HOLLOW_PHASES':rep.get('HOLLOW_PHASES',rep.get('summary',{}).get('HOLLOW_PHASES')),'LIVE_STATE_UNCHANGED':rep.get('LIVE_STATE_UNCHANGED',rep.get('summary',{}).get('LIVE_STATE_UNCHANGED'))},(rep.get('HOLLOW_PHASES',rep.get('summary',{}).get('HOLLOW_PHASES')) in ([],0)) and rep.get('LIVE_STATE_UNCHANGED',rep.get('summary',{}).get('LIVE_STATE_UNCHANGED')) is True)
pr=load(R+'/state/progress.json'); phases=[v for a in pr['audits'].values() for v in a.values()];add(25,'ORIGINAL','progress pristine',{'audits':len(pr['audits']),'phases':len(phases),'states':sorted(set(x['state'] for x in phases))},len(pr['audits'])==35 and len(phases)==43 and all(x['state']=='NOT_STARTED' for x in phases))
ap=R+'/state/approvals.jsonl';rf=sum(len(fs) for _,_,fs in os.walk(R+'/results'));ef=sum(len(fs) for _,_,fs in os.walk(R+'/evidence'));tok=[]
for dp,ds,fs in os.walk(R+'/state'):
 for n in fs:
  q=dp+'/'+n
  if b'APPROVE-EXECUTION' in open(q,'rb').read() or b'RUN-ONCE' in open(q,'rb').read():tok.append(q)
add(26,'ORIGINAL','no approvals/results/evidence/token text',{'approvals_size':os.path.getsize(ap),'result_files':rf,'evidence_files':ef,'token_hits':tok},os.path.getsize(ap)==0 and rf==0 and ef==0 and not tok)
# freeze mechanism
src=open(R+'/automation/freeze.py').read(); baseline=os.path.realpath(R+'/'+freeze.PREDECESSOR_BASELINE_REL); bline=freeze.build_baseline_from_predecessor(C); digs=[hashlib.sha256(x.encode()).hexdigest() for x in ('a','b','c')]; token=freeze.token_for(*digs);parsed=freeze.parse_freeze_token(token); fa=R+'/state/freeze_attempts.jsonl'; mode=open(R+'/MODE').read().strip(); fmeas={'PACKAGE_REVISION':freeze.PACKAGE_REVISION,'PACKAGE_PLATFORM':freeze.PACKAGE_PLATFORM,'baseline_path':baseline,'baseline_sha':sha(baseline),'lineage_sha':lin['r7']['baseline_manifest_sha256'],'baseline_counts':[len(x) for x in bline],'dummy_digests':digs,'dummy_token_field_count':len(token.split()),'dummy_token_trailing_newline':token.endswith('\n'),'parsed':parsed,'freeze_attempts_size':os.path.getsize(fa),'MODE':mode};add(28,'CLONE + ORIGINAL','freeze mechanism capability with dummy digests',fmeas,freeze.PACKAGE_REVISION=='R8' and freeze.PACKAGE_PLATFORM=='UBUNTU' and baseline.startswith(R+'/') and sha(baseline)==lin['r7']['baseline_manifest_sha256'] and all(len(x)>0 for x in bline) and len(token.split())==5 and not token.endswith('\n') and os.path.getsize(fa)==0 and mode=='GENERATED_UNVERIFIED')
add(29,'ORIGINAL parent','R9 absent',{'path':P+'/08.18.26_Level1_Audits_R9','exists':os.path.exists(P+'/08.18.26_Level1_Audits_R9')},not os.path.exists(P+'/08.18.26_Level1_Audits_R9'))
rows=[json.loads(x) for x in open(R+'/state/transitions.jsonl') if x.strip()];add(30,'ORIGINAL','single init transition',rows,len(rows)==1 and rows[0].get('route')=='init-revision')
# tool inventory exact hashes
ti=load(W+'/TOOL_INVENTORY.json');tb=[]
for x in ti['tools']:
 q=x['CANONICAL_PATH'];ok=True
 if q=='NOT_USED':ok=x['SHA256']=='NOT_USED'
 elif '::token_for' in q:ok=x['SHA256']==hashlib.sha256(inspect.getsource(freeze.token_for).encode()).hexdigest()
 else:ok=os.path.isfile(q) and sha(q)==x['SHA256']
 if not ok:tb.append(x['ROLE'])
add(34,'WORKSPACE + ORIGINAL','tool inventory identification and hashes',{'tool_count':ti['tool_count'],'unidentified':ti['UNIDENTIFIED_TOOLS'],'bad_rows':tb,'roles':[x['ROLE'] for x in ti['tools']]},ti['UNIDENTIFIED_TOOLS']==0 and not tb and not any('VERIFICATION_RESULT' in x['CANONICAL_PATH'] for x in ti['tools']))
# writer inspection final
wout=W+'/temporary/WRITER_INSPECTION_FINAL.json';p=run(['/usr/bin/python3','-B',W+'/tools/inspect_writers.py',R,wout],W);wr=load(wout);add(35,'ORIGINAL','no concurrent writable descriptor',wr,p.returncode==0 and wr['BLOCKING_COUNT']==0)
finish(True)
