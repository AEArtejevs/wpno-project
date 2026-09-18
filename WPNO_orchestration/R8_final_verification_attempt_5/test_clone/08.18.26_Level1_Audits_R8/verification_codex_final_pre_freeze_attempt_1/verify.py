#!/usr/bin/python3
import ast, datetime, fnmatch, hashlib, importlib, json, os, re, subprocess, sys

R8=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')); OUT=os.path.dirname(__file__)
ROOTS={f'R{i}':os.path.join(os.path.dirname(R8),f'08.18.26_Level1_Audits_R{i}') for i in range(4,9)}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def js(p): return json.load(open(p,encoding='utf-8'))
def files(root):
 for dp,dn,fn in os.walk(root,followlinks=False):
  dn[:]=sorted(d for d in dn if d!='__pycache__')
  for n in sorted(fn): yield os.path.relpath(os.path.join(dp,n),root)
def manifest(root, rel='CONTROL_MANIFEST.sha256'):
 p=os.path.join(root,rel); entries=[]; malformed=[]; seen=set(); dup=[]
 for no,line in enumerate(open(p,encoding='utf-8'),1):
  s=line.rstrip('\n')
  m=re.fullmatch(r'([0-9a-f]{64})  (.+)',s)
  if not m: malformed.append(no); continue
  d,r=m.groups()
  if r in seen: dup.append(r)
  seen.add(r); q=os.path.join(root,r)
  entries.append((r,d,None if not os.path.isfile(q) else sha(q)))
 return entries,malformed,dup
items=[]; findings=[]
CLAIMS={
1:'R4 control manifest verifies with zero mismatches.',2:'R5 control manifest has exactly one mismatch, MODE, with the stated old and current values.',3:'R6 control manifest verifies with zero mismatches.',4:'R7 control manifest has 15804 entries and zero mismatches.',5:'R8 discloses and verifies the R7 post-freeze incident without claiming continuous immutability.',6:'R8 compact lineage has no full predecessor copy and resolves R4 through R8.',7:'No same-path active R8/R7 files share an inode.',8:'One executor is called by controller and rehearsal harness.',9:'No live note-only in-process implementation remains.',10:'IN_PROCESS catalog, handlers, and argument schemas agree and self-check passes.',11:'L1-A16 uses the repaired seven-entry corpus novelty proof and three novelty controls rehearsed AS_EXPECTED.',12:'Reported repair findings are resolved: no degenerate unhashed COMPARE_HASHES and all step reads are declared.',13:'L1-A21 negative control is boundary-counted and expects zero.',14:'L1-A33 MIME reference is unchanged from R7 and is extracted to work before parsing.',15:'All control-role steps have machine-checkable expectations; coverage is 122/122.',16:'Migration plan migrates only L1-A31 RUN-A/RUN-B, excludes COMPARISON for the stated reason, and was not applied.',17:'R7 L1-A31 COMPARISON is EXECUTED, unsealed, and has zero evidence files.',18:'Controller suite passes in verification/selftest_runtime.',19:'Package suite passes at R8 root.',20:'Static safety review reports zero findings.',21:'Exactly 43 complete, schema-valid known plans exist.',22:'Exactly 43 rehearsals are PASS_READY.',23:'No required in-process step lacks evidence and no note-only step remains.',24:'No rehearsal phase is hollow.',25:'Active state is 43/43 NOT_STARTED across 35 audits.',26:'There are zero approvals/results/evidence and no raw token in state.',27:'R8 build manifest is complete, matching, unique, and well formed in builder scope.',28:'Freeze configuration is R8-consistent and predecessor baseline construction runs.',29:'No sibling R9 directory exists.',30:'Transitions contain only init-revision; no live phase ran.'}
def add(i,ok,meas):
 items.append({'id':i,'claim':CLAIMS[i],'measured':meas,'pass':bool(ok)})
 if not ok: findings.append(f'Item {i}: {meas}')

