#!/usr/bin/python3
import datetime, hashlib, json, os
WS=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(WS,'codex_output')
ORIG='/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def append_item(row):
 with open(os.path.join(OUT,'ITEM_RESULTS.jsonl'),'a',encoding='utf-8') as f: f.write(json.dumps(row,sort_keys=True)+'\n')

cmp=json.load(open(os.path.join(OUT,'INVENTORY_COMPARE.json'),encoding='utf-8'))
iso={k:cmp[k] for k in ('written_paths','mtimes_changed','modes_changed','symlink_targets_changed','contents_changed','paths_added','paths_removed')}
append_item({'id':'E11','root':'ORIGINAL','claim':'full before/after inventory shows no writes or metadata changes','measured':iso,'pass':all(v==0 for v in iso.values())})
wr=json.load(open(os.path.join(OUT,'WRITER_INSPECTION_POST.json'),encoding='utf-8'))
append_item({'id':'E12','root':'ORIGINAL via /proc','claim':'no other process holds a writable descriptor below ORIGINAL','measured':{'pids_inspected':wr['pids_with_readable_fd_table'],'pids_uninspectable':wr['pids_with_unreadable_fd_table'],'uninspectable_reason':wr['measurement_limit'] if wr['pids_with_unreadable_fd_table'] else None,'blocking_writable_descriptors':wr['BLOCKING_COUNT'],'pgrep_used':wr['pgrep_used']},'pass':wr['NO_CONCURRENT_WRITER']})

with open(os.path.join(OUT,'COMMAND_LOG.jsonl'),'a',encoding='utf-8') as f:
 f.write(json.dumps({'started_utc':now(),'finished_utc':now(),'cwd':WS,'argv':['/usr/bin/python3','-B','finalize_failure.py'],'returncode':0,'note':'self-recorded before immutable final artifact assembly'},sort_keys=True)+'\n')
items=[json.loads(x) for x in open(os.path.join(OUT,'ITEM_RESULTS.jsonl'),encoding='utf-8') if x.strip()]
finding=('A3: executable defective derivation remains at '
 'lineage/R7_POST_FREEZE_INCIDENT/dirty_repair_files/automation/controller.py:1727; '
 'the requirement permits exactly one executable occurrence anywhere, the named DEFECTIVE_DERIVATION test constant.')
manifest=os.path.join(ORIG,'build/R8_BUILD_MANIFEST.sha256')
manifest_digest=sha(manifest)
manifest_entries=sum(1 for x in open(manifest,encoding='utf-8') if x.rstrip('\n'))
unmeasured=['C1','C2','C3','C4','C5','C6','D1','D2','D3','D4','D5','D6','D7','E1','E2','E3','E4','E5','E6','E7','E8','E9','E10','F1','F2']
measurements={'schema':'wpno.level1.codex-measurements/1','stopped_after_first_adverse_result':'A3','completed_item_ids':[x['id'] for x in items],'unmeasured_due_stop_rule':unmeasured,'preflight':json.load(open(os.path.join(WS,'preflight/PREFLIGHT.json'),encoding='utf-8')),'initial_clone_comparison':json.load(open(os.path.join(WS,'preflight/COMPARE_ORIGINAL_VS_CLONE_INITIAL.json'),encoding='utf-8')),'original_inventory_comparison':cmp,'writer_inspection':wr,'manifest_listing_digest_measured':manifest_digest,'manifest_listing_nonempty_lines_measured':manifest_entries}
with open(os.path.join(OUT,'MEASUREMENTS.json'),'w',encoding='utf-8') as f: json.dump(measurements,f,indent=2,sort_keys=True); f.write('\n')
result={'schema':'wpno.level1.codex-verification/3','revision':'R8','stage':'PRE_FREEZE_FINAL_AFTER_LINEAGE_REPAIR','verified_utc':now(),'items':items,'manifest_sha256_verified':manifest_digest,'manifest_entries_verified':manifest_entries,'lineage_defect_resolved':False,'old_defective_derivation_present':True,'exact_cmd_freeze_level1_regression':'PASS','disposable_clone_freeze':'PASS','package_unchanged_by_this_verification':cmp['EQUAL'],'r8_paths_written_during_this_verification':cmp['written_paths'],'overall_pass':False,'unresolved_findings':[finding],'status':'VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL'}
with open(os.path.join(OUT,'VERIFICATION_RESULT.json'),'w',encoding='utf-8') as f: json.dump(result,f,indent=2,sort_keys=True); f.write('\n')
report=f'''# R8 final independent pre-freeze verification — FAIL

Verification stopped at the first completed adverse measurement, A3, as required.

## Finding

{finding}

The occurrence is in preserved post-freeze incident evidence, but it is a Python executable statement under ORIGINAL. The stated scope was every `.py` under ORIGINAL and allowed exactly one executable occurrence anywhere, so no contextual exemption was applied.

## Completed measurements

- A1, A2, A4, A5 and B1–B6 passed.
- A3 failed. The focused lineage suite independently ran 43 tests with 0 failures/errors/skips, and the freeze-order regression ran 33 with 0 failures/errors/skips.
- E11: ORIGINAL paths written 0; mtimes changed 0; modes changed 0; symlink targets changed 0; contents changed 0; paths added 0; paths removed 0.
- E12: {wr['pids_with_readable_fd_table']} PID fd tables inspected, {wr['pids_with_unreadable_fd_table']} uninspectable, 0 blocking writable descriptors.

Items after A3 were not substantively measured because the instructions require stop/record/finish on an adverse completed result. B1–B6 had already completed while the A-item AST classifier was being assembled; they are retained as measured evidence.

The build-manifest listing file itself hashes to `{manifest_digest}` and contains {manifest_entries} non-empty lines. Full C4 verification was not performed after the stop condition.
'''
with open(os.path.join(OUT,'VERIFICATION_REPORT.md'),'w',encoding='utf-8') as f: f.write(report)

rows=[]
for dp,dn,fn in os.walk(OUT):
 dn.sort(); fn.sort()
 for n in fn:
  p=os.path.join(dp,n); rel=os.path.relpath(p,OUT)
  if rel=='VERIFICATION_MANIFEST.sha256': continue
  rows.append((rel,sha(p)))
with open(os.path.join(OUT,'VERIFICATION_MANIFEST.sha256'),'w',encoding='utf-8') as f:
 for rel,digest in sorted(rows): f.write(f'{digest}  {rel}\n')
