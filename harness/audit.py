#!/usr/bin/env python3
"""Artifact audit harness: pull -> smoke-test -> extract signatures -> delete.

For each artifact in the inventory, runs the calibrated smoke suite (15
HumanEval+ tasks), records generations, cheap degeneration features, and
EvalPlus-scored pass results, then removes the model to bound disk use.

Resumable: artifacts already present in audit_results.jsonl are skipped.
Usage:
  python3 audit.py [--inventory ../inventory_candidates.json] [--limit N]
                   [--only TAG] [--keep-model]
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLLAMA_BIN = os.environ.get("OLLAMA_BIN", "ollama")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
RESULTS = os.path.join(ROOT, "results")
SUITE = json.load(open(os.path.join(ROOT, "smoke_suite_v1.json")))["suite_tasks"]

INSTRUCTION = (
    "Please provide a self-contained Python script that solves the following "
    "problem in a markdown code block:"
)

def api(path, payload=None, timeout=900):
    req = urllib.request.Request(
        OLLAMA + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def sh(*args, timeout=3600):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

def degeneration_features(prompt, out):
    """Cheap RQ2 signature features computed on raw model output."""
    toks = out.split()
    feats = {"out_chars": len(out), "out_words": len(toks)}
    # max repeated 6-gram share
    if len(toks) >= 12:
        grams = [" ".join(toks[i:i+6]) for i in range(len(toks)-5)]
        from collections import Counter
        top = Counter(grams).most_common(1)[0][1]
        feats["rep6_share"] = round(top * 6 / max(1, len(toks)), 3)
    else:
        feats["rep6_share"] = 0.0
    # prompt-echo overlap: fraction of prompt lines reproduced verbatim
    plines = [l.strip() for l in prompt.splitlines() if len(l.strip()) > 12]
    if plines:
        feats["echo_frac"] = round(sum(1 for l in plines if l in out) / len(plines), 3)
    else:
        feats["echo_frac"] = 0.0
    # code-shape heuristics
    feats["has_def"] = int(bool(re.search(r"(?m)^\s*def\s+\w+\s*\(.*\)\s*:", out)))
    feats["has_return"] = int("return" in out)
    return feats

def audit_one(entry, tasks, keep=False):
    tag = entry["tag"]
    rec = {"tag": tag, "family": entry.get("family"), "channel": entry.get("channel"),
           "quant": entry.get("quant"), "params_b": entry.get("params_b"),
           "file_size_gb": entry.get("file_size_gb"), "ts_start": time.time()}
    if tag.startswith("hf:"):
        rec["skip"] = "hf-manual"   # HF GGUFs handled by separate path later
        return rec
    if not entry.get("no_pull"):
        print(f"== {tag}: pulling", flush=True)
        t0 = time.monotonic()
        p = sh(OLLAMA_BIN, "pull", tag, timeout=7200)
        rec["pull_s"] = round(time.monotonic() - t0, 1)
        if p.returncode != 0:
            rec["error"] = "pull_failed: " + p.stderr.strip()[-200:]
            return rec
    gens, metrics = [], []
    try:
        for tid in tasks:
            prompt = TASKS[tid]["prompt"]
            t1 = time.monotonic()
            resp = api("/api/chat", {
                "model": tag,
                "messages": [{"role": "user", "content": f"{INSTRUCTION}\n```python\n{prompt}\n```\n"}],
                "stream": False,
                "options": {"temperature": 0.0, "seed": 42, "num_predict": 768, "num_ctx": 2048},
                "keep_alive": "10m",
            })
            out = resp.get("message", {}).get("content", "")
            gens.append({"task_id": tid, "solution": out})
            m = degeneration_features(prompt, out)
            m.update({"task_id": tid, "wall_s": round(time.monotonic() - t1, 2),
                      "eval_count": resp.get("eval_count"),
                      "eval_duration_ns": resp.get("eval_duration"),
                      "done_reason": resp.get("done_reason")})
            metrics.append(m)
    except Exception as e:
        rec["error"] = f"generation: {type(e).__name__}: {e}"[:300]
    finally:
        sh(OLLAMA_BIN, "stop", tag, timeout=120)
        if not keep:
            sh(OLLAMA_BIN, "rm", tag, timeout=600)
    rec["ts_end"] = time.time()
    if gens:
        safe = tag.replace(":", "_").replace("/", "_")
        gpath = os.path.join(RESULTS, "transcripts", safe + ".jsonl")
        os.makedirs(os.path.dirname(gpath), exist_ok=True)
        with open(gpath, "w") as f:
            for g in gens:
                f.write(json.dumps(g) + "\n")
        rec["transcript"] = os.path.basename(gpath)
        rec["metrics"] = metrics
        rec["trunc_frac"] = round(sum(1 for m in metrics if m.get("done_reason") == "length") / len(metrics), 3)
        rec["echo_frac_mean"] = round(sum(m["echo_frac"] for m in metrics) / len(metrics), 3)
        rec["rep6_share_mean"] = round(sum(m["rep6_share"] for m in metrics) / len(metrics), 3)
        rec["def_frac"] = round(sum(m["has_def"] for m in metrics) / len(metrics), 3)
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default=os.path.join(ROOT, "inventory_candidates.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default=None)
    ap.add_argument("--keep-model", action="store_true")
    ap.add_argument("--task-file", default=None, help="JSON list of task ids to run instead of the smoke suite")
    ap.add_argument("--results-dir", default=None)
    a = ap.parse_args()

    global TASKS, RESULTS
    from evalplus.data import get_human_eval_plus
    TASKS = get_human_eval_plus()
    tasks_to_run = SUITE
    if a.task_file:
        tasks_to_run = json.load(open(a.task_file))
    if a.results_dir:
        globals()["RESULTS"] = a.results_dir
        os.makedirs(a.results_dir, exist_ok=True)


    inv = json.load(open(a.inventory))["artifacts"]
    if a.only:
        inv = [e for e in inv if e["tag"] == a.only]
    out_path = os.path.join(globals()["RESULTS"], "audit_results.jsonl")
    os.makedirs(globals()["RESULTS"], exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            done = {json.loads(l)["tag"] for l in f if l.strip()}
    todo = [e for e in inv if e["tag"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(done)} done, {len(todo)} to audit", flush=True)
    with open(out_path, "a") as f:
        for i, e in enumerate(todo, 1):
            rec = audit_one(e, tasks_to_run, keep=a.keep_model)
            f.write(json.dumps(rec) + "\n"); f.flush()
            print(f"  [{i}/{len(todo)}] {rec['tag']} "
                  f"{'ERR ' + rec['error'][:60] if rec.get('error') else 'ok'}", flush=True)

if __name__ == "__main__":
    main()
