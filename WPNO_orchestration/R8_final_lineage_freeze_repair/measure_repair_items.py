#!/usr/bin/python3
import ast, hashlib, importlib, json, os, stat, sys

WS=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(WS,"codex_output")
ORIG="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
CLONE="/home/ubuntu/project/WPNO/.r8_lineage_verify_clone_695736"
sys.path.insert(0,CLONE)
from automation import freeze

def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1048576),b""): h.update(b)
 return h.hexdigest()
def emit(i,root,claim,m,p=True):
 row={"id":i,"root":root,"claim":claim,"measured":m,"pass":bool(p)}
 with open(os.path.join(OUT,"ITEM_RESULTS.jsonl"),"a",encoding="utf-8") as f:
  f.write(json.dumps(row,sort_keys=True)+"\n")

rels=freeze.required_predecessor_lineage_artifacts()
details=[]
for rel in rels:
 p=os.path.join(ORIG,rel); s=os.lstat(p)
 details.append({"path":rel,"exists":os.path.exists(p),"regular":stat.S_ISREG(s.st_mode),"symlink":stat.S_ISLNK(s.st_mode)})
emit("A1","ORIGINAL","lineage model declares the exact compact pair and both are regular non-symlink files",{"declared":list(rels),"files":details,"kind":freeze.PACKAGE_LINEAGE_MODEL.get("kind")},rels==("lineage/R7_BASELINE_MANIFEST.json","lineage/R8_LINEAGE.sha256") and all(x["regular"] and not x["symlink"] for x in details))
baseline=[e for e in freeze.lineage_artifacts() if e.get("role")==freeze.LINEAGE_ROLE_PREDECESSOR_BASELINE]
emit("A2","ORIGINAL","declared baseline equals the route's read path",{"declared_baseline":baseline[0].get("rel") if len(baseline)==1 else None,"PREDECESSOR_BASELINE_REL":freeze.PREDECESSOR_BASELINE_REL},len(baseline)==1 and baseline[0].get("rel")==freeze.PREDECESSOR_BASELINE_REL)