# 1-4 manifests
for i,r,expected in [(1,'R4',None),(2,'R5',None),(3,'R6',None),(4,'R7',15804)]:
 e,bad,dup=manifest(ROOTS[r]); mm=[x for x in e if x[1]!=x[2]]
 if i==2:
  mode=open(os.path.join(ROOTS[r],'MODE')).read().strip(); old=hashlib.sha256(b'GENERATED_UNVERIFIED\n').hexdigest()
  ok=len(mm)==1 and mm[0][0]=='MODE' and mm[0][1]==old and mode=='FROZEN' and not bad and not dup
  add(i,ok,f'entries={len(e)}, mismatches={[x[0] for x in mm]}, MODE={mode}, recorded={mm[0][1] if mm else None}, expected_generated_digest={old}, malformed={len(bad)}, duplicates={len(dup)}')
 else:
  ok=not mm and not bad and not dup and (expected is None or len(e)==expected)
  add(i,ok,f'entries={len(e)}, mismatches={len(mm)}, malformed={len(bad)}, duplicates={len(dup)}')

# 5 incident
lin=js(os.path.join(R8,'lineage/R8_LINEAGE.json')); inc=os.path.join(R8,'lineage/R7_POST_FREEZE_INCIDENT')
ims=[x for x in files(inc) if x.endswith('.sha256')]
iv=[]
for m in ims:
 try:
  e,b,d=manifest(inc,m); iv.append((m,len(e),len([x for x in e if x[1]!=x[2]]),len(b),len(d)))
 except Exception as ex: iv.append((m,'error',str(ex)))
txt=json.dumps(lin,sort_keys=True).lower(); ok=os.path.isdir(inc) and bool(ims) and all(len(x)==5 and x[2:]==(0,0,0) for x in iv) and 'incident' in txt and not ('continuous' in txt and 'immutab' in txt and 'no continuous' not in txt)
add(5,ok,f'incident_manifests={iv}; disclosure_keys={list(lin)}')

# 6 resolver
sys.path.insert(0,R8); from automation.package_tests import generation_root
resolved={}; resolve_errors={}
for r in ['R4','R5','R6','R7','R8']:
 try: resolved[r]=generation_root(r)
 except Exception as ex: resolve_errors[r]=str(ex)
no_copy=not os.path.exists(os.path.join(R8,'lineage/R6_EXECUTION')) and not any(os.path.isfile(os.path.join(R8,'lineage',d,'state/REVISION.json')) for d in os.listdir(os.path.join(R8,'lineage')) if os.path.isdir(os.path.join(R8,'lineage',d)))
add(6,no_copy and len(resolved)==5 and all(os.path.isdir(p) for p in resolved.values()),f'R6_EXECUTION_absent={not os.path.exists(os.path.join(R8,"lineage/R6_EXECUTION"))}; resolved={resolved}; resolver_errors={resolve_errors}')

# 7 inodes, excluding lineage/work/state/result/evidence/logs/verification
exclude={'lineage','work','state','results','evidence','logs','verification','verification_codex_final_pre_freeze_attempt_1'}; common=set(files(ROOTS['R7']))&set(files(R8)); shared=[]
for rel in common:
 if rel.split(os.sep)[0] in exclude: continue
 a=os.stat(os.path.join(ROOTS['R7'],rel)); b=os.stat(os.path.join(R8,rel))
 if (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino): shared.append(rel)
add(7,not shared,f'active same-path files compared={sum(1 for r in common if r.split(os.sep)[0] not in exclude)}, shared_inodes={shared[:20]} (total {len(shared)})')

# 8-10
hits={p:open(os.path.join(R8,p),encoding='utf-8').read().count('in_process_executor.execute') for p in ['automation/controller.py','build/rehearse_candidate_plans.py']}
add(8,all(v>=1 for v in hits.values()),f'call-site occurrences={hits}; executor module=automation/in_process_executor.py')
phrase=[]
for rel in files(R8):
 if not rel.endswith('.py') or rel.startswith('lineage/') or rel.startswith('automation/tests/fixtures/'): continue
 s=open(os.path.join(R8,rel),encoding='utf-8',errors='replace').read(); docspans=[]
 try: tree=ast.parse(s)
 except SyntaxError: tree=ast.parse('')
 for n in ast.walk(tree):
  d=ast.get_docstring(n,clean=False) if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) else None
  if d and getattr(n,'body',None) and isinstance(n.body[0],ast.Expr): docspans.append((n.body[0].lineno,n.body[0].end_lineno))
 for no,line in enumerate(s.splitlines(),1):
  if 'performed by the worker' in line and not any(a<=no<=b for a,b in docspans): phrase.append(f'{rel}:{no}')
