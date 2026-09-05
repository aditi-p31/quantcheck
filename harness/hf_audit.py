#!/usr/bin/env python3
"""Audit HuggingFace community GGUF artifacts + cross-distributor adjudication set.

For each entry whose tag is "hf:<repo>/<filename>":
  1. download the GGUF from huggingface.co/<repo>/resolve/main/<filename>
  2. create a temporary Ollama model: FROM <gguf> + TEMPLATE copied verbatim
     from the corresponding official Ollama entry for that family (recorded)
  3. run the same 15-task smoke suite via audit.audit_one
  4. delete model + file

Also runs ADJUDICATION extras: same-model same-quant GGUFs from independent
distributors for every defect-suspect group, to separate artifact defects
from capability limits and from harness effects.

Run on the pod after the main sweep: OLLAMA_BIN=... python3 hf_audit.py
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # reuse audit_one, api, RESULTS conventions

ROOT = os.path.dirname(HERE)
OLLAMA_BIN = os.environ.get("OLLAMA_BIN", "ollama")
DL = os.environ.get("HF_DL_DIR", "/workspace/hfdl")

# family -> official Ollama tag whose TEMPLATE we copy (verbatim)
TEMPLATE_DONOR = {
    "qwen2.5-coder": "qwen2.5-coder:0.5b-instruct-q4_K_M",
    "llama3.2": "llama3.2:1b-instruct-q4_K_M",
    "llama3.1": "llama3.2:1b-instruct-q4_K_M",
    "gemma2": "gemma2:2b-instruct-q4_0",
    "gemma3": "gemma2:2b-instruct-q4_0",
    "phi3.5": "phi3.5:3.8b-mini-instruct-q4_K_M",
    "deepseek-coder": "deepseek-coder:1.3b-instruct-q4_K_M",
    "mistral": "mistral:7b-instruct-q4_K_M",
    "codellama": "codellama:7b-instruct-q4_K_M",
    "starcoder2": "starcoder2:3b-q4_K_M",
}

# Cross-distributor adjudication set (independent conversions of the exact
# model+quant combos our defect suspects come from).
EXTRAS = [
    {"tag": "hf:bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/Qwen2.5-Coder-3B-Instruct-Q3_K_M.gguf",
     "family": "qwen2.5-coder", "quant": "q3_K_M", "params_b": 3.0, "channel": "hf-adjudication"},
    {"tag": "hf:bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/Qwen2.5-Coder-3B-Instruct-Q2_K.gguf",
     "family": "qwen2.5-coder", "quant": "q2_K", "params_b": 3.0, "channel": "hf-adjudication"},
    {"tag": "hf:TheBloke/deepseek-coder-1.3b-instruct-GGUF/deepseek-coder-1.3b-instruct.Q4_K_M.gguf",
     "family": "deepseek-coder", "quant": "q4_K_M", "params_b": 1.3, "channel": "hf-adjudication"},
    {"tag": "hf:bartowski/Llama-3.2-1B-Instruct-GGUF/Llama-3.2-1B-Instruct-Q3_K_L.gguf",
     "family": "llama3.2", "quant": "q2_K", "params_b": 1.0, "channel": "hf-adjudication"},
    {"tag": "hf:bartowski/Phi-3.5-mini-instruct-GGUF/Phi-3.5-mini-instruct-Q2_K.gguf",
     "family": "phi3.5", "quant": "q2_K", "params_b": 3.8, "channel": "hf-adjudication"},
]

def sh(*args, timeout=7200):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

def get_template(family):
    donor = TEMPLATE_DONOR.get(family)
    if not donor:
        return None, None
    sh(OLLAMA_BIN, "pull", donor)
    r = sh(OLLAMA_BIN, "show", "--template", donor)
    return (r.stdout, donor) if r.returncode == 0 and r.stdout.strip() else (None, donor)

def audit_hf(entry, tasks):
    tag = entry["tag"]
    assert tag.startswith("hf:")
    repo_file = tag[3:]
    repo, fname = repo_file.rsplit("/", 1)
    url = f"https://huggingface.co/{repo}/resolve/main/{fname}"
    os.makedirs(DL, exist_ok=True)
    local = os.path.join(DL, fname)
    rec = dict(entry)
    rec["ts_start"] = time.time()
    print(f"== {tag}: downloading", flush=True)
    t0 = time.monotonic()
    r = sh("curl", "-sL", "--fail", "-o", local, url, timeout=7200)
    rec["pull_s"] = round(time.monotonic() - t0, 1)
    if r.returncode != 0 or not os.path.exists(local):
        rec["error"] = f"download_failed: {url}"
        return rec
    template, donor = get_template(entry.get("family", ""))
    rec["template_donor"] = donor
    name = "hfaudit-tmp"
    mf = os.path.join(DL, "Modelfile")
    with open(mf, "w") as f:
        f.write(f"FROM {local}\n")
        if template:
            f.write('TEMPLATE """' + template.strip() + '"""\n')
    c = sh(OLLAMA_BIN, "create", name, "-f", mf, timeout=1800)
    if c.returncode != 0:
        rec["error"] = "create_failed: " + c.stderr.strip()[-200:]
        os.remove(local)
        return rec
    # delegate generation to audit.audit_one with the temp model name
    sub = audit.audit_one({"tag": name, "no_pull": True}, tasks, keep=False)
    for k in ("transcript", "metrics", "trunc_frac", "echo_frac_mean",
              "rep6_share_mean", "def_frac", "error"):
        if k in sub:
            rec[k] = sub[k]
    # rename transcript to the hf tag for uniqueness
    if rec.get("transcript"):
        safe = tag.replace(":", "_").replace("/", "_")
        src = os.path.join(audit.RESULTS, "transcripts", sub["transcript"])
        dst = os.path.join(audit.RESULTS, "transcripts", safe + ".jsonl")
        os.replace(src, dst)
        rec["transcript"] = os.path.basename(dst)
    sh(OLLAMA_BIN, "rm", name)
    if os.path.exists(local):
        os.remove(local)
    rec["ts_end"] = time.time()
    return rec

def main():
    from evalplus.data import get_human_eval_plus
    audit.TASKS = get_human_eval_plus()
    suite = audit.SUITE
    inv = json.load(open(os.path.join(ROOT, "inventory_candidates.json")))["artifacts"]
    hf_entries = [e for e in inv if e["tag"].startswith("hf:")]
    seen_tags = {e["tag"] for e in hf_entries}
    for x in EXTRAS:
        if x["tag"] not in seen_tags:
            hf_entries.append(x)
    out_path = os.path.join(audit.RESULTS, "audit_results.jsonl")
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            if not l.strip():
                continue
            r = json.loads(l)
            if not r.get("skip") and not r.get("error"):
                done.add(r["tag"])
    todo = [e for e in hf_entries if e["tag"] not in done]
    print(f"HF audit: {len(todo)} to run", flush=True)
    with open(out_path, "a") as f:
        for i, e in enumerate(todo, 1):
            try:
                rec = audit_hf(e, suite)
            except Exception as ex:
                rec = dict(e); rec["error"] = f"exception: {type(ex).__name__}: {ex}"[:300]
            f.write(json.dumps(rec) + "\n"); f.flush()
            print(f"  [{i}/{len(todo)}] {e['tag'][:60]} "
                  f"{'ERR' if rec.get('error') else 'ok'}", flush=True)

if __name__ == "__main__":
    main()
