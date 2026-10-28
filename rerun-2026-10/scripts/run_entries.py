#!/usr/bin/env python3
"""Run artifacts through the study's generation path under a named setting.

Prompt, instruction and degeneration features come from harness/audit.py unchanged; only the
Ollama options are a parameter, so R2 can vary them. Entry kinds:
  ollama  {"id", "kind": "ollama", "tag"}                  pulled from the registry
  gguf    {"id", "kind": "gguf", "path", "donor"}          local file; the donor tag's Modelfile
                                                           (TEMPLATE, PARAMETER, SYSTEM) is copied
  hf      {"id", "kind": "hf", "repo", "file", "donor"}    downloaded, then run as gguf
Resumable: (id, setting) pairs already in the results file are skipped.
Note (v3.4): donor_modelfile() drops lines that begin with "#" outside a triple-quoted block as
header comments. A donor whose TEMPLATE is a double-quoted multi-line string with such lines
(deepseek-coder's "### Instruction:" and "### Response:") therefore loses them; see
rerun-2026-10/results-tpl/ (the "donor" condition). None of the October reruns before the template test used such a donor.

Usage: run_entries.py ENTRIES.json --setting NAME [--options JSON] [--tasks suite|FILE]
                      [--results-dir DIR] [--keep] [--only ID]
"""
import argparse, hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))
import audit
import gguf_hash

OLL = os.environ.get("OLLAMA_BIN", "/root/p2/ollama/bin/ollama")
BASELINE = {"temperature": 0.0, "seed": 42, "num_predict": 768, "num_ctx": 2048}
HF_DIR = "/root/hfdl"


def sh(*args, timeout=7200):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def prune_orphan_blobs(models_dir=os.environ.get("OLLAMA_MODELS", "/root/omodels")):
    """Delete blobs no manifest references. Ollama 0.32.6 leaves them behind on `rm`."""
    ref = set()
    for root, _, files in os.walk(os.path.join(models_dir, "manifests")):
        for fn in files:
            d = json.load(open(os.path.join(root, fn)))
            for layer in [d.get("config", {})] + d.get("layers", []):
                if layer.get("digest"):
                    ref.add(layer["digest"].replace(":", "-"))
    blob_dir = os.path.join(models_dir, "blobs")
    for b in os.listdir(blob_dir):
        if b.startswith("sha256-") and b not in ref:
            os.remove(os.path.join(blob_dir, b))


def model_blob(tag):
    """Path of the GGUF blob behind an Ollama tag, from its Modelfile FROM line."""
    for line in sh(OLL, "show", "--modelfile", tag).stdout.splitlines():
        if line.startswith("FROM ") and "/blobs/" in line:
            return line[5:].strip()
    return None


def donor_modelfile(gguf_path, donor):
    """The donor's Modelfile with FROM pointed at gguf_path and header comments dropped."""
    if sh(OLL, "show", "--modelfile", donor).returncode != 0:
        sh(OLL, "pull", donor)
    text = sh(OLL, "show", "--modelfile", donor).stdout
    out, in_block = [], False
    for line in text.splitlines():
        if not in_block and line.startswith("#"):
            continue
        if not in_block and line.startswith("FROM "):
            out.append(f"FROM {gguf_path}")
            continue
        out.append(line)
        if line.count('"""') % 2 == 1:
            in_block = not in_block
    return "\n".join(out) + "\n"


def download_hf(repo, fname):
    os.makedirs(HF_DIR, exist_ok=True)
    local = os.path.join(HF_DIR, fname)
    if not os.path.exists(local):
        url = f"https://huggingface.co/{repo}/resolve/main/{fname}"
        r = sh("curl", "-sL", "--fail", "--retry", "4", "--retry-delay", "30", "-o", local, url)
        if r.returncode != 0:
            raise RuntimeError(f"download failed: {url}")
    return local