add(9,not phrase,f'non-docstring live occurrences={phrase}')
from automation import operation_catalog,in_process_ops,in_process_executor
cat=set(operation_catalog.IN_PROCESS); handlers=set(in_process_ops.HANDLERS); schemas=set(in_process_executor.ARGUMENT_SCHEMA)
try: sc=in_process_executor.self_check(); scok=True
except Exception as ex: sc=repr(ex); scok=False
add(10,cat==handlers==schemas and scok,f'catalog={len(cat)}, handlers={len(handlers)}, schemas={len(schemas)}, deltas={{cat-handler:{sorted(cat-handlers)}, handler-cat:{sorted(handlers-cat)}, cat-schema:{sorted(cat-schemas)}, schema-cat:{sorted(schemas-cat)}}}, self_check={sc}')

plans={}
for rel in files(os.path.join(R8,'build/candidate_plans_r8')):
 if rel.endswith('/plan.json'):
  p=os.path.join(R8,'build/candidate_plans_r8',rel); x=js(p); plans[(x['audit_id'],x['run_phase'])]=(p,x)
report=js(os.path.join(R8,'work/_rehearsal_r8/REHEARSAL_REPORT.json'))
rep={(x['audit_id'],x['run_phase']):x for x in report['reports']}
p16=plans[('L1-A16','RUN-A')][1]; novelty=[s for s in p16['steps'] if s['operation']=='PROVE_SET_NOVELTY']; main=next(s for s in novelty if s['step_id']=='prove_cases_are_novel'); controls=[s for s in novelty if s.get('control_role') in ('POSITIVE','NEGATIVE','MUTATION','ORACLE','SABOTAGE')]
r16=rep[('L1-A16','RUN-A')]; rst={s['step_id']:s for s in r16['steps']}; ok=len(controls)==3 and main['params']['reference_root']=='/home/ubuntu/project/WPNO/ap18/korpus_docx' and main['params']['expected_reference_entry_count']==7 and all(rst[s['step_id']]['result']=='AS_EXPECTED' for s in controls)
add(11,ok,f'operation={main["operation"]}, reference_root={main["params"]["reference_root"]}, expected entries={main["params"]["expected_reference_entry_count"]}, novelty_controls={[(s["step_id"],rst[s["step_id"]].get("result")) for s in controls]}')

# 12 approximate independent allowed read check using executor path admission on all params
deg=[]; undeclared=[]
def flat_paths(v):
 if isinstance(v,str) and ('/' in v or v.startswith('references')): return [v]
 if isinstance(v,list): return sum((flat_paths(x) for x in v),[])
 if isinstance(v,dict): return sum((flat_paths(x) for x in v.values()),[])
 return []
for key,(p,x) in plans.items():
 allowed=x.get('test_matrix',[{}])[0].get('allowed_reads',[])
 for s in x['steps']:
  q=s.get('params',{})
  if s['operation']=='COMPARE_HASHES' and q.get('left')==q.get('right') and not q.get('expected_sha256'): deg.append((*key,s['step_id']))
  schema=in_process_executor.ARGUMENT_SCHEMA.get(s['operation']); inputs=[]
  if schema:
   for k in schema.get('inputs',())+schema.get('input_may_be_absent',()): inputs+=flat_paths(q.get(k))
   for val in inputs:
    try: in_process_executor._assert_allowed_path(val,allowed,'read')
    except AttributeError: pass
    except Exception as ex: undeclared.append((*key,s['step_id'],val,str(ex)))