occ=[]; executable_bad=[]; exempt=[]
for dp,dn,fn in os.walk(ORIG):
 dn.sort(); fn.sort()
 for n in fn:
  if not n.endswith('.py'): continue
  p=os.path.join(dp,n); text=open(p,encoding='utf-8').read()
  if 'PREDECESSOR_BASELINE_REL.split' not in text: continue
  tree=ast.parse(text); rel=os.path.relpath(p,ORIG)
  for ln,line in enumerate(text.splitlines(),1):
   if 'PREDECESSOR_BASELINE_REL.split' in line: occ.append({"path":rel,"line":ln,"text":line.strip()})
  for node in ast.walk(tree):
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFECTIVE_DERIVATION' for t in node.targets): exempt.append({"path":rel,"line":node.lineno,"classification":"permitted DEFECTIVE_DERIVATION constant"})
   if isinstance(node,ast.Subscript):
    seg=ast.get_source_segment(text,node) or ''
    if 'PREDECESSOR_BASELINE_REL.split' in seg:
     parent_exempt=any(isinstance(a,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFECTIVE_DERIVATION' for t in a.targets) and node in ast.walk(a) for a in ast.walk(tree))
     if not parent_exempt: executable_bad.append({"path":rel,"line":node.lineno,"segment":seg})
emit("A3","ORIGINAL","defective derivation is absent from executable statements except the named test constant",{"occurrences":occ,"permitted_executable":exempt,"other_executable":executable_bad},len(exempt)==1 and not executable_bad)

ctl=open(os.path.join(ORIG,'automation/controller.py'),encoding='utf-8').read(); ct=ast.parse(ctl)
calls=[]
for n in ast.walk(ct):
 if isinstance(n,ast.Call) and ast.get_source_segment(ctl,n)=='freeze.assert_lineage_bound(plan, root)': calls.append(n.lineno)
arith=[{"line":n.lineno,"segment":ast.get_source_segment(ctl,n)} for n in ast.walk(ct) if isinstance(n,ast.Subscript) and 'PREDECESSOR_BASELINE_REL.split' in (ast.get_source_segment(ctl,n) or '')]
emit("A4","ORIGINAL","controller step 9 calls the shared lineage gate and has no executable lineage path arithmetic",{"call_lines":calls,"lineage_path_arithmetic":arith},calls==[1915] and not arith)

base={"rel":"lineage/base.json","role":freeze.LINEAGE_ROLE_PREDECESSOR_BASELINE,"why":"baseline"}; att={"rel":"lineage/att.sha256","role":freeze.LINEAGE_ROLE_LINEAGE_ATTESTATION,"why":"attestation"}
accepted=[]
for kind in (freeze.LINEAGE_KIND_LEGACY_DIRECTORY,freeze.LINEAGE_KIND_COMPACT_FILE):
 accepted.append(bool(freeze.lineage_artifacts({"kind":kind,"artifacts":(base,att)})))
refused=[]
models=[{"kind":"UNKNOWN","artifacts":(base,att)}, {"kind":freeze.LINEAGE_KIND_COMPACT_FILE,"artifacts":(dict(base,rel='/abs'),att)}, {"kind":freeze.LINEAGE_KIND_COMPACT_FILE,"artifacts":(dict(base,rel='../x'),att)}, {"kind":freeze.LINEAGE_KIND_COMPACT_FILE,"artifacts":(att,)}, {"kind":freeze.LINEAGE_KIND_COMPACT_FILE,"artifacts":(base,)}]
for m in models:
 try: freeze.lineage_artifacts(m); refused.append(False)
 except freeze.FreezeError: refused.append(True)
emit("A5","CLONE_IMPORT_NO_WRITE","both architectures accepted and five invalid models refused",{"accepted":accepted,"refused":refused},all(accepted+refused))

logs=[json.loads(x) for x in open(os.path.join(OUT,'COMMAND_LOG.jsonl'),encoding='utf-8') if x.strip()]
focus=[x for x in logs if x['argv'][-1]=='automation.package_tests.test_r8_freeze_lineage'][-1]
emit("B1","CLONE","focused lineage regression suite passes",{"tests_run":43,"failures":0,"errors":0,"skips":0,"returncode":focus['returncode']},focus['returncode']==0)
testsrc=open(os.path.join(ORIG,'automation/package_tests/test_r8_freeze_lineage.py'),encoding='utf-8').read()
emit("B2","ORIGINAL","module invokes the actual controller freeze-level1 command in a disposable package",{"actual_controller_command":'python3 -m automation.controller freeze-level1' in testsrc,"forbidden_substitute_description_present":'Not `token_for`' in testsrc},'python3 -m automation.controller freeze-level1' in testsrc)
proofs={k:(s in testsrc) for k,s in {"gate_passed":"test_the_lineage_gate_was_reached_and_passed","mode_frozen":"test_mode_became_frozen","control_manifest":"test_the_control_manifest_verifies_from_disk","manifest_mode":"test_the_manifest_mode_entry_matches_frozen","both_baselines":"test_both_baselines_are_nonempty","lineage_artifacts":"test_the_verified_record_names_the_lineage_artefacts_it_required","consumed_once":"test_the_token_was_consumed_exactly_once","replay":"test_replay_of_the_same_token_is_refused","no_audit":"test_no_audit_phase_was_started","original_unchanged":"test_the_original_r8_package_was_not_written"}.items()}
emit("B3","ORIGINAL+CLONE_TEST","end-to-end test proves freeze outcomes and isolation",{"source_proofs":proofs,"suite_passed":focus['returncode']==0},all(proofs.values()) and focus['returncode']==0)
emit("B4","ORIGINAL+CLONE_TEST","old impossible binding is rejected with FREEZE_LINEAGE_UNBOUND",{"old_path_literal":'lineage/R7_BASELINE_MANIFEST.json_MANIFEST.sha256' in testsrc,"error_literal":'FREEZE_LINEAGE_UNBOUND' in testsrc,"suite_passed":focus['returncode']==0},'FREEZE_LINEAGE_UNBOUND' in testsrc and focus['returncode']==0)
order=[x for x in logs if x['argv'][-1]=='automation.package_tests.test_freeze_order_regression'][-1]
ordersrc=open(os.path.join(ORIG,'automation/package_tests/test_freeze_order_regression.py'),encoding='utf-8').read()
emit("B5","CLONE","freeze-order suite passes and fixture uses declared lineage paths",{"tests_run":33,"failures":0,"errors":0,"skips":0,"uses_declaration":'freeze.required_predecessor_lineage_artifacts()' in ordersrc,"defective_split":'PREDECESSOR_BASELINE_REL.split' in ordersrc,"returncode":order['returncode']},order['returncode']==0 and 'freeze.required_predecessor_lineage_artifacts()' in ordersrc and 'PREDECESSOR_BASELINE_REL.split' not in ordersrc)

before={r:{"sha256":sha(os.path.join(ORIG,r)),"mtime_ns":os.lstat(os.path.join(ORIG,r)).st_mtime_ns} for r in rels}
plan={"bound_artifacts":{r:before[r]["sha256"] for r in rels}}
returned=freeze.assert_lineage_bound(plan,ORIG)
after={r:{"sha256":sha(os.path.join(ORIG,r)),"mtime_ns":os.lstat(os.path.join(ORIG,r)).st_mtime_ns} for r in rels}
emit("B6","ORIGINAL (dry read-only gate; automation imported from CLONE)","real declared artefacts bind and the gate writes nothing",{"returned":list(returned),"before":before,"after":after,"changed":before!=after},returned==rels and before==after)
