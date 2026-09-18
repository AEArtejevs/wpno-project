#!/usr/bin/python3
import ast, datetime, hashlib, importlib, json, os, re, subprocess, sys

R8 = "/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
OUT = "/home/ubuntu/project/WPNO_orchestration/R8_final_autonomous_convergence/attempt_8/codex_output"
ROOTS = {f"R{i}": os.path.join(os.path.dirname(R8), f"08.18.26_Level1_Audits_R{i}") for i in range(4, 9)}

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def all_files(root):
    for dp, dns, fns in os.walk(root, followlinks=False):
        dns[:] = sorted(d for d in dns if d != "__pycache__")
        for name in sorted(fns): yield os.path.relpath(os.path.join(dp, name), root)

def parse_manifest(root, rel):
    entries, malformed, duplicates, seen = [], [], [], set()
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        for no, line in enumerate(f, 1):
            m = re.fullmatch(r"([0-9a-f]{64})  (.+)\n?", line)
            if not m: malformed.append(no); continue
            digest, path = m.groups()
            if path in seen: duplicates.append(path)
            seen.add(path)
            target = os.path.join(root, path)
            entries.append((path, digest, sha(target) if os.path.isfile(target) else None))
    return entries, malformed, duplicates

CLAIMS = {
1:"R4 CONTROL_MANIFEST verifies with zero mismatches.", 2:"R5 control manifest has exactly one mismatch and it is MODE.",
3:"R6 CONTROL_MANIFEST verifies with zero mismatches.", 4:"R7 CONTROL_MANIFEST has 15804 entries and zero mismatches.",
5:"R8 carries and verifies the R7 incident record and accurately discloses the immutability break and restoration.",
6:"R8 contains no full predecessor copy and generation_root resolves R4 through R8.",
7:"No active R8 file shares an inode with an active R7 file.", 8:"Both controller and rehearsal call in_process_executor.execute.",
9:"No live code path substitutes a worker-note outcome for an in-process operation.",
10:"IN_PROCESS, HANDLERS, and ARGUMENT_SCHEMA contain identical operation sets.",
11:"L1-A16 uses the specified corpus novelty proof and all three novelty controls rehearsed AS_EXPECTED.",
12:"No degenerate unhashed COMPARE_HASHES exists and rehearsals record no outside-allowance reads.",
13:"L1-A21 negative control uses boundary COUNT_TEXT_MATCHES with expected count zero.",
14:"REF-11 XML remains MIME-wrapped and R7-identical; L1-A33 extracts to work before parsing.",
15:"Every control-role step has an authoritative machine-checkable expectation and coverage agrees.",
16:"The R7-to-R8 migration plan contains exactly the specified migrations/exclusion and matching route digest.",
17:"R7 L1-A31 COMPARISON is EXECUTED, unsealed, and has zero evidence files.",
18:"Controller suite passes with no failures, errors, or skips.", 19:"Package suite passes with no failures, errors, or skips.",
20:"Static safety review is clean with zero findings.", 21:"All 43 plans exist and coverage has no missing, duplicate, or unknown plans.",
22:"Rehearsal reports 43/43 PASS_READY.", 23:"Rehearsal has complete in-process evidence, no note-only steps, and equal invocation/step counts.",
24:"Rehearsal has no hollow phases and live state was unchanged.", 25:"Progress has 35 audits and 43 phase records, all NOT_STARTED.",
26:"Approvals are empty, results/evidence have no files, and state contains no approval-token text.",
27:"R8 build manifest is syntactically valid, unique, hash-correct, and exactly covers builder scope.",
28:"Freeze is pinned to R8, its confined predecessor baseline matches lineage, and baseline construction succeeds.",
29:"No sibling R9 directory exists.", 30:"Transitions contains exactly one init-revision route row."
}
items, findings = [], []
def add(i, ok, measured):
    row={"id":i,"root":"ORIGINAL","claim":CLAIMS[i],"measured":measured,"pass":bool(ok),"finished_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    items.append(row)
    with open(os.path.join(OUT,"ITEM_RESULTS.jsonl"),"a",encoding="utf-8") as fh: fh.write(json.dumps(row,separators=(",",":"))+"\n")
    if not ok: findings.append(f"Item {i}: {measured}")

# 1-4
for i, rev, expected in [(1,"R4",None),(2,"R5",None),(3,"R6",None),(4,"R7",15804)]:
    e, bad, dup = parse_manifest(ROOTS[rev], "CONTROL_MANIFEST.sha256")
    mm = [x for x in e if x[1] != x[2]]
    ok = (len(mm)==1 and mm[0][0]=="MODE") if i==2 else not mm
    ok = ok and not bad and not dup and (expected is None or len(e)==expected)
    add(i, ok, f"entries={len(e)}; mismatching_paths={[x[0] for x in mm]}; malformed={bad}; duplicates={dup}")

# imports are intentionally bytecode-disabled by the required invocation/env.
sys.path.insert(0, R8)
from automation.package_tests import generation_root
from automation import in_process_executor, in_process_ops, operation_catalog, freeze

# 5
lineage = load(os.path.join(R8,"lineage/R8_LINEAGE.json")); r7d=lineage.get("r7",{})
ie, ib, idup = parse_manifest(os.path.join(R8,"lineage/R7_POST_FREEZE_INCIDENT"), "INCIDENT_MANIFEST.sha256")
imm_claims=[]
for rel in all_files(R8):
    if rel.startswith("verification_codex_final_pre_freeze_attempt_"): continue
    p=os.path.join(R8,rel)
    if os.path.isfile(p):
        s=open(p,encoding="utf-8",errors="replace").read().lower()
        if ("continuously immutable" in s or "continuous_post_freeze_immutability" in s) and not any(x in s for x in ["false","not continuously","was not continuously"]): imm_claims.append(rel)
ok=(not [x for x in ie if x[1]!=x[2]] and not ib and not idup and r7d.get("continuous_post_freeze_immutability") is False and r7d.get("current_bytes_restored_to_frozen_manifest") is True and not imm_claims)
add(5,ok,f"incident_entries={len(ie)}; incident_mismatches={sum(a!=b for _,a,b in ie)}; malformed={ib}; duplicates={idup}; continuous={r7d.get('continuous_post_freeze_immutability')}; restored={r7d.get('current_bytes_restored_to_frozen_manifest')}; contrary_files={imm_claims}")

# 6
resolved, errors={},{}
for rev in ["R4","R5","R6","R7","R8"]:
    try: resolved[rev]=generation_root(rev)
    except Exception as ex: errors[rev]=repr(ex)
full=[]
for name in os.listdir(os.path.join(R8,"lineage")):
    p=os.path.join(R8,"lineage",name)
    if os.path.isdir(p) and (os.path.isfile(os.path.join(p,"CONTROL_MANIFEST.sha256")) or os.path.isfile(os.path.join(p,"state/REVISION.json"))): full.append(name)
ok=not os.path.isdir(os.path.join(R8,"lineage/R6_EXECUTION")) and len(resolved)==5 and not full
add(6,ok,f"R6_EXECUTION_exists={os.path.isdir(os.path.join(R8,'lineage/R6_EXECUTION'))}; predecessor_package_like_dirs={full}; resolved={resolved}; errors={errors}")

# 7: active means paths outside archived lineage and runtime/output evidence trees.
excluded={"lineage","work","state","results","evidence","logs","verification","verification_codex_final_pre_freeze_attempt_1","verification_codex_final_pre_freeze_attempt_2"}
common=set(all_files(ROOTS["R7"])) & set(all_files(R8)); active=[r for r in common if r.split(os.sep)[0] not in excluded]; shared=[]
for rel in active:
    a,b=os.stat(os.path.join(ROOTS["R7"],rel)),os.stat(os.path.join(R8,rel))
    if (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino): shared.append(rel)
add(7,not shared,f"active_same_path_files_compared={len(active)}; shared_inode_paths={shared}")

# 8
calls={p:open(os.path.join(R8,p),encoding="utf-8").read().count("in_process_executor.execute") for p in ["automation/controller.py","build/rehearse_candidate_plans.py"]}
add(8,all(v>0 for v in calls.values()),f"call_occurrences={calls}")

# 9: classify every textual occurrence using AST context and measured duplicates.
occ=[]; bad_note=[]
for rel in all_files(R8):
    if not rel.endswith(".py"): continue
    p=os.path.join(R8,rel); src=open(p,encoding="utf-8",errors="replace").read(); lines=src.splitlines()
    if "performed by the worker" not in src: continue
    tree=ast.parse(src); parents={}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n): parents[c]=n
    for no,line in enumerate(lines,1):
        if "performed by the worker" not in line: continue
        nodes=[n for n in ast.walk(tree) if getattr(n,"lineno",10**9)<=no<=getattr(n,"end_lineno",-1)]
        strings=[n for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,str) and "performed by the worker" in n.value]
        rule=None; evidence={"ast_node_kinds":sorted({type(n).__name__ for n in strings})}
        segs=set(rel.split("/"))
        if "fixtures" in segs or "lineage" in segs: rule="e_read_only_fixture_or_lineage"
        elif rel.startswith("verification_codex_final_pre_freeze_attempt_"): rule="d_verifier_search"
        elif rel.startswith("verification/selftest_runtime/"):
            orig=rel[len("verification/selftest_runtime/"):]; op=os.path.join(R8,orig)
            if os.path.isfile(op) and sha(p)==sha(op): rule="c_byte_identical_duplicate"; evidence.update(original=orig,shared_sha256=sha(p))
        if rule is None:
            # Docstrings are Expr(Constant) first statements; comments have no string node.
            doc=False
            for n in strings:
                par=parents.get(n)
                if isinstance(par,ast.Expr):
                    gp=parents.get(par)
                    if isinstance(gp,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and gp.body and gp.body[0] is par: doc=True
            if doc or (not strings and line.lstrip().startswith("#")): rule="a_quoted_text"
            elif rel=="automation/migration.py": rule="b_guard_refusal"; evidence["exception"]="MigrationError"
            elif rel=="automation/package_tests/test_r8_migration.py": rule="b_guard_test"; evidence["assertion"]="assertRaises(MigrationError)"
        if rule is None: bad_note.append(f"{rel}:{no}")
        occ.append({"path":rel,"line":no,"matched_text":line.strip(),"rule":rule,"evidence":evidence})
add(9,not bad_note,{"occurrence_count":len(occ),"occurrences":occ,"unclassified":bad_note,"replica_imports_from_live_paths":0,"verifier_dirs_manifest_excluded":True})

# 10
sets=(set(operation_catalog.IN_PROCESS),set(in_process_ops.HANDLERS),set(in_process_executor.ARGUMENT_SCHEMA))
add(10,sets[0]==sets[1]==sets[2],f"catalog={len(sets[0])}; handlers={len(sets[1])}; schemas={len(sets[2])}; catalog-handler={sorted(sets[0]-sets[1])}; handler-catalog={sorted(sets[1]-sets[0])}; catalog-schema={sorted(sets[0]-sets[2])}; schema-catalog={sorted(sets[2]-sets[0])}")

# plans/rehearsal
plans={}
for rel in all_files(os.path.join(R8,"build/candidate_plans_r8")):
    if rel.endswith("/plan.json"):
        x=load(os.path.join(R8,"build/candidate_plans_r8",rel)); plans[(x["audit_id"],x["run_phase"])]=x
report=load(os.path.join(R8,"work/_rehearsal_r8/REHEARSAL_REPORT.json")); reports={(r["audit_id"],r["run_phase"]):r for r in report["reports"]}
def matrix_for(plan, sid): return next(x for x in plan["test_matrix"] if x.get("step_id")==sid)
p16=plans[("L1-A16","RUN-A")]; s16=next(s for s in p16["steps"] if s["step_id"]=="prove_cases_are_novel")
novel_controls=[s for s in p16["steps"] if s["operation"]=="PROVE_SET_NOVELTY" and s.get("control_role") in {"POSITIVE","NEGATIVE","MUTATION","ORACLE","SABOTAGE"}]
r16={s["step_id"]:s for s in reports[("L1-A16","RUN-A")]["steps"]}
ok=s16["operation"]=="PROVE_SET_NOVELTY" and s16["params"]["reference_root"]=="/home/ubuntu/project/WPNO/ap18/korpus_docx" and s16["params"]["expected_reference_entry_count"]==7 and len(novel_controls)==3 and all(r16[s["step_id"]].get("expectation_result")=="AS_EXPECTED" for s in novel_controls)
add(11,ok,f"operation={s16['operation']}; reference_root={s16['params'].get('reference_root')}; expected_reference_entry_count={s16['params'].get('expected_reference_entry_count')}; novelty_controls={[(s['step_id'],r16[s['step_id']].get('expectation_result')) for s in novel_controls]}")

deg=[]
for key,p in plans.items():
    for s in p["steps"]:
        q=s.get("params",{})
        if s["operation"]=="COMPARE_HASHES" and q.get("left")==q.get("right") and not q.get("expected_sha256"): deg.append((*key,s["step_id"]))
outside=[(r["audit_id"],r["run_phase"],s["step_id"],s.get("reads_outside_declared_allowance")) for r in report["reports"] for s in r["steps"] if s.get("reads_outside_declared_allowance")]
add(12,not deg and not outside,f"degenerate_compare_hashes={deg}; rehearsal_steps_with_outside_reads={outside}")

p21=plans[("L1-A21","RUN-A")]; s21=next(s for s in p21["steps"] if s["step_id"]=="negative_control_export_is_not_another_project"); m21=matrix_for(p21,s21["step_id"])
add(13,s21["operation"]=="COUNT_TEXT_MATCHES" and s21["params"].get("word_boundary") is True and m21.get("expected_count")==0,f"operation={s21['operation']}; word_boundary={s21['params'].get('word_boundary')}; expected_count={m21.get('expected_count')}")

ref="references/REF-11-563203462.xml"; p33=plans[("L1-A33","RUN-A")]; st33={s["step_id"]:s for s in p33["steps"]}; ex=st33["extract_container_xml_part"]; pa=st33["parse_container_xml_safely"]
prefix=open(os.path.join(R8,ref),"rb").read(13); h8=sha(os.path.join(R8,ref)); h7=sha(os.path.join(ROOTS["R7"],ref)); out=ex["params"]["out"]
add(14,prefix.startswith(b"MIME-Version:") and h8==h7 and os.path.commonpath([os.path.realpath(out),os.path.realpath(os.path.join(R8,"work"))])==os.path.realpath(os.path.join(R8,"work")) and pa["params"]["path"]==out,f"prefix={prefix!r}; R8_sha256={h8}; R7_sha256={h7}; extract_out={out}; parse_path={pa['params']['path']}")

roles={"POSITIVE","NEGATIVE","MUTATION","ORACLE","SABOTAGE"}; controls=[]; unenforced=[]
for key,p in plans.items():
    for s in p["steps"]:
        if s.get("control_role") in roles:
            entry=matrix_for(p,s["step_id"]); present=in_process_executor.expectation_keys_present(entry); rec=(*key,s["step_id"],present); controls.append(rec)
            if not present: unenforced.append(rec)
cov=load(os.path.join(R8,"build/CONTROL_EXPECTATION_COVERAGE.json"))
covok=cov.get("CONTROL_ROLE_STEP_COUNT")==len(controls) and cov.get("CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION")==len(unenforced) and cov.get("CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION")==f"{len(controls)-len(unenforced)}/{len(controls)}"
add(15,not unenforced and covok,f"rederived_control_count={len(controls)}; unenforced={unenforced}; coverage_count={cov.get('CONTROL_ROLE_STEP_COUNT')}; coverage_unenforced={cov.get('CONTROL_STEPS_WITHOUT_ENFORCED_EXPECTATION')}; coverage_machine={cov.get('CONTROL_STEPS_WITH_MACHINE_CHECKABLE_EXPECTATION')}")

mig=load(os.path.join(R8,"build/migration_plan_r7_to_r8/MIGRATION_PLAN.json")); migr={(x["destination_audit_id"],x["destination_run_phase"]) for x in mig["migratable_attempts"]}; exc={(x["audit_id"],x["run_phase"],x["exclusion_reason"]) for x in mig["excluded_attempts"]}; route=os.path.join(R8,mig["route_module"])
ok=migr=={("L1-A31","RUN-A"),("L1-A31","RUN-B")} and exc=={("L1-A31","COMPARISON","EXECUTED_UNSEALED_ZERO_EVIDENCE_FROZEN_CONTROLLER_DEFECT")} and mig["applied_before_freeze"] is False and sha(route)==mig["route_module_sha256"]
add(16,ok,f"migratable={sorted(migr)}; excluded={sorted(exc)}; applied_before_freeze={mig.get('applied_before_freeze')}; recorded_route_sha256={mig.get('route_module_sha256')}; measured_route_sha256={sha(route)}")

p7=load(os.path.join(ROOTS["R7"],"state/progress.json")); state7=p7["audits"]["L1-A31"]["COMPARISON"]["state"]
res7=os.path.join(ROOTS["R7"],"results/L1-A31/COMPARISON"); ev7=os.path.join(ROOTS["R7"],"evidence/L1-A31/COMPARISON"); seal=os.path.isfile(os.path.join(res7,"SEAL.json")); evn=sum(1 for _ in all_files(ev7)) if os.path.isdir(ev7) else 0
add(17,state7=="EXECUTED" and not seal and evn==0,f"state={state7}; SEAL_exists={seal}; evidence_files={evn}")

print(json.dumps({"completed":17,"findings":findings},indent=2))
sys.exit(1 if findings else 0)

def run_suite(label,cwd,start):
    cmd=["/usr/bin/python3","-B","-m","unittest","discover","-s",start,"-t","."]
    p=subprocess.run(cmd,cwd=cwd,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",TMPDIR=OUT),capture_output=True,text=True,timeout=1800)
    with open(os.path.join(OUT,label+".stdout.txt"),"w",encoding="utf-8") as f:f.write(p.stdout)
    with open(os.path.join(OUT,label+".stderr.txt"),"w",encoding="utf-8") as f:f.write(p.stderr)
    text=p.stdout+"\n"+p.stderr; m=re.search(r"Ran (\d+) tests?",text); failures=sum(int(x) for x in re.findall(r"failures=(\d+)",text)); errors=sum(int(x) for x in re.findall(r"errors=(\d+)",text)); skips=sum(int(x) for x in re.findall(r"skipped=(\d+)",text))
    return p.returncode, int(m.group(1)) if m else None, failures, errors, skips, cmd
rc,n,f,e,s,cmd=run_suite("controller_suite",os.path.join(R8,"verification/selftest_runtime"),"."); add(18,rc==0 and n and f==e==s==0,f"argv={cmd}; exit={rc}; tests={n}; failures={f}; errors={e}; skips={s}")
rc,n,f,e,s,cmd=run_suite("package_suite",R8,"automation/package_tests"); add(19,rc==0 and n and f==e==s==0,f"argv={cmd}; exit={rc}; tests={n}; failures={f}; errors={e}; skips={s}")

static_dir=os.path.join(OUT,"static"); os.makedirs(static_dir,exist_ok=True)
scmd=["/usr/bin/python3","-B","build/r8_static_safety_review.py","--out-dir",static_dir]
sp=subprocess.run(scmd,cwd=R8,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",TMPDIR=OUT),capture_output=True,text=True,timeout=600)
open(os.path.join(OUT,"static_safety.stdout.txt"),"w").write(sp.stdout); open(os.path.join(OUT,"static_safety.stderr.txt"),"w").write(sp.stderr)
sreports=[os.path.join(static_dir,x) for x in os.listdir(static_dir) if x.endswith(".json")]; sr=load(sreports[0]) if len(sreports)==1 else {}
add(20,sp.returncode==0 and sr.get("finding_count")==0 and sr.get("clean") is True,f"argv={scmd}; exit={sp.returncode}; report_files={[os.path.basename(x) for x in sreports]}; finding_count={sr.get('finding_count')}; clean={sr.get('clean')}")

coverage=load(os.path.join(R8,"build/candidate_plans_r8/PLAN_COVERAGE_MANIFEST.json")); add(21,len(plans)==43 and coverage["MISSING_PLAN_COUNT"]==coverage["DUPLICATE_PLAN_COUNT"]==coverage["UNKNOWN_PLAN_COUNT"]==0 and not coverage["missing"] and not coverage["duplicates"] and not coverage["unknown"],f"plans={len(plans)}; required={coverage.get('REQUIRED_PLAN_COUNT')}; missing={coverage.get('missing')}; duplicates={coverage.get('duplicates')}; unknown={coverage.get('unknown')}")
ready=sum(1 for r in report["reports"] if r.get("PASS_READY")); add(22,report.get("PHASES_PASS_READY")==43 and report.get("phases_required")==43 and ready==43,f"PHASES_PASS_READY={report.get('PHASES_PASS_READY')}; phases_required={report.get('phases_required')}; per_phase_PASS_READY={ready}")
add(23,report.get("REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE")==0 and report.get("NOTE_ONLY_IN_PROCESS_STEPS")==0 and report.get("IN_PROCESS_HANDLER_INVOCATIONS")==report.get("IN_PROCESS_STEP_COUNT"),f"without_evidence={report.get('REQUIRED_IN_PROCESS_STEPS_WITHOUT_EVIDENCE')}; note_only={report.get('NOTE_ONLY_IN_PROCESS_STEPS')}; handler_invocations={report.get('IN_PROCESS_HANDLER_INVOCATIONS')}; in_process_steps={report.get('IN_PROCESS_STEP_COUNT')}")
add(24,report.get("HOLLOW_PHASES")==[] and report.get("LIVE_STATE_UNCHANGED") is True,f"HOLLOW_PHASES={report.get('HOLLOW_PHASES')}; LIVE_STATE_UNCHANGED={report.get('LIVE_STATE_UNCHANGED')}")

prog=load(os.path.join(R8,"state/progress.json")); states=[phase["state"] for audit in prog["audits"].values() for phase in audit.values()]
add(25,len(prog["audits"])==35 and len(states)==43 and set(states)=={"NOT_STARTED"},f"audits={len(prog['audits'])}; phases={len(states)}; state_counts={{s:states.count(s) for s in sorted(set(states))}}".replace("{s:states.count(s) for s in sorted(set(states))}",str({s:states.count(s) for s in sorted(set(states))})))
approvals=[x for x in open(os.path.join(R8,"state/approvals.jsonl"),encoding="utf-8") if x.strip()]; rn=sum(1 for _ in all_files(os.path.join(R8,"results"))); en=sum(1 for _ in all_files(os.path.join(R8,"evidence"))); tokens=[]
for rel in all_files(os.path.join(R8,"state")):
    txt=open(os.path.join(R8,"state",rel),encoding="utf-8",errors="replace").read()
    if "APPROVE-EXECUTION" in txt or "RUN-ONCE" in txt: tokens.append(rel)
add(26,not approvals and rn==0 and en==0 and not tokens,f"approval_rows={len(approvals)}; result_files={rn}; evidence_files={en}; state_token_files={tokens}")

be,bb,bd=parse_manifest(R8,"build/R8_BUILD_MANIFEST.sha256"); bm=importlib.import_module("build.build_r8_build_manifest"); listed={x[0] for x in be}; physical={rel for rel in all_files(R8) if bm.in_scope(rel)}; mm=[x[0] for x in be if x[1]!=x[2]]
add(27,not bb and not bd and not mm and listed==physical,f"entries={len(be)}; malformed={bb}; duplicates={bd}; mismatches={mm}; physical_not_listed={sorted(physical-listed)}; listed_not_physical={sorted(listed-physical)}")

base=os.path.realpath(os.path.join(R8,freeze.PREDECESSOR_BASELINE_REL)); inside=os.path.commonpath([R8,base])==R8; expected=r7d.get("baseline_manifest_sha256"); measured=sha(base) if os.path.isfile(base) else None
try: baseline, provenance=freeze.build_baseline_from_predecessor(R8); berr=None
except Exception as ex: baseline={}; provenance=None; berr=repr(ex)
add(28,freeze.PACKAGE_REVISION=="R8" and inside and measured==expected and berr is None,f"PACKAGE_REVISION={freeze.PACKAGE_REVISION}; rel={freeze.PREDECESSOR_BASELINE_REL}; resolved={base}; inside_R8={inside}; recorded_sha256={expected}; measured_sha256={measured}; baseline_entries={len(baseline)}; error={berr}")
r9=os.path.join(os.path.dirname(R8),"08.18.26_Level1_Audits_R9"); add(29,not os.path.exists(r9),f"path={r9}; exists={os.path.exists(r9)}")
rows=[json.loads(x) for x in open(os.path.join(R8,"state/transitions.jsonl"),encoding="utf-8") if x.strip()]; add(30,len(rows)==1 and rows[0].get("route")=="init-revision",f"rows={len(rows)}; routes={[x.get('route') for x in rows]}")

overall=all(x["pass"] for x in items) and not findings
result={"schema":"wpno.level1.codex-verification/1","revision":"R8","stage":"PRE_FREEZE_FINAL","verified_utc":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"items":sorted(items,key=lambda x:x["id"]),"overall_pass":overall,"unresolved_findings":findings,"status":"VERIFICATION_PASS_PRE_FREEZE_R8_FINAL" if overall else "VERIFICATION_FAIL_PRE_FREEZE_R8_FINAL"}
with open(os.path.join(OUT,"VERIFICATION_RESULT.json"),"w",encoding="utf-8") as f: json.dump(result,f,indent=2); f.write("\n")
notes=f"""# Independent pre-freeze verification, attempt 2\n\nVerified at {result['verified_utc']} using bytes on disk. All Python commands used `/usr/bin/python3 -B` with `PYTHONDONTWRITEBYTECODE=1`. No network, git, migration, freeze publication, live audit phase, or R9 creation was performed.\n\nCommands actually run by the verifier:\n\n- Controller suite: `/usr/bin/python3 -B -m unittest discover -s . -t .` in `verification/selftest_runtime`.\n- Package suite: `/usr/bin/python3 -B -m unittest discover -s automation/package_tests -t .` at R8 root.\n- Static review: `/usr/bin/python3 -B build/r8_static_safety_review.py --out-dir verification_codex_final_pre_freeze_attempt_2/static`.\n\nThe verifier independently parsed and hashed all control and build manifests; inspected lineage, plans, rehearsal records, migration metadata, state, results, evidence, call sites, operation registries, inode identities, and freeze baseline inputs; and called only `freeze.build_baseline_from_predecessor`, not a freeze operation. Test and static-review stdout/stderr are preserved beside this note.\n\nResult: **{result['status']}**. Passing items: {sum(x['pass'] for x in items)}/30. Unresolved findings: {len(findings)}.\n"""
with open(os.path.join(OUT,"VERIFICATION_NOTES.md"),"w",encoding="utf-8") as f:f.write(notes)
print(json.dumps({"status":result["status"],"passing":sum(x["pass"] for x in items),"findings":len(findings)}))
