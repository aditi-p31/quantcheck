#!/usr/bin/env python3
"""Re-test TheBloke deepseek-coder-6.7b suspects with their NATIVE embedded
chat template (no Ollama template override) to rule out a harness-induced
template confound. Runs smoke 15 + full 164 for each. Mac-local.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit
from evalplus.data import get_human_eval_plus

DL = os.path.join(os.path.dirname(HERE), "hfdl")
OUT = os.path.join(os.path.dirname(HERE), "results-native")
FILES = [
    ("TheBloke/deepseek-coder-6.7B-instruct-GGUF", "deepseek-coder-6.7b-instruct.Q3_K_M.gguf"),
    ("TheBloke/deepseek-coder-6.7B-instruct-GGUF", "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"),
]

def sh(*a, timeout=7200):
    return subprocess.run(a, capture_output=True, text=True, timeout=timeout)

def main():
    audit.TASKS = get_human_eval_plus()
    audit.RESULTS = OUT
    os.makedirs(DL, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    all_ids = list(audit.TASKS.keys())
    out = open(os.path.join(OUT, "audit_results.jsonl"), "a")
    for repo, fname in FILES:
        local = os.path.join(DL, fname)
        if not os.path.exists(local):
            print(f"downloading {fname}", flush=True)
            r = sh("curl", "-sL", "--fail", "-o", local,
                   f"https://huggingface.co/{repo}/resolve/main/{fname}")
            if r.returncode != 0:
                print("download failed", fname); continue
        name = "native-test"
        mf = os.path.join(DL, "Modelfile.native")
        with open(mf, "w") as f:
            f.write(f"FROM {local}\n")   # NO TEMPLATE line: use GGUF-embedded template
        c = sh(audit.OLLAMA_BIN, "create", name, "-f", mf, timeout=1800)
        if c.returncode != 0:
            print("create failed:", c.stderr[-200:]); continue
        # record what template Ollama actually adopted
        tpl = sh(audit.OLLAMA_BIN, "show", "--template", name).stdout
        # smoke 15 then full 164 (single run over all ids; smoke is a subset)
        rec = audit.audit_one({"tag": name, "no_pull": True}, all_ids, keep=False)
        rec["source_file"] = f"hf:{repo}/{fname}"
        rec["native_template"] = tpl[:400]
        rec["condition"] = "native-embedded-template"
        # rename transcript to identify file
        if rec.get("transcript"):
            safe = fname.replace(".gguf", "") + ".native.jsonl"
            os.replace(os.path.join(OUT, "transcripts", rec["transcript"]),
                       os.path.join(OUT, "transcripts", safe))
            rec["transcript"] = safe
        out.write(json.dumps(rec) + "\n"); out.flush()
        sh(audit.OLLAMA_BIN, "rm", name)
        print(f"done {fname}", flush=True)
    out.close()

if __name__ == "__main__":
    main()
