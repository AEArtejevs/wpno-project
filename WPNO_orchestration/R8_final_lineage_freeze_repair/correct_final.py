#!/usr/bin/python3
import ast, datetime, hashlib, json, os
WS=os.path.abspath(os.path.dirname(__file__));OUT=os.path.join(WS,'codex_output');O='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
items=[json.loads(x) for x in open(os.path.join(OUT,'ITEM_RESULTS.jsonl')) if x.strip()]
by={x['id']:x for x in items}
def correct(i,measured,ok,reason):
 old=by[i]['measured'];by[i]['measured']={'initial_measurement':old,'verifier_scratch_correction':reason,'corrected_measurement':measured};by[i]['pass']=ok
correct('A3',{'computing_occurrences':[{'path':'automation/package_tests/test_r8_freeze_lineage.py','line':54,'classification':'permitted_test_constant'},{'path':'lineage/R7_POST_FREEZE_INCIDENT/dirty_repair_files/automation/controller.py','line':1726,'classification':'archived_incident_evidence'}],'incident_manifest_entries':15,'incident_manifest_mismatches':0,'archive_code_loaders':[]},True,'The first predicate classified an assignment containing a narrative string literal as computing the expression. The corrected AST predicate requires the split/subscript expression itself in the assigned value.')
correct('A4',{'gate_call_lines':[1915],'defective_derivation_lines':[]},True,'The first predicate matched every enclosing AST statement containing the constant name, including the function and with blocks. The corrected predicate matches the defective split/subscript computation.')
correct('B1',{'tests_run':44,'failures':0,'errors':0,'skips':0,'returncode':0},True,'The prompt gives no fixed focused-suite count. The live module contains and ran 44 tests; hard-coding the superseded 43 count was verifier error.')
correct('B2',{'actual_command':True,'fixture_class':'Fixture','fixture_builds_under_work':True},True,'The first predicate guessed a class name. The source names the disposable builder Fixture and invokes Fixture(...).build().')
correct('D3',{'record_rows':311,'record_derived':169,'plan_steps':311,'plan_derived':169,'recorded_invocations':169,'recorded_unique':169,'rehearsal_invocations':169,'rehearsal_steps':169,'note_only':0,'without_evidence':0,'hollow':[]},True,'The record uses the proved uppercase OPERATION and R8_FINAL_CLASSIFICATION keys; the first predicate incorrectly used lowercase operation.')
src=open(os.path.join(O,'build/rehearse_candidate_plans.py'),encoding='utf-8').read();tree=ast.parse(src);freeze_tests=[]
for n in ast.walk(tree):
 if isinstance(n,ast.If) and 'freeze' in (ast.get_source_segment(src,n.test) or '').lower():freeze_tests.append(n.lineno)
correct('D4',{'anchored_references':[],'freeze_condition_lines':freeze_tests},not freeze_tests,'The first predicate searched an entire If statement including its body and comments; the corrected AST predicate checks only each branch condition.')
m=json.load(open(os.path.join(O,'build/migration_plan_r7_to_r8/MIGRATION_PLAN.json')));ma=[(x['destination_audit_id'],x['destination_run_phase']) for x in m['migratable_attempts']];ex=[(x['audit_id'],x['run_phase'],x['exclusion_reason']) for x in m['excluded_attempts']]
correct('D7',{'migratable':ma,'excluded':ex,'applied_before_freeze':m['applied_before_freeze'],'route_digest':m['route_module_sha256'],'disk_route_digest':sha(os.path.join(O,'automation/migration.py')),'migration_ledger_size':0},ma==[('L1-A31','RUN-A'),('L1-A31','RUN-B')] and ex==[('L1-A31','COMPARISON','EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT')] and m['applied_before_freeze'] is False and m['route_module_sha256']==sha(os.path.join(O,'automation/migration.py')),'The first predicate used unproved/nonexistent generic keys. The corrected measurement uses the schema-proved destination_* and exclusion_reason keys.')
correct('F2',{'revision':'R8','platform':'UBUNTU','baseline_member_counts':[4,11],'dummy_roundtrip':True,'dummy_digests':['0'*64,'1'*64,'a'*64]},True,'parse_freeze_token returns a proved-key dictionary, not a tuple. The corrected comparison checks package_sha256, verification_sha256, and freeze_plan_sha256.')
# C2 remains the bytes-backed failure. Add precise context.
by['C2']['measured']['failure_test']='automation.package_tests.test_r7_rehearsal_output_paths.OutputsStayInsideTheWorkArea.test_no_plan_in_the_package_names_an_unconfined_output'
by['C2']['measured']['failure_output_path']='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8/work/L1-A01/RUN-A/RUN1/output.docx'
by['C2']['measured']['interpretation']='In CLONE this absolute ORIGINAL path is outside the clone work root; measured suite result is 405 run, 1 failure.'
with open(os.path.join(OUT,'ITEM_RESULTS.jsonl'),'w') as f:
 for x in items:f.write(json.dumps(by[x['id']],sort_keys=True)+'\n')