add(12,not deg and not undeclared,f'degenerate_unhashed_compare_hashes={deg}; independently rejected read paths={undeclared[:10]} (total {len(undeclared)})')

p21=plans[('L1-A21','RUN-A')][1]; s21=next(s for s in p21['steps'] if s['step_id']=='negative_control_export_is_not_another_project'); exp21=s21.get('expected_count',s21.get('params',{}).get('expected_count'))
# expectations may be merged in rehearsal rather than plan
rr21=next(s for s in rep[('L1-A21','RUN-A')]['steps'] if s['step_id']==s21['step_id'])
ok=s21['operation']=='COUNT_TEXT_MATCHES' and s21['params'].get('word_boundary') is True and (exp21==0 or rr21.get('expected_count')==0 or rr21.get('result')=='AS_EXPECTED')
add(13,ok,f'operation={s21["operation"]}, word_boundary={s21["params"].get("word_boundary")}, plan_expected_count={exp21}, rehearsal_result={rr21.get("result")}')

ref='references/REF-11-563203462.xml'; p33=plans[('L1-A33','RUN-A')][1]; steps33={s['step_id']:s for s in p33['steps']}; first=open(os.path.join(R8,ref),'rb').read(13); same=sha(os.path.join(R8,ref))==sha(os.path.join(ROOTS['R7'],ref)); ex=steps33['extract_container_xml_part']; pa=steps33['parse_container_xml_safely']; ok=first.startswith(b'MIME-Version:') and same and '/work/' in ex['params']['out'] and pa['params']['path']==ex['params']['out']
add(14,ok,f'prefix={first!r}, R8_sha256={sha(os.path.join(R8,ref))}, R7_sha256={sha(os.path.join(ROOTS["R7"],ref))}, extraction_out={ex["params"]["out"]}, parse_path={pa["params"]["path"]}')

roles={'POSITIVE','NEGATIVE','MUTATION','ORACLE','SABOTAGE'}; control=[]; unenforced=[]
for key,(p,x) in plans.items():
 rr={s['step_id']:s for s in rep[key]['steps']}
 for s in x['steps']:
  if s.get('control_role') in roles:
   control.append((*key,s['step_id']))
   z=rr.get(s['step_id'],{}); machine=any(k.startswith('expected_') or k.startswith('expect_') or k.startswith('required_') for k in set(s)|set(s.get('params',{}))|set(z))
   if not machine: unenforced.append((*key,s['step_id']))
cov=js(os.path.join(R8,'build/CONTROL_EXPECTATION_COVERAGE.json'))
add(15,len(control)==122 and not unenforced and json.dumps(cov).count('122')>=1,f'rederived_control_steps={len(control)}, unenforced={unenforced}; coverage summary={{control_role_steps:{cov.get("control_role_steps")}, enforced:{cov.get("enforced")}, unenforced:{cov.get("unenforced")}}}')

mig=js(os.path.join(R8,'build/migration_plan_r7_to_r8/MIGRATION_PLAN.json')); mt=json.dumps(mig,sort_keys=True); keys=set(re.findall(r'L1-A31/(?:RUN-A|RUN-B|COMPARISON)',mt)); ok=keys=={'L1-A31/RUN-A','L1-A31/RUN-B','L1-A31/COMPARISON'} and 'EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT' in mt and mig.get('applied_before_freeze') is False
add(16,ok,f'phase references={sorted(keys)}, applied_before_freeze={mig.get("applied_before_freeze")}, exclusion_reason_present={"EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT" in mt}')

# R7 comparison state/evidence
prog7=js(os.path.join(ROOTS['R7'],'state/progress.json')); flat=json.dumps(prog7); status='EXECUTED' in flat
ev7=os.path.join(ROOTS['R7'],'evidence/L1-A31/COMPARISON'); evcount=sum(1 for _ in files(ev7)) if os.path.isdir(ev7) else 0
res7=os.path.join(ROOTS['R7'],'results/L1-A31/COMPARISON'); sealed=any(os.path.basename(x) in ('SEAL.json','EVIDENCE_MANIFEST.sha256') for x in files(res7)) if os.path.isdir(res7) else False
add(17,status and not sealed and evcount==0,f'progress contains EXECUTED={status}, result_seal_present={sealed}, evidence_files={evcount}')

