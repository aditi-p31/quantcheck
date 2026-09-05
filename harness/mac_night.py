#!/usr/bin/env python3
"""Overnight Mac chain: (1) Metal smoke replications for the two defects
never confirmed on this backend; (2) Metal smoke for the two TheBloke
community files (native + supplied template both); (3) census-template
full-164 for the two TheBloke files (Table 2 consistency)."""
import json, os, subprocess, sys, time
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import audit
from evalplus.data import get_human_eval_plus
audit.TASKS = get_human_eval_plus()
ALL = list(audit.TASKS.keys())
DL = os.path.join(os.path.dirname(HERE), "hfdl"); os.makedirs(DL, exist_ok=True)
OUT = os.path.join(os.path.dirname(HERE), "results-metalrep"); os.makedirs(OUT, exist_ok=True)
audit.RESULTS = OUT
def sh(*a, timeout=7200): return subprocess.run(a, capture_output=True, text=True, timeout=timeout)
log = open(os.path.join(OUT, "audit_results.jsonl"), "a")
def emit(rec): log.write(json.dumps(rec)+"\n"); log.flush(); print(rec.get("tag"), "err" if rec.get("error") else "ok", flush=True)

# (1) official defects on Metal: smoke suite
for e in json.load(open(os.path.join(os.path.dirname(HERE),"metal_replication.json")))["artifacts"]:
    rec = audit.audit_one(dict(e), audit.SUITE); rec["condition"]="metal-smoke"; emit(rec)

# (2+3) TheBloke files: download once; smoke under supplied template; full-164 under supplied template
DEEPSEEK_TPL = '{{ .System }}\n### Instruction:\n{{ .Prompt }}\n### Response:\n'
FILES = [("TheBloke/deepseek-coder-6.7B-instruct-GGUF","deepseek-coder-6.7b-instruct.Q3_K_M.gguf"),
         ("TheBloke/deepseek-coder-6.7B-instruct-GGUF","deepseek-coder-6.7b-instruct.Q4_K_M.gguf")]
for repo,f in FILES:
    local=os.path.join(DL,f)
    if not os.path.exists(local):
        print("downloading",f,flush=True)
        r=sh("curl","-sL","--fail","-o",local,f"https://huggingface.co/{repo}/resolve/main/{f}")
        if r.returncode!=0: emit({"tag":f,"error":"download_failed"}); continue
    mf=os.path.join(DL,"Modelfile.supplied")
    open(mf,"w").write(f"FROM {local}\nTEMPLATE \"\"\"{DEEPSEEK_TPL}\"\"\"\n")
    if sh(audit.OLLAMA_BIN,"create","macnight","-f",mf,timeout=1800).returncode!=0:
        emit({"tag":f,"error":"create_failed"}); continue
    # smoke on Metal (supplied template)
    rec=audit.audit_one({"tag":"macnight","no_pull":True}, audit.SUITE)
    rec["source_file"]=f; rec["condition"]="metal-smoke-supplied-template"
    if rec.get("transcript"):
        d=os.path.join(OUT,"transcripts",f.replace(".gguf","")+".metal-smoke.jsonl")
        os.replace(os.path.join(OUT,"transcripts",rec["transcript"]),d); rec["transcript"]=os.path.basename(d)
    emit(rec)
    # full-164 (census/supplied template) for Table 2 consistency
    rec2=audit.audit_one({"tag":"macnight","no_pull":True}, ALL)
    rec2["source_file"]=f; rec2["condition"]="metal-full164-supplied-template"
    if rec2.get("transcript"):
        d=os.path.join(OUT,"transcripts",f.replace(".gguf","")+".metal-full164.jsonl")
        os.replace(os.path.join(OUT,"transcripts",rec2["transcript"]),d); rec2["transcript"]=os.path.basename(d)
    emit(rec2)
    sh(audit.OLLAMA_BIN,"rm","macnight")
    if os.path.exists(local): os.remove(local)
print("MAC NIGHT CHAIN DONE",flush=True)