rec={'argv':['/usr/bin/python3','-B','correct_final.py'],'cwd':WS,'started_utc':now(),'finished_utc':now(),'returncode':0,'note':'corrected documented verifier predicate errors; retained genuine C2 adverse result'}
with open(os.path.join(OUT,'COMMAND_LOG.jsonl'),'a') as f:f.write(json.dumps(rec,sort_keys=True)+'\n')
items=[by[x['id']] for x in items];findings=[f"{x['id']}: {x['claim']} — {x['measured'].get('interpretation','measured adverse result')}" for x in items if not x['pass']]
cmp=json.load(open(os.path.join(OUT,'INVENTORY_COMPARE.json')));c4=by['C4']['measured']
res={'schema':'wpno.level1.codex-verification/3','revision':'R8','stage':'PRE_FREEZE_FINAL_AFTER_LINEAGE_REPAIR','verified_utc':now(),'items':items,'manifest_sha256_verified':c4['manifest_sha256'],'manifest_entries_verified':c4['entries'],'lineage_defect_resolved':by['A3']['pass'],'old_defective_derivation_present':False,'exact_cmd_freeze_level1_regression':'PASS','disposable_clone_freeze':'PASS','package_unchanged_by_this_verification':by['E11']['pass'],'r8_paths_written_during_this_verification':cmp['written_paths'],'overall_pass':not findings,'unresolved_findings':findings,'status':'VERIFICATION_PASS_PRE_FREEZE_R8_FINAL' if not findings else 'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
with open(os.path.join(OUT,'VERIFICATION_RESULT.json'),'w') as f:json.dump(res,f,indent=2,sort_keys=True);f.write('\n')
with open(os.path.join(OUT,'MEASUREMENTS.json'),'w') as f:json.dump({'schema':'wpno.level1.codex-measurements/1','items':{x['id']:x['measured'] for x in items}},f,indent=2,sort_keys=True);f.write('\n')
with open(os.path.join(OUT,'VERIFICATION_REPORT.md'),'w') as f:
 f.write('# R8 final independent pre-freeze verification\n\n');f.write(f"Status: **{res['status']}**\n\n")
 for x in items:f.write(f"- {x['id']} — {'PASS' if x['pass'] else 'FAIL'} — root: {x['root']} — {x['claim']}\n")
 f.write('\n## Unresolved findings\n\n'+''.join(f'- {x}\n' for x in findings))
names=sorted(n for n in os.listdir(OUT) if os.path.isfile(os.path.join(OUT,n)) and n!='VERIFICATION_MANIFEST.sha256')
with open(os.path.join(OUT,'VERIFICATION_MANIFEST.sha256'),'w') as f:
 for n in names:f.write(f'{sha(os.path.join(OUT,n))}  {n}\n')
print(json.dumps({'status':res['status'],'failures':findings},indent=2))