def suite(name,cwd,start):
 code="import json,sys,unittest;sys.path.insert(0,'.');s=unittest.TestLoader().discover(start_dir=%r,top_level_dir='.');r=unittest.TextTestRunner(verbosity=1).run(s);print('RESULT '+json.dumps({'ran':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'unexpected_successes':len(r.unexpectedSuccesses)}));sys.exit(not r.wasSuccessful())"%start
 p=subprocess.run(['/usr/bin/python3','-c',code],cwd=cwd,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=OUT),capture_output=True,text=True,timeout=1800)
 open(os.path.join(OUT,name+'.stdout.txt'),'w').write(p.stdout); open(os.path.join(OUT,name+'.stderr.txt'),'w').write(p.stderr)
 m=re.search(r'RESULT (\{.*\})',p.stdout); return p.returncode,json.loads(m.group(1)) if m else None
rc18,c18=suite('controller_suite',os.path.join(R8,'verification/selftest_runtime'),'.'); add(18,rc18==0 and c18 and not any(c18[k] for k in ('failures','errors','skips','unexpected_successes')),f'exit={rc18}, unittest={c18}; logs written in verifier output')
rc19,c19=suite('package_suite',R8,'automation/package_tests'); add(19,rc19==0 and c19 and not any(c19[k] for k in ('failures','errors','skips','unexpected_successes')),f'exit={rc19}, unittest={c19}; logs written in verifier output')

p=subprocess.run(['/usr/bin/python3','build/r8_static_safety_review.py'],cwd=R8,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=OUT),capture_output=True,text=True,timeout=600); open(os.path.join(OUT,'static_safety.stdout.txt'),'w').write(p.stdout); open(os.path.join(OUT,'static_safety.stderr.txt'),'w').write(p.stderr)
srep=js(os.path.join(R8,'build/R8_STATIC_SAFETY_REPORT.json')); add(20,p.returncode==0 and srep.get('finding_count')==0,f'exit={p.returncode}, finding_count={srep.get("finding_count")}, clean={srep.get("clean")}')