def prepare(e, do_hash=True):
    """Make the entry runnable in Ollama; return (model name, info dict)."""
    info = {}
    if e["kind"] == "ollama":
        if sh(OLL, "show", "--modelfile", e["tag"]).returncode != 0:
            t0 = time.monotonic()
            for attempt in range(1, 5):  # the registry returns transient 503s
                p = sh(OLL, "pull", e["tag"])
                if p.returncode == 0:
                    break
                time.sleep(30 * attempt)
            info["pull_s"] = round(time.monotonic() - t0, 1)
            info["pull_attempts"] = attempt
            if p.returncode != 0:
                raise RuntimeError("pull failed: " + p.stderr.strip()[-200:])
        info["blob"] = model_blob(e["tag"])
        if info["blob"] and do_hash:
            info["hash"] = gguf_hash.describe(e["id"], info["blob"])
        return e["tag"], info
    path = e["path"] if e["kind"] == "gguf" else download_hf(e["repo"], e["file"])
    info["gguf_path"] = path
    if do_hash:
        info["hash"] = gguf_hash.describe(e["id"], path)
    name = "p2ref-" + e["id"].lower()
    mf = donor_modelfile(path, e["donor"])
    info["donor"] = e["donor"]
    info["modelfile_sha256"] = hashlib.sha256(mf.encode()).hexdigest()
    mf_path = os.path.join("/root", f"Modelfile.{name}")
    with open(mf_path, "w") as f:
        f.write(mf)
    if sh(OLL, "show", "--modelfile", name).returncode != 0:
        c = sh(OLL, "create", name, "-f", mf_path)
        if c.returncode != 0:
            raise RuntimeError("create failed: " + c.stderr.strip()[-200:])
    return name, info


def generate(model, task_ids, options):
    gens, metrics = [], []
    for tid in task_ids:
        prompt = audit.TASKS[tid]["prompt"]
        t1 = time.monotonic()
        resp = audit.api("/api/chat", {
            "model": model,
            "messages": [{"role": "user", "content": f"{audit.INSTRUCTION}\n```python\n{prompt}\n```\n"}],
            "stream": False,
            "options": options,
            "keep_alive": "10m",
        })
        out = resp.get("message", {}).get("content", "")
        gens.append({"task_id": tid, "solution": out})
        m = audit.degeneration_features(prompt, out)
        m.update({"task_id": tid, "wall_s": round(time.monotonic() - t1, 2),
                  "eval_count": resp.get("eval_count"), "done_reason": resp.get("done_reason")})
        metrics.append(m)
    return gens, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("--setting", required=True)
    ap.add_argument("--options", default=None, help="JSON merged over the census baseline")
    ap.add_argument("--tasks", default="suite")
    ap.add_argument("--results-dir", default="/workspace/p2rerun/results")
    ap.add_argument("--keep", action="store_true", help="keep models after the run")
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-hash", action="store_true", help="skip GGUF hashing (already recorded)")
    a = ap.parse_args()

    from evalplus.data import get_human_eval_plus
    audit.TASKS = get_human_eval_plus()
    task_ids = audit.SUITE if a.tasks == "suite" else json.load(open(a.tasks))
    options = dict(BASELINE, **(json.loads(a.options) if a.options else {}))
    entries = json.load(open(a.entries))
    if a.only:
        entries = [e for e in entries if e["id"] == a.only]

    os.makedirs(os.path.join(a.results_dir, "transcripts"), exist_ok=True)
    out_path = os.path.join(a.results_dir, "runs.jsonl")
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            if l.strip():
                r = json.loads(l)
                if not r.get("error"):
                    done.add((r["id"], r["setting"]))

    for i, e in enumerate(entries, 1):
        if (e["id"], a.setting) in done:
            print(f"[{i}/{len(entries)}] skip {e['id']} ({a.setting})", flush=True)
            continue
        rec = {k: v for k, v in e.items()}
        rec.update({"setting": a.setting, "options": options, "n_tasks": len(task_ids),
                    "tasks": a.tasks, "ts_start": time.time()})
        model = None
        try:
            model, info = prepare(e, do_hash=not a.no_hash)
            rec.update(info)
            gens, metrics = generate(model, task_ids, options)
            tpath = os.path.join(a.results_dir, "transcripts", f"{e['id']}__{a.setting}.jsonl")
            with open(tpath, "w") as f:
                for g in gens:
                    f.write(json.dumps(g) + "\n")
            rec["transcript"] = os.path.basename(tpath)
            rec["metrics"] = metrics
            rec["trunc_frac"] = round(sum(m["done_reason"] == "length" for m in metrics) / len(metrics), 3)
        except Exception as ex:
            rec["error"] = f"{type(ex).__name__}: {ex}"[:300]
        finally:
            keep = a.keep or e.get("keep")
            if model:
                sh(OLL, "stop", model, timeout=120)
                if not keep:
                    sh(OLL, "rm", model, timeout=600)
                    prune_orphan_blobs()
            if e["kind"] == "hf" and not keep and rec.get("gguf_path") and os.path.exists(rec["gguf_path"]):
                os.remove(rec["gguf_path"])
        rec["ts_end"] = time.time()
        with open(out_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        status = "ERR " + rec["error"][:80] if rec.get("error") else f"{(rec['ts_end'] - rec['ts_start']) / 60:.1f} min"
        print(f"[{i}/{len(entries)}] {e['id']} ({a.setting}): {status}", flush=True)
    print("RUN_DONE", a.setting)


if __name__ == "__main__":
    main()