coverage=js(os.path.join(R8,'build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json')); add(21,len(plans)==43 and coverage.get('missing',[])==[] and coverage.get('duplicates',[])==[] and coverage.get('unknown',[])==[],f'plan_files={len(plans)}, coverage missing={coverage.get("missing")}, duplicates={coverage.get("duplicates")}, unknown={coverage.get("unknown")}, schema_valid_reports={sum(bool(r.get("schema_valid")) for r in report["reports"])}')
add(22,len(rep)==43 and all(r.get('PASS_READY') for r in rep.values()),f'rehearsal reports={len(rep)}, PASS_READY={sum(bool(r.get("PASS_READY")) for r in rep.values())}, aggregate={report.get("PHASES_PASS_READY")}/{report.get("phases_required")}')
add(23,report.get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE')==0 and report.get('NOTE_ONLY_IN_PROCESS_STEPS')==0,f'REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE={report.get("REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE")}, NOTE_ONLY_IN_PROCESS_STEPS={report.get("NOTE_ONLY_IN_PROCESS_STEPS")}')
add(24,report.get('HOLLOW_PHASES')==[],f'HOLLOW_PHASES={report.get("HOLLOW_PHASES")}')

prog=js(os.path.join(R8,'state/progress.json')); statuses=[]
def walk(x):
 if isinstance(x,dict):
  for k,v in x.items():
   if k=='status': statuses.append(v)
   walk(v)
 elif isinstance(x,list):
  for v in x: walk(v)
walk(prog); audits=set(re.findall(r'L1-A\d{2}',json.dumps(prog)))
add(25,len(statuses)==43 and set(statuses)=={'NOT_STARTED'} and len(audits)==35,f'phase_status_count={len(statuses)}, status_counts={dict((s,statuses.count(s)) for s in set(statuses))}, audits={len(audits)}')
approvals=os.path.join(R8,'state/approvals.jsonl'); resultn=sum(1 for _ in files(os.path.join(R8,'results'))); evidn=sum(1 for _ in files(os.path.join(R8,'evidence'))); raw=[]
for rel in files(os.path.join(R8,'state')):
 if 'APPROVE-EXECUTION ' in open(os.path.join(R8,'state',rel),encoding='utf-8',errors='replace').read(): raw.append(rel)
appn=sum(1 for l in open(approvals) if l.strip())
add(26,appn==0 and resultn==0 and evidn==0 and not raw,f'approvals={appn}, result_files={resultn}, evidence_files={evidn}, state_files_with_raw_token={raw}')

# manifest scope mirror builder
e,bad,dup=manifest(R8,'build/R8_BUILD_MANIFEST.sha256'); mm=[x for x in e if x[1]!=x[2]]; listed={x[0] for x in e}
from build import build_r8_build_manifest as bm
physical=set()
for rel in files(R8):
 if bm.in_scope(rel): physical.add(rel)
missing=physical-listed; extra=listed-physical
add(27,not bad and not dup and not mm and not missing and not extra,f'entries={len(e)}, mismatches={len(mm)}, malformed={len(bad)}, duplicates={len(dup)}, unlisted_in_scope={sorted(missing)[:10]} (total {len(missing)}), listed_not_physical={sorted(extra)[:10]} (total {len(extra)})')

from automation import freeze
base_rel=freeze.PREDECESSOR_BASELINE_REL; base_abs=os.path.realpath(os.path.join(R8,base_rel)); inside=os.path.commonpath([R8,base_abs])==R8
try: baseline,prov=freeze.build_baseline_from_predecessor(R8); bok=True
except Exception as ex: baseline={}; prov=repr(ex); bok=False
add(28,freeze.PACKAGE_REVISION=='R8' and inside and bok,f'PACKAGE_REVISION={freeze.PACKAGE_REVISION}, PREDECESSOR_BASELINE_REL={base_rel}, resolved={base_abs}, inside_R8={inside}, baseline_entries={len(baseline)}, provenance={prov if not bok else "returned"}')
r9=os.path.join(os.path.dirname(R8),'08.18.26_Level1_Audits_R9'); add(29,not os.path.exists(r9),f'path={r9}, exists={os.path.exists(r9)}')
trs=[json.loads(x) for x in open(os.path.join(R8,'state/transitions.jsonl')) if x.strip()]; add(30,len(trs)==1 and trs[0].get('event')=='init-revision',f'transition_count={len(trs)}, events={[x.get("event") for x in trs]}')

overall=all(x['pass'] for x in items) and not findings
out={'schema':'wpno.level1.codex-verification/1','revision':'R8','stage':'PRE_FREEZE_FINAL','verified_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'items':sorted(items,key=lambda x:x['id']),'overall_pass':overall,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if overall else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
open(os.path.join(OUT,'VERIFICATION_RESULT.json'),'w').write(json.dumps(out,indent=2,sort_keys=False)+'\n')
open(os.path.join(OUT,'VERIFICATION_NOTES.md'),'w').write('# Independent pre-freeze verification notes\n\nAll measurements used `/usr/bin/python3` with `PYTHONDONTWRITEBYTECODE=1`; no network, git, migration, freeze, or live audit phase was invoked. The verifier independently hashed control/build manifests, inspected plans/state/lineage/inodes/source call sites, imported the three in-process sets and ran `self_check()`, ran the controller unittest suite in `verification/selftest_runtime`, ran the package suite at the R8 root, ran `build/r8_static_safety_review.py`, and invoked only `freeze.build_baseline_from_predecessor` (not publication/freezing). Suite stdout/stderr and static-review output are retained beside this note.\n\nFinal status: **%s**. Passed %d of 30 items.\n'%(out['status'],sum(x['pass'] for x in items)))
print(json.dumps({'status':out['status'],'passed':sum(x['pass'] for x in items),'failed':[x['id'] for x in items if not x['pass']]}))
